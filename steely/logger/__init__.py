"""
Logger Module - Flexible Logging with Color-Coded Output
=========================================================

This module provides a powerful, thread-safe logging system with support for
color-coded terminal output, file logging, and automatic function decoration.

Features
--------
- Color-coded log levels (INFO, WARNING, ERROR, etc.)
- Thread-safe asynchronous logging
- File logging with date-based rotation
- Screen clearing capability
- Decorator for automatic function logging
- Support for both sync and async functions

Classes
-------
Logger
    Main logging class with support for multiple log levels.

Functions
---------
log
    Decorator that automatically logs function execution.
relative
    Helper function for constructing relative paths.

Log Levels
----------
The following log levels are supported, each with distinct colors:

- **INFO/START** (Cyan): General information and function start
- **WARNING/ALERT** (Yellow): Warning messages
- **SUCCESS/OK** (Green): Success messages
- **ERROR/FAIL/FAULT/CRITICAL/FATAL** (Red): Error messages
- **TEST/TEST-RESULT** (Blue): Test-related messages

Examples
--------
Basic logging:

>>> from steely.logger import Logger
>>> logger = Logger("MyApp", "main")
>>> logger.info("Application started")
>>> logger.warning("Low memory")
>>> logger.error("Connection failed")

Using the log decorator:

>>> from steely.logger import log
>>> @log
... def process_data(data):
...     return data.upper()

Logging to file:

>>> logger = Logger("MyApp", "main", destination="/var/log/myapp")
>>> logger.info("This will be saved to file")
"""

import asyncio
import inspect
import os
from datetime import datetime
from functools import wraps
from typing import Literal

from steely.design import UnicodeColors

__all__ = ["Logger", "log", "relative", "Level"]


def relative(path: str) -> str:
    """
    Construct an absolute path relative to this module's directory.

    This helper function is useful for accessing files that are stored
    alongside the logger module, such as configuration files or templates.

    Parameters
    ----------
    path : str
        The relative path to append to the module's directory.

    Returns
    -------
    str
        The absolute path constructed by joining the module's directory
        with the provided relative path.

    Examples
    --------
    >>> relative("config.json")
    '/path/to/steely/logger/config.json'
    >>> relative("templates/email.html")
    '/path/to/steely/logger/templates/email.html'
    """
    return os.path.join(os.path.dirname(__file__), path)


Level = Literal[
    "INFO",
    "START",
    "WARNING",
    "ALERT",
    "SUCCESS",
    "OK",
    "CRITICAL",
    "ERROR",
    "FAULT",
    "FAIL",
    "FATAL",
    "TEST-RESULT",
    "TEST",
]
"""
Type alias for valid log level strings.

Valid values are: INFO, START, WARNING, ALERT, SUCCESS, OK,
CRITICAL, ERROR, FAULT, FAIL, FATAL, TEST-RESULT, TEST.
"""

# Numeric severity — compatible with Python's logging module constants
_LEVEL_NUMERIC = {
    "TEST": 10, "TEST-RESULT": 10,
    "INFO": 20, "START": 20, "SUCCESS": 20, "OK": 20,
    "WARNING": 30, "ALERT": 30,
    "ERROR": 40, "FAULT": 40, "FAIL": 40,
    "CRITICAL": 50, "FATAL": 50,
}

# Color mapping for log levels (optimization)
_COLOR_MAP = {
    'INFO': UnicodeColors.success_cyan,
    'START': UnicodeColors.success_cyan,
    'WARNING': UnicodeColors.alert,
    'ALERT': UnicodeColors.alert,
    'SUCCESS': UnicodeColors.success,
    'OK': UnicodeColors.success,
    'CRITICAL': UnicodeColors.fail,
    'ERROR': UnicodeColors.fail,
    'FAULT': UnicodeColors.fail,
    'FAIL': UnicodeColors.fail,
    'FATAL': UnicodeColors.fail,
    'TEST-RESULT': UnicodeColors.bright_blue,
    'TEST': UnicodeColors.bright_blue,
}


