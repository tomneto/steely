import asyncio
import inspect
from datetime import datetime
from functools import wraps

from steely.logger import Logger


def cronos(func):
    log = Logger('*-cronos-*', func.__name__).log

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = datetime.now()
            try:
                res = await func(*args, **kwargs)
            finally:
                time_elapsed = datetime.now() - start
                log('TEST-RESULT', f'Total Time Elapsed: {time_elapsed}')
            return res

        # Preserve the original signature for FastAPI
        async_wrapper.__signature__ = inspect.signature(func)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):

            start = datetime.now()
            try:
                res = func(*args, **kwargs)
            finally:
                time_elapsed = datetime.now() - start
                log('TEST-RESULT', f'Total Time Elapsed: {time_elapsed}')
            return res

        # Preserve the original signature for FastAPI
        sync_wrapper.__signature__ = inspect.signature(func)
        return sync_wrapper
