"""
stdlib bridge — intercept Python's ``logging`` module and redirect records
through Steely's ``Logger``, so third-party libraries (uvicorn, SQLAlchemy,
httpx, …) produce the same formatted output as native Steely log calls.
"""

import logging
import threading
import traceback

# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------
# Every mutation of the interception state — the handler singleton, the
# dictConfig monkeypatch, the set of intercepted logger names and the handler
# lists on the stdlib loggers — happens under this one lock.  Without it, the
# check-then-act pairs below race: two threads calling ``intercept_stdlib()``
# concurrently could build two handlers and attach both (duplicated log lines),
# and two threads installing the dictConfig patch could capture the *patched*
# function as ``_original_dictConfig`` — infinite recursion on the next
# ``dictConfig()`` call.
#
# It is an ``RLock`` because ``logging.config.dictConfig()`` runs arbitrary
# user-supplied factories, and one of those calling back into
# ``intercept_stdlib()`` on the same thread must not self-deadlock.
#
# LOCK ORDERING INVARIANT: this lock is only ever acquired *before* the
# ``logging`` module's internal lock, never after. Concretely, never take this
# lock from inside a handler's ``emit()`` (logging already holds its own lock
# there) — that would invert the order and can deadlock.
_LOCK = threading.RLock()

# ---------------------------------------------------------------------------
# dictConfig patch — uvicorn and other frameworks re-configure the logging
# tree via ``logging.config.dictConfig()``, which removes every handler we
# attached.  We patch it so our handlers are re-applied after every call.
# ---------------------------------------------------------------------------

_original_dictConfig = None
_dictConfig_patch_applied = False


def _reapply_handlers_locked():
    """Re-attach the interception handler. Caller must hold ``_LOCK``."""
    from steely.logger import Logger

    handler = Logger._stdlib_handler
    if handler is None:
        return

    if Logger._stdlib_root_intercepted:
        logging.root.handlers[:] = []
        logging.root.addHandler(handler)

    # Iterate a snapshot: the live set must not be mutated under us, and
    # holding the lock across getLogger/addHandler keeps each logger's
    # (handlers, propagate, level) triple internally consistent.
    for name in tuple(Logger._intercepted_stdlib_loggers):
        log = logging.getLogger(name)
        log.handlers[:] = []
        log.addHandler(handler)
        log.propagate = False
        log.setLevel(1)


def _patched_dictConfig(config):
    with _LOCK:
        _original_dictConfig(config)
        _reapply_handlers_locked()


def _ensure_dictConfig_patch_locked():
    """Install the dictConfig patch once. Caller must hold ``_LOCK``."""
    global _original_dictConfig, _dictConfig_patch_applied
    if _dictConfig_patch_applied:
        return
    # ``logging.config`` is a separate module; import it lazily.
    import logging.config
    _original_dictConfig = logging.config.dictConfig
    logging.config.dictConfig = _patched_dictConfig
    _dictConfig_patch_applied = True

# Mapping from Python logging numeric levels to Steely level strings.
# Compatible with the numeric table in ``Logger.setLevel`` /
# ``_LEVEL_NUMERIC``.
_STDLIB_TO_STEELY = {
    0: "TEST",      # NOTSET
    10: "TEST",     # DEBUG
    20: "INFO",     # INFO
    30: "WARNING",  # WARNING
    40: "ERROR",    # ERROR
    50: "CRITICAL", # CRITICAL
}


