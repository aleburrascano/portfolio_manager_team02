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


class FakeFastInfo(dict):
    """fast_info answers .get(), which is all quote_fields asks of it."""


class FakeAsset:
    def __init__(self, metadata=None):
        self.history_metadata = metadata


def fast_info(last=110.0, previous=100.0):
    return FakeFastInfo({
        'lastPrice': last, 'previousClose': previous, 'dayLow': last - 5, 'dayHigh': last + 5,
    })


def test_quote_fields_measures_change_from_the_official_close():
    """The baseline is the previous session's close, not fast_info's guess."""
    fields = market_data.quote_fields(
        fast_info(last=110.0, previous=100.0), {'previousClose': 105.0}
    )

    assert fields['change'] == pytest.approx(5.0)
    assert fields['changePercent'] == pytest.approx(5.0 / 105.0 * 100)


def test_quote_fields_falls_back_when_no_official_close_is_available():
    """A slightly-off quote beats one with no change at all."""
    fields = market_data.quote_fields(fast_info(last=110.0, previous=100.0), {})

    assert fields['change'] == pytest.approx(10.0)
    assert fields['changePercent'] == pytest.approx(10.0)


def test_quote_fields_reports_no_change_without_any_baseline():
    fields = market_data.quote_fields(FakeFastInfo({'lastPrice': 110.0}), {})

    assert fields['change'] is None
    assert fields['changePercent'] is None


def test_quote_fields_ignores_a_baseline_it_cannot_read_as_a_number():
    fields = market_data.quote_fields(FakeFastInfo({'lastPrice': 110.0}), {'previousClose': 'n/a'})

    assert fields['change'] is None


def test_chart_metadata_is_empty_when_the_response_carried_none():
    assert market_data.chart_metadata(FakeAsset(None)) == {}
    assert market_data.chart_metadata(FakeAsset({})) == {}
    assert market_data.chart_metadata(object()) == {}


def test_quote_fields_covers_a_bar_less_response_from_the_chart_metadata():
    """
    A throttled chart request answers with metadata and no bars, which is
    what used to blank the day's range while the price above it read fine.
    """
    metadata = {
        'regularMarketPrice': 315.58,
        'previousClose': 311.0,
        'regularMarketDayLow': 313.49,
        'regularMarketDayHigh': 316.29,
    }
    fields = market_data.quote_fields(FakeFastInfo({}), metadata)

    assert fields['currentPrice'] == pytest.approx(315.58)
    assert fields['dayLow'] == pytest.approx(313.49)
    assert fields['dayHigh'] == pytest.approx(316.29)
    assert fields['change'] == pytest.approx(4.58)


def test_quote_fields_prefers_fast_info_over_the_metadata_it_came_with():
    fields = market_data.quote_fields(fast_info(last=110.0), {'regularMarketPrice': 999.0})

    assert fields['currentPrice'] == pytest.approx(110.0)


def test_quote_fields_treats_a_nan_as_absent():
    """
    NaN reaches here from a bar Yahoo has opened but not yet filled, and it
    has no JSON literal - one of them served raw breaks the whole response.
    """
    fields = market_data.quote_fields(
        FakeFastInfo({'lastPrice': 110.0, 'dayHigh': float('nan')}),
        {'regularMarketDayHigh': 112.0},
    )

    assert fields['dayHigh'] == pytest.approx(112.0)


def test_quoted_volume_reads_a_zero_as_not_yet_aggregated():
    """
    Yahoo opens the day's bar before anything goes into it, so fast_info
    reports 0 shares beside a price that is plainly moving. Unlike the
    absent open and range beside it, 0 is defined enough to satisfy the
    fallback, which is how the panel traded an em-dash for a wrong number.
    """
    volume = market_data.quoted_volume(
        FakeFastInfo({'lastVolume': 0}), {'regularMarketVolume': 9786160}
    )

    assert volume == pytest.approx(9786160)


def test_quoted_volume_keeps_a_zero_every_source_agrees_on():
    """A halted session really did trade nothing, and 0 says so."""
    volume = market_data.quoted_volume(
        FakeFastInfo({'lastVolume': 0}), {'regularMarketVolume': 0}
    )

    assert volume == 0


def test_quoted_volume_is_none_when_nobody_reports_one():
    assert market_data.quoted_volume(FakeFastInfo({}), {}) is None


def test_quoted_volume_falls_through_to_the_caller_s_last_resort():
    volume = market_data.quoted_volume(FakeFastInfo({'lastVolume': 0}), {}, 6144001)

    assert volume == pytest.approx(6144001)


