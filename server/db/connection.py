"""
Shared MySQL connection, scoped to the Flask request context.
"""
import os
from typing import Optional
from flask import Flask, g
import mysql.connector
from mysql.connector import Error
from mysql.connector.connection import MySQLConnection

def get_db() -> Optional[MySQLConnection]:
    """
    Get (or lazily open) the MySQL connection for the current request.

    Returns:
        MySQLConnection | None: The connection, or None if it failed to connect.
    """
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                user=os.environ.get('DB_USER', 'root'),
                password=os.environ.get('DB_PASSWORD', ''),
                database=os.environ.get('DB_NAME', 'portfolio_manager')
            )
        except Error as e:
            print(f"Database connection error: {e}")
            g.db = None
    return g.db

def close_db(exception: Optional[BaseException] = None) -> None:
    """Close the request-scoped MySQL connection, if one was opened."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app: Flask) -> None:
    """Register the connection teardown with the given Flask app."""
    app.teardown_appcontext(close_db)
