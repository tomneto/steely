import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import threading
import time

from steely.logger import Logger
from steely.design import UnicodeColors


class TestLoggerInit:
    """Tests for Logger initialization."""

    def test_logger_basic_init(self):
        """Test basic Logger initialization."""
        logger = Logger("test-owner", "test-app")

        assert logger.app_name_upper == "TEST-APP"
        assert logger.owner == "test-owner"
        assert logger.debug is True
        assert logger.path is None

    def test_logger_with_none_app_name(self):
        """Test Logger with None app_name is None."""
        logger = Logger("owner")

        assert logger.app_name_upper is None

    def test_logger_with_destination(self):
        """Test Logger with custom destination path."""
        logger = Logger("owner", "app", destination="/tmp/logs")

        assert logger.path == "/tmp/logs"

    def test_logger_debug_false(self):
        """Test Logger with debug=False."""
        logger = Logger("owner", "app", debug=False)

        assert logger.debug is False
        assert logger.environment is None

    def test_logger_debug_true_sets_environment(self):
        """Test Logger with debug=True sets environment."""
        logger = Logger("owner", "app", debug=True)

        assert logger.debug is True
        assert logger.environment == "debug"

    def test_logger_clean_flag(self):
        """Test Logger with clean=True sets master_clean."""
        logger = Logger("owner", "app", clean=True)

        assert logger.master_clean is True

    def test_logger_kwargs_stored(self):
        """Test Logger stores additional kwargs."""
        logger = Logger("owner", "app", custom_key="value", another="param")

        assert logger.kwargs == {"custom_key": "value", "another": "param"}

    def test_logger_app_name_converted_to_uppercase(self):
        """Test Logger converts app_name to uppercase."""
        logger = Logger("owner", "my-app")

        assert logger.app_name_upper == "MY-APP"


class TestLoggerLog:
    """Tests for Logger.log method."""

    def test_log_returns_true(self):
        """Test that log method returns True."""
        logger = Logger("owner", "app")

        result = logger.log("INFO", "Test message")

        assert result is True

    def test_log_spawns_thread(self):
        """Test that log method spawns a thread."""
        logger = Logger("owner", "app")

        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            logger.log("INFO", "Test message")

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_log_passes_correct_kwargs_to_thread(self):
        """Test that log passes correct kwargs to subprocess_log."""
        logger = Logger("owner", "app")

        with patch('threading.Thread') as mock_thread:
            logger.log("WARNING", "Warning message", app_name="custom-app", clean=True)

            call_kwargs = mock_thread.call_args[1]['kwargs']
            assert call_kwargs['level'] == "WARNING"
            assert call_kwargs['message'] == "Warning message"
            assert call_kwargs['app_name'] == "custom-app"
            assert call_kwargs['clean'] is True


class TestLoggerSubprocessLog:
    """Tests for Logger._subprocess_log static method."""

    def test_subprocess_log_info_level(self, capsys):
        """Test subprocess_log with INFO level."""
        logger = Logger("owner", "app")

        content = Logger._subprocess_log(
            logger, "INFO", "Info message", supress=False, debug=True
        )

        assert "[APP]" in content
        assert "[OWNER]" in content
        assert "[INFO]" in content
        assert "Info message" in content

    def test_subprocess_log_warning_level(self, capsys):
        """Test subprocess_log with WARNING level."""
        logger = Logger("owner", "app")

        content = Logger._subprocess_log(
            logger, "WARNING", "Warning message", supress=False, debug=True
        )

        assert "[WARNING]" in content
        assert "Warning message" in content

    def test_subprocess_log_error_level(self, capsys):
        """Test subprocess_log with ERROR level."""
        logger = Logger("owner", "app")

        content = Logger._subprocess_log(
            logger, "ERROR", "Error message", supress=False, debug=True
        )

        assert "[ERROR]" in content
        assert "Error message" in content

    def test_subprocess_log_custom_app_name(self, capsys):
        """Test subprocess_log with custom app_name."""
        logger = Logger("owner", "original-app")

        content = Logger._subprocess_log(
            logger, "INFO", "Message", app_name="custom-app", supress=False, debug=True
        )

        assert "[CUSTOM-APP]" in content

    def test_subprocess_log_level_uppercase(self, capsys):
        """Test subprocess_log converts level to uppercase."""
        logger = Logger("owner", "app")

        content = Logger._subprocess_log(
            logger, "info", "Message", supress=False, debug=True
        )

        assert "[INFO]" in content

    def test_subprocess_log_with_extra_kwargs(self, capsys):
        """Test subprocess_log includes extra kwargs in message."""
        logger = Logger("owner", "app", tag="mytag")

        content = Logger._subprocess_log(
            logger, "INFO", "Message", supress=False, debug=True, extra="value"
        )

        assert "[MYTAG]" in content
        assert "[VALUE]" in content

    def test_subprocess_log_writes_to_file(self):
        """Test subprocess_log writes to log file when path is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger("owner", "app", destination=tmpdir, debug=False)

            Logger._subprocess_log(
                logger, "INFO", "File log message", supress=False, debug=True
            )

            log_files = os.listdir(tmpdir)
            assert len(log_files) == 1
            assert log_files[0].endswith(".log")

            with open(os.path.join(tmpdir, log_files[0]), 'r') as f:
                content = f.read()
                assert "File log message" in content

    def test_subprocess_log_with_debug_environment(self):
        """Test subprocess_log creates debug directory when environment is debug."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger("owner", "app", destination=tmpdir, debug=True)

            Logger._subprocess_log(
                logger, "INFO", "Debug message", supress=False, debug=True
            )

            expected_dir = f"{tmpdir}_debug"
            assert os.path.exists(expected_dir)

            # Cleanup
            import shutil
            shutil.rmtree(expected_dir, ignore_errors=True)

    def test_subprocess_log_timestamp_format(self, capsys):
        """Test subprocess_log includes properly formatted timestamp."""
        logger = Logger("owner", "app")

        content = Logger._subprocess_log(
            logger, "INFO", "Message", supress=False, debug=True
        )

        # Check timestamp format (DD-MM-YYYY HH:MM:SS)
        import re
        timestamp_pattern = r'\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, content) is not None


