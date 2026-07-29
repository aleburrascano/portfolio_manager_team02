"""
Flask application entry point: loads config, wires up the database, and
registers all route blueprints.
"""
from flask import Flask
from dotenv import load_dotenv
from db.connection import init_app as init_db
from routes.wallet import wallet_bp
from routes.assets import assets_bp
from routes.history import history_bp
from routes.auth import auth_bp

load_dotenv()

app = Flask(__name__)
init_db(app)

app.register_blueprint(wallet_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(history_bp)
app.register_blueprint(auth_bp)

@app.route('/')
def index() -> dict:
    """Health check endpoint."""
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(debug=True)
