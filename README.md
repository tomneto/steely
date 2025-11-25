# Steely

A Python debugging and analysis toolkit with beautiful, colorful terminal output.

Steely provides powerful decorators that help developers understand their code's behavior at runtime through automatic logging, execution timing, and real-time variable tracking.

## Features

- **Dan.log** - Automatic function logging with start/success/error tracking
- **Dan.cronos** - Execution time measurement and profiling
- **Dan.scan** - Real-time variable tracking with type-colored output
- **Logger** - Flexible, thread-safe logging with color-coded output and file support

## Installation

### Using pip

```bash
pip install steely
```

### Using uv

```bash
uv add steely
```

### From source

```bash
git clone https://github.com/your-username/steely.git
cd steely
pip install -e .
```

## Requirements

- Python 3.9 or higher
- No external dependencies

## Quick Start

```python
from steely import Dan

# Log function execution
@Dan.log
def fetch_data(url):
    return {"data": "example"}

# Measure execution time
@Dan.cronos
def slow_operation():
    import time
    time.sleep(1)
    return "done"

# Track variables in real-time
@Dan.scan
def calculate(a, b):
    total = a + b
    squared = total ** 2
    return squared

# Run the functions
fetch_data("https://api.example.com")
slow_operation()
calculate(3, 4)
```

## Decorators

### Dan.log

The `log` decorator automatically tracks function execution lifecycle - when it starts, succeeds, or fails.

```python
from steely import Dan

@Dan.log
def process_user(user_id):
    # Your code here
    return {"id": user_id, "status": "processed"}

process_user(123)
```

**Output:**
```
[PROCESS_USER] [START]: Function called
[PROCESS_USER] [SUCCESS]: Function completed
```

#### With async functions

```python
@Dan.log
async def fetch_api_data(endpoint):
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as response:
            return await response.json()
```

#### Error tracking

When an exception occurs, the decorator logs the error before re-raising it:

```python
@Dan.log
def risky_operation():
    raise ValueError("Something went wrong")

risky_operation()
# Output:
# [RISKY_OPERATION] [START]: Function called
# [RISKY_OPERATION] [ERROR]: Something went wrong
# Traceback...
```

---

### Dan.cronos

Named after the Greek god of time, `cronos` measures and reports function execution time.

```python
from steely import Dan
import time

@Dan.cronos
def compute_heavy_task(n):
    time.sleep(n)
    return sum(range(n * 1000000))

compute_heavy_task(2)
```

**Output:**
```
[*-CRONOS-*] [COMPUTE_HEAVY_TASK] [TEST-RESULT]: Total Time Elapsed: 0:00:02.001234
```

#### With async functions

```python
import asyncio

@Dan.cronos
async def async_task():
    await asyncio.sleep(0.5)
    return "completed"

asyncio.run(async_task())
# Output: Total Time Elapsed: 0:00:00.500xxx
```

---

### Dan.scan

The `scan` decorator provides real-time variable tracking with beautiful, type-colored output. It shows every variable assignment, its type, value, and the line number where it was set.

```python
from steely import Dan

@Dan.scan
def example(x, y):
    name = "Alice"
    numbers = [1, 2, 3]
    total = x + y
    data = {"key": "value"}
    return total

example(10, 20)
```

**Output:**
```
┌─────────────────────────────────────────────────────────────────────────────────────
│ ⚡ SCAN: example
│    module: __main__
├─────────────────────────────────────────────────────────────────────────────────────
│ Parameters:
│    ◈ x: int → 10
│    ◈ y: int → 20
├─────────────────────────────────────────────────────────────────────────────────────
│ Variables:
│    ▸ line 4   ◈ name     ◉ str  → 'Alice'
│    ▸ line 5   ◈ numbers  ◉ list → [1, 2, 3]
│    ▸ line 6   ◈ total    ◉ int  → 30
│    ▸ line 7   ◈ data     ◉ dict → {'key': 'value'}
├─────────────────────────────────────────────────────────────────────────────────────
│ ⟼ Return: int → 30
└───────────────────────────────────────────────────────────── elapsed: 0.12ms ──────
```

#### Type Colors

Each Python type is displayed in a distinct color for easy visual identification:

