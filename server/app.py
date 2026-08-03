"""
Flask application entry point: loads config, wires up the database and the
Socket.IO server, and registers all route blueprints.
"""
import fnmatch
import logging
import os
from typing import List, Tuple
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from api.docs import init_app as init_apidocs
from api.authorization import init_app as init_sessions
from db.connection import init_app as init_db
from api.errors import register_error_handlers
from limit_order_poller import start as start_limit_order_poller
from api.observability import health, init_app as init_observability
from api.realtime import init_app as init_realtime, socketio
from api.routes.wallet import wallet_bp
from api.routes.assets import assets_bp
from api.routes.history import history_bp
from api.routes.auth import auth_bp
from api.routes.limit_orders import limit_orders_bp

load_dotenv()

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)

app = Flask(__name__)
init_db(app)
init_sessions(app)
init_observability(app)

def _allowed_origins() -> List[str]:
    """
    The browser origin patterns allowed to reach this server, logged on boot.

    Entries may contain `*`, because the frontend does not have one stable
    hostname: the host mints a fresh one for every deployment and another
    per branch, so an enumerated list is out of date the next time anyone
    pushes. `https://app-name-*.vercel.app` covers them without widening
    the rule to somebody else's project.

    Cleaned rather than split raw, because this value is typed into a
    hosting dashboard by hand and is compared to the Origin header
    character for character. A space after a comma, or the trailing slash
    the address bar shows, produces an entry that matches nothing and a
    rejection naming an origin that looks identical to the one configured.

    Deployed, these name the frontend's origin, not this server's. Getting
    it wrong fails exactly half the quote feed's requests - Engine.IO
    checks Origin only when the browser sends one, which it does on
    long-polling's POSTs and not on its GETs.
    """
    raw = os.environ.get('CORS_ORIGINS', 'http://localhost:5173')
    return [origin.strip().rstrip('/') for origin in raw.split(',') if origin.strip()]


def _origin_allowed(origin: str, environ=None) -> bool:
    """
    Whether one browser origin matches any configured pattern.

    Handed to Engine.IO as a callable, which is the only shape of its
    `cors_allowed_origins` that can express a pattern - a list is compared
    by equality and `'*'` disables the check for everyone.
    """
    if not origin:
        return True
    candidate = origin.rstrip('/')
    return any(fnmatch.fnmatchcase(candidate, pattern) for pattern in cors_origins)


def _cors_patterns(patterns: List[str]) -> List[str]:
    """
    The same patterns as the anchored regexes flask-cors matches against.

    Every entry is translated, not just the ones with a `*`. flask-cors
    reads a bare origin as a regex and matches it unanchored, so the dots
    in a hostname stand for any character and a pattern meant for
    `example.com` also accepts `example.com.somewhere-else.net`.
    """
    return [fnmatch.translate(pattern) for pattern in patterns]


cors_origins = _allowed_origins()
logging.getLogger(__name__).info('Allowed browser origins: %s', ', '.join(cors_origins))

CORS(app, origins=_cors_patterns(cors_origins), supports_credentials=True)
init_realtime(app, _origin_allowed)

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
