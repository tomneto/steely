"""
Tests for ``Logger.intercept_stdlib()`` — redirecting Python's standard
``logging`` module through Steely's ``Logger``.
"""

import logging
import logging.config
import sys
import threading
import time

import pytest

from steely.logger import Logger, _stdlib_bridge

# Captured at import (collection) time, before any test can install the
# monkeypatch — this is the genuine, unpatched ``logging.config.dictConfig``.
_PRISTINE_DICTCONFIG = logging.config.dictConfig

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _reset():
    """Clean global state that tests may mutate."""
    Logger._registry.clear()
    Logger._global_level = 0
    Logger._global_app_name = None
    Logger._stdlib_root_intercepted = False
    Logger._intercepted_stdlib_loggers.clear()
    Logger._stdlib_handler = None
    logging.root.handlers[:] = []
    _reset_dictconfig_patch()


def _reset_dictconfig_patch():
    """Un-install the dictConfig monkeypatch.

    Without this, the patch (and whatever it captured as "original") leaks
    between tests, so a test's outcome depends on what ran before it.
    """
    logging.config.dictConfig = _PRISTINE_DICTCONFIG
    _stdlib_bridge._original_dictConfig = None
    _stdlib_bridge._dictConfig_patch_applied = False


# ---------------------------------------------------------------------------
# autouse fixture — runs before/after every test (including class-based)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_state():
    _reset()
    yield
    _reset()


# ===================================================================
# Level mapping
# ===================================================================

class TestLevelMapping:
    """Every stdlib level maps to the correct Steely level string."""

    def test_mapping_via_handler(self, capsys):
        """End-to-end: levels that stdlib actually emits (DEBUG+) pass through."""
        Logger.set_global_app_name("TestApp")
        Logger.intercept_stdlib()

        logging.getLogger("mapper").info("hello info")
        captured = capsys.readouterr()
        assert "[INFO]" in captured.out

    def test_notset_is_mapped_correctly(self):
        """NOTSET maps to TEST — verified via the mapping dict directly
        because CPython's ``logging.disable(NOTSET)`` (the default)
        silently drops level‑0 records at the ``isEnabledFor`` check,
        before they ever reach our handler."""
        from steely.logger._stdlib_bridge import _STDLIB_TO_STEELY
        assert _STDLIB_TO_STEELY[logging.NOTSET] == "TEST"

    @pytest.mark.parametrize("stdlib_level,expected", [
        (logging.DEBUG,    "TEST"),
        (logging.INFO,     "INFO"),
        (logging.WARNING,  "WARNING"),
        (logging.ERROR,    "ERROR"),
        (logging.CRITICAL, "CRITICAL"),
    ])
    def test_level_mapping(self, stdlib_level, expected, capsys):
        Logger.set_global_app_name("TestApp")
        Logger.intercept_stdlib()

        logging.getLogger("test_mapper").log(stdlib_level, "hello")

        captured = capsys.readouterr()
        assert f"[{expected}]" in captured.out, (
            f"stdlib level {stdlib_level} should map to [{expected}]"
        )


# ===================================================================
# Owner inference
# ===================================================================

