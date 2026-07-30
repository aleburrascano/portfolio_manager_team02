"""
Consistent JSON error envelope ({'error': {'message', 'code'}}) for both
routes that catch their own exceptions and ones that don't.
"""
from typing import Optional, Tuple
from flask import Flask
from werkzeug.exceptions import HTTPException

_DEFAULT_CODES = {
    400: 'bad_request',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    409: 'conflict',
    500: 'internal_error',
}


def _default_code(status: int) -> str:
    return _DEFAULT_CODES.get(status, 'error')


def error_body(message: str, status: int = 500, code: Optional[str] = None) -> dict:
    """Build just the `{'error': {...}}` envelope, for merging into a response dict."""
    return {'error': {'message': message, 'code': code or _default_code(status)}}


def error_response(message: str, status: int, code: Optional[str] = None) -> Tuple[dict, int]:
    """Build a full (body, status) error response."""
    return error_body(message, status, code), status


def register_error_handlers(app: Flask) -> None:
    """
    Make routes that raise instead of returning also produce the same
    envelope: known HTTP errors (404, 405, ...) keep their status and
    description; anything else is hidden behind a generic 500.
    """
    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        return error_response(e.description or e.name or 'Error', e.code or 500)

    @app.errorhandler(Exception)
    def handle_exception(e: Exception):
        app.logger.exception(e)
        return error_response('Internal server error', 500)
