"""
Routes for registering an account and logging in with a password.
"""
from typing import Tuple
from flask import Blueprint, request
from services.auth import authenticate, get_user, register
from authorization import current_user_id, log_in, log_out, require_user
from errors import error_response
from links import user_links

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8

@auth_bp.route('/users/<int:user_id>', methods=['GET'])
@require_user
def get_user_route(user_id: int) -> Tuple[dict, int]:
    """
    Look up a user by ID.

    Returns:
        dict: {'userId': int, 'username': str, 'firstName': str,
        'lastName': str, '_links': dict}, or a 404 error.
    """
    user = get_user(user_id)
    if user is None:
        return error_response('User not found', 404)

    return {**user, '_links': user_links(user_id)}, 200

@auth_bp.route('/auth/me', methods=['GET'])
def get_current_user_route() -> Tuple[dict, int]:
    """
    Get the user owning the caller's session, used by the client to restore
    a login on page load.

    Returns:
        dict: The current user, or a 401 error if there's no live session.
    """
    user_id = current_user_id()
    user = get_user(user_id) if user_id is not None else None
    if user is None:
        # The session outlived the user record it points at.
        log_out()
        return error_response('Authentication required', 401)

    return {**user, '_links': user_links(user['userId'])}, 200

@auth_bp.route('/auth/register', methods=['POST'])
def register_route() -> Tuple[dict, int]:
    """
    Create an account.

    Body:
        dict: {'username': str, 'password': str, 'firstName': str, 'lastName': str}

    Returns:
        dict: The new user, or a 400/409 error.
    """
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    first_name = (body.get('firstName') or '').strip()
    last_name = (body.get('lastName') or '').strip()

    if not username or not first_name or not last_name:
        return error_response('username, firstName and lastName are required', 400)
    if len(password) < MIN_PASSWORD_LENGTH:
        return error_response(f'Password must be at least {MIN_PASSWORD_LENGTH} characters', 400)

    user = register(username, password, first_name, last_name)
    if user is None:
        return error_response('That username is already taken', 409)

    log_in(user['userId'])
    return {**user, '_links': user_links(user['userId'])}, 201

@auth_bp.route('/auth/login', methods=['POST'])
def login_route() -> Tuple[dict, int]:
    """
    Log in with a username and password.

    Body:
        dict: {'username': str, 'password': str}

    Returns:
        dict: The user, or a 400/401 error.
    """
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    if not username or not password:
        return error_response('username and password are required', 400)

    user = authenticate(username, password)
    if user is None:
        return error_response('Incorrect username or password', 401)

    log_in(user['userId'])
    return {**user, '_links': user_links(user['userId'])}, 200

@auth_bp.route('/auth/logout', methods=['POST'])
def logout_route() -> Tuple[dict, int]:
    """
    End the caller's session.

    Returns:
        dict: A success message.
    """
    log_out()
    return {'message': 'Logged out.'}, 200
