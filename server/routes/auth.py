"""
Routes for demo login by first/last name.
"""
from typing import Tuple
from flask import Blueprint, request
from services.auth import login, get_user
from errors import error_response

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_route(user_id: int) -> Tuple[dict, int]:
    """
    Look up a user by ID, used to validate a client-stored session on load.

    Returns:
        dict: {'userId': int, 'firstName': str, 'lastName': str}, or a
        404/500 error.
    """
    user, db_error = get_user(user_id)
    if db_error:
        return error_response('Database connection failed', 500)
    if user is None:
        return error_response('User not found', 404)

    return user, 200

@auth_bp.route('/auth/login', methods=['POST'])
def login_route() -> Tuple[dict, int]:
    """
    Log in (or create) a user by first and last name.

    Body:
        dict: {'firstName': str, 'lastName': str}

    Returns:
        dict: {'userId': int, 'firstName': str, 'lastName': str}, or a 400/500 error.
    """
    body = request.get_json(silent=True) or {}
    first_name = (body.get('firstName') or '').strip()
    last_name = (body.get('lastName') or '').strip()
    if not first_name or not last_name:
        return error_response('firstName and lastName are required', 400)

    user = login(first_name, last_name)
    if user is None:
        return error_response('Database connection failed', 500)

    return user, 200
