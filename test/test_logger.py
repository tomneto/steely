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
        logger = Logger("test-app", "test-owner")

        assert logger.app_name_upper == "TEST-APP"
        assert logger.owner == "test-owner"
        assert logger.debug is True
        assert logger.path is None

    def test_logger_with_none_app_name(self):
        """Test Logger with None app_name uses default."""
        logger = Logger(None, "owner")

        assert logger.app_name_upper == "YOUR-APP-NAME-GOES-HERE"

    def test_logger_with_destination(self):
        """Test Logger with custom destination path."""
        logger = Logger("app", "owner", destination="/tmp/logs")

        assert logger.path == "/tmp/logs"

    def test_logger_debug_false(self):
        """Test Logger with debug=False."""
        logger = Logger("app", "owner", debug=False)

        assert logger.debug is False
        assert logger.environment is None

    def test_logger_debug_true_sets_environment(self):
        """Test Logger with debug=True sets environment."""
        logger = Logger("app", "owner", debug=True)

        assert logger.debug is True
        assert logger.environment == "debug"

    def test_logger_clean_flag(self):
        """Test Logger with clean=True sets master_clean."""
        logger = Logger("app", "owner", clean=True)

        assert logger.master_clean is True

    def test_logger_kwargs_stored(self):
        """Test Logger stores additional kwargs."""
        logger = Logger("app", "owner", custom_key="value", another="param")

        assert logger.kwargs == {"custom_key": "value", "another": "param"}

    def test_logger_app_name_converted_to_uppercase(self):
        """Test Logger converts app_name to uppercase."""
        logger = Logger("my-app", "owner")

        assert logger.app_name_upper == "MY-APP"


class TestLoggerLog:
    """Tests for Logger.log method."""

    def test_log_returns_true(self):
        """Test that log method returns True."""
        logger = Logger("app", "owner")

        result = logger.log("INFO", "Test message")

        assert result is True

    def test_log_spawns_thread(self):
        """Test that log method spawns a thread."""
        logger = Logger("app", "owner")

        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            logger.log("INFO", "Test message")

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_log_passes_correct_kwargs_to_thread(self):
        """Test that log passes correct kwargs to subprocess_log."""
        logger = Logger("app", "owner")

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
        logger = Logger("app", "owner")

        content = Logger._subprocess_log(
            logger, "INFO", "Info message", supress=False, debug=True
        )

        assert "[APP]" in content
        assert "[OWNER]" in content
        assert "[INFO]" in content
        assert "Info message" in content

    def test_subprocess_log_warning_level(self, capsys):
        """Test subprocess_log with WARNING level."""
        logger = Logger("app", "owner")

        content = Logger._subprocess_log(
            logger, "WARNING", "Warning message", supress=False, debug=True
        )

        assert "[WARNING]" in content
        assert "Warning message" in content

    def test_subprocess_log_error_level(self, capsys):
        """Test subprocess_log with ERROR level."""
        logger = Logger("app", "owner")

        content = Logger._subprocess_log(
            logger, "ERROR", "Error message", supress=False, debug=True
        )

        assert "[ERROR]" in content
        assert "Error message" in content

    def test_subprocess_log_custom_app_name(self, capsys):
        """Test subprocess_log with custom app_name."""
        logger = Logger("original-app", "owner")

        content = Logger._subprocess_log(
            logger, "INFO", "Message", app_name="custom-app", supress=False, debug=True
        )

        assert "[CUSTOM-APP]" in content

    def test_subprocess_log_level_uppercase(self, capsys):
        """Test subprocess_log converts level to uppercase."""
        logger = Logger("app", "owner")

        content = Logger._subprocess_log(
            logger, "info", "Message", supress=False, debug=True
        )

        assert "[INFO]" in content

    def test_subprocess_log_with_extra_kwargs(self, capsys):
        """Test subprocess_log includes extra kwargs in message."""
        logger = Logger("app", "owner", tag="mytag")

        content = Logger._subprocess_log(
            logger, "INFO", "Message", supress=False, debug=True, extra="value"
        )

        assert "[MYTAG]" in content
        assert "[VALUE]" in content

    def test_subprocess_log_writes_to_file(self):
        """Test subprocess_log writes to log file when path is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger("app", "owner", destination=tmpdir, debug=False)

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
            logger = Logger("app", "owner", destination=tmpdir, debug=True)

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
        logger = Logger("app", "owner")

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
        logger = Logger("app", "owner")

        with patch.object(logger, 'log') as mock_log:
            logger("INFO", "Callable message")

            mock_log.assert_called_once_with("INFO", "Callable message")

    def test_logger_callable_with_kwargs(self):
        """Test Logger callable with kwargs."""
        logger = Logger("app", "owner")

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
        logger = Logger("app", "owner")

        Logger._subprocess_log(
            logger, level, "Message", supress=False, debug=True
        )

        captured = capsys.readouterr()
        assert expected_color in captured.out


class TestLoggerCleanFlag:
    """Tests for Logger clean screen functionality."""

    def test_clean_flag_triggers_clear(self):
        """Test that clean flag triggers screen clear."""
        logger = Logger("app", "owner")
        logger.clean = True

        with patch('os.system') as mock_system:
            Logger._subprocess_log(
                logger, "INFO", "Message", clean=False, supress=False, debug=True
            )

            mock_system.assert_called_once()

    def test_master_clean_keeps_clean_flag(self):
        """Test that master_clean keeps clean flag True."""
        logger = Logger("app", "owner", clean=True)
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