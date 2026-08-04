"""
market_data helpers that don't touch the feed.
"""
import pytest

from services import market_data


@pytest.mark.parametrize(
    'days, period',
    [
        (7, '1y'),
        (30, '1y'),
        (365, '1y'),
        (366, '2y'),
        (730, '2y'),
        (731, '5y'),
        (1825, '5y'),
    ],
)
def test_period_covering_picks_the_smallest_span_that_fits(days, period):
    assert market_data.period_covering(days) == period
