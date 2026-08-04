"""
Tests for ``Logger.intercept_stdlib()`` — redirecting Python's standard
``logging`` module through Steely's ``Logger``.
"""

import logging

import pytest

from steely.logger import Logger


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
