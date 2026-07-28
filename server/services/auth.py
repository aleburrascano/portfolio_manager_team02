"""
Demo auth: identify a user by first/last name only, creating them if new.
"""
from typing import Optional, Dict, Any
from db.connection import get_db

def login(first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
    """
    Find the user matching first_name/last_name, or create one if none exists.

    Args:
        first_name (str): The user's first name.
        last_name (str): The user's last name.

    Returns:
        dict | None: {'userId', 'firstName', 'lastName'}, or None if the
        database connection failed.
    """
    db = get_db()
    if db is None:
        return None

    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT userId, firstName, lastName FROM Users WHERE firstName = %s AND lastName = %s",
        (first_name, last_name)
    )
    user = cursor.fetchone()

    if user is None:
        cursor.execute(
            "INSERT INTO Users (firstName, lastName) VALUES (%s, %s)",
            (first_name, last_name)
        )
        db.commit()
        user = {'userId': cursor.lastrowid, 'firstName': first_name, 'lastName': last_name}

    cursor.close()
    return user
