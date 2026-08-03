import limit_order_poller as poller


def test_run_once_returns_the_fill_count(app, monkeypatch):
    monkeypatch.setattr(poller, 'evaluate_pending_orders', lambda: 2)
    assert poller.run_once(app) == 2


def test_run_once_swallows_exceptions_and_returns_zero(app, monkeypatch):
    def boom():
        raise RuntimeError('market data is down')

    monkeypatch.setattr(poller, 'evaluate_pending_orders', boom)
    assert poller.run_once(app) == 0
