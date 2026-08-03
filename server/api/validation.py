"""
Validation for the numeric fields on the money-moving routes.

The API is a trust boundary in its own right - the client's checks in
lib/validation.ts are a convenience for the person typing, not a guarantee, so
anything that reaches a transaction has to be re-checked here.

Amounts and quantities are parsed to Decimal rather than float so the value
that gets stored is exactly the value that was sent.
"""
from decimal import Decimal, InvalidOperation
from typing import Any

from services.exceptions import InvalidInput

MAX_DECIMAL_PLACES = 8
MAX_AMOUNT = Decimal('1000000000')


def _to_decimal(raw: Any, field: str) -> Decimal:
    if raw is None:
        raise InvalidInput(f'{field} is required.')
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
        raise InvalidInput(f'{field} must be a number.')

    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise InvalidInput(f'{field} must be a number.') from None

    if not value.is_finite():
        raise InvalidInput(f'{field} must be a finite number.')
    return value


def _check_range(value: Decimal, field: str, maximum: Decimal) -> Decimal:
    if value <= 0:
        raise InvalidInput(f'{field} must be greater than zero.')
    if value > maximum:
        raise InvalidInput(f'{field} is too large.')
    if -value.as_tuple().exponent > MAX_DECIMAL_PLACES:
        raise InvalidInput(f'{field} cannot have more than {MAX_DECIMAL_PLACES} decimal places.')
    return value


def parse_amount(raw: Any) -> Decimal:
    """
    Validate a cash amount.

    Raises:
        InvalidInput: if it isn't a finite, positive, in-range number.
    """
    return _check_range(_to_decimal(raw, 'amount'), 'amount', MAX_AMOUNT)


def parse_quantity(raw: Any) -> Decimal:
    """
    Validate a trade quantity.

    Raises:
        InvalidInput: if it isn't a finite, positive, in-range number.
    """
    return _check_range(_to_decimal(raw, 'quantity'), 'quantity', MAX_AMOUNT)


def parse_side(raw: Any) -> str:
    """
    Validate a limit order's buy/sell side.

    Raises:
        InvalidInput: if it isn't 'buy' or 'sell'.
    """
    if raw not in ('buy', 'sell'):
        raise InvalidInput("side must be 'buy' or 'sell'.")
    return raw


def parse_order_type(raw: Any) -> str:
    """
    Validate a conditional order's kind.

    Raises:
        InvalidInput: if it isn't 'limit' or 'stop'.
    """
    if raw not in ('limit', 'stop'):
        raise InvalidInput("orderType must be 'limit' or 'stop'.")
    return raw


def parse_limit_price(raw: Any) -> Decimal:
    """
    Validate a limit order's trigger price.

    Raises:
        InvalidInput: if it isn't a finite, positive, in-range number.
    """
    return _check_range(_to_decimal(raw, 'limitPrice'), 'limitPrice', MAX_AMOUNT)


MIN_DAYS = 7
MAX_DAYS = 1825
DEFAULT_DAYS = 365


def parse_days(raw: Any) -> int:
    """
    Validate a chart window in days, defaulting when it isn't given.

    Raises:
        InvalidInput: if it isn't a whole number in range.
    """
    if raw is None or raw == '':
        return DEFAULT_DAYS

    try:
        days = int(raw)
    except (TypeError, ValueError):
        raise InvalidInput('days must be a whole number.') from None

    if not MIN_DAYS <= days <= MAX_DAYS:
        raise InvalidInput(f'days must be between {MIN_DAYS} and {MAX_DAYS}.')
    return days
