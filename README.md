# Portfolio Manager

TAP 2026 Project — a simulated stock trading app. Users get a cash wallet, can search
live market data, and buy/sell stocks against their balance.

![DB Schema](assets/db-schema.PNG)
![Wireframes](assets/wireframes.PNG)

## Stack

- **Server**: Flask + SQLAlchemy (MySQL in production, SQLite for local dev), live market data via `yfinance`.
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

### Database

The server talks to the database through SQLAlchemy, so the backend is
switchable via a single `DATABASE_URL` in `.env`.

For local development, SQLite needs no setup — the tables are created on
first run:

```
DATABASE_URL=sqlite:///dev.db
```

For MySQL, create the database and load the schema first:

```bash
mysql -u root -p < db/schema/schema.sql
```

then either set `DATABASE_URL=mysql+mysqlconnector://root:password@localhost/portfolio_manager`,
or leave it blank and fill in the `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`
variables it falls back to.

Optionally load ~2 years of demo transactions for a user:

```bash
python -m db.seed --first Demo --last User
```

Run the server:

```bash
python app.py
```

The API is available at `http://localhost:5000`.

### Endpoints

All routes are served under an `/api/v1` prefix (kept separate from Vite's
build output, which also lives under `/assets` in production, and versioned
so future breaking changes can live alongside it at `/api/v2`).

| Method | Route                                  | Description                                  |
| ------ | ---------------------------------------- | --------------------------------------------- |
| GET    | `/api/v1/users/:userId/balance`          | Get a user's wallet balance                   |
| GET    | `/api/v1/users/:userId/transactions`     | Get a user's chronological transaction history |
| GET    | `/api/v1/assets/:assetType/search?q=`    | Search assets by ticker or name (assetType: stock, crypto) |
| GET    | `/api/v1/assets/:assetType/popular`      | Get popular assets of that type               |

Responses include a `_links` map of related endpoint URLs (HATEOAS), and
errors are always shaped as `{'error': {'message': str, 'code': str}}`.

Set `CORS_ORIGINS` (comma-separated) in `.env` to allow the client's origin;
defaults to `http://localhost:5173`.

## Client setup

```bash
cd client
npm install
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies `/api` requests to
the Flask server at `http://localhost:5000`, so run both at once.

Other scripts: `npm run build`, `npm run lint`, `npm run preview`.
