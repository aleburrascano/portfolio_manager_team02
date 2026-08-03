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
| `LOG_LEVEL` | Defaults to `INFO`, which logs one line per request with its status and duration. `WARNING` keeps only the slow ones, the 500s, and background work that failed. |
| `START_LIMIT_ORDER_POLLER` | Set to `false` to stop the background thread that fills conditional orders and redeems matured bonds. The only switch that keeps this process off the market data feed on a timer, which is why the test suite sets it — leave it alone otherwise, or nothing ever fills. |

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

The e2e suite starts its own server and client against a throwaway database,
with `MARKET_DATA=fake` so prices come from `services/fake_feed.py` rather
than from Yahoo. That is what lets it trade stocks and crypto, and watch a
conditional order actually fill, without depending on a third party being up
or on a company keeping its name.

## Layout

```
server/
  app.py        entry point — wires the app together
  api/          everything that speaks HTTP: schemas and validation, the
                error envelope, sessions, idempotency, HATEOAS links, the
                OpenAPI setup, request logging, the Socket.IO feed
    routes/     blueprints — HTTP only, no business logic
  services/     business logic, market data, domain exceptions
  db/           SQLAlchemy models, engine, request-scoped session
  migrations/   Alembic revisions — the source of schema history
  scripts/      seeding and password reset
client/src/
  api/          one module per resource, behind a shared fetch helper
  pages/        one per screen the address bar can reach
  components/
    layout/     the chrome every signed-in page sits inside
    ui/         presentational pieces that carry no domain logic
    portfolio/  what the dashboard is made of
    trading/    what the trade screens are made of
  context/      session-wide state and its providers
  hooks/        the live quote feed, idempotency keys
  lib/          formatting, input validation, backend origin
```

Layering runs one way: `api/ → services/ → db/`. Routes never touch the
database or `yfinance`; services never import Flask. A service raises from
`services/exceptions.py` to reject a request (each exception carries the status
it surfaces as), so routes carry no `try`/`except`. All market data access lives
in `services/market_data.py`, so swapping or stubbing the feed is a one-file
change.

Routes are served under `/api/v1`. Responses carry a `_links` map of related
endpoints, and errors are always `{'error': {'message': str, 'code': str}}`.

Browsable docs live at `/apidocs`, with the raw spec at `/apispec_1.json`.
flask-smorest builds that spec from the same marshmallow schemas that parse
incoming requests, so it can't describe a body the code would reject — one
declaration, used twice. Routes and their path parameters come from the
blueprints, so a new endpoint is documented as soon as it is registered.

Request shapes live in `api/schemas.py`; the rules behind them stay in
`api/validation.py`, which each field defers to. Adding a field means adding it
to the schema — the docs and the parser both follow from that.

## Deployment

The server runs on Railway (with its MySQL), the client on Vercel. Pushing to
`main` deploys both.

The browser never addresses Railway directly. `client/vercel.json` rewrites
`/api` and `/socket.io` to the Railway service, so every request the client
makes goes to its own origin — mirroring what Vite's proxy does locally. That
is not a detail: the session cookie has to be first-party, and a cookie set by
another domain is a third-party cookie, which Safari blocks outright and Chrome
is retiring. Pointed straight at Railway, signing in worked and then every
following request came back 401, in Safari and in any browser with third-party
cookies turned off.

The last rewrite in that file is the one client-side routing needs: anything
that isn't `/api`, `/socket.io`, or a real file is an address this app resolves
itself, so it has to be served `index.html`. Without it, opening
`/trade/stock/NVDA` directly — or reloading on it — 404s at the edge before the
app ever loads. (`vercel.json` is schema-validated and JSON has no comments, so
this note lives here rather than beside the rule.)

The one cost is that Vercel's rewrites don't carry a WebSocket upgrade, so the
quote feed settles on Socket.IO's long-polling transport. It was already
falling back to polling before this, so nothing was lost. A custom domain
(`app.example.com` and `api.example.com`) would make both first-party and keep
the upgrade, if the project ever gets one.

Migrations run on boot: the server starts with `alembic upgrade head`, so a
merged migration reaches the deployed database without anyone remembering to
apply it. Forgetting had already broken production twice, which is a worse
failure than the one being guarded against — a single service with one worker
gives concurrent upgrades little room to race, and `upgrade head` is a no-op
once there.

A failing migration stops the container from starting, and the previous
deployment keeps serving until a good one replaces it. The cost is that a
rollback is no longer just redeploying an older commit: the schema has already
moved, so going back means `alembic downgrade`.

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
goes for idempotency (`api/idempotency.py`) and the live quote feed
(`api/realtime.py`), which each explain themselves where they live.
