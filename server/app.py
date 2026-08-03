"""
Flask application entry point: loads config, wires up the database and the
Socket.IO server, and registers all route blueprints.
"""
import logging
import os
from typing import Tuple
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from apidocs import init_app as init_apidocs
from authorization import init_app as init_sessions
from db.connection import init_app as init_db
from errors import register_error_handlers
from limit_order_poller import start as start_limit_order_poller
from observability import health, init_app as init_observability
from realtime import init_app as init_realtime, socketio
from routes.wallet import wallet_bp
from routes.assets import assets_bp
from routes.history import history_bp
from routes.auth import auth_bp
from routes.limit_orders import limit_orders_bp

load_dotenv()

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)

app = Flask(__name__)
init_db(app)
init_sessions(app)
init_observability(app)

cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',')
CORS(app, origins=cors_origins, supports_credentials=True)
init_realtime(app, cors_origins)

API_PREFIX = '/api/v1'
api = init_apidocs(app)

register_error_handlers(app)

api.register_blueprint(wallet_bp, url_prefix=API_PREFIX)
api.register_blueprint(assets_bp, url_prefix=API_PREFIX)
api.register_blueprint(history_bp, url_prefix=API_PREFIX)
api.register_blueprint(auth_bp, url_prefix=API_PREFIX)
api.register_blueprint(limit_orders_bp, url_prefix=API_PREFIX)

def _should_start_poller() -> bool:
    """
    Whether this process is the one that should run the background poller.

    Disabled outright in tests (see tests/conftest.py) so the suite doesn't
    get a live thread hitting real market data against the shared in-memory
    database.

    Otherwise: exactly one process, and specifically the one holding the
    sockets. Under `python app.py` the Werkzeug reloader imports this module
    twice - once in the supervising parent and once in the child that
    actually serves - and only the child has clients connected. With both
    polling, they race for the same pending orders, and whenever the parent
    won, the fill was committed by a process with nobody to announce it to.
    The order filled and the owner's screen never heard. It also doubled
    every upstream price call the poller makes.

    The child is the one with WERKZEUG_RUN_MAIN set. Under gunicorn this
    module is imported rather than run, so neither condition applies and the
    single worker polls as it should.
    """
    if os.environ.get('START_LIMIT_ORDER_POLLER', 'true').lower() == 'false':
        return False
    return not (__name__ == '__main__' and not os.environ.get('WERKZEUG_RUN_MAIN'))


if _should_start_poller():
    start_limit_order_poller(app)

@app.route('/')
def index() -> Tuple[dict, int]:
    """
    Health check.

    Answers 200 while the process can serve at all, and says separately
    whether the database is reachable - a 503 here would tell a platform to
    replace a container that is merely waiting on its database.

    Returns:
        dict: {'status', 'database', 'marketDataCache'}
    """
    return health(app), 200

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
