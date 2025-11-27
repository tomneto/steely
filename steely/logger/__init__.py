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
import multiprocessing
import os
import threading
from functools import wraps
from time import sleep
from datetime import datetime
from typing import Literal, Any

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


class Logger:
	"""
	A flexible, thread-safe logger with color-coded terminal output.

	Logger provides a comprehensive logging solution with support for multiple
	log levels, file output, screen clearing, and beautiful color-coded
	terminal output using ANSI escape codes.

	Parameters
	----------
	app_name : str
		The application name displayed in log messages. Will be converted
		to uppercase. If None, defaults to 'YOUR-APP-NAME-GOES-HERE'.
	owner : str
		The owner/component name displayed in log messages (e.g., function
		name, module name). Will be converted to uppercase.
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
	**kwargs
		Additional keyword arguments that will be included as tags in
		each log message.

	Attributes
	----------
	app_name_upper : str
		The uppercase application name.
	owner : str
		The owner/component name.
	path : str or None
		The destination path for file logging.
	debug : bool
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

	def __init__(self, owner: str, app_name: str = None, destination: str = None, debug: bool = True, clean: bool = False, **kwargs):

		self.kwargs = kwargs

		if clean:
			self.master_clean = True

		if app_name is None:
			self.app_name_upper = None
		else:
			self.app_name_upper = str(app_name).upper()

		self.path = destination
		self.debug = debug
		self.owner = owner

		if debug:
			self.environment = "debug"

	@staticmethod
	def _subprocess_log(logger, level: Level, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, self_debug: bool = True, **kwargs):
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

		def generate_log_path():
			# Initialize base directory path
			if logger.environment is not None and logger.path is not None:
				try:
					base_dir = f"{logger.path}_{logger.environment}"
				except TypeError:
					base_dir = os.path.join('.', f"log_{logger.environment}")
			else:
				base_dir = str(logger.path) if logger.path is not None else '.'

			# Ensure base_dir is treated as a directory
			try:
				os.makedirs(base_dir, exist_ok=True)
			except Exception:
				pass

			# Construct filename and full path
			filename = datetime.now().strftime('%d-%m-%Y') + ".log"
			full_path = os.path.join(base_dir, filename)

			return full_path

		if logger.clean:
			os.system('cls' if os.name == 'nt' else 'clear')
			if not logger.master_clean:
				logger.clean = False

		timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
		level = level.upper()
		owner = logger.owner.upper()
		correspondent_clr = UnicodeColors.reset

		# Determine which app_name to use (priority order):
		# 1. Explicit app_name parameter
		# 2. Global app_name (if set)
		# 3. Instance app_name
		if app_name is not None:
			# Explicitly provided app_name takes highest priority
			_current_app = str(app_name).upper()
		elif Logger._global_app_name is not None:
			# Use global app_name if set
			_current_app = Logger._global_app_name
		else:
			# Fall back to instance app_name
			_current_app = logger.app_name_upper

		try:
			del kwargs["suppress"]
		except: pass

		# Build message with optional app_name
		app_name_part = f" - [{_current_app}]" if _current_app is not None else " - "
		message_enclose = timestamp + app_name_part + f" [{owner}]" + ' ' + ' '.join(
			[f'[{str(item).upper()}]' for item in [*logger.kwargs.values()]]) + ' '.join(
			[f'[{str(item).upper()}]' for item in [*kwargs.values()]]) + f" [{level}]"

		content = f"\n{message_enclose.replace('  ', ' ')}: {str(message)}"

		if logger.path is not None:
			with open(generate_log_path(), 'a+') as f:
				f.write(str(content))

		if level == 'INFO' or level == 'START':
			correspondent_clr = UnicodeColors.success_cyan
		elif level == 'WARNING' or level == 'ALERT':
			correspondent_clr = UnicodeColors.alert
		elif level == 'SUCCESS' or level == 'OK':
			correspondent_clr = UnicodeColors.success
		elif level in ['CRITICAL', 'ERROR', 'FAULT', 'FAIL', 'FATAL']:
			correspondent_clr = UnicodeColors.fail
		elif level == 'TEST-RESULT' or level == 'TEST':
			correspondent_clr = UnicodeColors.bright_blue

		if not supress or debug or self_debug:
			print(correspondent_clr, content[1:], UnicodeColors.reset)
			if clean:
				logger.clean = True

		return content

	def log(self, level: Level, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""
		Log a message with the specified level.

		This is the main logging method that accepts any valid log level.
		The actual logging is performed asynchronously in a separate thread.

		Parameters
		----------
		level : Level
			The log level. Must be one of: INFO, START, WARNING, ALERT,
			SUCCESS, OK, CRITICAL, ERROR, FAULT, FAIL, FATAL, TEST-RESULT, TEST.
		message : str
			The message to log.
		app_name : str, optional
			Override the default app name for this message.
		clean : bool, optional
			Clear the screen after logging. Default is False.
		supress : bool, optional
			Suppress terminal output (still writes to file). Default is False.
		debug : bool, optional
			Force output even if suppressed. Default is True.
		**kwargs
			Additional tags to include in the log message.

		Returns
		-------
		bool
			Always returns True indicating the log was queued.

		Examples
		--------
		>>> logger = Logger("MyApp", "main")
		>>> logger.log("INFO", "Server started on port 8080")
		>>> logger.log("ERROR", "Connection failed", retry_count="3")
		"""
		thread = threading.Thread(target=self._subprocess_log, kwargs={
			"logger": self, "level": level, "message": message, "app_name": app_name, "clean": clean, "suppress": supress, "debug": debug, "self_debug": self.debug, **kwargs
		})
		thread.start()

		return True

	def __call__(self, *args, **kwargs):
		"""Allow the logger instance to be called directly like a function."""
		self.log(*args, **kwargs)

	def info(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log an informational message (cyan color)."""
		return self.log("INFO", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def start(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a start/initialization message (cyan color)."""
		return self.log("START", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def warning(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a warning message (yellow color)."""
		return self.log("WARNING", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def alert(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log an alert message (yellow color)."""
		return self.log("ALERT", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def success(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a success message (green color)."""
		return self.log("SUCCESS", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def ok(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log an OK/confirmation message (green color)."""
		return self.log("OK", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def critical(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a critical error message (red color)."""
		return self.log("CRITICAL", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def error(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log an error message (red color)."""
		return self.log("ERROR", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def fault(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a fault message (red color)."""
		return self.log("FAULT", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def fail(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a failure message (red color)."""
		return self.log("FAIL", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def fatal(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a fatal error message (red color)."""
		return self.log("FATAL", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def test_result(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a test result message (blue color)."""
		return self.log("TEST-RESULT", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

	def test(self, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""Log a test message (blue color)."""
		return self.log("TEST", message, app_name=app_name, clean=clean, supress=supress, debug=debug, **kwargs)

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
