"""
Tests for Logger.getLogger(), setLevel(), and hierarchical level inheritance.
"""

import logging  # for standard constants: logging.INFO=20, logging.WARNING=30, etc.

from steely.logger import Logger


def setup_function():
    Logger._registry.clear()
    Logger._global_level = 0


def teardown_function():
    Logger._registry.clear()
    Logger._global_level = 0


# ---------------------------------------------------------------------------
# getLogger — cache behaviour
# ---------------------------------------------------------------------------

def test_getlogger_returns_same_instance():
    a = Logger.getLogger("myapp.service")
    b = Logger.getLogger("myapp.service")
    assert a is b


def test_getlogger_different_names_different_instances():
    a = Logger.getLogger("myapp.service")
    b = Logger.getLogger("myapp.repository")
    assert a is not b


def test_getlogger_sets_owner():
    log = Logger.getLogger("src.infrastructure")
    assert log.owner == "src.infrastructure"


# ---------------------------------------------------------------------------
# setLevel — instance filtering
# ---------------------------------------------------------------------------

def test_setlevel_string_filters_below():
    log = Logger.getLogger("app")
    log.setLevel("INFO")
    assert log._level == 20


def test_setlevel_int_compat_with_logging_module():
    log = Logger.getLogger("app")
    log.setLevel(logging.WARNING)  # 30
    assert log._level == 30


def test_setlevel_none_clears_level():
    log = Logger.getLogger("app")
    log.setLevel("ERROR")
    log.setLevel(None)
    assert log._level is None


def test_log_filtered_below_level(capsys):
    log = Logger.getLogger("filtered")
    log.setLevel("WARNING")   # numeric 30

    result_info = log.info("should be filtered")
    result_warn = log.warning("should pass")

    assert result_info is None
    captured = capsys.readouterr()
    assert "should be filtered" not in captured.out
    assert "should pass" in captured.out


def test_log_passes_at_and_above_level(capsys):
    log = Logger.getLogger("threshold")
    log.setLevel("ERROR")   # 40

    log.warning("filtered")  # 30 < 40
    log.error("shown")       # 40 >= 40
    log.fatal("also shown")  # 50 >= 40

    captured = capsys.readouterr()
    assert "filtered" not in captured.out
    assert "shown" in captured.out
    assert "also shown" in captured.out


# ---------------------------------------------------------------------------
# Hierarchical level inheritance
# ---------------------------------------------------------------------------

def test_child_inherits_parent_level(capsys):
    Logger.getLogger("src").setLevel("WARNING")
    child = Logger.getLogger("src.infrastructure")

    child.info("should be filtered")
    child.warning("should pass")

    captured = capsys.readouterr()
    assert "should be filtered" not in captured.out
    assert "should pass" in captured.out


def test_child_level_overrides_parent(capsys):
    Logger.getLogger("src").setLevel("WARNING")
    child = Logger.getLogger("src.infrastructure")
    child.setLevel("INFO")   # overrides parent

    child.info("should pass now")

    captured = capsys.readouterr()
    assert "should pass now" in captured.out


def test_deep_hierarchy_inherits_nearest_ancestor(capsys):
    Logger.getLogger("a").setLevel("ERROR")
    Logger.getLogger("a.b").setLevel("WARNING")
    grandchild = Logger.getLogger("a.b.c")  # no level → inherits "a.b" (WARNING)

    grandchild.info("filtered")
    grandchild.warning("shown")

    captured = capsys.readouterr()
    assert "filtered" not in captured.out
    assert "shown" in captured.out


def test_no_parent_falls_back_to_global(capsys):
    Logger.set_global_level("ERROR")
    log = Logger.getLogger("orphan")  # no parent, no own level

    log.warning("filtered by global")
    log.error("shown")

    captured = capsys.readouterr()
    assert "filtered by global" not in captured.out
    assert "shown" in captured.out


# ---------------------------------------------------------------------------
# set_global_level
# ---------------------------------------------------------------------------

def test_set_global_level_string():
    Logger.set_global_level("WARNING")
    assert Logger._global_level == 30


def test_set_global_level_int():
    Logger.set_global_level(logging.INFO)
    assert Logger._global_level == 20


def test_set_global_level_zero_resets():
    Logger.set_global_level("ERROR")
    Logger.set_global_level(0)
    assert Logger._global_level == 0


def test_global_level_does_not_affect_instance_with_own_level(capsys):
    Logger.set_global_level("CRITICAL")  # very restrictive globally
    log = Logger.getLogger("special")
    log.setLevel("INFO")   # own level overrides global

    log.info("should pass despite global")

    captured = capsys.readouterr()
    assert "should pass despite global" in captured.out
