"""
Example: intercept stdlib logging from third-party libs (uvicorn, httpx, …)
with Steely's Logger.

Run:  python examples/stdlib_intercept.py
"""

import logging

from steely.logger import Logger

# 1. Set a global app name (required — or pass app_name= directly below)
Logger.set_global_app_name("MyAPI")

# 2. Intercept — catch everything via root logger
Logger.intercept_stdlib()

# 3. Now every stdlib log from any library is formatted by Steely
logging.getLogger("uvicorn").info("Server started on port 8000")
logging.getLogger("uvicorn.access").warning("Slow request detected")
logging.getLogger("sqlalchemy.engine").error("Connection pool exhausted")

# 4. Filtering by level still works via Logger.getLogger
Logger.getLogger("uvicorn.access").setLevel("ERROR")
logging.getLogger("uvicorn.access").warning("This will be suppressed (setLevel)")

# 5. Exceptions are captured with full traceback
try:
    1 / 0
except ZeroDivisionError:
    logging.getLogger("app").error("Division failed", exc_info=True)

# 6. Owner is inferred dynamically; context tags (file/line/func) are added
logging.getLogger("mymodule.custom").info("Check the tags — file, line and func appear")
