"""
Performance comparison test between Python's built-in logging and steely Logger.

This test compares the execution speed of logging operations between:
1. Python's standard logging module
2. Steely's custom Logger class

The test measures:
- Single log message execution time
- Batch logging operations (1000, 10000, and 100000 messages)
- File size overhead
- Throughput (messages per second)

Expected Results:
-----------------
Python's built-in logging is significantly faster than steely Logger because:
1. Python logging is synchronous and writes directly to files
2. Steely Logger uses threading for each log message, adding overhead
3. Steely Logger has additional formatting and color processing

However, Steely Logger provides benefits in production scenarios:
- Non-blocking logging that doesn't slow down the main application
- Beautiful color-coded terminal output for better readability
- Thread-safe asynchronous logging
- Rich metadata and tagging support

Use Cases:
----------
- Use Python logging for: High-throughput applications, batch processing
- Use Steely Logger for: Development, debugging, real-time monitoring, user-facing applications
"""

import logging
import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from io import StringIO

from steely.logger import Logger


@contextmanager
def temporary_directory():
    """Create a temporary directory and clean it up afterwards."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def setup_python_logger(log_path: str) -> logging.Logger:
    """
    Set up Python's built-in logger with file handler.

    Parameters
    ----------
    log_path : str
        Path to the log file.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    logger = logging.getLogger('test_logger')
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # Create file handler
    handler = logging.FileHandler(log_path)
    handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - [%(name)s] [%(levelname)s]: %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger


def benchmark_python_logger(num_messages: int, log_path: str) -> float:
    """
    Benchmark Python's built-in logger.

    Parameters
    ----------
    num_messages : int
        Number of messages to log.
    log_path : str
        Path to the log file.

    Returns
    -------
    float
        Time taken in seconds.
    """
    logger = setup_python_logger(log_path)

    start_time = time.perf_counter()

    for i in range(num_messages):
        logger.info(f"Test message {i}")

    # Wait for handlers to flush
    for handler in logger.handlers:
        handler.flush()

    end_time = time.perf_counter()

    return end_time - start_time


def benchmark_steely_logger(num_messages: int, log_path: str) -> float:
    """
    Benchmark steely Logger.

    Parameters
    ----------
    num_messages : int
        Number of messages to log.
    log_path : str
        Path to the log directory.

    Returns
    -------
    float
        Time taken in seconds.
    """
    logger = Logger("TestOwner", "TestApp", destination=log_path, debug=False)

    # Suppress stdout to prevent console output from affecting benchmarks
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    start_time = time.perf_counter()

    for i in range(num_messages):
        logger.info(f"Test message {i}", supress=True, debug=False)

    # Wait for threads to complete
    # Give extra time for threading operations
    time.sleep(0.5)

    end_time = time.perf_counter()

    # Restore stdout
    sys.stdout = old_stdout

    return end_time - start_time


def test_single_message_performance():
    """Test performance of a single log message."""
    print("\n" + "=" * 80)
    print("TEST: Single Message Performance")
    print("=" * 80)

    with temporary_directory() as temp_dir:
        # Python logger
        python_log_file = os.path.join(temp_dir, "python_single.log")
        python_time = benchmark_python_logger(1, python_log_file)

        # Steely logger
        steely_log_dir = os.path.join(temp_dir, "steely_single")
        steely_time = benchmark_steely_logger(1, steely_log_dir)

        print(f"\nPython logging: {python_time * 1000:.4f} ms")
        print(f"Steely Logger:  {steely_time * 1000:.4f} ms")

        if python_time < steely_time:
            diff_percent = ((steely_time - python_time) / python_time) * 100
            print(f"\nPython is faster by {diff_percent:.2f}%")
        else:
            diff_percent = ((python_time - steely_time) / steely_time) * 100
            print(f"\nSteely is faster by {diff_percent:.2f}%")


def test_batch_performance_1000():
    """Test performance with 1000 messages."""
    print("\n" + "=" * 80)
    print("TEST: Batch Performance (1,000 messages)")
    print("=" * 80)

    num_messages = 1000

    with temporary_directory() as temp_dir:
        # Python logger
        python_log_file = os.path.join(temp_dir, "python_1000.log")
        python_time = benchmark_python_logger(num_messages, python_log_file)
        python_throughput = num_messages / python_time

        # Steely logger
        steely_log_dir = os.path.join(temp_dir, "steely_1000")
        steely_time = benchmark_steely_logger(num_messages, steely_log_dir)
        steely_throughput = num_messages / steely_time

        print(f"\nPython logging: {python_time:.4f} seconds ({python_throughput:.0f} msg/s)")
        print(f"Steely Logger:  {steely_time:.4f} seconds ({steely_throughput:.0f} msg/s)")

        if python_time < steely_time:
            diff_percent = ((steely_time - python_time) / python_time) * 100
            print(f"\nPython is faster by {diff_percent:.2f}%")
        else:
            diff_percent = ((python_time - steely_time) / steely_time) * 100
            print(f"\nSteely is faster by {diff_percent:.2f}%")