class TestLoggerCallable:
    """Tests for Logger __call__ method."""

    def test_logger_callable(self):
        """Test that Logger instance is callable."""
        logger = Logger("owner", "app")

        with patch.object(logger, 'log') as mock_log:
            logger("INFO", "Callable message")

            mock_log.assert_called_once_with("INFO", "Callable message")

    def test_logger_callable_with_kwargs(self):
        """Test Logger callable with kwargs."""
        logger = Logger("owner", "app")

        with patch.object(logger, 'log') as mock_log:
            logger("ERROR", "Error", app_name="test", clean=True)

            mock_log.assert_called_once_with("ERROR", "Error", app_name="test", clean=True)


class TestLoggerLevelColors:
    """Tests for Logger level color mapping."""

    @pytest.mark.parametrize("level,expected_color", [
        ("INFO", UnicodeColors.success_cyan),
        ("START", UnicodeColors.success_cyan),
        ("WARNING", UnicodeColors.alert),
        ("ALERT", UnicodeColors.alert),
        ("SUCCESS", UnicodeColors.success),
        ("OK", UnicodeColors.success),
        ("CRITICAL", UnicodeColors.fail),
        ("ERROR", UnicodeColors.fail),
        ("FAULT", UnicodeColors.fail),
        ("FAIL", UnicodeColors.fail),
        ("FATAL", UnicodeColors.fail),
        ("TEST-RESULT", UnicodeColors.bright_blue),
        ("TEST", UnicodeColors.bright_blue),
    ])
    def test_level_colors(self, level, expected_color, capsys):
        """Test that different levels use correct colors."""
        logger = Logger("owner", "app")

        Logger._subprocess_log(
            logger, level, "Message", supress=False, debug=True
        )

        captured = capsys.readouterr()
        assert expected_color in captured.out


class TestLoggerCleanFlag:
    """Tests for Logger clean screen functionality."""

    def test_clean_flag_triggers_clear(self):
        """Test that clean flag triggers screen clear."""
        logger = Logger("owner", "app")
        logger.clean = True

        with patch('os.system') as mock_system:
            Logger._subprocess_log(
                logger, "INFO", "Message", clean=False, supress=False, debug=True
            )

            mock_system.assert_called_once()

    def test_master_clean_keeps_clean_flag(self):
        """Test that master_clean keeps clean flag True."""
        logger = Logger("owner", "app", clean=True)
        logger.clean = True

        with patch('os.system'):
            Logger._subprocess_log(
                logger, "INFO", "Message", clean=False, supress=False, debug=True
            )

            # master_clean should keep clean True
            assert logger.master_clean is True


class TestRelativeFunction:
    """Tests for the relative helper function."""

    def test_relative_function(self):
        """Test relative function returns correct path."""
        from steely.logger import relative

        result = relative("test.txt")

        expected_dir = os.path.dirname(os.path.abspath(__file__).replace("test/test_logger.py", "steely/logger/__init__.py"))
        # Just verify it's constructing a path with the filename
        assert result.endswith("test.txt")


