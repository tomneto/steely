"""
Curl Recorder Module - FastAPI Request Recording to Curl Commands
==================================================================

This module provides a decorator for recording FastAPI endpoint requests as
executable curl commands. Useful for:
- API testing and debugging
- Creating reproducible test scripts
- Documenting API calls
- Sharing API examples with team members

Features
--------
- Automatic curl command generation from FastAPI requests
- Support for both sync and async endpoints
- Executable shell script output
- Request-only capture (no response interpretation)
- Pre-execution recording for reliability

Examples
--------
Basic usage:

>>> from steely.fastapi import recorder
>>> from fastapi import FastAPI
>>>
>>> app = FastAPI()
>>>
>>> @app.get("/users/{user_id}")
>>> @recorder.curl()
>>> async def get_user(user_id: int):
>>>     return {"user_id": user_id, "name": "John"}

The decorator will create/update a curl script at:
./.curl_scripts/<function_name>.sh
"""

import asyncio
import inspect
import json
import os
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from fastapi import Request

__all__ = ["curl", "CurlRecorder"]


class CurlRecorder:
    """
    Handles recording and storage of API requests as curl commands.

    This class manages the creation and updating of executable shell scripts
    containing curl commands, organizing requests by endpoint.

    Parameters
    ----------
    script_name : str
        Name of the curl script file (typically the function name)
    output_dir : str, optional
        Directory to store script files. Default is './.curl_scripts'
    group_mode : bool, optional
        If True, appends commands to a single file. If False, replaces.
        Default is True.

    Attributes
    ----------
    script_name : str
        The name of the script
    output_dir : str
        Directory path for storing scripts
    script_path : str
        Full path to the script file
    group_mode : bool
        Whether to group multiple commands in one file
    """

    def __init__(
        self,
        script_name: str,
        output_dir: str = "./.curl_scripts",
        group_mode: bool = True
    ):
        self.script_name = script_name
        self.output_dir = output_dir
        self.script_path = os.path.join(output_dir, f"{script_name}.sh")
        self.group_mode = group_mode

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Initialize script file if it doesn't exist or not in group mode
        if not group_mode or not os.path.exists(self.script_path):
            self._init_script()

    def _init_script(self):
        """Initialize a new script file with header."""
        with open(self.script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Auto-generated curl commands for {self.script_name}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("#\n")
            f.write("# Usage: bash {}\n".format(os.path.basename(self.script_path)))
            f.write("#\n\n")

        # Make script executable
        os.chmod(self.script_path, 0o755)

    def _format_curl_command(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Any],
        comment: Optional[str] = None
    ) -> str:
        """
        Format a curl command from request data.

        Parameters
        ----------
        method : str
            HTTP method
        url : str
            Full request URL
        headers : dict
            Request headers
        body : any
            Request body
        comment : str, optional
            Comment to add above the command

        Returns
        -------
        str
            Formatted curl command
        """
        lines = []

        # Add comment if provided
        if comment:
            lines.append(f"# {comment}")

        # Start curl command
        cmd_parts = ["curl"]

        # Add method if not GET
        if method.upper() != "GET":
            cmd_parts.append(f"-X {method.upper()}")

        # Add URL (quoted)
        cmd_parts.append(f'"{url}"')

        # Add headers (filter out some common ones)
        skip_headers = {'host', 'content-length', 'connection', 'accept-encoding'}
        for key, value in headers.items():
            if key.lower() not in skip_headers:
                # Escape quotes in header values
                safe_value = value.replace('"', '\\"')
                cmd_parts.append(f'-H "{key}: {safe_value}"')

        # Add body if present
        if body is not None:
            if isinstance(body, (dict, list)):
                # JSON body
                json_str = json.dumps(body)
                # Escape single quotes for shell
                safe_json = json_str.replace("'", "'\\''")
                cmd_parts.append(f"-d '{safe_json}'")
            else:
                # Plain text body
                safe_body = str(body).replace("'", "'\\''")
                cmd_parts.append(f"-d '{safe_body}'")

        # Join with line continuations for readability
        if len(cmd_parts) <= 3:
            # Short command, single line
            lines.append(" ".join(cmd_parts))
        else:
            # Multi-line with continuations
            lines.append(cmd_parts[0] + " \\")
            for part in cmd_parts[1:-1]:
                lines.append(f"  {part} \\")
            lines.append(f"  {cmd_parts[-1]}")

        return "\n".join(lines)

    def record_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Any],
        path: str,
        query_string: str = ""
    ):
        """
        Record a request as a curl command.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, etc.)
        url : str
            Full request URL
        headers : dict
            Request headers
        body : any
            Request body
        path : str
            Endpoint path pattern
        query_string : str, optional
            Query string for context
        """
        # Generate comment
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        comment = f"{method} {path}"
        if query_string:
            comment += f" - {timestamp}"
        else:
            comment += f" - {timestamp}"

        # Format curl command
        curl_cmd = self._format_curl_command(method, url, headers, body, comment)

        # Append to script file
        with open(self.script_path, 'a') as f:
            f.write("\n")
            f.write(curl_cmd)
            f.write("\n")

    def get_script_path(self) -> str:
        """
        Get the path to the generated script.

        Returns
        -------
        str
            Absolute path to the script file
        """
        return os.path.abspath(self.script_path)


