"""
Flask application entry point: loads config, wires up the database and the
Socket.IO server, and registers all route blueprints.
"""
import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from apidocs import init_app as init_apidocs
from authorization import init_app as init_sessions
from db.connection import init_app as init_db
from errors import register_error_handlers
from limit_order_poller import start as start_limit_order_poller
from realtime import init_app as init_realtime, socketio
from routes.wallet import wallet_bp
from routes.assets import assets_bp
from routes.history import history_bp
from routes.auth import auth_bp
from routes.limit_orders import limit_orders_bp

load_dotenv()

app = Flask(__name__)
init_db(app)
init_sessions(app)

cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',')
CORS(app, origins=cors_origins, supports_credentials=True)
init_realtime(app, cors_origins)

API_PREFIX = '/api/v1'
# Through the Api rather than Flask directly: that is what puts a
# blueprint's routes and schemas into the spec.
api = init_apidocs(app)

# After the Api, deliberately. flask-smorest installs its own handler for
# HTTPException, which answers a rejected request with its own envelope
# ({'code', 'errors', 'status'}). Registering ours second puts this API's
# single error shape back in front of it - the client reads
# error.message and knows nothing about smorest's.
register_error_handlers(app)
api.register_blueprint(wallet_bp, url_prefix=API_PREFIX)
api.register_blueprint(assets_bp, url_prefix=API_PREFIX)
api.register_blueprint(history_bp, url_prefix=API_PREFIX)
api.register_blueprint(auth_bp, url_prefix=API_PREFIX)
api.register_blueprint(limit_orders_bp, url_prefix=API_PREFIX)

# Disabled in tests (see tests/conftest.py) so the suite doesn't get a live
# thread hitting real market data against the shared in-memory database.
if os.environ.get('START_LIMIT_ORDER_POLLER', 'true').lower() != 'false':
    start_limit_order_poller(app)

@app.route('/')
def index() -> dict:
    """Health check endpoint."""
    return {'status': 'ok'}

if __name__ == '__main__':
    # socketio.run rather than app.run, so the WebSocket endpoint is served
    # alongside the REST routes on the same port. allow_unsafe_werkzeug is
    # needed to start this dev server at all under CI/e2e, which run it
    # without a tty attached to stdin.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
