"""
Routes for demo login by first/last name.
"""
from typing import Tuple
from flask import Blueprint, request
from services.auth import login

auth_bp = Blueprint('auth', __name__)

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
        return {'error': 'firstName and lastName are required'}, 400

    user = login(first_name, last_name)
    if user is None:
        return {'error': 'Database connection failed'}, 500

    return user, 200