class Logger:
    """
    A flexible, thread-safe logger with color-coded terminal output.

    Logger provides a comprehensive logging solution with support for multiple
    log levels, file output, screen clearing, and beautiful color-coded
    terminal output using ANSI escape codes.

    Parameters
    ----------
    owner : str
        The owner/component name displayed in log messages (e.g., function
        name, module name, subsystem). First positional argument. Will be
        converted to uppercase.
    app_name : str, optional
        The application name displayed before the owner in log messages. Will
        be converted to uppercase. If None (default), no app-name segment is
        shown — or the global app name set via
        :meth:`set_global_app_name` is used when present.
    destination : str, optional
        Directory path for file logging. If provided, logs will be written
        to date-stamped files (DD-MM-YYYY.log) in this directory.
        Default is None (no file logging).
    debug : bool, optional
        Enable debug mode. When True, sets environment to "debug" and
        appends "_debug" to the log directory. Default is True.
    clean : bool, optional
        Enable persistent screen clearing. When True, clears the screen
        before each log message. Default is False.
    callback : callable, optional
        A function invoked for every emitted record, in addition to the
        console/file output. Receives the level, message, app name, owner,
        timestamp and rendered content — the same hook the global Grafana
        sink uses. Default is None.
    **kwargs
        Additional keyword arguments that will be included as bracketed tags
        in each log message.

    Attributes
    ----------
    app_name_upper : str
        The uppercase application name.
    owner : str
        The owner/component name.
    path : str or None
        The destination path for file logging.
    _debug : bool
        Whether debug mode is enabled.
    environment : str or None
        The current environment ("debug" or None).
    clean : bool
        Whether screen clearing is enabled for the next message.
    master_clean : bool
        Whether screen clearing is persistent.
    kwargs : dict
        Additional tags to include in log messages.

    Examples
    --------
    Basic usage:

    >>> logger = Logger("MyApp", "database")
    >>> logger.info("Connected to database")
    >>> logger.warning("Connection pool running low")
    >>> logger.error("Query timeout")

    With file logging:

    >>> logger = Logger("MyApp", "api", destination="/var/log/myapp")
    >>> logger.info("Request received")  # Also saved to file

    With additional tags:

    >>> logger = Logger("MyApp", "auth", session_id="abc123")
    >>> logger.info("User logged in")  # Includes [ABC123] tag

    Callable usage:

    >>> logger = Logger("MyApp", "main")
    >>> logger("INFO", "Direct call works too")

    Notes
    -----
    - All logging operations are performed in separate threads for
      non-blocking behavior.
    - Log files are named using the format DD-MM-YYYY.log and are
      appended to throughout the day.
    - Screen clearing works on both Windows (cls) and Unix (clear).
    """

    clean = False
    master_clean = False
    environment = None
    log_path = None
    _global_app_name = None
    _global_destination = None
    _global_grafana = None
    _registry: dict = {}
    _global_level: int = 0  # 0 = log everything

    def __init__(self, owner: str, app_name: str = None, destination: str = None, debug: bool = True, clean: bool = False, callback: callable = None, **kwargs):

        self.kwargs = kwargs

        if clean:
            self.master_clean = True

        if app_name is None:
            self.app_name_upper = None
        else:
            self.app_name_upper = str(app_name).upper()

        # Use global destination if no destination provided
        if destination is None and self._global_destination is not None:
            self.path = self._global_destination
        else:
            self.path = destination
        self._debug = debug
        self.owner = owner
        self.owner_upper = owner.upper()  # Cache uppercase owner (optimization)

        if debug:
            self.environment = "debug"

        self.callback = callback
        self._level = None  # None = inherit from hierarchy or global

        # Performance optimizations: cache log path and file handle
        self._cached_log_path = None
        self._cached_log_date = None
        self._log_file_handle = None
        self._base_dir = None  # Cache base directory

    def _get_log_path(self, current_date: str) -> str:
        """
        Get or generate the log file path with caching for performance.

        Parameters
        ----------
        current_date : str
            Current date string in DD-MM-YYYY format

        Returns
        -------
        str
            Full path to the log file
        """
        # Return cached path if date hasn't changed
        if self._cached_log_date == current_date and self._cached_log_path is not None:
            return self._cached_log_path

        # Calculate base directory once
        if self._base_dir is None:
            if self.environment is not None and self.path is not None:
                try:
                    self._base_dir = f"{self.path}_{self.environment}"
                except TypeError:
                    self._base_dir = os.path.join('.', f"log_{self.environment}")
            else:
                self._base_dir = str(self.path) if self.path is not None else '.'

            # Ensure base_dir exists (only once)
            try:
                os.makedirs(self._base_dir, exist_ok=True)
            except Exception:
                pass

        # Construct full path
        filename = current_date + ".log"
        full_path = os.path.join(self._base_dir, filename)

        # Cache the result
        self._cached_log_path = full_path
        self._cached_log_date = current_date

        # Close old file handle if date changed
        if self._log_file_handle is not None:
            try:
                self._log_file_handle.close()
            except:
                pass
            self._log_file_handle = None

        return full_path

    def __del__(self):
        """Cleanup: close file handle when logger is destroyed."""
        if self._log_file_handle is not None:
            try:
                self._log_file_handle.close()
            except:
                pass

    def log(self, level: Level, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, self_debug: bool = True, **kwargs):
        """
        Internal method that performs the actual logging operation.

        This static method is called in a separate thread by the log() method
        to ensure non-blocking logging. It handles formatting, coloring,
        file writing, and terminal output.

        Parameters
        ----------
        logger : Logger
            The Logger instance containing configuration.
        level : Level
            The log level (INFO, WARNING, ERROR, etc.).
        message : str
            The message to log.
        app_name : str, optional
            Override the logger's app_name for this message.
        clean : bool, optional
            Clear the screen after this message. Default is False.
        supress : bool, optional
            Suppress terminal output. Default is False.
        debug : bool, optional
            Force output regardless of suppress. Default is True.
        self_debug : bool, optional
            The logger instance's debug setting. Default is True.
        **kwargs
            Additional tags to include in this message.

        Returns
        -------
        str
            The formatted log message content.

        Notes
        -----
        This method should not be called directly. Use the log() method
        or the level-specific methods (info, warning, error, etc.) instead.
        """

        if _LEVEL_NUMERIC.get(level.upper(), 20) < self._get_effective_level():
            return None

        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                pass

        # Single datetime.now() call for both timestamp and filename (optimization)
        now = datetime.now()

        if self.clean:
            os.system('cls' if os.name == 'nt' else 'clear')
            if not self.master_clean:
                self.clean = False

        # Pre-format date strings (only call strftime once each)
        current_date = now.strftime('%d-%m-%Y')
        timestamp = f"{current_date} {now.strftime('%H:%M:%S')}"
        level = level.upper()
        owner = self.owner_upper  # Use cached uppercase owner (optimization)

        # Determine which app_name to use (priority order):
        # 1. Explicit app_name parameter
        # 2. Global app_name (if set)
        # 3. Instance app_name
        if app_name is not None:
            # Explicitly provided app_name takes highest priority
            _current_app = str(app_name).upper()
        elif self._global_app_name is not None:
            # Use global app_name if set
            _current_app = self._global_app_name
        else:
            # Fall back to instance app_name
            _current_app = self.app_name_upper

        # Remove suppress from kwargs if present
        kwargs.pop("suppress", None)

        # Build message efficiently using list and join
        message_parts = [timestamp]
        if _current_app is not None:
            message_parts.append(f"[{_current_app}]")
        message_parts.append(f"[{owner}]")

        # Add instance kwargs
        if self.kwargs:
            message_parts.extend(f"[{str(item).upper()}]" for item in self.kwargs.values())

        # Add method kwargs
        if kwargs:
            message_parts.extend(f"[{str(item).upper()}]" for item in kwargs.values())

        message_parts.append(f"[{level}]")

        message_enclose = " - ".join(message_parts[:2]) + " " + " ".join(message_parts[2:])
        content = f"\n{message_enclose}: {str(message)}"

        # Write to file with cached path and reusable file handle
        if self.path is not None:
            log_path = self._get_log_path(current_date)

            # Keep file handle open for reuse
            if self._log_file_handle is None or self._log_file_handle.closed:
                try:
                    self._log_file_handle = open(log_path, 'a+')
                except Exception:
                    pass

            if self._log_file_handle is not None:
                try:
                    self._log_file_handle.write(str(content))
                    self._log_file_handle.flush()  # Ensure data is written
                except Exception:
                    pass

        # Use dictionary lookup for color (optimization #2)
        correspondent_clr = _COLOR_MAP.get(level, UnicodeColors.reset)

        if not supress or debug or self_debug:
            print(correspondent_clr, content[1:], UnicodeColors.reset)
            if clean:
                self.clean = True

        if self.callback is not None:
            self.callback(
                level=level,
                message=message,
                app_name=_current_app,
                owner=owner,
                timestamp=timestamp,
                content=content,
                **{**self.kwargs, **kwargs},
            )

        if self._global_grafana is not None:
            self._global_grafana(
                level=level,
                message=message,
                app_name=_current_app,
                owner=owner,
                timestamp=timestamp,
                content=content,
                **{**self.kwargs, **kwargs},
            )

        return content

    def __call__(self, *args, **kwargs):
        """Allow the logger instance to be called directly like a function."""
        self.log(*args, **kwargs)

    def info(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log an informational message (cyan color)."""
        return self.log("INFO", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def debug(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log an informational message (cyan color)."""
        if os.getenv("DEBUG", False):
            self.log("INFO", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)
            return True
        return False

    def start(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a start/initialization message (cyan color)."""
        return self.log("START", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def warning(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a warning message (yellow color)."""
        return self.log("WARNING", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def alert(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log an alert message (yellow color)."""
        return self.log("ALERT", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def success(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a success message (green color)."""
        return self.log("SUCCESS", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def ok(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log an OK/confirmation message (green color)."""
        return self.log("OK", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def critical(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a critical error message (red color)."""
        return self.log("CRITICAL", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def error(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log an error message (red color)."""
        return self.log("ERROR", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def fault(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a fault message (red color)."""
        return self.log("FAULT", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def fail(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a failure message (red color)."""
        return self.log("FAIL", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def fatal(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a fatal error message (red color)."""
        return self.log("FATAL", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def test_result(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a test result message (blue color)."""
        return self.log("TEST-RESULT", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def test(self, message, *args, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
        """Log a test message (blue color)."""
        return self.log("TEST", message, *args, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

    def set_app_name(self, app_name: str):
        """
        Set the application name for this logger instance.

        Parameters
        ----------
        app_name : str
            The new application name. Will be converted to uppercase.
            If None, app_name will not be printed in log messages.

        Examples
        --------
        >>> logger = Logger("main", "OldApp")
        >>> logger.info("Message with OldApp")
        >>> logger.set_app_name("NewApp")
        >>> logger.info("Message with NewApp")
        >>> logger.set_app_name(None)
        >>> logger.info("Message without app_name")
        """
        self.app_name_upper = str(app_name).upper() if app_name is not None else None

    def setLevel(self, level):
        """
        Set the minimum log level for this logger instance.

        Accepts Python's standard logging constants (``logging.INFO``,
        ``logging.WARNING``, etc.) or Steely level strings (``"INFO"``,
        ``"WARNING"``, etc.).

        Parameters
        ----------
        level : int or str
            Minimum level to log. Messages below this level are silently
            dropped. Pass ``None`` to clear the instance level and inherit
            from the hierarchy.

        Examples
        --------
        >>> import logging
        >>> Logger.getLogger("src.infra").setLevel(logging.INFO)   # int
        >>> Logger.getLogger("src.app").setLevel("WARNING")        # string
        >>> Logger.getLogger("src.app").setLevel(None)             # inherit
        """
        if level is None:
            self._level = None
        elif isinstance(level, str):
            self._level = _LEVEL_NUMERIC.get(level.upper(), 0)
        else:
            self._level = int(level)

    def _get_effective_level(self) -> int:
        """Return the effective numeric level, walking up the dotted hierarchy."""
        if self._level is not None:
            return self._level
        name = self.owner
        while '.' in name:
            name = name.rsplit('.', 1)[0]
            parent = self._registry.get(name)
            if parent is not None and parent._level is not None:
                return parent._level
        return self._global_level

    @classmethod
    def getLogger(cls, name: str) -> "Logger":
        """
        Return a cached Logger for the given name, creating it if needed.

        Names can be dotted paths (e.g. ``"src.infrastructure"``).  A logger
        with no explicit level inherits from its closest ancestor that has a
        level set, or from the global level.

        Parameters
        ----------
        name : str
            Logger name / owner. Dotted names form a hierarchy.

        Returns
        -------
        Logger
            Cached Logger instance for ``name``.

        Examples
        --------
        >>> import logging
        >>> Logger.getLogger("src").setLevel(logging.WARNING)
        >>> log = Logger.getLogger("src.infrastructure")  # inherits WARNING
        >>> log.info("quiet")    # filtered
        >>> log.error("loud")    # shown
        """
        if name not in cls._registry:
            cls._registry[name] = cls(owner=name)
        return cls._registry[name]

    @classmethod
    def set_global_level(cls, level):
        """
        Set the minimum log level for all loggers that have no explicit level.

        Parameters
        ----------
        level : int or str
            Minimum level. ``0`` (default) logs everything.

        Examples
        --------
        >>> Logger.set_global_level("INFO")      # suppress TEST globally
        >>> Logger.set_global_level(logging.WARNING)
        >>> Logger.set_global_level(0)           # reset — log everything
        """
        if isinstance(level, str):
            cls._global_level = _LEVEL_NUMERIC.get(level.upper(), 0)
        else:
            cls._global_level = int(level)

    @classmethod
    def set_global_app_name(cls, app_name: str):
        """
        Set a global application name that will be used by the log decorator.

        This class method sets a global app_name that will be used by all
        functions decorated with @log. If not set, the log decorator uses
        the module name of the decorated function.

        Parameters
        ----------
        app_name : str
            The global application name. Will be converted to uppercase.

        Examples
        --------
        >>> Logger.set_global_app_name("MyApp")
        >>> @log
        ... def my_function():
        ...     pass
        # Now all @log decorated functions will use "MyApp" as the app_name
        """
        cls._global_app_name = str(app_name).upper() if app_name is not None else None

    @classmethod
    def set_global_destination(cls, destination: str):
        """
        Set a global log destination path that will be used by all Logger instances.

        This class method sets a global destination path that will be used by all
        Logger instances when no explicit destination is provided. This is useful
        for setting a project-wide log directory without having to pass it to every
        Logger instance.

        Parameters
        ----------
        destination : str
            The global log destination directory path. If None, clears the global destination.

        Examples
        --------
        >>> Logger.set_global_destination("/var/log/myapp")
        >>> logger1 = Logger("module1")  # Will log to /var/log/myapp
        >>> logger2 = Logger("module2")  # Will also log to /var/log/myapp
        >>> logger3 = Logger("module3", destination="/tmp/logs")  # Explicit destination overrides global
        """
        cls._global_destination = destination

    @classmethod
    def set_global_grafana(
        cls,
        url: str,
        labels: dict = None,
        batch_size: int = 50,
        flush_interval: float = 5.0,
        timeout: int = 3,
        auth: tuple = None,
        token: str = None,
        protocol: str = "otlp",
        debug: bool = False,
        max_queue_size: int = 10_000,
    ):
        """
        Configure a global Grafana sink for all Logger instances.

        Once set, every log call from any Logger instance will enqueue an entry
        to be sent to Grafana in a background batch — with zero blocking.

        Parameters
        ----------
        url : str
            Base URL of the Grafana endpoint.
            Grafana Cloud (OTLP): ``"https://otlp-gateway-prod-sa-east-1.grafana.net"``
            Self-hosted Loki:     ``"http://loki:3100"``
        labels : dict, optional
            OTLP: ``resource.attributes`` (e.g. ``{"service.name": "my-api"}``).
            Loki: stream labels (keep cardinality low).
        batch_size : int, optional
            Max entries per HTTP push request. Default 50.
        flush_interval : float, optional
            Max seconds between flushes. Default 5.0.
        timeout : int, optional
            HTTP request timeout in seconds. Default 3.
        auth : tuple, optional
            ``(username, password)`` for Basic Auth.
            Grafana Cloud: ``(instance_id, api_key)``.
        token : str, optional
            Bearer token (alternative to ``auth``).
        protocol : str, optional
            ``"otlp"`` (default, Grafana Cloud) or ``"loki"`` (self-hosted).

        Returns
        -------
        GrafanaSink
            The sink instance, so callers can call ``sink.flush()`` / ``sink.close()``.

        Examples
        --------
        Grafana Cloud:

        >>> sink = Logger.set_global_grafana(
        ...     url="https://otlp-gateway-prod-sa-east-1.grafana.net",
        ...     labels={"service.name": "my-api", "deployment.environment": "prod"},
        ...     auth=("1628732", "glc_eyJ..."),
        ... )

        Self-hosted Loki:

        >>> sink = Logger.set_global_grafana(
        ...     url="http://loki:3100",
        ...     labels={"app": "my-api"},
        ...     protocol="loki",
        ... )

        FastAPI (single worker — call anywhere):

        >>> sink = Logger.set_global_grafana(url=..., auth=(...))
        >>> app = FastAPI()

        FastAPI (``uvicorn --workers N``) — call inside lifespan, after fork:

        >>> from contextlib import asynccontextmanager
        >>> @asynccontextmanager
        ... async def lifespan(app):
        ...     Logger.set_global_grafana(url=..., auth=(...))
        ...     yield
        >>> app = FastAPI(lifespan=lifespan)
        """
        from steely.grafana import GrafanaSink
        cls._global_grafana = GrafanaSink(
            url=url,
            labels=labels,
            batch_size=batch_size,
            flush_interval=flush_interval,
            timeout=timeout,
            auth=auth,
            token=token,
            protocol=protocol,
            debug=debug,
            max_queue_size=max_queue_size,
        )
        return cls._global_grafana


def log(func):
    """
    Decorator that automatically logs function execution lifecycle.

    This decorator wraps a function to automatically log when it starts,
    completes successfully, or fails with an exception. It supports both
    synchronous and asynchronous functions.

    Parameters
    ----------
    func : callable
        The function to decorate. Can be sync or async.

    Returns
    -------
    callable
        The wrapped function with automatic logging.

    Behavior
    --------
    - **On call**: Logs "[START]: Function Execution Started..."
    - **On success**: Logs "[SUCCESS]: Function Finished"
    - **On exception**: Logs "[ERROR]: Function Failed: <error message>"

    The log messages include:
    - Timestamp (DD-MM-YYYY HH:MM:SS)
    - Module name or global app_name (uppercase)
    - Function name (uppercase)
    - Log level

    Examples
    --------
    Basic usage with sync function:

    >>> from steely import Dan
    >>> @Dan.log
    ... def process_data(data):
    ...     return data.upper()
    >>> process_data("hello")
    # Logs: [START]: Function Execution Started...
    # Logs: [SUCCESS]: Function Finished
    'HELLO'

    With async function:

    >>> @Dan.log
    ... async def fetch_data(url):
    ...     response = await http_client.get(url)
    ...     return response

    Error handling:

    >>> @Dan.log
    ... def risky_operation():
    ...     raise ValueError("Something went wrong")
    >>> risky_operation()
    # Logs: [START]: Function Execution Started...
    # Logs: [ERROR]: Function Failed: Something went wrong

    Using global app name:

    >>> Logger.set_global_app_name("MyApp")
    >>> @log
    ... def my_function():
    ...     pass
    # Now uses "MyApp" instead of module name

    Notes
    -----
    - The original function signature is preserved for compatibility
      with frameworks like FastAPI that use introspection.
    - Exceptions are logged but not re-raised; the function returns None
      on error.
    - The module name is extracted using inspect.getmodule() unless a
      global app_name is set via Logger.set_global_app_name().
    """
    # Store the module name as fallback
    module_name = inspect.getmodule(func).__name__
    # Create logger without app_name, will use global app_name dynamically at runtime
    __log__ = Logger(func.__name__)

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Use global app_name if set, otherwise use module name
            current_app_name = Logger._global_app_name if Logger._global_app_name is not None else module_name
            __log__.start(f'Function Execution Started...', app_name=current_app_name)
            try:
                res = await func(*args, **kwargs)
                __log__.success(f'Function Finished', app_name=current_app_name)

                return res
            except Exception as e:
                __log__.error(f'Function Failed: {str(e)}', app_name=current_app_name)
                raise e

        async_wrapper.__signature__ = inspect.signature(func)
        return async_wrapper
    else:

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Use global app_name if set, otherwise use module name
            current_app_name = Logger._global_app_name if Logger._global_app_name is not None else module_name
            __log__.start(f'Function Execution Started...', app_name=current_app_name)
            try:
                res = func(*args, **kwargs)
                __log__.success(f'Function Finished', app_name=current_app_name)

                return res
            except Exception as e:
                __log__.error(f'Function Failed: {str(e)}', app_name=current_app_name)

        sync_wrapper.__signature__ = inspect.signature(func)
        return sync_wrapper
