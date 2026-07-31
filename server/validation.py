"""
Validation for the numeric fields on the money-moving routes.

The API is a trust boundary in its own right - the client's checks in
validation.ts are a convenience for the person typing, not a guarantee, so
anything that reaches a transaction has to be re-checked here.

Amounts and quantities are parsed to Decimal rather than float so the value
that gets stored is exactly the value that was sent.
"""
from decimal import Decimal, InvalidOperation
from typing import Any

from services.exceptions import InvalidInput

# The columns behind these values are DECIMAL(18,8), so more precision than
# that would be silently rounded away - better to reject it.
MAX_DECIMAL_PLACES = 8
MAX_AMOUNT = Decimal('1000000000')


def _to_decimal(raw: Any, field: str) -> Decimal:
    if raw is None:
        raise InvalidInput(f'{field} is required.')
    # bool is an int subclass, and True would otherwise parse as 1.
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
        raise InvalidInput(f'{field} must be a number.')

    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise InvalidInput(f'{field} must be a number.') from None

    # JSON permits NaN and Infinity, and both would poison the arithmetic.
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
