# Portfolio Manager

TAP 2026 Project — a simulated stock trading app. Users get a cash wallet, can search
live market data, and buy/sell stocks against their balance.

![DB Schema](assets/db-schema.PNG)
![Wireframes](assets/wireframes.PNG)

## Stack

- **Server**: Flask + MySQL (`mysql-connector-python`), live market data via `yfinance`.
- **Client**: React + TypeScript, built with Vite.

## Project structure

```
server/   Flask API (routes/, services/, db/)
client/   React + Vite frontend
assets/   DB schema and wireframe references
```

## Server setup

```bash
cd server
python -m venv venv
./venv/Scripts/activate        # or `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```

Create a MySQL database and load the schema:

```bash
mysql -u root -p < db/schema/schema.sql
```

Copy `.env.example` to `.env` and fill in your MySQL credentials:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=
DB_NAME=portfolio_manager
```

Run the server:

```bash
python app.py
```

The API is available at `http://localhost:5000`.

### Endpoints

| Method | Route                          | Description                                  |
| ------ | ------------------------------ | --------------------------------------------- |
| GET    | `/users/:userId/balance`       | Get a user's wallet balance                   |
| GET    | `/users/:userId/transactions`  | Get a user's chronological transaction history |
| GET    | `/assets/:assetType/search?q=` | Search assets by ticker or name (assetType: stock, crypto) |
| GET    | `/assets/:assetType/popular`   | Get the top 10 most actively traded assets of that type |

## Client setup

```bash
cd client
npm install
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies `/users` and `/assets`
requests to the Flask server at `http://localhost:5000`, so run both at once.

Other scripts: `npm run build`, `npm run lint`, `npm run preview`.
