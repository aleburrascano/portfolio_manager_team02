"""
HATEOAS link builders: small `_links` maps attached to API responses so
clients can navigate to related resources/actions instead of hardcoding
route shapes.
"""
from flask import url_for


def user_links(user_id: int) -> dict:
    return {
        'self': url_for('auth.get_user_route', user_id=user_id),
        'update': url_for('auth.update_user_route', user_id=user_id),
        'balance': url_for('wallet.get_wallet_balance', user_id=user_id),
        'portfolio': url_for('wallet.get_portfolio_breakdown', user_id=user_id),
        'transactions': url_for('history.get_transaction_history', user_id=user_id),
    }


def balance_links(user_id: int) -> dict:
    return {
        'self': url_for('wallet.get_wallet_balance', user_id=user_id),
        'deposit': url_for('wallet.deposit_cash', user_id=user_id),
        'withdraw': url_for('wallet.withdraw_cash', user_id=user_id),
        'portfolio': url_for('wallet.get_portfolio_breakdown', user_id=user_id),
    }


def portfolio_links(user_id: int) -> dict:
    return {
        'self': url_for('wallet.get_portfolio_breakdown', user_id=user_id),
        'balance': url_for('wallet.get_wallet_balance', user_id=user_id),
        'transactions': url_for('history.get_transaction_history', user_id=user_id),
    }


def transactions_links(user_id: int) -> dict:
    return {
        'self': url_for('history.get_transaction_history', user_id=user_id),
        'balance': url_for('wallet.get_wallet_balance', user_id=user_id),
        'portfolio': url_for('wallet.get_portfolio_breakdown', user_id=user_id),
    }


def asset_summary_links(asset_type: str, symbol: str) -> dict:
    """Links for a plain asset dict in search/popular list results."""
    return {'self': url_for('assets.get_asset_detail', asset_type=asset_type, ticker=symbol)}


def asset_detail_links(asset_type: str, ticker: str) -> dict:
    return {
        'self': url_for('assets.get_asset_detail', asset_type=asset_type, ticker=ticker),
        'history': url_for('assets.get_asset_history', asset_type=asset_type, ticker=ticker),
    }


def holdings_links(user_id: int, asset_type: str, ticker: str) -> dict:
    return {
        'self': url_for('assets.get_asset_holdings', user_id=user_id, asset_type=asset_type, ticker=ticker),
        'detail': url_for('assets.get_asset_detail', asset_type=asset_type, ticker=ticker),
        'buy': url_for('assets.buy_asset', user_id=user_id, asset_type=asset_type),
        'sell': url_for('assets.sell_asset', user_id=user_id, asset_type=asset_type),
    }
