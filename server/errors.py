"""
Consistent JSON error envelope ({'error': {'message', 'code'}}) for both
routes that catch their own exceptions and ones that don't.
"""
from typing import Optional, Tuple
from flask import Flask
from werkzeug.exceptions import HTTPException

from services.exceptions import ServiceError

_DEFAULT_CODES = {
    400: 'bad_request',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    409: 'conflict',
    500: 'internal_error',
    502: 'upstream_error',
}


def _default_code(status: int) -> str:
    return _DEFAULT_CODES.get(status, 'error')


def _schema_message(exception: HTTPException) -> Optional[str]:
    """
    The field message behind a failed schema validation, if that is what
    this is.

    webargs hangs its messages off the exception, nested by location -
    {'json': {'amount': ['amount must be greater than zero.']}} - and
    leaves the description as a bare "Bad Request". Without digging them
    out, every rejected body would surface as the same useless sentence.
    Only the first is taken: the envelope carries one message, and the
    first failing field is the one worth naming.
    """
    data = getattr(exception, 'data', None)
    if not isinstance(data, dict):
        return None

    for fields in data.get('messages', {}).values():
        if not isinstance(fields, dict):
            continue
        for texts in fields.values():
            if isinstance(texts, str):
                return texts
            if isinstance(texts, (list, tuple)) and texts:
                return str(texts[0])
    return None


def error_response(message: str, status: int, code: Optional[str] = None) -> Tuple[dict, int]:
    """Build a full (body, status) error response."""
    return {'error': {'message': message, 'code': code or _default_code(status)}}, status


def register_error_handlers(app: Flask) -> None:
    """
    Make routes that raise instead of returning also produce the same
    envelope: domain failures (services.exceptions) surface their own
    message and status, known HTTP errors (404, 405, ...) keep theirs, and
    anything else is hidden behind a generic 500 so internal exception
    text never reaches the client.
    """
    @app.errorhandler(ServiceError)
    def handle_service_error(e: ServiceError):
        return error_response(str(e), e.status)

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        message = _schema_message(e) or e.description or e.name or 'Error'
        return error_response(message, e.code or 500)

    @app.errorhandler(Exception)
    def handle_exception(e: Exception):
        app.logger.exception(e)
        return error_response('Internal server error', 500)
