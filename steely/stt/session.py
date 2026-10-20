"""
QueueSession — the concrete session base every real adapter subclasses.

It owns all the plumbing that is identical across backends:

- a background *receive pump* task that drains the adapter's ``_receive`` async
  generator and puts canonical :class:`STTEvent` objects on an ``asyncio.Queue``;
- the async-iterator surface (``__aiter__``/``__anext__``) that reads that queue;
- transparent reconnection driven by a :class:`ReconnectPolicy`;
- audio resampling on :meth:`push_frame` via
  :func:`~steely.stt.audio.resample.to_backend_pcm`.

Each adapter only implements the backend-specific hooks (``_connect``,
``_send_bytes``, ``_signal_end``, ``_receive``, ``_close_conn``) plus the
``name`` property and the ``BACKEND_RATE``/``BACKEND_ENCODING`` class attributes.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from steely.logger import Logger
from steely.stt.audio.resample import to_backend_pcm
from steely.stt.base import STTSession
from steely.stt.config import STTConfig
from steely.stt.errors import STTConnectionError, STTError
from steely.stt.event import STTEvent
from steely.stt.reconnect import ReconnectPolicy

# Sentinel placed on the queue to mark end-of-stream (clean or after an error).
_END: Any = object()


class QueueSession(STTSession):
    """Base session wiring a background receive pump to an async iterator.

    Subclasses set ``BACKEND_RATE`` / ``BACKEND_ENCODING`` and implement the
    ``_connect`` / ``_send_bytes`` / ``_signal_end`` / ``_receive`` /
    ``_close_conn`` hooks. All queue, iterator and reconnection logic is shared.
    """

    #: Sample rate (Hz) the backend requires; frames are resampled to this.
    BACKEND_RATE: int = 16000
    #: Encoding the backend requires. Only ``"pcm_s16le"`` is produced today.
    BACKEND_ENCODING: str = "pcm_s16le"

    @property
    def name(self) -> str:
        """Short session id used for logging / task naming. Adapters may
        override; defaults to the class name."""
        return type(self).__name__

    def __init__(
        self,
        config: STTConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        max_queue: int = 512,
    ) -> None:
        self._config = config
        self._reconnect = reconnect or ReconnectPolicy()
        self._queue: asyncio.Queue[STTEvent | object] = asyncio.Queue(max_queue)
        self._recv_task: asyncio.Task[None] | None = None
        self._error: BaseException | None = None
        self._closed = False
        self._conn: Any = None
        self._resample_state: dict = {}
        self.__logger__ = Logger(app_name=self.__class__.__name__, owner="stt").log

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
    async def _connect(self, config: STTConfig) -> Any:
        """Open the backend WS/gRPC stream (applying language mapping and the
        backend's required sample_rate/encoding) and return a connection handle."""
        raise NotImplementedError

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        """Write already-transcoded PCM to the backend."""
        raise NotImplementedError

    async def _signal_end(self, conn: Any) -> None:
        """Tell the backend no more audio is coming (e.g. Deepgram CloseStream)."""
        raise NotImplementedError

    async def _receive(self, conn: Any) -> AsyncIterator[STTEvent]:
        """Yield canonical :class:`STTEvent` objects translated from native
        messages. Return (stop yielding) when the backend closes cleanly.

        Raise :class:`STTConnectionError` (``retryable=True``) on a recoverable
        drop so the pump can reconnect transparently.
        """
        raise NotImplementedError
        yield  # pragma: no cover - marks this as an async generator

    async def _close_conn(self, conn: Any) -> None:
        """Close the underlying WS/gRPC handle."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Receive pump (with transparent reconnection)
    # ------------------------------------------------------------------ #
    async def _pump(self) -> None:
        try:
            while True:
                try:
                    async for event in self._receive(self._conn):
                        self._reconnect.reset()
                        await self._queue.put(event)
                    break  # clean backend close -> stream is done
                except asyncio.CancelledError:
                    raise
                except self._reconnect.retryable_excs as exc:
                    if self._closed or not self._reconnect.should_retry(exc):
                        raise STTConnectionError(str(exc)) from exc
                    self.__logger__("WARNING", f"{self.name} stream dropped, reconnecting: {exc}")
                    await self._reconnect.backoff_sleep()
                    self._conn = await self._connect(self._config)
                    # loop continues; the consumer never sees the drop
        except asyncio.CancelledError:
            pass
        except BaseException as exc:  # noqa: BLE001 - surfaced to the consumer
            self._error = exc if isinstance(exc, STTError) else STTConnectionError(str(exc))
        finally:
            await self._queue.put(_END)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def push_frame(self, frame: bytes) -> None:
        if self._closed:
            raise STTError("push_frame after close")
        pcm = to_backend_pcm(
            frame,
            in_rate=self._config.sample_rate,
            in_channels=self._config.channels,
            in_encoding=self._config.encoding,
            out_rate=self.BACKEND_RATE,
            out_channels=1,
            out_encoding=self.BACKEND_ENCODING,
            state=self._resample_state,
        )
        await self._send_bytes(self._conn, pcm)

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
    def __aiter__(self) -> AsyncIterator[STTEvent]:
        return self

    async def __anext__(self) -> STTEvent:
        item = await self._queue.get()
        if item is _END:
            if self._error is not None:
                raise self._error
            raise StopAsyncIteration
        return item  # type: ignore[return-value]


class CallbackQueueSession(QueueSession):
    """QueueSession variant for callback/push-based SDKs.

    Many vendor SDKs (Deepgram, Azure, Amazon Transcribe) deliver results via
    callbacks — often on another thread — rather than an awaitable stream. Such
    an adapter wires those callbacks to :meth:`emit` / :meth:`emit_error` /
    :meth:`emit_end` (all thread-safe), and :meth:`_receive` simply drains the
    internal queue. Adapters then only implement ``_connect`` (registering the
    callbacks), ``_send_bytes``, ``_signal_end`` and ``_close_conn``.
    """

    def __init__(
        self,
        config: STTConfig,
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

    async def _receive(self, conn: Any) -> AsyncIterator[STTEvent]:
        while True:
            item = await self._cb_queue.get()
            if item is _END:
                return
            if isinstance(item, BaseException):
                raise item
            yield item

    def emit(self, event: STTEvent) -> None:
        """Thread-safe: push a translated event from an SDK callback."""
        self._schedule(event)

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
