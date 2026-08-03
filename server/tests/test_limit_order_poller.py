import limit_order_poller as poller


def fill(order_id=1, user_id=7):
    return {
        'userId': user_id, 'limitOrderId': order_id, 'ticker': 'AAPL', 'side': 'buy',
        'orderType': 'limit', 'quantity': 5.0, 'price': 9.0, 'assetTransactionId': order_id,
    }


def test_run_once_returns_the_fill_count(app, monkeypatch):
    monkeypatch.setattr(poller, 'notify_order_filled', lambda _: None)
    monkeypatch.setattr(poller, 'evaluate_pending_orders', lambda: [fill(1), fill(2)])
    assert poller.run_once(app) == 2


def test_run_once_swallows_exceptions_and_returns_zero(app, monkeypatch):
    def boom():
        raise RuntimeError('market data is down')

    monkeypatch.setattr(poller, 'evaluate_pending_orders', boom)
    assert poller.run_once(app) == 0


# The fill is committed by the time it gets here, so the announcement is the
# only thing that tells its owner - who has no request in flight - about it.
def test_run_once_announces_every_fill(app, monkeypatch):
    announced = []
    monkeypatch.setattr(poller, 'notify_order_filled', announced.append)
    monkeypatch.setattr(poller, 'evaluate_pending_orders', lambda: [fill(1), fill(2)])

    poller.run_once(app)
    assert [f['limitOrderId'] for f in announced] == [1, 2]


def test_run_once_announces_nothing_when_nothing_filled(app, monkeypatch):
    announced = []
    monkeypatch.setattr(poller, 'notify_order_filled', announced.append)
    monkeypatch.setattr(poller, 'evaluate_pending_orders', lambda: [])

    assert poller.run_once(app) == 0
    assert announced == []