def test_batch_performance_10000():
    """Test performance with 10,000 messages."""
    print("\n" + "=" * 80)
    print("TEST: Batch Performance (10,000 messages)")
    print("=" * 80)

    num_messages = 10000

    with temporary_directory() as temp_dir:
        # Python logger
        python_log_file = os.path.join(temp_dir, "python_10000.log")
        python_time = benchmark_python_logger(num_messages, python_log_file)
        python_throughput = num_messages / python_time

        # Steely logger
        steely_log_dir = os.path.join(temp_dir, "steely_10000")
        steely_time = benchmark_steely_logger(num_messages, steely_log_dir)
        steely_throughput = num_messages / steely_time

        print(f"\nPython logging: {python_time:.4f} seconds ({python_throughput:.0f} msg/s)")
        print(f"Steely Logger:  {steely_time:.4f} seconds ({steely_throughput:.0f} msg/s)")

        if python_time < steely_time:
            diff_percent = ((steely_time - python_time) / python_time) * 100
            print(f"\nPython is faster by {diff_percent:.2f}%")
        else:
            diff_percent = ((python_time - steely_time) / steely_time) * 100
            print(f"\nSteely is faster by {diff_percent:.2f}%")


def test_batch_performance_100000():
    """Test performance with 100,000 messages."""
    print("\n" + "=" * 80)
    print("TEST: Batch Performance (100,000 messages)")
    print("=" * 80)

    num_messages = 100000

    with temporary_directory() as temp_dir:
        # Python logger
        python_log_file = os.path.join(temp_dir, "python_100000.log")
        python_time = benchmark_python_logger(num_messages, python_log_file)
        python_throughput = num_messages / python_time

        # Steely logger
        steely_log_dir = os.path.join(temp_dir, "steely_100000")
        steely_time = benchmark_steely_logger(num_messages, steely_log_dir)
        steely_throughput = num_messages / steely_time

        print(f"\nPython logging: {python_time:.4f} seconds ({python_throughput:.0f} msg/s)")
        print(f"Steely Logger:  {steely_time:.4f} seconds ({steely_throughput:.0f} msg/s)")

        if python_time < steely_time:
            diff_percent = ((steely_time - python_time) / python_time) * 100
            print(f"\nPython is faster by {diff_percent:.2f}%")
        else:
            diff_percent = ((python_time - steely_time) / steely_time) * 100
            print(f"\nSteely is faster by {diff_percent:.2f}%")


def test_console_output_performance():
    """Test performance with console output enabled."""
    print("\n" + "=" * 80)
    print("TEST: Console Output Performance (1,000 messages)")
    print("=" * 80)

    num_messages = 1000

    with temporary_directory() as temp_dir:
        # Python logger with console output
        python_log_file = os.path.join(temp_dir, "python_console.log")
        logger = setup_python_logger(python_log_file)

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

        start_time = time.perf_counter()
        for i in range(num_messages):
            logger.info(f"Test message {i}")
        for handler in logger.handlers:
            handler.flush()
        python_time = time.perf_counter() - start_time

        # Steely logger with console output (debug=True)
        steely_log_dir = os.path.join(temp_dir, "steely_console")
        logger_steely = Logger("TestOwner", "TestApp", destination=steely_log_dir, debug=True)

        start_time = time.perf_counter()
        for i in range(num_messages):
            logger_steely.info(f"Test message {i}")
        time.sleep(0.5)  # Wait for threads
        steely_time = time.perf_counter() - start_time

        print(f"\nPython logging (with console): {python_time:.4f} seconds")
        print(f"Steely Logger (with console):  {steely_time:.4f} seconds")

        if python_time < steely_time:
            diff_percent = ((steely_time - python_time) / python_time) * 100
            print(f"\nPython is faster by {diff_percent:.2f}%")
        else:
            diff_percent = ((python_time - steely_time) / steely_time) * 100
            print(f"\nSteely is faster by {diff_percent:.2f}%")


def test_file_size_comparison():
    """Compare the file sizes generated by both loggers."""
    print("\n" + "=" * 80)
    print("TEST: Log File Size Comparison (10,000 messages)")
    print("=" * 80)

    num_messages = 10000

    with temporary_directory() as temp_dir:
        # Python logger
        python_log_file = os.path.join(temp_dir, "python_size.log")
        benchmark_python_logger(num_messages, python_log_file)
        python_size = os.path.getsize(python_log_file)

        # Steely logger
        steely_log_dir = os.path.join(temp_dir, "steely_size")
        benchmark_steely_logger(num_messages, steely_log_dir)

        # Find the steely log file
        steely_files = os.listdir(steely_log_dir)
        steely_log_file = os.path.join(steely_log_dir, steely_files[0])
        steely_size = os.path.getsize(steely_log_file)

        print(f"\nPython log file size: {python_size:,} bytes ({python_size / 1024:.2f} KB)")
        print(f"Steely log file size: {steely_size:,} bytes ({steely_size / 1024:.2f} KB)")

        if python_size < steely_size:
            diff_percent = ((steely_size - python_size) / python_size) * 100
            print(f"\nSteely files are larger by {diff_percent:.2f}%")
        else:
            diff_percent = ((python_size - steely_size) / steely_size) * 100
            print(f"\nPython files are larger by {diff_percent:.2f}%")


def run_all_benchmarks():
    """Run all performance benchmarks."""
    print("\n" + "=" * 80)
    print("STEELY LOGGER vs PYTHON LOGGING - PERFORMANCE COMPARISON")
    print("=" * 80)

    test_single_message_performance()
    test_batch_performance_1000()
    test_batch_performance_10000()
    test_batch_performance_100000()
    test_file_size_comparison()

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_all_benchmarks()
