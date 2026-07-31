from decimal import Decimal

import pytest

from services.exceptions import InvalidInput
from validation import parse_amount, parse_quantity

PARSERS = [parse_amount, parse_quantity]


@pytest.mark.parametrize('parser', PARSERS)
@pytest.mark.parametrize('raw', [
    None, True, False, 'abc', float('nan'), float('inf'), float('-inf'),
    0, -1, '-1', 1_000_000_001, '1.123456789', [], {},
])
def test_rejects_invalid_input(parser, raw):
    with pytest.raises(InvalidInput):
        parser(raw)


@pytest.mark.parametrize('parser', PARSERS)
@pytest.mark.parametrize('raw,expected', [
    ('1.5', Decimal('1.5')),
    (10, Decimal('10')),
    (0.01, Decimal('0.01')),
    ('1000000000', Decimal('1000000000')),
    ('1.12345678', Decimal('1.12345678')),
])
def test_accepts_valid_input(parser, raw, expected):
    assert parser(raw) == expected
