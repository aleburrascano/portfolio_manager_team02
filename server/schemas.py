"""
Marshmallow schemas for the request bodies and query strings.

The rules stay in validation.py. Each field here delegates to the parser
that was already written and already tested, so the schema decides the
*shape* of a request while validation.py keeps deciding what counts as
valid. One answer to "is this a legal amount" rather than two that can
drift apart, and the existing error wording survives unchanged.

Fields subclass the marshmallow type that matches what they produce, so
the generated OpenAPI says `number` where a Decimal comes back rather
than falling back to an untyped field.
"""
from typing import Any

import marshmallow as ma

from services.exceptions import InvalidInput
from validation import (
    parse_amount, parse_days, parse_limit_price, parse_order_type, parse_quantity, parse_side,
)


class _Parsed:
    """
    Mixin: hand deserialization to a validation.py parser.

    The parsers raise InvalidInput and marshmallow expects ValidationError,
    so the message is carried across untouched - the caller sees the same
    sentence they saw before this file existed.
    """

    _parse: Any = None

    def _deserialize(self, value: Any, attr: Any, data: Any, **kwargs: Any) -> Any:
        try:
            return type(self)._parse(value)
        except InvalidInput as error:
            raise ma.ValidationError(str(error)) from None


# Each field says what a *missing* value should read as. marshmallow checks
# `required` before the value ever reaches the parser, so without this an
# absent amount would report "Missing data for required field." where it
# used to say "amount is required." - same rejection, worse sentence.
class Amount(_Parsed, ma.fields.Decimal):
    _parse = staticmethod(parse_amount)
    default_error_messages = {'required': 'amount is required.'}


class Quantity(_Parsed, ma.fields.Decimal):
    _parse = staticmethod(parse_quantity)
    default_error_messages = {'required': 'quantity is required.'}


class LimitPrice(_Parsed, ma.fields.Decimal):
    _parse = staticmethod(parse_limit_price)
    default_error_messages = {'required': 'limitPrice is required.'}


class Side(_Parsed, ma.fields.String):
    _parse = staticmethod(parse_side)
    default_error_messages = {'required': "side must be 'buy' or 'sell'."}


class OrderType(_Parsed, ma.fields.String):
    _parse = staticmethod(parse_order_type)
    default_error_messages = {'required': "orderType must be 'limit' or 'stop'."}


class Days(_Parsed, ma.fields.Integer):
    _parse = staticmethod(parse_days)


class Ticker(ma.fields.String):
    """
    A ticker symbol, trimmed. Mirrors the check the routes used to make
    inline, including treating a non-string the same as a missing one.
    """

    default_error_messages = {'required': 'ticker is required.'}

    def _deserialize(self, value: Any, attr: Any, data: Any, **kwargs: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ma.ValidationError('ticker is required.')
        return value.strip()


class DepositSchema(ma.Schema):
    amount = Amount(required=True, metadata={'example': 500.00})


class TradeSchema(ma.Schema):
    ticker = Ticker(required=True, metadata={'example': 'NVDA'})
    quantity = Quantity(required=True, metadata={'example': 1.5})


class LimitOrderSchema(ma.Schema):
    ticker = Ticker(required=True, metadata={'example': 'NVDA'})
    side = Side(required=True, metadata={'enum': ['buy', 'sell'], 'example': 'buy'})
    quantity = Quantity(required=True, metadata={'example': 10})
    limitPrice = LimitPrice(required=True, metadata={'example': 120.50})
    # Defaulted rather than required, so a caller written before stop orders
    # existed keeps placing limit orders and means it.
    orderType = OrderType(
        load_default='limit',
        metadata={
            'enum': ['limit', 'stop'],
            'example': 'limit',
            'description': (
                "'limit' waits for a price at least as good as limitPrice; "
                "'stop' waits for one at least as bad."
            ),
        },
    )


class PerformanceQuerySchema(ma.Schema):
    days = Days(load_default=None, metadata={'description': 'How far back to chart.'})


class LimitOrderQuerySchema(ma.Schema):
    status = ma.fields.String(
        load_default=None,
        validate=ma.validate.OneOf(['pending', 'filled', 'cancelled'], error='invalid status'),
        metadata={'description': 'Filter by status. Omitted returns all.'},
    )
    limit = ma.fields.Integer(
        load_default=None,
        metadata={'description': 'Maximum orders to return. Omitted returns all.'},
    )


class SearchQuerySchema(ma.Schema):
    # The custom required message keeps the sentence the route used to
    # return; marshmallow's default would replace it with its own.
    q = ma.fields.String(
        required=True,
        error_messages={'required': 'Search query required'},
        metadata={'example': 'NVDA'},
    )


class TransactionsQuerySchema(ma.Schema):
    limit = ma.fields.Integer(load_default=None)
    offset = ma.fields.Integer(load_default=0)
    # Sorting is the database's job, not the caller's: reversing one page in
    # the client would only reverse the rows that page happens to hold.
    sort = ma.fields.String(
        load_default='newest',
        validate=ma.validate.OneOf(['newest', 'oldest'], error='invalid sort'),
        metadata={'description': 'Order by date, newest or oldest first.'},
    )


# Credentials are deliberately not marked required here. The rules that
# apply to them are cross-field ones the routes already make - a password
# length, a username that is taken - and marshmallow's generic "Missing
# data for required field." would replace sentences the client shows to
# people. The schema documents the shape; routes/auth.py still judges it.
class RegisterSchema(ma.Schema):
    username = ma.fields.String(metadata={'example': 'ada'})
    password = ma.fields.String(metadata={'format': 'password'})
    firstName = ma.fields.String(metadata={'example': 'Ada'})
    lastName = ma.fields.String(metadata={'example': 'Lovelace'})


class LoginSchema(ma.Schema):
    username = ma.fields.String(metadata={'example': 'ada'})
    password = ma.fields.String(metadata={'format': 'password'})


class UpdateUserSchema(ma.Schema):
    """Every field optional - that is what a PATCH means here."""

    username = ma.fields.String()
    firstName = ma.fields.String()
    lastName = ma.fields.String()
    currentPassword = ma.fields.String(
        metadata={'format': 'password', 'description': 'Required whenever newPassword is set.'},
    )
    newPassword = ma.fields.String(metadata={'format': 'password'})
