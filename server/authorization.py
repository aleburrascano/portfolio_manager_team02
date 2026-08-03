"""
Session-based authorization: who the caller is, and whether they're allowed
to act on the user named in the URL.

The signed session cookie is the only thing that establishes identity - a
`user_id` in a route is a claim about *which* user is being addressed, never
proof of who is asking.
"""
import os
import secrets
from functools import wraps
from typing import Optional

from flask import Flask, session

from errors import error_response

SESSION_USER_KEY = 'userId'


def log_in(user_id: int) -> None:
    """Attach the given user to the caller's session."""
    session[SESSION_USER_KEY] = user_id


def log_out() -> None:
    """Drop the caller's session."""
    session.clear()


def current_user_id() -> Optional[int]:
    """The logged-in user's ID, or None if the caller has no session."""
    return session.get(SESSION_USER_KEY)


def require_user(view):
    """
    Guard a user-scoped route. The caller must be logged in, and the
    `user_id` in the route must be their own.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        caller_id = current_user_id()
        if caller_id is None:
            return error_response('Authentication required', 401)
        if kwargs.get('user_id') != caller_id:
            return error_response('You cannot access another user\'s data', 403)
        return view(*args, **kwargs)

    # Lets a test assert that every user-scoped route is actually guarded,
    # without depending on how many other decorators are stacked on it.
    wrapped.requires_user = True
    return wrapped


def init_app(app: Flask) -> None:
    """
    Configure session cookie signing. Without a SECRET_KEY the app still
    runs, on a per-process random key - fine for local dev, but every
    restart (and every worker) invalidates existing sessions, so it has to
    be set for real deployments.
    """
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        app.logger.warning('SECRET_KEY is not set; sessions will not survive a restart.')
        secret_key = secrets.token_hex(32)

    app.secret_key = secret_key
    app.config['SESSION_COOKIE_HTTPONLY'] = True

    # Deployed, the frontend is served from its own domain, which makes this
    # cookie cross-site: Lax withholds it from every XHR, so logging in
    # would appear to work and then every authenticated call would 401.
    # SameSite=None is only honoured alongside Secure, so the two move
    # together - and Secure would break plain-HTTP local development, which
    # is why this is opt-in rather than the default.
    cross_site = os.environ.get('CROSS_SITE_COOKIE', '').lower() in ('1', 'true', 'yes')
    app.config['SESSION_COOKIE_SAMESITE'] = 'None' if cross_site else 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = cross_site
