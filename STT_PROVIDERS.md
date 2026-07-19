# steely.stt — Streaming STT Providers Guide

> Canonical integration guide for **humans and AI coding agents** consuming
> `steely` for streaming speech-to-text. If you are an agent working in a worker
> that transcribes LiveKit audio, **read this file before writing any STT code.**
> It tells you exactly what to import, how to stream, and the rules you must not
> break.

`steely.stt` streams audio to **Deepgram**, **AssemblyAI**, **Google Cloud /
Chirp**, **Azure AI Speech**, or **Amazon Transcribe** behind one small, async,
provider-agnostic interface. The worker pushes raw frames and consumes a uniform
stream of transcript events; switching providers is a one-line change.

---

## Install

```bash
pip install steely                     # core steely.stt — NO new deps (stdlib asyncio)
pip install "steely[stt-deepgram]"     # + Deepgram SDK
pip install "steely[stt-assemblyai]"   # + AssemblyAI SDK
pip install "steely[stt-google]"       # + Google Cloud Speech SDK
pip install "steely[stt-azure]"        # + Azure Speech SDK
pip install "steely[stt-aws]"          # + Amazon Transcribe streaming SDK
pip install "steely[stt-whisperlive]"  # + WhisperLive client (websockets)
pip install "steely[stt-all]"          # + all backends
```

Each backend's SDK is imported **lazily** inside its provider's constructor, so
`import steely.stt` never fails when an SDK is absent — only *constructing* that
provider does, raising `ProviderNotAvailableError` (loud, at construction time,
never a silent failure mid-stream).

> On **Python 3.13+**, `audioop` (used for resampling) was removed from the
> stdlib; add the `audio` extra: `pip install "steely[audio]"`.

---

## The 30-second version

```python
import asyncio
from steely.stt import STTClient, STTConfig

async def main():
    # 1) Pick a provider by name (+ its config). Or pass a provider instance.
    client = STTClient("deepgram", api_key="dg_xxx")

    # 2) Describe the frames the worker WILL push (input format, not backend).
    config = STTConfig(language="pt-BR", sample_rate=48000, channels=1)

    # 3) Open a session, push raw frames, iterate canonical events.
    session = await client.open_session(config)
    async with session:
        async for frame in livekit_audio():           # your frame source
            await session.push_frame(frame.data.tobytes())   # RAW bytes
        await session.end_input()
        async for event in session:                   # interim... final
            print(event.type.value, event.text, event.start, event.end)

asyncio.run(main())
```

To use a different backend, change **only** step 1:

```python
client = STTClient("assemblyai", api_key="aai_xxx")
# or STTClient("google") / STTClient("azure", subscription_key=..., region=...)
# or STTClient("aws", region="us-east-1")
```

Everything else — the `STTConfig`, the `push_frame`/`end_input` calls, and the
`STTEvent` you receive — stays identical.

---

## Core concepts

| Type | What it is |
|---|---|
| `STTClient` | Front door. `STTClient(provider_name, **creds)` or `STTClient(provider_instance)`. |
| `STTConfig` | Session config: `model`, `language` (canonical BCP-47), `sample_rate`, `encoding`, `channels`, `interim_results`. Describes the **input** the worker pushes. |
| `STTSession` | A live session. `await push_frame(bytes)`, `await end_input()`, `await aclose()`; it is an **async iterator** of `STTEvent` and an **async context manager**. |
| `STTEvent` | The single canonical event: `type` (`interim`/`final`), `text`, `start`/`end` (**int milliseconds** from stream start), optional `speaker`, `confidence`, `language`. |
| `EventType` | `EventType.INTERIM` \| `EventType.FINAL`. |
| `ReconnectPolicy` | Reconnection strategy (extension point). Pass to `open_session(..., reconnect=...)`. |

**Timestamps are integer milliseconds** from the start of the stream. Every
adapter converts its native units once, so consumers never see unit ambiguity.

**Speaker** is optional and is **not** produced by diarization — the worker sets
it from the LiveKit track. `steely.stt` does not abstract diarization,
translation, or custom vocabulary.

---

## Rules you must not break

1. **Push the raw frame.** The worker always pushes the raw bytes from LiveKit
   (`frame.data.tobytes()`). Resampling / format conversion happens **inside the
   adapter** — never resample in the worker. Declare the input format once in
   `STTConfig` (`sample_rate`/`encoding`/`channels`).
2. **`interim`/`final` is uniform.** Some backends emit `final` via their own
   endpointing and at different latencies; the adapter normalizes them so
   consumers behave the same everywhere.
3. **Speak canonical language tags.** Pass BCP-47 like `"pt-BR"`; the adapter
   maps it to the provider's own code. `STTEvent.language` echoes the canonical
   tag back, never the provider code.
4. **One error type.** Every network/backend failure surfaces as
   `STTConnectionError` out of the `async for`. No backend-native exception,
   field, or concept reaches the worker.
5. **Credentials come from config/env, never hardcoded.** Pass them as kwargs to
   `STTClient(name, ...)`, or set the provider's env var.

---

## Reconnection

