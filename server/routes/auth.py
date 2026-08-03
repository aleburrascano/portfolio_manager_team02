"""
Routes for registering an account and logging in with a password.
"""
from typing import Tuple
from flask import Blueprint, request
from services.auth import authenticate, get_user, register, update_user
from apidocs import documents
from authorization import current_user_id, log_in, log_out, require_user
from errors import error_response
from links import user_links

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8

_CREDENTIALS = {
    'username': {'type': 'string', 'example': 'ada'},
    'password': {'type': 'string', 'format': 'password', 'example': 'correct-horse-battery'},
}

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

@auth_bp.route('/users/<int:user_id>', methods=['PATCH'])
@require_user
# No required list: every field is optional, which is the point of a PATCH.
@documents(body={
    'username': {'type': 'string'},
    'firstName': {'type': 'string'},
    'lastName': {'type': 'string'},
    'currentPassword': {
        'type': 'string',
        'format': 'password',
        'description': 'Required whenever newPassword is set.',
    },
    'newPassword': {'type': 'string', 'format': 'password'},
})
def update_user_route(user_id: int) -> Tuple[dict, int]:
    """
    Edit the caller's own username, name, and/or password. Only the fields
    present in the body are changed.

    Body:
        dict: {'username': str, 'firstName': str, 'lastName': str,
        'currentPassword': str, 'newPassword': str}, all optional, though
        currentPassword is required whenever newPassword is set.

    Returns:
        dict: The updated user, or a 400/401/403/409 error.
    """
    body = request.get_json(silent=True) or {}
    username = body.get('username')
    first_name = body.get('firstName')
    last_name = body.get('lastName')
    current_password = body.get('currentPassword') or None
    new_password = body.get('newPassword') or None

    if username is not None:
        username = username.strip()
        if not username:
            return error_response('username cannot be empty', 400)
    if first_name is not None:
        first_name = first_name.strip()
        if not first_name:
            return error_response('firstName cannot be empty', 400)
    if last_name is not None:
        last_name = last_name.strip()
        if not last_name:
            return error_response('lastName cannot be empty', 400)
    if new_password is not None and len(new_password) < MIN_PASSWORD_LENGTH:
        return error_response(f'Password must be at least {MIN_PASSWORD_LENGTH} characters', 400)

    user = update_user(
        user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        current_password=current_password,
        new_password=new_password,
    )
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
@documents(
    body={
        **_CREDENTIALS,
        'firstName': {'type': 'string', 'example': 'Ada'},
        'lastName': {'type': 'string', 'example': 'Lovelace'},
    },
    required=['username', 'password', 'firstName', 'lastName'],
)
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
@documents(body=_CREDENTIALS, required=['username', 'password'])
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