class StdlibInterceptHandler(logging.Handler):
    """A ``logging.Handler`` that forwards every record to Steely's
    ``Logger.getLogger(owner)``, preserving level, exception info,
    and caller context as tags.
    """

    def __init__(self, app_name=None):
        super().__init__(level=0)  # capture everything
        self._app_name = app_name

    def emit(self, record):
        # Lazy import to avoid circular dependency at module level.
        from steely.logger import Logger

        # 1. Map level
        steely_level = _STDLIB_TO_STEELY.get(record.levelno, "INFO")

        # 2. Infer owner
        owner = record.name if record.name and record.name != "root" else record.module

        # 3. Interpolate %s / %d placeholders (stdlib stores the format
        #    string in record.msg and the values in record.args; we must
        #    call getMessage() to merge them).
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            message = record.msg

        # 4. Append traceback when exc_info is present
        if record.exc_info and record.exc_info[0] is not None:
            tb_text = "".join(traceback.format_exception(*record.exc_info))
            message = f"{message}\n{tb_text}"

        # 5. Dispatch through Steely's named-logger registry
        steely_logger = Logger.getLogger(owner)
        steely_logger.log(
            steely_level,
            message,
            app_name=self._app_name,
        )


def intercept_stdlib(logger_names=None, app_name=None):
    """Intercept standard-library loggers and route them through Steely.

    Parameters
    ----------
    logger_names : list of str, optional
        Specific logger names to intercept (e.g. ``["uvicorn",
        "uvicorn.error"]``).  When *None* (default) the **root** logger
        is intercepted, which catches **every** stdlib log message.
    app_name : str, optional
        Application name to use for intercepted logs.  When *None* the
        value set via ``Logger.set_global_app_name()`` is used.  At
        least one must be set or a ``ValueError`` is raised.

    Raises
    ------
    ValueError
        If neither *app_name* nor ``Logger._global_app_name`` is set.

    Notes
    -----
    - Idempotent — calling ``intercept_stdlib`` multiple times with the
      same *logger_names* does **not** duplicate handlers or log lines.
    - **Thread-safe.** The whole installation runs under a module-level lock,
      so concurrent calls from several threads cannot build two handlers,
      attach a handler twice, or corrupt the dictConfig monkeypatch.
    - Named loggers have ``propagate`` set to *False* to prevent
      double-emission through parent loggers or the root logger.
    - Existing handlers on the targeted loggers are removed (silenced).
    """
    from steely.logger import Logger

    # --- validate app_name ------------------------------------------------
    # Read once: a concurrent set_global_app_name() must not make the check
    # below disagree with what we hand to the handler.
    if app_name is None and Logger._global_app_name is None:
        raise ValueError(
            "No global app_name set. Call Logger.set_global_app_name('MyApp') "
            "first, or pass app_name='MyApp' to Logger.intercept_stdlib()."
        )

    # Everything past this point is check-then-act on shared state, so it all
    # runs under one lock. Note the ordering invariant documented at _LOCK:
    # we take _LOCK first and only then call into ``logging`` (which takes its
    # own lock) — never the reverse.
    with _LOCK:
        # --- create / reuse handler singleton -----------------------------
        if Logger._stdlib_handler is None:
            Logger._stdlib_handler = StdlibInterceptHandler(app_name=app_name)
        elif app_name is not None:
            Logger._stdlib_handler._app_name = app_name

        handler = Logger._stdlib_handler

        # --- patch dictConfig so uvicorn (and others) can't erase our handlers
        _ensure_dictConfig_patch_locked()

        # --- clear any module-wide suppress level set via logging.disable() --
        logging.disable(logging.NOTSET)

        # --- attach to root -----------------------------------------------
        if logger_names is None:
            if not Logger._stdlib_root_intercepted:
                logging.root.handlers[:] = []
                logging.root.setLevel(0)
                logging.root.addHandler(handler)
                Logger._stdlib_root_intercepted = True
            return handler

        # --- attach to named loggers --------------------------------------
        for name in logger_names:
            if name in Logger._intercepted_stdlib_loggers:
                continue
            log = logging.getLogger(name)
            log.handlers[:] = []
            log.setLevel(1)
            log.addHandler(handler)
            log.propagate = False
            # Recorded last: a name is only "intercepted" once it fully is, so a
            # crash midway cannot leave the set claiming a logger we never wired.
            Logger._intercepted_stdlib_loggers.add(name)

        return handler
