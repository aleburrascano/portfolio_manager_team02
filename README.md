# TreeTop Trading

TAP 2026 Project — a simulated trading app. Users get a cash wallet, browse live
market data, and buy or sell stocks, crypto and bonds against their balance.

![DB Schema](assets/db-schema.PNG)
![Wireframes](assets/wireframes.PNG)

**Stack** — Flask + SQLAlchemy on the server (MySQL in production, SQLite locally),
live prices from `yfinance` pushed over Socket.IO; React + TypeScript on the client,
built with Vite.

## Running it

Two processes, both needed.

```bash
# server — http://localhost:5000
cd server
python -m venv venv
./venv/Scripts/activate          # source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
alembic upgrade head             # creates or updates the schema
python app.py
```

```bash
# client — http://localhost:5173
cd client
npm install
npm run dev
```

The client proxies `/api` and `/socket.io` to the server, so run both.

### Configuration

Everything lives in `server/.env` (not committed):

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `sqlite:///dev.db`, or `mysql+mysqlconnector://user:pass@host/db`. Falls back to the `DB_*` variables if unset. |
| `SECRET_KEY` | Signs the session cookie. Without it sessions don't survive a restart. |
| `CORS_ORIGINS` | Comma-separated. Defaults to `http://localhost:5173`. |
| `CROSS_SITE_COOKIE` | Set to `1` only where the client is on a different domain than the server. Sends the session cookie as `SameSite=None; Secure`, which needs HTTPS — so it breaks local sign-in. |

MySQL needs its (empty) database to exist first; SQLite doesn't.

The client reads one variable, `VITE_API_URL`, from `client/.env`. Leave it unset
locally: Vite's proxy already forwards `/api` and `/socket.io` to port 5000, and
setting it would bypass that. Both folders have a `.env.example` to copy.

## Demo data

`scripts/seed` builds an account with ~2 years of history — stocks, crypto and
bonds, priced from real market data — which is what makes the dashboard's
performance chart, composition donut and holdings table worth looking at.

```bash
cd server
python -m scripts.seed --username demo --password demopassword --first Ada --last Lovelace
```

Then sign in as `demo` / `demopassword`. Re-running regenerates that user's
transactions, so it's safe to repeat.

To keep demo data away from your working database, point it somewhere separate:

```bash
DATABASE_URL=sqlite:///demo.db alembic upgrade head
DATABASE_URL=sqlite:///demo.db python -m scripts.seed
DATABASE_URL=sqlite:///demo.db python app.py
```

`scripts/set_password` resets a password if you need to get back into an account.

## Tests

```bash
cd server && pytest              # services and routes
cd client && npm test            # components and API layer
cd e2e    && npx playwright test # full stack, real browser
```

The e2e suite starts its own server and client against a throwaway database.

## Layout

```
server/
  routes/       blueprints — HTTP only, no business logic
  services/     business logic, market data, domain exceptions
  db/           SQLAlchemy models, engine, request-scoped session
  migrations/   Alembic revisions — the source of schema history
  scripts/      seeding and password reset
client/src/
  api/          one module per resource, behind a shared fetch helper
  pages/        one per navigation destination
  components/   reusable pieces
```

Layering runs one way: `routes/ → services/ → db/`. Routes never touch the
database or `yfinance`; services never import Flask. A service raises from
`services/exceptions.py` to reject a request (each exception carries the status
it surfaces as), so routes carry no `try`/`except`. All market data access lives
in `services/market_data.py`, so swapping or stubbing the feed is a one-file
change.

Routes are served under `/api/v1`. Responses carry a `_links` map of related
endpoints, and errors are always `{'error': {'message': str, 'code': str}}`.

Browsable docs live at `/apidocs`, with the raw spec at `/apispec_1.json`. The
route list is generated from Flask's URL map, so a new endpoint appears there as
soon as it is registered — nothing to remember. What can't be introspected, the
JSON body and any query parameters, is declared with `@documents` beside the
route; see `apidocs.py`.

## Deployment

The server runs on Railway (with its MySQL), the client on Vercel. Pushing to
`main` deploys both.

Migrations are the exception and are deliberately manual — three people merging
at once should not race `alembic upgrade head` against a shared database. After
merging a migration, run it once, from one machine, against the deployed
database.

## Changing the schema

Edit `db/models.py`, generate the migration, and read what it wrote before
committing it:

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

`alembic check` fails when the models and the migration history disagree.

The conventions the schema relies on — nothing derived is stored, timestamps are
UTC, transactions are append-only, `CHECK` constraints keep each type column
agreeing with the sign beside it — are documented in `db/models.py`. The same
goes for idempotency (`idempotency.py`) and the live quote feed (`realtime.py`),
which each explain themselves where they live.
