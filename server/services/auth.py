"""
Demo auth: identify a user by first/last name only, creating them if new.
"""
from typing import Any, Dict, Optional

from sqlalchemy import select

from db.connection import get_session
from db.models import User


def _serialize(user: User) -> Dict[str, Any]:
    return {'userId': user.userId, 'firstName': user.firstName, 'lastName': user.lastName}


def login(first_name: str, last_name: str) -> Dict[str, Any]:
    """
    Find the user matching first_name/last_name, or create one if none exists.

    Args:
        first_name (str): The user's first name.
        last_name (str): The user's last name.

    Returns:
        dict: {'userId', 'firstName', 'lastName'}.
    """
    session = get_session()
    user = session.scalar(
        select(User).where(User.firstName == first_name, User.lastName == last_name)
    )

    if user is None:
        user = User(firstName=first_name, lastName=last_name)
        session.add(user)
        session.commit()

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
