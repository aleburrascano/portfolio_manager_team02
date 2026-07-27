from flask import Flask
from dotenv import load_dotenv
from db.connection import init_app as init_db
from routes.wallet import wallet_bp
from routes.stocks import stocks_bp

load_dotenv()

app = Flask(__name__)
init_db(app)

app.register_blueprint(wallet_bp)
app.register_blueprint(stocks_bp)

@app.route('/')
def index():
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(debug=True)