| Type | Color |
|------|-------|
| `int` | Blue |
| `float` | Deep Blue |
| `str` | Orange |
| `bool` | Magenta |
| `None` | Gray |
| `list` | Sea Green |
| `dict` | Gold |
| `tuple` | Light Purple |
| `set` | Pink |
| `callable` | Cyan |
| `class` | Lavender |

#### Async Functions

For async functions, variable tracking is disabled (due to event loop tracing limitations), but parameters and return values are still displayed:

```python
@Dan.scan
async def fetch_data(url):
    response = await some_api_call(url)
    return response

await fetch_data("https://api.example.com")
```

---

## Combining Decorators

You can stack multiple decorators to get combined functionality:

```python
from steely import Dan

@Dan.log
@Dan.cronos
@Dan.scan
def important_operation(data):
    processed = data.upper()
    result = len(processed)
    return result

important_operation("hello world")
```

This will:
1. Log the function start/success
2. Measure execution time
3. Track all variable assignments

---

## Logger

The `Logger` class provides a flexible, thread-safe logging system with color-coded terminal output and optional file logging.

### Basic Usage

```python
from steely.logger import Logger

# Create a logger instance
logger = Logger("MyApp", "database")

# Log messages with different levels
logger.info("Connected to database")
logger.success("Query executed successfully")
logger.warning("Connection pool running low")
logger.error("Query timeout after 30s")
```

**Output:**
```
25-11-2025 14:30:00 - [MYAPP] [DATABASE] [INFO]: Connected to database
25-11-2025 14:30:00 - [MYAPP] [DATABASE] [SUCCESS]: Query executed successfully
25-11-2025 14:30:01 - [MYAPP] [DATABASE] [WARNING]: Connection pool running low
25-11-2025 14:30:02 - [MYAPP] [DATABASE] [ERROR]: Query timeout after 30s
```

### Log Levels

| Level | Color | Method | Use Case |
|-------|-------|--------|----------|
| `INFO` | Cyan | `logger.info()` | General information |
| `START` | Cyan | `logger.start()` | Process initialization |
| `SUCCESS` | Green | `logger.success()` | Successful operations |
| `OK` | Green | `logger.ok()` | Confirmations |
| `WARNING` | Yellow | `logger.warning()` | Warning messages |
| `ALERT` | Yellow | `logger.alert()` | Alert notifications |
| `ERROR` | Red | `logger.error()` | Error messages |
| `CRITICAL` | Red | `logger.critical()` | Critical errors |
| `FATAL` | Red | `logger.fatal()` | Fatal errors |
| `FAIL` | Red | `logger.fail()` | Failed operations |
| `FAULT` | Red | `logger.fault()` | System faults |
| `TEST` | Blue | `logger.test()` | Test messages |
| `TEST-RESULT` | Blue | `logger.test_result()` | Test results |

### File Logging

Enable file logging by providing a destination directory:

```python
from steely.logger import Logger

# Logs will be saved to /var/log/myapp/DD-MM-YYYY.log
logger = Logger("MyApp", "api", destination="/var/log/myapp")

logger.info("Request received")      # Printed AND saved to file
logger.error("Request failed")       # Printed AND saved to file
```

Log files are automatically named with the current date (e.g., `25-11-2025.log`) and appended throughout the day.

### Additional Tags

Add custom tags to your log messages for better filtering:

```python
from steely.logger import Logger

# Tags defined at creation apply to all messages
logger = Logger("MyApp", "auth", session_id="abc123", user_id="42")

logger.info("User logged in")
# Output: [MYAPP] [AUTH] [ABC123] [42] [INFO]: User logged in

# Or add tags per-message
logger.info("Action performed", request_id="req-789")
# Output: [MYAPP] [AUTH] [ABC123] [42] [REQ-789] [INFO]: Action performed
```

### Using log() Method Directly

For dynamic log levels, use the `log()` method:

```python
from steely.logger import Logger

logger = Logger("MyApp", "main")

# Using log() with any level
logger.log("INFO", "Application started")
logger.log("SUCCESS", "Initialization complete")
logger.log("ERROR", "Connection failed")

# Logger instances are callable
logger("WARNING", "This also works!")
```

### Screen Clearing

Enable screen clearing for a cleaner terminal experience:

