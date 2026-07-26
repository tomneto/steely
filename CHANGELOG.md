# Changelog

All notable changes to **steely** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses a four-segment `MAJOR.MINOR.PATCH.BUILD` version scheme.

## [1.0.3.0] — 2026-07-19

The **streaming speech-to-text** release. `steely.stt` joins the multi-provider
email subsystem shipped in 1.0.2.2, and the documentation was overhauled so both
subsystems are discoverable from the README.

### Added

- **`steely.stt` — provider-agnostic streaming speech-to-text.** Push raw audio
  frames into an async session and consume a uniform stream of `STTEvent`
  objects; switching backends is a one-line `STTClient(...)` change.
  - Backends: **Deepgram**, **AssemblyAI**, **Google Cloud / Chirp**, **Azure AI
    Speech**, **Amazon Transcribe**, self-hosted **WhisperLive**, and an
    in-memory **`fake`** provider for tests. Each SDK is imported lazily, so
    `import steely.stt` is always safe; a missing SDK raises
    `ProviderNotAvailableError` loudly at construction.
  - Public API: `STTClient`, `STTConfig`, `STTEvent`, `EventType`, `STTProvider`,
    `STTSession`, `ReconnectPolicy`, and the error hierarchy (`STTError`,
    `ProviderNotAvailableError`, `STTConfigError`, `STTConnectionError`) — all
    re-exported from the top-level `steely` package.
  - Canonical `STTEvent`: uniform `interim`/`final` semantics and **integer
    millisecond** timestamps across every backend.
  - Transparent reconnection via `ReconnectPolicy` (exponential backoff + jitter);
    the consumer's `async for` only ever sees a brief pause.
  - Internal frame resampling/transcoding to each backend's required format — you
    always push the raw frame and declare the input format once in `STTConfig`.
  - New optional extras: `stt-deepgram`, `stt-assemblyai`, `stt-google`,
    `stt-azure`, `stt-aws`, `stt-whisperlive`, `stt-all`, `audio` (Python 3.13+
    `audioop` back-port), and an aggregate `all`.
  - Guide: [`STT_PROVIDERS.md`](STT_PROVIDERS.md); runnable example:
    [`examples/stt_streaming.py`](examples/stt_streaming.py).

### Changed

- **README** now documents the full surface, including a complete **Streaming
  STT** section, a table of contents, and an optional-extras install matrix.
- Package **description** and **keywords** updated to reflect the toolkit's full
  scope (logging, Grafana, email, STT, FastAPI) rather than debugging alone.

### Documentation

- Added this `CHANGELOG.md`.
- Cross-linked the deep-dive guides ([`EMAIL_PROVIDERS.md`](EMAIL_PROVIDERS.md),
  [`STT_PROVIDERS.md`](STT_PROVIDERS.md)) from the README.

## [1.0.2.2] — 2026-07-14

### Added

- **`steely.email` — provider-agnostic email.** Send over **SMTP** (pure stdlib,
  no extra deps), **Resend**, or any REST API via a generic `HTTPAPIProvider`,
  all behind one interface. Build an `EmailMessage`, call `client.send(...)`, and
  get back a uniform `EmailResult` that never raises on a rejected send.
  - Public API: `EmailClient`, `EmailMessage`, `EmailResult`, `EmailProvider`,
    `SMTPProvider`, `ResendProvider`, `HTTPAPIProvider`, and the error hierarchy.
  - HTTP providers (`resend`, `api`/`http`) use the optional `http` extra
    (`pip install "steely[http]"`, pulls `httpx`) with automatic retry/backoff on
    429/5xx/network errors.
  - Guide: [`EMAIL_PROVIDERS.md`](EMAIL_PROVIDERS.md).

### Changed

- **Legacy `steely.smtp.SendEmail`** preserved unchanged, now delegating to
  `SMTPProvider` internally. New code should prefer `EmailClient` / `EmailMessage`.

## [1.0.2.1] — 2026-05-08

### Added

- **`GrafanaSink`** — non-blocking background log shipper for **Grafana Cloud**
  (OTLP) and self-hosted **Loki**, wired in via `Logger.set_global_grafana(...)`.
  Zero third-party dependencies (pure stdlib); flushes automatically at exit.

## [1.0.1.6] — 2026-04-25

### Added

- **Named loggers & hierarchical level filtering:** `Logger.getLogger(name)`
  (cached), `setLevel(...)` accepting `logging` numeric constants or Steely level
  strings, dotted-name inheritance, and a global baseline level.

## [1.0.1.4] — 2025-12-18

### Added

- **FastAPI request recorders:** `@recorder.postman(...)` and `@recorder.curl(...)`
  capture live requests into Postman Collection v2.1 files and executable curl
  scripts. See [`POSTMAN_RECORDER_UPDATES.md`](POSTMAN_RECORDER_UPDATES.md) and
  [`CURL_RECORDER_SUMMARY.md`](CURL_RECORDER_SUMMARY.md).

## [1.0.1.3] — 2025-12-10

### Added

- Core decorators under the `Dan` namespace and as standalone imports:
  - `Dan.log` — automatic start/success/error lifecycle logging.
  - `Dan.cronos` — execution-time measurement.
  - `Dan.scan` — real-time, type-colored variable tracking.
- Thread-safe **`Logger`** with color-coded levels and date-stamped file logging.
- **`pprint`** — print with clickable caller `file:line` location.
- **`steely.design`** — shared terminal styling primitives (`UnicodeColors`,
  `TypeColors`, `Symbols`).

[1.0.3.0]: https://github.com/tomneto/steely
[1.0.2.2]: https://github.com/tomneto/steely
[1.0.2.1]: https://github.com/tomneto/steely
[1.0.1.6]: https://github.com/tomneto/steely
[1.0.1.4]: https://github.com/tomneto/steely
[1.0.1.3]: https://github.com/tomneto/steely
