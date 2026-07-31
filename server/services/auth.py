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
from services.exceptions import InvalidInput, UnknownUser, UsernameTaken


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


def update_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    current_password: Optional[str] = None,
    new_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Edit a user's profile fields and/or password. Only the fields passed
    (non-None) are changed; everything else is left as-is.

    Args:
        user_id (int): The ID of the user to edit.
        username (str | None): The new username, if changing it.
        first_name (str | None): The new first name, if changing it.
        last_name (str | None): The new last name, if changing it.
        current_password (str | None): The caller's existing password,
            required to prove ownership when new_password is set.
        new_password (str | None): The new password, if changing it.

    Returns:
        dict: The updated user.

    Raises:
        UnknownUser: No user with that ID exists.
        UsernameTaken: Another account already uses the requested username.
        InvalidInput: A password change was requested but current_password
            doesn't match the account's existing password.
    """
    session = get_session()
    user = session.get(User, user_id)
    if user is None:
        raise UnknownUser('User not found')

    if username is not None:
        normalized = normalize_username(username)
        if normalized != user.username:
            existing = session.scalar(select(User).where(User.username == normalized))
            if existing is not None:
                raise UsernameTaken('That username is already taken')
            user.username = normalized

    if first_name is not None:
        user.firstName = first_name
    if last_name is not None:
        user.lastName = last_name

    if new_password is not None:
        if not current_password or not check_password_hash(user.passwordHash, current_password):
            raise InvalidInput('Current password is incorrect')
        user.passwordHash = generate_password_hash(new_password)

    session.commit()
    return _serialize(user)
