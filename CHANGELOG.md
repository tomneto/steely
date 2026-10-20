# Changelog

All notable changes to **steely** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses a four-segment `MAJOR.MINOR.PATCH.BUILD` version scheme.

## [Unreleased]

Hardening pass on security, performance, packaging and tooling.

### Security

- **The FastAPI recorders now redact credentials by default.** `steely.fastapi.recorder`
  writes plain-text scripts and collections to disk, so before anything is
  written it masks sensitive headers (`Authorization`, `Cookie`, `Set-Cookie`,
  `Proxy-Authorization`, `X-API-Key`, `API-Key`, `X-Auth-Token`) and JSON body
  values under sensitive keys (`password`, `token`, `secret`, `api_key`,
  `credit_card`, `cvv`, …, nested structures included). New knobs on both
  `curl()` and `postman()`: `sensitive_headers=`, `keep_sensitive_headers=True`
  (opt back in to replayable auth) and `redact_body=False`.
- **`build.sh` no longer contains the PyPI token.** It reads `$PYPI_TOKEN` from
  the environment and fails loudly if unset. `.env` holds placeholders only, and
  `.env.example` documents the variables.

### Fixed

- **`intercept_stdlib()` is now thread-safe.** Its installation was a series of
  unguarded check-then-act pairs. Worst case, two threads both saw the
  `dictConfig` patch as un-installed and the second captured the *already
  patched* function as `_original_dictConfig` — `_patched_dictConfig` then
  called itself, so every subsequent `logging.config.dictConfig()` call in the
  process died with `RecursionError`. Concurrent callers could also build
  several interception handlers and attach them to the same logger (duplicated
  log lines), and `_reapply_handlers` iterated the intercepted-names set while
  another thread mutated it. The whole installation now runs under one module
  lock, always acquired *before* the `logging` module's own lock — a handler's
  `emit()` never takes it, which keeps that ordering and rules out deadlock.

- **The `log` decorator no longer swallows exceptions in sync functions.** The
  sync wrapper logged `Function Failed` and then returned `None`, silently
  converting a raised exception into a successful-looking `None` result, while
  the async wrapper re-raised. Both now re-raise with a bare `raise`, so the
  original traceback survives and the two paths behave identically. This matches
  what the README always documented.

### Changed

- **`fastapi` is an optional extra**, not a hard dependency: `pip install "steely[fastapi]"`.
  `import steely` never pulls FastAPI in, and the recorders resolve
  `fastapi.Request` lazily — using a decorator without the extra raises
  `FastAPINotAvailableError` with the install command. `twine` moved out of the
  runtime dependencies into the dev group.
- **Single source of truth for the version**: `__version__` in
  `steely/__init__.py`, read by `pyproject.toml` via `[tool.hatch.version]`.
  `setup.py` (stale, and carrying an invalid nested `install_requires`) was
  deleted; hatchling via `pyproject.toml` is the only build path.
- **`Logger` thread-safety is now real.** A per-instance `threading.Lock` guards
  the file write, the console print and the callbacks, so concurrent threads no
  longer interleave partial lines. Docstrings and the README no longer claim
  logging happens on background threads — it is synchronous and thread-*safe*.

### Performance

- `cronos` and `scan` measure elapsed time with `time.perf_counter()` instead of
  wall-clock `datetime.now()`, so timings survive clock adjustments (NTP, DST).
- Screen clearing uses the ANSI sequence `\x1b[2J\x1b[H` instead of
  `os.system('clear'|'cls')` — no subprocess per message.
- `Logger.log()` makes one `strftime` call instead of two.
- `GrafanaSink` caches Loki stream labels per `(level, owner, app)`, avoiding a
  dict copy plus `json.dumps(sort_keys=True)` for every log entry.
- `scan` compares container lengths (O(1)) before falling back to a deep
  equality walk (O(n)) when tracking variable changes.

### Tooling

- **Ruff** is configured (`line-length = 100`, `E,F,I,UP,B,SIM`, py39 target) and
  the codebase is clean against it.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): lint, the test suite on
  Python 3.9–3.13, and a wheel build + `twine check`, on every push and PR.
- `[dependency-groups] dev` collects pytest, pytest-asyncio, ruff, twine and the
  optional SDKs the suite needs; `[tool.pytest.ini_options]` sets `testpaths`
  and `asyncio_mode = "auto"`.
- `test_logger_performance.py` reported numbers instead of asserting them, so it
  moved to `examples/benchmarks/logger_performance.py`. New
  `test/test_recorder_redaction.py` covers the redaction contract.

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
