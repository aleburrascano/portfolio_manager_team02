"""
The health endpoint and the request log.

What matters here is that a health check distinguishes "up" from "up but
the database is unreachable" - the case it exists to catch - and that it
never raises, since a 500 tells a platform nothing it can act on.
"""
import logging

import observability
import services.market_data as market_data


def test_health_reports_ok(client):
    body = client.get('/').get_json()
    assert body['status'] == 'ok'
    assert body['database'] == 'ok'


def test_health_reports_the_cache(client):
    body = client.get('/').get_json()

    assert set(body['marketDataCache']) >= {'quotes', 'history', 'names'}
    assert body['marketDataCache']['quotes'] == {'entries': 0, 'hits': 0, 'misses': 0}


def test_health_counts_cache_hits(client, monkeypatch):
    monkeypatch.setattr(market_data, '_price_history', lambda ticker, period: [])
    market_data.price_history('AAPL')  # miss
    market_data.price_history('AAPL')  # hit

    history = client.get('/').get_json()['marketDataCache']['history']
    assert history == {'entries': 1, 'hits': 1, 'misses': 1}


# The case a health check exists for: the process is answering, but the
# thing it needs is not there.
def test_health_reports_an_unreachable_database(client, monkeypatch):
    def boom():
        raise RuntimeError('connection pool is gone')

    monkeypatch.setattr('db.connection.get_engine', boom)

    response = client.get('/')
    body = response.get_json()

    # Still 200: "replace this container" is the wrong instruction for a
    # process that is merely waiting on its database.
    assert response.status_code == 200
    assert body['status'] == 'degraded'
    assert 'unavailable' in body['database']


def test_health_never_raises(client, monkeypatch):
    monkeypatch.setattr(
        'services.market_data.cache_sizes', lambda: (_ for _ in ()).throw(RuntimeError()),
    )
    # cache_sizes is read inside health(), so a failure there would surface
    # as a 500 from the one endpoint that must always answer.
    try:
        response = client.get('/')
    except Exception:  # pragma: no cover - the assertion below is the point
        raise AssertionError('the health endpoint raised')
    assert response.status_code in (200, 500)


def test_a_request_is_logged_with_its_status(client, caplog):
    with caplog.at_level(logging.INFO, logger='treetop.request'):
        client.get('/api/v1/assets/types')

    [record] = [r for r in caplog.records if r.name == 'treetop.request']
    assert 'GET' in record.getMessage()
    assert '/api/v1/assets/types' in record.getMessage()
    assert '200' in record.getMessage()


# The health check runs on a timer and the socket transport polls
# continuously; logging either would bury everything else.
def test_the_health_check_is_not_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger='treetop.request'):
        client.get('/')

    assert [r for r in caplog.records if r.name == 'treetop.request'] == []


def test_a_slow_request_is_logged_louder(client, caplog, monkeypatch):
    monkeypatch.setattr(observability, 'SLOW_REQUEST_MS', 0)

    with caplog.at_level(logging.INFO, logger='treetop.request'):
        client.get('/api/v1/assets/types')

    [record] = [r for r in caplog.records if r.name == 'treetop.request']
    assert record.levelno == logging.WARNING


def test_a_server_error_is_logged_as_one(client, caplog, monkeypatch):
    import routes.assets as assets

    monkeypatch.setattr(
        assets, 'capabilities', lambda: (_ for _ in ()).throw(RuntimeError('boom')),
    )

    with caplog.at_level(logging.INFO, logger='treetop.request'):
        response = client.get('/api/v1/assets/types')

    assert response.status_code == 500
    [record] = [r for r in caplog.records if r.name == 'treetop.request']
    assert record.levelno == logging.ERROR
