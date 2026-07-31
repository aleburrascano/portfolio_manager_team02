"""
Flask application entry point: loads config, wires up the database and the
Socket.IO server, and registers all route blueprints.
"""
import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from authorization import init_app as init_sessions
from db.connection import init_app as init_db
from errors import register_error_handlers
from realtime import init_app as init_realtime, socketio
from routes.wallet import wallet_bp
from routes.assets import assets_bp
from routes.history import history_bp
from routes.auth import auth_bp

load_dotenv()

app = Flask(__name__)
init_db(app)
init_sessions(app)
register_error_handlers(app)

cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',')
CORS(app, origins=cors_origins, supports_credentials=True)
init_realtime(app, cors_origins)

API_PREFIX = '/api/v1'
app.register_blueprint(wallet_bp, url_prefix=API_PREFIX)
app.register_blueprint(assets_bp, url_prefix=API_PREFIX)
app.register_blueprint(history_bp, url_prefix=API_PREFIX)
app.register_blueprint(auth_bp, url_prefix=API_PREFIX)

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