def test_quoted_number_survives_a_field_that_raises():
    """
    fast_info computes lastVolume with an int cast, and int(NaN) raises -
    which used to take down every quote for that ticker, not just its volume.
    """
    class Raising(dict):
        def get(self, key, default=None):
            raise ValueError('cannot convert float NaN to integer')

    assert market_data.quoted_number(
        Raising(), {'regularMarketVolume': 6144001}, 'lastVolume'
    ) == pytest.approx(6144001)


def test_price_history_asks_for_unadjusted_closes(monkeypatch):
    """
    The chart and the performance replay have to be on the same scale as the
    prices trades are booked at, so dividend adjustment stays off.
    """
    asked = {}

    class FakeTicker:
        def __init__(self, ticker):
            asked['ticker'] = ticker

        def history(self, period, auto_adjust=True):
            asked['period'] = period
            asked['auto_adjust'] = auto_adjust
            return _EMPTY_FRAME

    monkeypatch.setattr(market_data.yf, 'Ticker', FakeTicker)
    market_data._price_history('KO', '1y')

    assert asked == {'ticker': 'KO', 'period': '1y', 'auto_adjust': False}


class _EmptyFrame:
    empty = True

    def iterrows(self):
        return iter(())


_EMPTY_FRAME = _EmptyFrame()


class FakeHourlyFrame:
    """The MultiIndex frame yf.download hands back for hourly bars."""

    def __init__(self, closes_by_symbol):
        self._closes = closes_by_symbol

    def __getitem__(self, symbol):
        return {'Close': FakeSeries(self._closes[symbol])}


class FakeSeries:
    def __init__(self, values):
        self._values = values

    def dropna(self):
        return self

    def __len__(self):
        return len(self._values)

    @property
    def iloc(self):
        return self._values


def test_rolling_24h_closes_reads_the_bar_a_day_back(monkeypatch):
    """25 hourly bars back from the latest is 24 hours of movement."""
    closes = [float(hour) for hour in range(30)]
    monkeypatch.setattr(
        market_data.yf, 'download', lambda *a, **k: FakeHourlyFrame({'BTC-USD': closes}),
    )

    assert market_data.rolling_24h_closes(['BTC-USD']) == {'BTC-USD': closes[-25]}


def test_rolling_24h_closes_skips_a_symbol_without_a_full_day(monkeypatch):
    monkeypatch.setattr(
        market_data.yf, 'download', lambda *a, **k: FakeHourlyFrame({'NEW-USD': [1.0, 2.0]}),
    )

    assert market_data.rolling_24h_closes(['NEW-USD']) == {}


def test_rolling_24h_closes_survives_a_failing_download(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('feed down')

    monkeypatch.setattr(market_data.yf, 'download', boom)
    assert market_data.rolling_24h_closes(['BTC-USD']) == {}


def test_rolling_24h_closes_only_fetches_once(monkeypatch):
    calls = []

    def download(*args, **kwargs):
        calls.append(args)
        return FakeHourlyFrame({'BTC-USD': [float(hour) for hour in range(30)]})

    monkeypatch.setattr(market_data.yf, 'download', download)
    market_data.rolling_24h_closes(['BTC-USD'])
    market_data.rolling_24h_closes(['BTC-USD'])

    assert len(calls) == 1


def test_with_24h_change_measures_from_the_day_old_price(monkeypatch):
    monkeypatch.setattr(market_data, 'rolling_24h_closes', lambda symbols: {'BTC-USD': 100.0})

    [row] = market_data.with_24h_change([
        {'symbol': 'BTC-USD', 'currentPrice': 110.0, 'change': 999.0, 'changePercent': 999.0},
    ])

    assert row['change'] == pytest.approx(10.0)
    assert row['changePercent'] == pytest.approx(10.0)


def test_with_24h_change_leaves_a_row_alone_without_a_baseline(monkeypatch):
    monkeypatch.setattr(market_data, 'rolling_24h_closes', lambda symbols: {})
    original = {'symbol': 'BTC-USD', 'currentPrice': 110.0, 'change': 5.0}

    assert market_data.with_24h_change([original]) == [original]


def test_with_24h_change_does_not_edit_the_cached_row(monkeypatch):
    monkeypatch.setattr(market_data, 'rolling_24h_closes', lambda symbols: {'BTC-USD': 100.0})
    original = {'symbol': 'BTC-USD', 'currentPrice': 110.0, 'change': 5.0}

    market_data.with_24h_change([original])
    assert original['change'] == 5.0
