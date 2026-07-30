"""
Password-based auth: users register with a unique username and log in
against a stored password hash. Passwords themselves are never stored.

Usernames are normalised to lowercase on the way in. Left alone, "Ada" and
"ada" would be the same account on MySQL (whose default collation is
case-insensitive) and two different ones on SQLite (which compares bytes) -
so the same registration would succeed in dev and fail in production.
"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from db.connection import get_session
from db.models import User


def normalize_username(username: str) -> str:
    """The canonical form of a username: trimmed and lowercased."""
    return username.strip().lower()


def _serialize(user: User) -> Dict[str, Any]:
    """The public view of a user - never includes the password hash."""
    return {
        'userId': user.userId,
        'username': user.username,
        'firstName': user.firstName,
        'lastName': user.lastName,
    }


def register(username: str, password: str, first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
    """
    Create a new user with a hashed password.

    Args:
        username (str): The desired username.
        password (str): The plaintext password, hashed before it is stored.
        first_name (str): The user's first name.
        last_name (str): The user's last name.

    Returns:
        dict | None: The new user, or None if the username is already taken.
    """
    username = normalize_username(username)
    session = get_session()
    if session.scalar(select(User).where(User.username == username)) is not None:
        return None

    user = User(
        username=username,
        firstName=first_name,
        lastName=last_name,
        passwordHash=generate_password_hash(password),
    )
    session.add(user)
    session.commit()
    return _serialize(user)


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Check a username/password pair.

    Args:
        username (str): The username to log in as.
        password (str): The plaintext password to verify.

    Returns:
        dict | None: The user if the credentials match, None otherwise.
    """
    user = get_session().scalar(select(User).where(User.username == normalize_username(username)))
    if user is None or not check_password_hash(user.passwordHash, password):
        return None
    return _serialize(user)


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Look up a user by ID.

    Args:
        user_id (int): The ID of the user.

    Returns:
        dict | None: The user, or None if no such user exists.
    """
    user = get_session().get(User, user_id)
    return _serialize(user) if user else None
