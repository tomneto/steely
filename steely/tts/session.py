"""
QueueSession — the concrete session base streaming adapters subclass.

It owns all the plumbing that is identical across streaming backends:

- a background *receive pump* task that drains the adapter's ``_receive`` async
  generator and puts canonical :class:`AudioChunk` objects on an ``asyncio.Queue``;
- the async-iterator surface (``__aiter__``/``__anext__``) that reads that queue;
- transparent reconnection driven by a :class:`ReconnectPolicy`.

Each adapter only implements the backend-specific hooks (``_connect``,
``_send_text``, ``_signal_end``, ``_receive``, ``_close_conn``) plus the ``name``
property. One-shot HTTP backends that don't stream can implement
:class:`~steely.tts.base.TTSSession` directly instead (see the OpenAI adapter).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from steely.logger import Logger
from steely.tts.audio_chunk import AudioChunk
from steely.tts.base import TTSSession
from steely.tts.config import TTSConfig
from steely.tts.errors import TTSConnectionError, TTSError
from steely.tts.reconnect import ReconnectPolicy

# Sentinel placed on the queue to mark end-of-stream (clean or after an error).
_END: Any = object()


class QueueSession(TTSSession):
    """Base session wiring a background receive pump to an async iterator.

    Subclasses implement the ``_connect`` / ``_send_text`` / ``_signal_end`` /
    ``_receive`` / ``_close_conn`` hooks. All queue, iterator and reconnection
    logic is shared.
    """

    @property
    def name(self) -> str:
        """Short session id used for logging / task naming. Adapters may
        override; defaults to the class name."""
        return type(self).__name__

    def __init__(
        self,
        config: TTSConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        max_queue: int = 512,
    ) -> None:
        self._config = config
        self._reconnect = reconnect or ReconnectPolicy()
        self._queue: asyncio.Queue[AudioChunk | object] = asyncio.Queue(max_queue)
        self._recv_task: asyncio.Task[None] | None = None
        self._error: BaseException | None = None
        self._closed = False
        self._conn: Any = None
        self.__logger__ = Logger(app_name=self.__class__.__name__, owner="tts").log

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def _start(self) -> None:
        """Connect and spawn the receive pump. Called by the provider right
        after construction (kept out of ``__init__`` because it is async)."""
        self._conn = await self._connect(self._config)
        self._recv_task = asyncio.create_task(self._pump(), name=f"{self.name}-recv")

    # ------------------------------------------------------------------ #
    # Backend hooks — implemented per adapter
    # ------------------------------------------------------------------ #
    async def _connect(self, config: TTSConfig) -> Any:
        """Open the backend WS/HTTP stream (applying voice/language mapping and
        the requested output format) and return a connection handle."""
        raise NotImplementedError

    async def _send_text(self, conn: Any, text: str) -> None:
        """Write a text fragment to the backend."""
        raise NotImplementedError

    async def _signal_end(self, conn: Any) -> None:
        """Tell the backend no more text is coming so it flushes final audio."""
        raise NotImplementedError

    async def _receive(self, conn: Any) -> AsyncIterator[AudioChunk]:
        """Yield canonical :class:`AudioChunk` objects translated from native
        messages. Return (stop yielding) when the backend closes cleanly.

        Raise :class:`TTSConnectionError` (``retryable=True``) on a recoverable
        drop so the pump can reconnect transparently.
        """
        raise NotImplementedError
        yield  # pragma: no cover - marks this as an async generator

    async def _close_conn(self, conn: Any) -> None:
        """Close the underlying WS/HTTP handle."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Receive pump (with transparent reconnection)
    # ------------------------------------------------------------------ #
    async def _pump(self) -> None:
        try:
            while True:
                try:
                    async for chunk in self._receive(self._conn):
                        self._reconnect.reset()
                        await self._queue.put(chunk)
                    break  # clean backend close -> stream is done
                except asyncio.CancelledError:
                    raise
                except self._reconnect.retryable_excs as exc:
                    if self._closed or not self._reconnect.should_retry(exc):
                        raise TTSConnectionError(str(exc)) from exc
                    self.__logger__("WARNING", f"{self.name} stream dropped, reconnecting: {exc}")
                    await self._reconnect.backoff_sleep()
                    self._conn = await self._connect(self._config)
                    # loop continues; the consumer never sees the drop
        except asyncio.CancelledError:
            pass
        except BaseException as exc:  # noqa: BLE001 - surfaced to the consumer
            self._error = exc if isinstance(exc, TTSError) else TTSConnectionError(str(exc))
        finally:
            await self._queue.put(_END)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def push_text(self, text: str) -> None:
        if self._closed:
            raise TTSError("push_text after close")
        await self._send_text(self._conn, text)

    async def end_input(self) -> None:
        if self._closed:
            return
        await self._signal_end(self._conn)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._recv_task is not None:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._conn is not None:
            try:
                await self._close_conn(self._conn)
            except Exception:  # noqa: BLE001 - closing is best-effort
                pass

    # ------------------------------------------------------------------ #
    # Async iterator
    # ------------------------------------------------------------------ #
    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        return self

    async def __anext__(self) -> AudioChunk:
        item = await self._queue.get()
        if item is _END:
            if self._error is not None:
                raise self._error
            raise StopAsyncIteration
        return item  # type: ignore[return-value]


class CallbackQueueSession(QueueSession):
    """QueueSession variant for callback/push-based SDKs.

    Some vendor SDKs deliver audio via callbacks — often on another thread —
    rather than an awaitable stream. Such an adapter wires those callbacks to
    :meth:`emit` / :meth:`emit_error` / :meth:`emit_end` (all thread-safe), and
    :meth:`_receive` simply drains the internal queue. Adapters then only
    implement ``_connect`` (registering the callbacks), ``_send_text``,
    ``_signal_end`` and ``_close_conn``.
    """

    def __init__(
        self,
        config: TTSConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        max_queue: int = 512,
    ) -> None:
        super().__init__(config, reconnect=reconnect, max_queue=max_queue)
        self._cb_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def _start(self) -> None:
        self._loop = asyncio.get_running_loop()
        await super()._start()

    async def _receive(self, conn: Any) -> AsyncIterator[AudioChunk]:
        while True:
            item = await self._cb_queue.get()
            if item is _END:
                return
            if isinstance(item, BaseException):
                raise item
            yield item

    def emit(self, chunk: AudioChunk) -> None:
        """Thread-safe: push a translated audio chunk from an SDK callback."""
        self._schedule(chunk)

    def emit_error(self, exc: BaseException) -> None:
        """Thread-safe: surface a backend error (retryable -> reconnect)."""
        self._schedule(exc)

    def emit_end(self) -> None:
        """Thread-safe: signal the backend closed the stream cleanly."""
        self._schedule(_END)

    def _schedule(self, item: Any) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._cb_queue.put_nowait, item)
