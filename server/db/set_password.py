"""
Set a user's password from the command line.

Mainly for accounts that predate password auth: migration 0002 backfills
them with an empty hash, which never matches, so they can't be logged into
until a password is set here. Also handy for resetting a forgotten one.

Usage (from the server/ directory):
    python -m db.set_password <username> <password>
    python -m db.set_password --list
"""
import argparse
import sys

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from db.connection import get_engine
from db.models import User

MIN_PASSWORD_LENGTH = 8


def list_users(session) -> None:
    users = session.scalars(select(User).order_by(User.userId)).all()
    if not users:
        print('No users.')
        return

    print(f"{'id':<5}{'username':<20}{'name':<28}password set?")
    for user in users:
        name = f'{user.firstName} {user.lastName}'
        print(f'{user.userId:<5}{user.username:<20}{name:<28}{"yes" if user.passwordHash else "NO"}')


def set_password(session, username: str, password: str) -> int:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        print(f'No user with username {username!r}.', file=sys.stderr)
        return 1

    user.passwordHash = generate_password_hash(password)
    session.commit()
    print(f'Password set for {user.username} ({user.firstName} {user.lastName}, userId={user.userId}).')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('username', nargs='?', help='the account to set a password on')
    parser.add_argument('password', nargs='?', help='the new password')
    parser.add_argument('--list', action='store_true', help='list users and whether they have a password')
    args = parser.parse_args()

    load_dotenv()
    with Session(get_engine()) as session:
        if args.list:
            list_users(session)
            return 0

        if not args.username or not args.password:
            parser.error('give a username and password, or --list')
        if len(args.password) < MIN_PASSWORD_LENGTH:
            parser.error(f'password must be at least {MIN_PASSWORD_LENGTH} characters')

        return set_password(session, args.username, args.password)


if __name__ == '__main__':
    sys.exit(main())
