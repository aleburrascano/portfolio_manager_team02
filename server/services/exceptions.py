"""
Domain failures that the API is expected to report back to the caller.

Services raise these instead of returning False, so the reason a trade
failed survives the trip up to the route layer. Each carries the HTTP
status it should surface as; errors.py turns them into the standard
error envelope, which is why no route needs to catch them.
"""


class ServiceError(Exception):
    """Base for failures that are the caller's business, not a bug."""

    status = 400


class InvalidInput(ServiceError):
    """A request field is missing, malformed, or out of range."""


class InsufficientFunds(ServiceError):
    """The wallet doesn't cover the withdrawal or purchase."""


class InsufficientHoldings(ServiceError):
    """The user doesn't own enough of the asset to sell that many."""


class UnknownUser(ServiceError):
    """No user with that ID exists."""

    status = 404


class UsernameTaken(ServiceError):
    """Another account already uses that username."""

    status = 409


class MarketDataUnavailable(ServiceError):
    """The upstream market data provider had no answer for us."""

    status = 502
