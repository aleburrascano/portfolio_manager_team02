"""
Routes for reading and updating a user's cash wallet balance.
"""
from typing import Tuple
from services.user_transactions import get_user_balance
import services.cash_transactions as ct
import services.asset_transactions as at
import services.holdings as holdings
import services.portfolio_performance as pp
from apidocs import IDEMPOTENCY_KEY, Blueprint
from authorization import require_user
from idempotency import idempotent
from links import balance_links, portfolio_links
from schemas import DepositSchema, PerformanceQuerySchema
from validation import parse_days

wallet_bp = Blueprint('wallet', __name__, description='Cash balance and portfolio')

@wallet_bp.route('/users/<int:user_id>/balance', methods=['GET'])
@require_user
def get_wallet_balance(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's current wallet balance.

    Returns:
        dict: {'userId': int, 'balance': float, '_links': dict}
    """
    return {
        'userId': user_id,
        'balance': round(float(get_user_balance(user_id)), 2),
        '_links': balance_links(user_id),
    }, 200

@wallet_bp.route('/users/<int:user_id>/portfolio', methods=['GET'])
@require_user
def get_portfolio_breakdown(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's portfolio breakdown across cash, stocks, crypto, and bonds.

    Returns:
        dict: {'cash': float, 'stock': float, 'crypto': float, 'bond': float, '_links': dict}
    """
    return {**at.get_portfolio_values(user_id), '_links': portfolio_links(user_id)}, 200

@wallet_bp.route('/users/<int:user_id>/deposit', methods=['POST'])
@require_user
@idempotent
@wallet_bp.doc(parameters=[IDEMPOTENCY_KEY])
@wallet_bp.arguments(DepositSchema)
def deposit_cash(body: dict, user_id: int) -> Tuple[dict, int]:
    """
    Deposit cash into the user's account.

    Returns:
        dict: A success message, or a 400 error.
    """
    ct.deposit_cash(user_id, body['amount'])
    return {'message': 'Cash deposit successful!', '_links': balance_links(user_id)}, 200

@wallet_bp.route('/users/<int:user_id>/withdraw', methods=['POST'])
@require_user
@idempotent
@wallet_bp.doc(parameters=[IDEMPOTENCY_KEY])
@wallet_bp.arguments(DepositSchema)
def withdraw_cash(body: dict, user_id: int) -> Tuple[dict, int]:
    """
    Withdraw cash from the user's account.

    Returns:
        dict: A success message, or a 400 error.
    """
    ct.withdraw_cash(user_id, body['amount'])
    return {'message': 'Cash withdrawal successful!', '_links': balance_links(user_id)}, 200

@wallet_bp.route('/users/<int:user_id>/portfolio/performance', methods=['GET'])
@require_user
@wallet_bp.arguments(PerformanceQuerySchema, location='query')
def get_portfolio_performance(query: dict, user_id: int) -> Tuple[dict, int]:
    """
    Get a user's portfolio value over time, against what they paid in and
    against what the same deposits would have made in a broad index fund.

    Returns:
        dict: {'series': [{'date', 'portfolioValue', 'investedValue', 'cash',
        'netDeposits', 'benchmarkValue'}], 'summary': {...}, 'byAssetType':
        [...], 'benchmark': {'ticker', 'label'}, '_links': dict}
    """
    days = parse_days(query.get('days'))
    return {**pp.get_portfolio_performance(user_id, days), '_links': portfolio_links(user_id)}, 200

@wallet_bp.route('/users/<int:user_id>/portfolio/holdings', methods=['GET'])
@require_user
def get_portfolio_holdings(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's open positions, with cost basis and unrealised gain/loss,
    largest position first. Re-sorting is done in the client.

    Returns:
        dict: {'holdings': [...], 'totals': {...}, '_links': dict}
    """
    return {**holdings.get_holdings(user_id), '_links': portfolio_links(user_id)}, 200
