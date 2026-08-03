"""
Idempotency-Key support for the routes that move money.

A client that doesn't get a response back has no way to know whether its
deposit or trade landed. Retrying blind risks doing it twice; not retrying
risks not doing it at all. Sending an Idempotency-Key makes the retry safe:
the first request to claim a key does the work and its response is stored,
and any later request carrying the same key gets that same response back
without the work happening again.

The header is optional - a request without one behaves exactly as before.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import request
from sqlalchemy import delete, or_, update
from sqlalchemy.exc import IntegrityError

from db.connection import get_session
from db.models import IdempotentRequest
from errors import error_response

HEADER = 'Idempotency-Key'
MAX_KEY_LENGTH = 64

RETENTION = timedelta(hours=24)
STALE_CLAIM = timedelta(minutes=5)


def _fingerprint() -> str:
    """Identify the request a key was claimed for, to catch key reuse."""
    payload = f'{request.method} {request.path} '.encode() + (request.get_data() or b'')
    return hashlib.sha256(payload).hexdigest()


def _purge_expired(session, user_id: int) -> None:
    """
    Drop this user's records that are past retention, or claims abandoned by
    a request that never finished.

    Swept here rather than on a schedule so it needs no cron to stay
    bounded; it's a range scan over an indexed column, per user.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session.execute(
        delete(IdempotentRequest).where(
            IdempotentRequest.userId == user_id,
            or_(
                IdempotentRequest.createdAt < now - RETENTION,
                (IdempotentRequest.responseBody.is_(None))
                & (IdempotentRequest.createdAt < now - STALE_CLAIM),
            ),
        )
    )
    session.commit()


def _replay(session, user_id: int, key: str, fingerprint: str):
    """Answer a request whose key was already claimed."""
    record = session.get(IdempotentRequest, {'userId': user_id, 'idempotencyKey': key})

    if record is None:
        return error_response('That request was released, please retry', 409, 'idempotency_retry')

    if record.fingerprint != fingerprint:
        return error_response(f'That {HEADER} was already used for a different request', 409)

    if record.responseBody is None:
        return error_response(f'A request with that {HEADER} is still in progress', 409)

    return json.loads(record.responseBody), 200


def idempotent(view):
    """
    Make a user-scoped, money-moving route replay-safe.

    Only successful responses are recorded. A rejected request (bad input,
    insufficient funds) changes nothing, so its key is released and the
    caller can correct the request and retry with the same one.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        key = request.headers.get(HEADER)
        if not key:
            return view(*args, **kwargs)
        if len(key) > MAX_KEY_LENGTH:
            return error_response(f'{HEADER} must be at most {MAX_KEY_LENGTH} characters', 400)

        user_id = kwargs['user_id']
        fingerprint = _fingerprint()
        session = get_session()
        owns = (IdempotentRequest.userId == user_id, IdempotentRequest.idempotencyKey == key)

        _purge_expired(session, user_id)
        session.add(IdempotentRequest(userId=user_id, idempotencyKey=key, fingerprint=fingerprint))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return _replay(session, user_id, key, fingerprint)

        def release() -> None:
            session.rollback()
            session.execute(delete(IdempotentRequest).where(*owns))
            session.commit()

        try:
            body, status = view(*args, **kwargs)
        except Exception:
            release()
            raise

        if not 200 <= status < 300:
            release()
            return body, status

        session.execute(update(IdempotentRequest).where(*owns).values(
            responseBody=json.dumps(body)
        ))
        session.commit()
        return body, status

    return wrapped
