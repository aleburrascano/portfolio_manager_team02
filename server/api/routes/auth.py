"""
Routes for registering an account and logging in with a password.
"""
import re
from typing import Optional, Tuple
from services.auth import authenticate, get_user, register, update_user
from api.docs import Blueprint
from api.authorization import current_user_id, log_in, log_out, require_user
from api.errors import error_response
from api.links import user_links
from api.schemas import LoginSchema, RegisterSchema, UpdateUserSchema

auth_bp = Blueprint('auth', __name__, description='Accounts and sessions')

MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 32
NAME_PATTERN = re.compile(r"^[A-Za-z' -]+$")
USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+$')


def _name_error(value: str, field: str, label: str) -> Optional[str]:
    """The first rule `value` breaks as a display name, or None if it's fine."""
    if len(value) > MAX_NAME_LENGTH:
        return f'{field} must be {MAX_NAME_LENGTH} characters or fewer'
    if not NAME_PATTERN.match(value):
        return f'{label} can only contain letters, spaces, hyphens, and apostrophes'
    return None


def _username_error(value: str) -> Optional[str]:
    """The first rule `value` breaks as a username, or None if it's fine."""
    if len(value) > MAX_NAME_LENGTH:
        return f'username must be {MAX_NAME_LENGTH} characters or fewer'
    if not USERNAME_PATTERN.match(value):
        return 'Username can only contain letters, numbers, underscores, dots, and hyphens'
    return None

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
@auth_bp.arguments(UpdateUserSchema)
def update_user_route(body: dict, user_id: int) -> Tuple[dict, int]:
    """
    Edit the caller's own username, name, and/or password. Only the fields
    present in the body are changed. currentPassword is required whenever
    newPassword is set.

    Returns:
        dict: The updated user, or a 400/401/403/409 error.
    """
    username = body.get('username')
    first_name = body.get('firstName')
    last_name = body.get('lastName')
    current_password = body.get('currentPassword') or None
    new_password = body.get('newPassword') or None

    if username is not None:
        username = username.strip()
        if not username:
            return error_response('username cannot be empty', 400)
        error = _username_error(username)
        if error:
            return error_response(error, 400)
    if first_name is not None:
        first_name = first_name.strip()
        if not first_name:
            return error_response('firstName cannot be empty', 400)
        error = _name_error(first_name, 'firstName', 'First name')
        if error:
            return error_response(error, 400)
    if last_name is not None:
        last_name = last_name.strip()
        if not last_name:
            return error_response('lastName cannot be empty', 400)
        error = _name_error(last_name, 'lastName', 'Last name')
        if error:
            return error_response(error, 400)
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
        log_out()
        return error_response('Authentication required', 401)

    return {**user, '_links': user_links(user['userId'])}, 200

@auth_bp.route('/auth/register', methods=['POST'])
@auth_bp.arguments(RegisterSchema)
def register_route(body: dict) -> Tuple[dict, int]:
    """
    Create an account.

    Returns:
        dict: The new user, or a 400/409 error.
    """
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    first_name = (body.get('firstName') or '').strip()
    last_name = (body.get('lastName') or '').strip()

    if not username or not first_name or not last_name:
        return error_response('username, firstName and lastName are required', 400)
    error = (
        _username_error(username)
        or _name_error(first_name, 'firstName', 'First name')
        or _name_error(last_name, 'lastName', 'Last name')
    )
    if error:
        return error_response(error, 400)
    if len(password) < MIN_PASSWORD_LENGTH:
        return error_response(f'Password must be at least {MIN_PASSWORD_LENGTH} characters', 400)

    user = register(username, password, first_name, last_name)
    if user is None:
        return error_response('That username is already taken', 409)

    log_in(user['userId'])
    return {**user, '_links': user_links(user['userId'])}, 201

@auth_bp.route('/auth/login', methods=['POST'])
@auth_bp.arguments(LoginSchema)
def login_route(body: dict) -> Tuple[dict, int]:
    """
    Log in with a username and password.

    Returns:
        dict: The user, or a 400/401 error.
    """
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
