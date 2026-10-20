"""
Postman Recorder Module - FastAPI Request/Response Recording
============================================================

This module provides a decorator for recording FastAPI endpoint requests and
responses in Postman Collection v2.1 format. Useful for:
- API documentation generation
- Testing and debugging
- Creating Postman collections from live traffic

Features
--------
- Automatic request/response capture for FastAPI endpoints
- Support for both sync and async endpoints
- Postman Collection v2.1 format output
- JSON file storage with automatic collection updates

Examples
--------
Basic usage:

>>> from steely.fastapi import recorder
>>> from fastapi import FastAPI
>>>
>>> app = FastAPI()
>>>
>>> @app.get("/users/{user_id}")
>>> @postman
>>> async def get_user(user_id: int):
>>>     return {"user_id": user_id, "name": "John"}

The decorator will create/update a Postman collection file at:
./.postman_collections/<function_name>.json
"""

import asyncio
import inspect
import json
import os
from datetime import datetime
from functools import wraps
from typing import Any, Optional

from steely.fastapi.recorder._compat import require_request
from steely.fastapi.recorder._redact import redact_body as _redact_body
from steely.fastapi.recorder._redact import redact_headers

__all__ = ["postman", "PostmanRecorder"]


class PostmanRecorder:
    """
    Handles recording and storage of API requests/responses in Postman format.

    This class manages the creation and updating of Postman Collection v2.1
    JSON files, organizing requests by endpoint and automatically updating
    collections as new requests are captured.

    Parameters
    ----------
    collection_name : str
        Name of the Postman collection (typically the function name)
    output_dir : str, optional
        Directory to store collection files. Default is './.postman_collections'
    sensitive_headers : set of str, optional
        Header names to mask. Defaults to
        :data:`steely.fastapi.recorder._redact.SENSITIVE_HEADERS`.
    redact_headers : bool, optional
        Mask sensitive headers. Default is True.
    redact_body : bool, optional
        Mask sensitive keys in JSON bodies. Default is True.

    Attributes
    ----------
    collection_name : str
        The name of the collection
    output_dir : str
        Directory path for storing collections
    collection_path : str
        Full path to the collection JSON file
    """

    def __init__(
        self,
        collection_name: str,
        output_dir: str = "./.postman_collections",
        sensitive_headers: Optional[set[str]] = None,
        redact_headers: bool = True,
        redact_body: bool = True,
    ):
        self.collection_name = collection_name
        self.output_dir = output_dir
        self.collection_path = os.path.join(output_dir, f"{collection_name}.json")
        self.sensitive_headers = sensitive_headers
        self.redact_headers = redact_headers
        self.redact_body = redact_body

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Initialize or load existing collection
        self._init_collection()

    def _init_collection(self):
        """Initialize a new collection or load existing one."""
        if os.path.exists(self.collection_path):
            with open(self.collection_path) as f:
                self.collection = json.load(f)
        else:
            self.collection = {
                "info": {
                    "name": self.collection_name,
                    "description": f"Auto-generated collection for {self.collection_name}",
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                    "_postman_id": (
                        f"{self.collection_name}-"
                        f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    ),
                },
                "item": []
            }

    def _save_collection(self):
        """Save the collection to disk."""
        with open(self.collection_path, 'w') as f:
            json.dump(self.collection, f, indent=2)

    def record_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        query_params: dict[str, Any],
        body: Optional[Any],
        path: str
    ):
        """
        Record a single request/response pair to the collection.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, etc.)
        url : str
            Full request URL
        headers : dict
            Request headers
        query_params : dict
            Query parameters
        body : any
            Request body
        path : str
            Endpoint path pattern

        Notes
        -----
        Credentials are stripped here, before anything touches the disk.
        """
        headers = redact_headers(
            headers, self.sensitive_headers, enabled=self.redact_headers
        )
        body = _redact_body(body, enabled=self.redact_body)

        # Build Postman request item
        item = {
            "name": f"{method} {path}",
            "request": {
                "method": method.upper(),
                "header": [
                    {"key": k, "value": v, "type": "text"}
                    for k, v in headers.items()
                    if k.lower() not in ['host', 'content-length']
                ],
                "url": {
                    "raw": url,
                    "protocol": url.split("://")[0] if "://" in url else "http",
                    "host": [url.split("://")[1].split("/")[0] if "://" in url else "localhost"],
                    "path": path.strip("/").split("/"),
                    "query": [
                        {"key": k, "value": str(v)}
                        for k, v in query_params.items()
                    ] if query_params else []
                }
            },
            "response": []
        }

        # Add body if present
        if body is not None:
            if isinstance(body, (dict, list)):
                item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(body, indent=2),
                    "options": {
                        "raw": {
                            "language": "json"
                        }
                    }
                }
            else:
                item["request"]["body"] = {
                    "mode": "raw",
                    "raw": str(body)
                }

        # Check if this endpoint already exists and update or append
        existing_index = None
        for idx, existing_item in enumerate(self.collection["item"]):
            if existing_item["name"] == item["name"]:
                existing_index = idx
                break

        if existing_index is not None:
            # Update existing item's response examples
            existing_responses = self.collection["item"][existing_index].get("response", [])
            item["response"].extend(existing_responses)
            self.collection["item"][existing_index] = item
        else:
            # Add new item
            self.collection["item"].append(item)

        self._save_collection()

    @staticmethod
    def _get_status_text(status_code: int) -> str:
        """Get status text for common HTTP status codes."""
        status_texts = {
            200: "OK",
            201: "Created",
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            422: "Unprocessable Entity",
            500: "Internal Server Error"
        }
        return status_texts.get(status_code, "Response")