Network drops are handled transparently. `QueueSession`'s background receive
pump consults a `ReconnectPolicy`: on a retryable drop it backs off and re-opens
the stream, so the consumer's `async for` only sees a brief pause. Tune it:

```python
from steely.stt import ReconnectPolicy
policy = ReconnectPolicy(max_retries=5, base_delay=0.5, backoff=2.0, max_delay=10)
session = await client.open_session(config, reconnect=policy)
```

Set `max_retries=0` to disable reconnection; exhausted retries (or a
non-retryable error) raise `STTConnectionError` at the consumer.

---

## Per-provider reference

| Provider (`name` / aliases) | Authenticate | pt-BR code | Backend sample rate / encoding | Protocol |
|---|---|---|---|---|
| **Deepgram** (`deepgram`) | `api_key=` or `DEEPGRAM_API_KEY` | `pt-BR` | 16 kHz `linear16` (PCM s16le) mono | WebSocket |
| **AssemblyAI** (`assemblyai`) | `api_key=` or `ASSEMBLYAI_API_KEY` | `pt` ¹ | 16 kHz PCM s16le mono | WebSocket |
| **Google / Chirp** (`google`, `chirp`) | `credentials_path=` or `GOOGLE_APPLICATION_CREDENTIALS` (service-account JSON) | `pt-BR` | 16 kHz `LINEAR16` mono | gRPC bidi |
| **Azure AI Speech** (`azure`) | `subscription_key=` + `region=` or `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` | `pt-BR` | 16 kHz 16-bit PCM mono | SDK push-stream |
| **Amazon Transcribe** (`aws`, `transcribe`) | standard AWS credential chain + `region=` or `AWS_REGION` | `pt-BR` | 16 kHz PCM s16le mono | HTTP/2 event stream |
| **WhisperLive** (`whisperlive`, `whisper`) | none (self-hosted); `endpoint_url=` or `WHISPERLIVE_URL` (default `ws://localhost:9090`) | `pt` | 16 kHz **float32** mono | WebSocket |

¹ AssemblyAI's realtime streaming supports a narrower language set than its batch
API. If the requested language is unsupported by the installed SDK/plan,
`open_session` raises `STTConfigError` **before** any audio is pushed.

All five converge on **16 kHz mono 16-bit PCM**; the adapter resamples the
worker's frames to that. Deepgram and AWS also accept 8 kHz.

Choose a model with `STTConfig(model=...)` (e.g. Deepgram `"nova-2"`, Google
`"chirp_2"`); `"default"` lets each adapter pick a sensible model.

---

## Testing without a network

Use the `"fake"` provider — an in-memory backend implementing the same contract,
no SDK required:

```python
from steely.stt import STTClient, STTConfig, STTEvent, EventType

script = [STTEvent(EventType.FINAL, "olá mundo", 0, 900, language="pt-BR")]
client = STTClient(__import__("steely.stt.providers.fake", fromlist=["FakeProvider"]).FakeProvider(script=script))
session = await client.open_session(STTConfig())
events = [ev async for ev in session]     # replays your script, records pushed frames
```

See `test/test_stt_client.py` (contract + factory) and `test/test_stt_session.py`
(pump, error propagation, transparent reconnect) for the full patterns.

---

## WhisperLive (faster-whisper, self-hosted)

WhisperLive wraps faster-whisper and is **batch under the hood**, so endpointing
is the *adapter's* responsibility — the interface never assumes it comes from the
backend. This adapter owns endpointing by enabling WhisperLive's server-side VAD
(`use_vad=True`) and mapping each segment's `completed` flag to `final` (an
in-progress segment is `interim`), deduplicating finals across WhisperLive's
re-sent segment list. The result is the **exact same** uniform `interim`/`final`
stream as every other backend — no interface change was needed.

```python
# Self-hosted: point at your WhisperLive server (default ws://localhost:9090).
client = STTClient("whisperlive", endpoint_url="ws://my-host:9090")
session = await client.open_session(STTConfig(language="pt-BR", sample_rate=48000))
```

Audio is streamed as little-endian **float32** at 16 kHz mono (the adapter
resamples and converts from the worker's raw frames). `end_input()` sends
WhisperLive's `END_OF_AUDIO` marker so the server flushes its remaining finals.

---

## Adding a new provider (checklist)

1. Create `steely/stt/providers/<name>.py` with an `<Name>Provider(STTProvider)`
   and an `<Name>Session` (subclass `QueueSession`, or `CallbackQueueSession`
   for callback-based SDKs).
2. Lazily `import` the SDK inside `<Name>Provider.__init__`; raise
   `ProviderNotAvailableError` on `ImportError` and `STTConfigError` on missing
   credentials. Read creds from kwargs **or** an env var.
3. Implement the session hooks: `_connect`, `_send_bytes`, `_signal_end`,
   `_receive` (translate native → `STTEvent`), `_close_conn`. Set `BACKEND_RATE`
   / `BACKEND_ENCODING`. Convert timestamps to **int ms**.
4. Add a language mapping in `steely/stt/languages.py` and wrap all
   transport/protocol exceptions as `STTConnectionError`.
5. Register the name in `steely.stt.client._FACTORY`, add the extra to
   `pyproject.toml`, and a row to the table above.