```python
from steely.logger import Logger

# Clear screen before each log message
logger = Logger("MyApp", "installer", clean=True)

logger.info("Step 1: Downloading...")  # Clears screen, then prints
logger.info("Step 2: Installing...")   # Clears screen, then prints
logger.success("Installation complete!")
```

### Debug Mode

Control debug output with the `debug` parameter:

```python
from steely.logger import Logger

# Debug mode enabled (default) - appends "_debug" to log directory
logger = Logger("MyApp", "main", destination="/logs", debug=True)
# Logs go to: /logs_debug/DD-MM-YYYY.log

# Production mode
logger = Logger("MyApp", "main", destination="/logs", debug=False)
# Logs go to: /logs/DD-MM-YYYY.log
```

### Thread Safety

All logging operations run in separate threads for non-blocking behavior:

```python
from steely.logger import Logger
import time

logger = Logger("MyApp", "worker")

def process_items(items):
    for item in items:
        logger.info(f"Processing {item}")  # Non-blocking
        # Heavy processing here...
        time.sleep(0.1)
    logger.success("All items processed")

# Logging won't slow down your processing
process_items(["item1", "item2", "item3"])
```

### Complete Example

```python
from steely.logger import Logger

class DatabaseService:
    def __init__(self):
        self.logger = Logger("MyApp", "database", destination="./logs")

    def connect(self, host, port):
        self.logger.start(f"Connecting to {host}:{port}")
        try:
            # Connection logic here...
            self.logger.success("Connected successfully")
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    def query(self, sql):
        self.logger.info(f"Executing query: {sql[:50]}...")
        try:
            # Query logic here...
            self.logger.success("Query executed")
            return {"rows": 42}
        except Exception as e:
            self.logger.error(f"Query failed: {e}")
            raise

# Usage
db = DatabaseService()
db.connect("localhost", 5432)
db.query("SELECT * FROM users WHERE active = true")
```

---

## Advanced Usage

### Using Individual Decorators

You can import decorators individually if you prefer:

```python
from steely import cronos, log, scan

@log
def my_function():
    pass

@cronos
def timed_function():
    pass

@scan
def tracked_function():
    pass
```

### Using Design Components

Steely's design module provides terminal styling utilities you can use in your own code:

```python
from steely.design import UnicodeColors as C, Symbols as S, TypeColors

# Colored output
print(f"{C.green}Success!{C.reset}")
print(f"{C.bold}{C.red}Error!{C.reset}")

# Symbols
print(f"{S.CHECK} Task completed")
print(f"{S.ARROW_RIGHT} Next step")
print(f"{S.CROSS} Failed")

# Type-based colors
value = [1, 2, 3]
color = TypeColors.get_color(value)
print(f"{color}{value}{C.reset}")
```

---

## Examples

### Web API Debugging

```python
from steely import Dan
import requests

@Dan.log
@Dan.cronos
def fetch_user(user_id):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

user = fetch_user(42)
```

### Algorithm Profiling

```python
from steely import Dan

@Dan.cronos
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

@Dan.cronos
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

import random
data = [random.randint(0, 1000) for _ in range(1000)]

bubble_sort(data.copy())  # See timing
quick_sort(data.copy())   # Compare timing
```

### Debugging Complex Logic

```python
from steely import Dan

@Dan.scan
def calculate_discount(price, quantity, member_status):
    subtotal = price * quantity

    if member_status == "gold":
        discount_rate = 0.20
    elif member_status == "silver":
        discount_rate = 0.10
    else:
        discount_rate = 0.0

    discount = subtotal * discount_rate
    final_price = subtotal - discount

    return final_price

calculate_discount(99.99, 3, "gold")
# See exactly how each variable is computed
```

---

## Framework Compatibility

All Steely decorators preserve the original function's signature, making them compatible with frameworks that rely on function introspection:

### FastAPI

```python
from fastapi import FastAPI
from steely import Dan

app = FastAPI()

@app.get("/users/{user_id}")
@Dan.log
@Dan.cronos
async def get_user(user_id: int, include_email: bool = False):
    return {"user_id": user_id, "include_email": include_email}
```

### Flask

```python
from flask import Flask
from steely import Dan

app = Flask(__name__)

@app.route("/hello/<name>")
@Dan.log
def hello(name):
    return f"Hello, {name}!"
```

---

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