def curl(
    output_dir: str = "./.curl_scripts",
    script_name: Optional[str] = None,
    group_mode: bool = True
):
    """
    Decorator that records FastAPI endpoint requests as curl commands.

    This decorator intercepts FastAPI endpoint calls and generates executable
    curl commands that can be used to reproduce the requests. Commands are
    saved to shell script files.

    Parameters
    ----------
    output_dir : str, optional
        Directory to store curl script files. Default is './.curl_scripts'
    script_name : str, optional
        Custom name for the script. If not provided, uses the function name.
    group_mode : bool, optional
        If True, appends multiple requests to the same file.
        If False, replaces the file each time. Default is True.

    Returns
    -------
    callable
        The decorated function with automatic curl command recording.

    Examples
    --------
    Basic usage:

    >>> from steely.fastapi import recorder
    >>> from fastapi import FastAPI
    >>>
    >>> app = FastAPI()
    >>>
    >>> @app.get("/users/{user_id}")
    >>> @recorder.curl()
    >>> async def get_user(user_id: int):
    >>>     return {"user_id": user_id, "name": "John"}

    With custom script name:

    >>> @app.post("/users")
    >>> @recorder.curl(script_name="user_api")
    >>> async def create_user(name: str):
    >>>     return {"name": name, "id": 123}

    Multiple endpoints in one script:

    >>> @app.get("/users")
    >>> @recorder.curl(script_name="user_api")
    >>> async def list_users():
    >>>     return [{"id": 1, "name": "John"}]
    >>>
    >>> @app.post("/users")
    >>> @recorder.curl(script_name="user_api")
    >>> async def create_user(name: str):
    >>>     return {"name": name, "id": 123}

    Notes
    -----
    - The decorator requires the FastAPI Request object to be injected.
    - Scripts are automatically created/updated in the specified output directory.
    - Generated scripts are executable (chmod +x applied automatically).
    - Recording happens BEFORE endpoint execution (pre-execution recording).
    - Works with both sync and async FastAPI endpoints.
    """
    def decorator(func):
        # Determine script name
        scr_name = script_name if script_name else func.__name__
        recorder = CurlRecorder(scr_name, output_dir, group_mode)

        # Get the function signature to check if Request is already a parameter
        sig = inspect.signature(func)
        has_request_param = any(
            param.annotation == Request or param.name == "request"
            for param in sig.parameters.values()
        )

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Extract or inject Request object
                request = kwargs.get('request')
                if request is None:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break

                if request is None:
                    # If Request is not found, just execute function
                    return await func(*args, **kwargs)

                # Capture request data
                method = request.method
                url = str(request.url)
                headers = dict(request.headers)
                path = request.url.path
                query_string = str(request.url.query) if request.url.query else ""

                # Try to get body
                body = None
                try:
                    content_type = headers.get('content-type', '')
                    if 'application/json' in content_type:
                        body = await request.json()
                    elif content_type and content_type != 'application/x-www-form-urlencoded':
                        body_bytes = await request.body()
                        body = body_bytes.decode('utf-8') if body_bytes else None
                except (ValueError, UnicodeDecodeError, RuntimeError):
                    # Body might be already consumed or invalid
                    pass

                # Record curl command BEFORE execution
                recorder.record_request(
                    method=method,
                    url=url,
                    headers=headers,
                    body=body,
                    path=path,
                    query_string=query_string
                )

                # Remove request from kwargs if it wasn't in the original signature
                func_kwargs = kwargs.copy()
                if not has_request_param and 'request' in func_kwargs:
                    func_kwargs.pop('request')

                # Execute the actual function
                response = await func(*args, **func_kwargs)

                return response

            # Preserve signature but inject Request if not present
            if not has_request_param:
                params = list(sig.parameters.values())
                params.append(inspect.Parameter('request', inspect.Parameter.KEYWORD_ONLY, annotation=Request))
                async_wrapper.__signature__ = sig.replace(parameters=params)
            else:
                async_wrapper.__signature__ = sig

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Extract Request object
                request = kwargs.get('request')
                if request is None:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break

                if request is None:
                    return func(*args, **kwargs)

                # Capture request data
                method = request.method
                url = str(request.url)
                headers = dict(request.headers)
                path = request.url.path
                query_string = str(request.url.query) if request.url.query else ""

                # Try to get body (sync version - limited support)
                body = None
                try:
                    content_type = headers.get('content-type', '')
                    if 'application/json' in content_type:
                        # For sync, body reading is limited
                        pass
                except (ValueError, UnicodeDecodeError, RuntimeError):
                    pass

                # Record curl command BEFORE execution
                recorder.record_request(
                    method=method,
                    url=url,
                    headers=headers,
                    body=body,
                    path=path,
                    query_string=query_string
                )

                # Remove request from kwargs if it wasn't in the original signature
                func_kwargs = kwargs.copy()
                if not has_request_param and 'request' in func_kwargs:
                    func_kwargs.pop('request')

                # Execute function
                response = func(*args, **func_kwargs)

                return response

            # Preserve signature but inject Request if not present
            if not has_request_param:
                params = list(sig.parameters.values())
                params.append(inspect.Parameter('request', inspect.Parameter.KEYWORD_ONLY, annotation=Request))
                sync_wrapper.__signature__ = sig.replace(parameters=params)
            else:
                sync_wrapper.__signature__ = sig

            return sync_wrapper

    return decorator
