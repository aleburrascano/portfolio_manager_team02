"""
Serialising stored timestamps for the API.
"""
from datetime import datetime, timezone
from typing import Optional


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    """
    ISO-8601 for a stored timestamp, marked as UTC.

    The database stamps in UTC but hands datetimes back naive, and a naive
    isoformat() - '2026-08-03T17:37:17' - is read as *local* time by a
    browser, sliding a trade an hour or across midnight into the day before.
    Pinning the offset ('...+00:00') leaves the reader nothing to guess.

    Passes None through, so a caller can hand it an optional column without
    guarding first.
    """
    if value is None:
        return None
    stamped = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return stamped.isoformat()