class TestOwnerInference:
    """Owner is extracted from ``logging.LogRecord.name``."""

    def test_owner_from_record_name(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        logging.getLogger("uvicorn.error").info("port 8000")

        captured = capsys.readouterr()
        assert "[UVICORN.ERROR]" in captured.out

    def test_owner_fallback_when_root(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        # Root logger — fallback uses record.module
        logging.root.info("from root")

        captured = capsys.readouterr()
        # record.module will be something like "test_stdlib_intercept"
        # Just check that it isn't empty and doesn't say "ROOT"
        assert captured.out != ""
        assert "[ROOT]" not in captured.out


# ===================================================================
# Exception / traceback formatting
# ===================================================================

class TestExceptionFormatting:
    """LogRecord with exc_info has traceback appended to the message."""

    def test_traceback_appended(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("test_exc").error("oops", exc_info=True)

        captured = capsys.readouterr()
        assert "oops" in captured.out
        assert "ValueError" in captured.out
        assert "boom" in captured.out
        assert "Traceback" in captured.out

    def test_no_exc_info_no_traceback(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        logging.getLogger("test_noexc").info("fine")

        captured = capsys.readouterr()
        assert "fine" in captured.out
        assert "Traceback" not in captured.out


# ===================================================================
# Context tags (file, line, func)
# ===================================================================

class TestOutputCleanliness:
    """Intercepted output should be free of internal context tags."""

    def test_no_context_tags_in_output(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        logging.getLogger("ctx").info("tag me")

        captured = capsys.readouterr()
        assert "[APP]" in captured.out
        assert "[CTX]" in captured.out
        assert "[INFO]" in captured.out
        # Verify no file/line/func tags leak into output
        assert ".PY]" not in captured.out  # no file path tag
        assert "TEST_NO_CONTEXT_TAGS_IN_OUTPUT]" not in captured.out  # no funcName


# ===================================================================
# Idempotency
# ===================================================================

class TestIdempotency:
    """Calling ``intercept_stdlib`` multiple times must not duplicate."""

    def test_double_call_root_no_duplicate(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()   # first
        Logger.intercept_stdlib()   # second

        logging.root.info("once")

        captured = capsys.readouterr()
        assert captured.out.count("once") == 1, (
            f"Expected exactly 1 occurrence of 'once', got: {captured.out}"
        )

    def test_double_call_named_no_duplicate(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib(["mylib"])
        Logger.intercept_stdlib(["mylib"])

        logging.getLogger("mylib").info("once")

        captured = capsys.readouterr()
        assert captured.out.count("once") == 1, (
            f"Expected exactly 1 occurrence of 'once', got: {captured.out}"
        )


# ===================================================================
# Fail without app_name
# ===================================================================

class TestFailWithoutAppName:
    """A clear error must be raised when no app_name is configured."""

    def test_raises_without_any_app_name(self):
        with pytest.raises(ValueError) as exc:
            Logger.intercept_stdlib()
        assert "app_name" in str(exc.value).lower()

    def test_works_with_global_app_name(self, capsys):
        Logger.set_global_app_name("GlobalApp")
        # Should not raise
        Logger.intercept_stdlib()
        logging.root.info("ok")
        captured = capsys.readouterr()
        assert "[GLOBALAPP]" in captured.out

    def test_works_with_explicit_app_name(self, capsys):
        # Should not raise (app_name passed explicitly, no global set)
        Logger.intercept_stdlib(app_name="Explicit")
        logging.root.info("ok")
        captured = capsys.readouterr()
        assert "[EXPLICIT]" in captured.out


# ===================================================================
# Respect setLevel / hierarchy
# ===================================================================

class TestRespectsSetLevel:
    """Intercepted logs must respect ``Logger.getLogger(...).setLevel(...)``."""

    def test_setlevel_filters_intercepted_log(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        Logger.getLogger("mylib").setLevel("WARNING")

        logging.getLogger("mylib").info("should be filtered")
        logging.getLogger("mylib").warning("should pass")

        captured = capsys.readouterr()
        assert "should be filtered" not in captured.out
        assert "should pass" in captured.out

    def test_hierarchical_inheritance(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib()

        Logger.getLogger("parent").setLevel("ERROR")

        # "parent.child" has no explicit level → inherits "ERROR" from parent
        logging.getLogger("parent.child").warning("filtered")
        logging.getLogger("parent.child").error("passes")

        captured = capsys.readouterr()
        assert "filtered" not in captured.out
        assert "passes" in captured.out


# ===================================================================
# Propagation disabled for named loggers
# ===================================================================

class TestPropagation:
    """Named loggers must have propagate=False to avoid double emission."""

    def test_propagate_false_for_named(self):
        Logger.intercept_stdlib(app_name="App", logger_names=["mylib"])
        log = logging.getLogger("mylib")
        assert log.propagate is False

    def test_no_double_emit_when_root_and_named(self, capsys):
        """Intercepting both root and a named logger must not double-emit."""
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib(["mylib"])
        Logger.intercept_stdlib()  # also root

        logging.getLogger("mylib").info("single")

        captured = capsys.readouterr()
        assert captured.out.count("single") == 1


# ===================================================================
# Named-logger effective level (regression: setLevel(0)/NOTSET defers to
# root's default WARNING, silently dropping INFO — e.g. uvicorn.access)
# ===================================================================

class TestNamedLoggerEffectiveLevel:
    """Named loggers must have a real effective level, not NOTSET, so
    INFO records are never silently swallowed before reaching the
    handler — regardless of the root logger's own level."""

    def test_effective_level_enables_info(self):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib(["uvicorn.access"])

        log = logging.getLogger("uvicorn.access")
        assert log.getEffectiveLevel() <= logging.INFO
        assert log.isEnabledFor(logging.INFO)

    def test_info_passes_even_with_root_at_warning(self, capsys):
        # Simulate a process where root's level is left at its default
        # (WARNING) — e.g. because uvicorn's own configure_logging() ran
        # before intercept_stdlib(), like in `--reload` worker subprocesses.
        logging.root.setLevel(logging.WARNING)

        Logger.set_global_app_name("App")
        Logger.intercept_stdlib(["uvicorn.access"])

        logging.getLogger("uvicorn.access").info("GET / 200")

        captured = capsys.readouterr()
        assert "GET / 200" in captured.out


# ===================================================================
# Resilience to logging.config.dictConfig (uvicorn's setup)
# ===================================================================

class TestDictConfigResilience:
    """Our handlers must survive ``logging.config.dictConfig()`` calls."""

    def test_survives_dictconfig(self, capsys):
        Logger.set_global_app_name("App")
        Logger.intercept_stdlib(["mylib"])

        # Simulate what uvicorn does: call dictConfig with a new config
        import logging.config
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
            "loggers": {
                "mylib": {"level": "INFO"},
            },
        })

        logging.getLogger("mylib").info("after dictConfig")

        captured = capsys.readouterr()
        assert "after dictConfig" in captured.out


# ===================================================================
# Thread safety
# ===================================================================

class TestThreadSafety:
    """``intercept_stdlib`` is called from application startup code, which is
    not always single-threaded (worker bootstraps, lazy imports under a thread
    pool, ``--reload`` supervisors). Every check-then-act pair inside it used to
    race; these tests exercise those windows directly.
    """

    THREADS = 16

    @staticmethod
    def _run_concurrently(target, threads):
        """Fire `threads` workers at `target` as simultaneously as possible.

        The GIL switch interval is driven down to the minimum for the duration:
        the windows being tested are only a few bytecodes wide, so at the default
        5ms interval a thread almost always runs a whole check-then-act pair
        without being preempted and the race simply never reproduces.
        """
        barrier = threading.Barrier(threads)
        errors = []

        def worker(i):
            try:
                barrier.wait()
                target(i)
            except Exception as exc:  # pragma: no cover - only on a real failure
                errors.append(exc)

        original_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            pool = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
            for t in pool:
                t.start()
            for t in pool:
                t.join()
        finally:
            sys.setswitchinterval(original_interval)
        assert not errors, f"worker(s) raised: {errors}"

    def test_concurrent_root_interception_attaches_one_handler(self):
        """Racing callers must not each clear-and-attach onto root."""
        Logger.set_global_app_name("App")

        self._run_concurrently(lambda _: Logger.intercept_stdlib(), self.THREADS)

        assert len(logging.root.handlers) == 1
        assert logging.root.handlers[0] is Logger._stdlib_handler

    def test_concurrent_interception_builds_a_single_handler(self):
        """The handler singleton must be created exactly once."""
        Logger.set_global_app_name("App")
        seen = []

        def install(_):
            seen.append(Logger.intercept_stdlib())

        self._run_concurrently(install, self.THREADS)

        assert len(set(map(id, seen))) == 1, "more than one handler was built"
        assert seen[0] is Logger._stdlib_handler

    def test_concurrent_root_interception_emits_each_line_once(self, capsys):
        """The observable symptom of the race: duplicated log lines."""
        Logger.set_global_app_name("App")

        self._run_concurrently(lambda _: Logger.intercept_stdlib(), self.THREADS)
        capsys.readouterr()  # discard anything emitted during setup

        logging.root.info("once")

        out = capsys.readouterr().out
        assert out.count("once") == 1, f"line was duplicated: {out!r}"

    def test_concurrent_named_interception_of_same_name(self, capsys):
        """Racing on the same name must attach one handler, not one per thread."""
        Logger.set_global_app_name("App")

        self._run_concurrently(lambda _: Logger.intercept_stdlib(["shared"]), self.THREADS)
        capsys.readouterr()

        log = logging.getLogger("shared")
        assert len(log.handlers) == 1
        assert log.propagate is False

        log.info("once")
        out = capsys.readouterr().out
        assert out.count("once") == 1, f"line was duplicated: {out!r}"

    def test_concurrent_named_interception_of_distinct_names(self, capsys):
        """Every name must end up wired exactly once, none lost."""
        Logger.set_global_app_name("App")
        names = [f"lib{i}" for i in range(self.THREADS)]

        self._run_concurrently(lambda i: Logger.intercept_stdlib([names[i]]), self.THREADS)
        capsys.readouterr()

        assert Logger._intercepted_stdlib_loggers == set(names)
        for name in names:
            assert len(logging.getLogger(name).handlers) == 1

    @pytest.fixture
    def slow_handler_construction(self, monkeypatch):
        """Widen the concurrency window by making handler construction slow.

        The unguarded region in ``intercept_stdlib`` is only a handful of
        bytecodes, so at any realistic switch interval a thread runs the whole
        check-then-act pair before being preempted and the race never shows up.
        Sleeping inside the real ``StdlibInterceptHandler.__init__`` parks every
        thread *inside* that region at once, which is exactly the state a slow
        import or a contended interpreter produces in production.
        """
        real_init = _stdlib_bridge.StdlibInterceptHandler.__init__

        def slow_init(self, *args, **kwargs):
            real_init(self, *args, **kwargs)
            time.sleep(0.05)

        monkeypatch.setattr(
            _stdlib_bridge.StdlibInterceptHandler, "__init__", slow_init
        )

    def test_concurrent_install_is_atomic(self, slow_handler_construction, capsys):
        """The whole installation must be atomic, not just its individual steps.

        With every thread parked inside the critical region, the pre-fix code
        fails in two ways at once: N handlers get built and attached (duplicated
        log lines), and ``_ensure_dictConfig_patch`` captures its own patched
        function as the "original", so every later ``dictConfig()`` call in the
        process dies with RecursionError.
        """
        Logger.set_global_app_name("App")
        built = []

        self._run_concurrently(lambda _: built.append(Logger.intercept_stdlib()), 8)
        capsys.readouterr()

        # One handler, and it is the one on root.
        assert len(set(map(id, built))) == 1, "more than one handler was built"
        assert logging.root.handlers == [Logger._stdlib_handler]

        # The dictConfig patch captured the real function, not itself.
        assert _stdlib_bridge._original_dictConfig is _PRISTINE_DICTCONFIG
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})

        # And no line is emitted twice.
        capsys.readouterr()
        logging.root.info("once")
        out = capsys.readouterr().out
        assert out.count("once") == 1, f"line was duplicated: {out!r}"

    def test_concurrent_install_does_not_corrupt_dictconfig_patch(self):
        """The dictConfig monkeypatch must be installed exactly once.

        Pre-fix, ``_ensure_dictConfig_patch`` was a bare check-then-act: two
        threads both saw ``_dictConfig_patch_applied == False``, and the second
        captured the *already patched* function as ``_original_dictConfig``.
        ``_patched_dictConfig`` then called itself — every later
        ``dictConfig()`` call in the process died with RecursionError.
        """
        Logger.set_global_app_name("App")

        self._run_concurrently(lambda _: Logger.intercept_stdlib(), self.THREADS)

        assert _stdlib_bridge._dictConfig_patch_applied is True
        assert _stdlib_bridge._original_dictConfig is _PRISTINE_DICTCONFIG, (
            "the patch captured a non-pristine dictConfig — it patched itself"
        )

        # And the practical consequence: this must not blow the stack.
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})

    def test_dictconfig_reapply_races_with_new_interceptions(self, capsys):
        """``_reapply_handlers`` iterates the intercepted-names set while other
        threads add to it; an unsynchronized iteration raises
        "Set changed size during iteration".
        """
        import logging.config

        Logger.set_global_app_name("App")
        Logger.intercept_stdlib(["seed"])

        def churn(i):
            if i % 2:
                Logger.intercept_stdlib([f"churn{i}"])
            else:
                logging.config.dictConfig(
                    {"version": 1, "disable_existing_loggers": False}
                )

        self._run_concurrently(churn, self.THREADS)
        capsys.readouterr()

        # Interception still works after all that churn.
        logging.getLogger("seed").info("still here")
        assert "still here" in capsys.readouterr().out
