"""
FastAPI Integration Module
===========================

This module provides FastAPI-specific decorators and utilities for the steely toolkit.

Exports
-------
postman : decorator
    Records FastAPI endpoint requests to Postman collections
PostmanRecorder : class
    Handles recording and storage of API requests in Postman format
curl : decorator
    Records FastAPI endpoint requests as executable curl commands
CurlRecorder : class
    Handles recording and storage of API requests as curl shell scripts
"""

from steely.fastapi import recorder

__all__ = ["recorder"]