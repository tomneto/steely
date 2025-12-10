"""
FastAPI Integration Module
===========================

This module provides FastAPI-specific decorators and utilities for the steely toolkit.

Exports
-------
postman : decorator
    Records FastAPI endpoint requests/responses to Postman collections
PostmanRecorder : class
    Handles recording and storage of API requests/responses in Postman format
"""

from steely.fastapi.recorder import postman, PostmanRecorder

__all__ = ["postman", "PostmanRecorder"]