def postman(
    output_dir: str = "./.postman_collections",
    collection_name: Optional[str] = None,
    sensitive_headers: Optional[set[str]] = None,
    keep_sensitive_headers: bool = False,
    redact_body: bool = True,
):
    """
    Decorator that records FastAPI endpoint requests/responses to Postman collections.

    This decorator intercepts FastAPI endpoint calls and records the request and
    response data in Postman Collection v2.1 format. Each decorated endpoint gets
    its own collection file (or shares one if collection_name is specified).

    Parameters
    ----------
    output_dir : str, optional
        Directory to store Postman collection files. Default is './.postman_collections'
    collection_name : str, optional
        Custom name for the collection. If not provided, uses the function name.
    sensitive_headers : set of str, optional
        Header names to mask instead of the built-in list
        (``authorization``, ``cookie``, ``set-cookie``, ``proxy-authorization``,
        ``x-api-key``, ``api-key``, ``x-auth-token``). Matching is
        case-insensitive.
    keep_sensitive_headers : bool, optional
        Write credential headers verbatim into the collection. Only set this
        when the collection really must replay authentication — the file is
        plain JSON on disk. Default is False (headers are masked as ``***``).
    redact_body : bool, optional
        Mask values of sensitive-looking JSON keys (``password``, ``token``,
        ``secret``, ``api_key``, ``credit_card``, …). Default is True.

    Returns
    -------
    callable
        The decorated function with automatic request/response recording.

    Examples
    --------
    Basic usage:

    >>> from steely.fastapi import recorder
    >>> from fastapi import FastAPI
    >>>
    >>> app = FastAPI()
    >>>
    >>> @app.get("/users/{user_id}")
    >>> @recorder.postman()
    >>> async def get_user(user_id: int):
    >>>     return {"user_id": user_id, "name": "John"}

    With custom collection name:

    >>> @app.post("/users")
    >>> @recorder.postman(collection_name="user_api")
    >>> async def create_user(name: str):
    >>>     return {"name": name, "id": 123}

    Multiple endpoints in one collection:

    >>> @app.get("/users")
    >>> @recorder.postman(collection_name="user_api")
    >>> async def list_users():
    >>>     return [{"id": 1, "name": "John"}]
    >>>
    >>> @app.get("/users/{user_id}")
    >>> @recorder.postman(collection_name="user_api")
    >>> async def get_user(user_id: int):
    >>>     return {"id": user_id, "name": "John"}

    Notes
    -----
    - The decorator requires the FastAPI Request object to be injected.
      FastAPI automatically provides this when present in the function signature.
    - Collections are automatically created/updated in the specified output directory.
    - Each request/response is saved as an example in the Postman collection.
    - The decorator preserves the original function signature for FastAPI compatibility.
    - Works with both sync and async FastAPI endpoints.
    - Credential headers and sensitive body keys are redacted by default; see
      ``keep_sensitive_headers`` / ``redact_body`` to change that.
    - Requires the optional FastAPI extra: ``pip install "steely[fastapi]"``.
    """
    def decorator(func):
        request_cls = require_request()

        coll_name = collection_name if collection_name else func.__name__
        recorder: PostmanRecorder = PostmanRecorder(
            coll_name,
            output_dir,
            sensitive_headers=sensitive_headers,
            redact_headers=not keep_sensitive_headers,
            redact_body=redact_body,
        )

        sig = inspect.signature(func)
        has_request_param = any(
            param.annotation is request_cls or param.name == "request"
            for param in sig.parameters.values()
        )

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):

                request = kwargs.get('request')
                if request is None:
                    for arg in args:
                        if isinstance(arg, request_cls):
                            request = arg
                            break

                if request is None:
                    return await func(*args, **kwargs)

                method = request.method
                url = str(request.url)
                headers = dict(request.headers)
                query_params = dict(request.query_params)
                path = request.url.path

                body = None
                try:
                    content_type = headers.get('content-type', '')
                    if 'application/json' in content_type:
                        body = await request.json()
                    elif content_type:
                        body_bytes = await request.body()
                        body = body_bytes.decode('utf-8') if body_bytes else None
                except (ValueError, UnicodeDecodeError, RuntimeError):
                    pass

                func_kwargs = kwargs.copy()
                if not has_request_param and 'request' in func_kwargs:
                    func_kwargs.pop('request')

                recorder.record_request(
                    method=method,
                    url=url,
                    headers=headers,
                    query_params=query_params,
                    body=body,
                    path=path
                )

                response = await func(*args, **func_kwargs)

                return response

            if not has_request_param:
                params = list(sig.parameters.values())
                params.append(inspect.Parameter(
                    'request', inspect.Parameter.KEYWORD_ONLY, annotation=request_cls
                ))
                async_wrapper.__signature__ = sig.replace(parameters=params)
            else:
                async_wrapper.__signature__ = sig

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                request = kwargs.get('request')
                if request is None:
                    for arg in args:
                        if isinstance(arg, request_cls):
                            request = arg
                            break

                if request is None:
                    return func(*args, **kwargs)
                method = request.method
                url = str(request.url)
                headers = dict(request.headers)
                query_params = dict(request.query_params)
                path = request.url.path

                body = None
                try:
                    content_type = headers.get('content-type', '')
                    if 'application/json' in content_type:
                        pass
                except (ValueError, UnicodeDecodeError, RuntimeError):
                    pass

                func_kwargs = kwargs.copy()
                if not has_request_param and 'request' in func_kwargs:
                    func_kwargs.pop('request')

                recorder.record_request(
                    method=method,
                    url=url,
                    headers=headers,
                    query_params=query_params,
                    body=body,
                    path=path
                )

                response = func(*args, **func_kwargs)

                return response

            if not has_request_param:
                params = list(sig.parameters.values())
                params.append(inspect.Parameter(
                    'request', inspect.Parameter.KEYWORD_ONLY, annotation=request_cls
                ))
                sync_wrapper.__signature__ = sig.replace(parameters=params)
            else:
                sync_wrapper.__signature__ = sig

            return sync_wrapper

    return decorator