class TestLoggerSetAppName:
    """Tests for Logger.set_app_name instance method."""

    def test_logger_without_app_name_does_not_print_it(self, capsys):
        """Test that logger without app_name doesn't print app_name field."""
        logger = Logger("owner")

        Logger._subprocess_log(logger, "INFO", "Test message", supress=False, debug=True)

        captured = capsys.readouterr()
        # Should have owner but not app_name (no double dash pattern " - [")
        assert "[OWNER]" in captured.out
        assert " - [" not in captured.out

    def test_set_app_name_changes_app_name(self):
        """Test that set_app_name changes the app_name."""
        logger = Logger("owner", "OriginalApp")

        assert logger.app_name_upper == "ORIGINALAPP"

        logger.set_app_name("NewApp")

        assert logger.app_name_upper == "NEWAPP"

    def test_set_app_name_converts_to_uppercase(self):
        """Test that set_app_name converts to uppercase."""
        logger = Logger("owner", "app")

        logger.set_app_name("lowercase-app")

        assert logger.app_name_upper == "LOWERCASE-APP"

    def test_set_app_name_with_none(self):
        """Test that set_app_name with None sets app_name to None."""
        logger = Logger("owner", "app")

        logger.set_app_name(None)

        assert logger.app_name_upper is None

    def test_set_app_name_affects_subsequent_logs(self, capsys):
        """Test that set_app_name affects subsequent log messages."""
        logger = Logger("owner", "FirstApp")

        # Log with first app name
        Logger._subprocess_log(logger, "INFO", "First message", supress=False, debug=True)

        logger.set_app_name("SecondApp")

        # Log with second app name
        Logger._subprocess_log(logger, "INFO", "Second message", supress=False, debug=True)

        captured = capsys.readouterr()
        assert "[FIRSTAPP]" in captured.out
        assert "[SECONDAPP]" in captured.out

    def test_set_app_name_multiple_times(self):
        """Test setting app_name multiple times."""
        logger = Logger("owner", "App1")

        logger.set_app_name("App2")
        assert logger.app_name_upper == "APP2"

        logger.set_app_name("App3")
        assert logger.app_name_upper == "APP3"

        logger.set_app_name("App4")
        assert logger.app_name_upper == "APP4"

    def test_set_app_name_with_special_characters(self):
        """Test set_app_name with special characters."""
        logger = Logger("owner", "app")

        logger.set_app_name("my-app_v2.0")

        assert logger.app_name_upper == "MY-APP_V2.0"


class TestLoggerSetGlobalAppName:
    """Tests for Logger.set_global_app_name class method."""

    def setup_method(self):
        """Reset global app name before each test."""
        Logger._global_app_name = None

    def teardown_method(self):
        """Reset global app name after each test."""
        Logger._global_app_name = None

    def test_set_global_app_name_sets_class_variable(self):
        """Test that set_global_app_name sets the class variable."""
        Logger.set_global_app_name("GlobalApp")

        assert Logger._global_app_name == "GLOBALAPP"

    def test_set_global_app_name_converts_to_uppercase(self):
        """Test that set_global_app_name converts to uppercase."""
        Logger.set_global_app_name("lowercase-global")

        assert Logger._global_app_name == "LOWERCASE-GLOBAL"

    def test_set_global_app_name_with_none(self):
        """Test that set_global_app_name with None clears it."""
        Logger.set_global_app_name("GlobalApp")
        Logger.set_global_app_name(None)

        assert Logger._global_app_name is None

    def test_set_global_app_name_affects_all_instances(self):
        """Test that set_global_app_name is shared across all instances."""
        Logger.set_global_app_name("SharedApp")

        logger1 = Logger("owner1", "Local1")
        logger2 = Logger("owner2", "Local2")

        assert Logger._global_app_name == "SHAREDAPP"
        assert logger1._global_app_name == "SHAREDAPP"
        assert logger2._global_app_name == "SHAREDAPP"

    def test_set_global_app_name_multiple_times(self):
        """Test setting global app_name multiple times."""
        Logger.set_global_app_name("Global1")
        assert Logger._global_app_name == "GLOBAL1"

        Logger.set_global_app_name("Global2")
        assert Logger._global_app_name == "GLOBAL2"

        Logger.set_global_app_name("Global3")
        assert Logger._global_app_name == "GLOBAL3"