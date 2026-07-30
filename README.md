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
server/
  app.py            Flask entry point: config, blueprints
  authorization.py  session identity + the require_user route guard
  errors.py         the single JSON error envelope, and the handlers feeding it
  links.py          HATEOAS _links builders
  routes/           blueprints - HTTP only, no business logic
  services/         business logic, market data, domain exceptions
  db/               SQLAlchemy models, engine/session, seed + admin scripts
  migrations/       Alembic revisions - the one source of schema history
client/
  src/api/          one module per resource, behind a shared fetch helper
  src/pages/        one per sidebar destination
  src/components/   reusable pieces
assets/             DB schema and wireframe references
```

Layering runs one way: `routes/ → services/ → db/`. Routes never touch the
database or `yfinance` directly, and services never import Flask. A service
raises from `services/exceptions.py` to reject a request (each exception
carries the HTTP status it surfaces as), so routes carry no `try`/`except`.
All market data access lives in `services/market_data.py`, so swapping or
stubbing the price feed is a one-file change.

## Server setup

```bash
cd server
python -m venv venv
./venv/Scripts/activate        # or `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```

### Database

The server talks to the database through SQLAlchemy, so the backend is
switchable via a single `DATABASE_URL` in `.env`:

```
DATABASE_URL=sqlite:///dev.db                                              # local dev
DATABASE_URL=mysql+mysqlconnector://root:password@localhost/portfolio_manager
```

Leave it blank to fall back to the `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`
variables. MySQL needs its (empty) database to exist first; SQLite doesn't.

Create or update the schema with Alembic — the same command for either
backend, and the only supported way to build one:

```bash
alembic upgrade head
```

Optionally load ~2 years of demo transactions for a user:

```bash
python -m db.seed --first Demo --last User
```

#### Changing the schema

Edit `db/models.py`, then autogenerate the migration and read what it wrote
before committing it:

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

`alembic check` fails when the models and the migration history disagree,
which is what keeps them from drifting apart — worth running in CI.

Two notes for existing databases. One created before Alembic was adopted
already has the `0001` schema, so tell Alembic that rather than re-running
it:

```bash
alembic stamp 0001 && alembic upgrade head
```

And migration `0002` backfills pre-existing users with an empty password
hash, which never matches, so those accounts can't be logged into until a
password is set:

```bash
python -m db.set_password --list
python -m db.set_password <username> <password>
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
| POST   | `/api/v1/auth/register`                  | Create an account (username, password, name)  |
| POST   | `/api/v1/auth/login`                     | Log in with a username and password           |
| POST   | `/api/v1/auth/logout`                    | End the current session                       |
| GET    | `/api/v1/auth/me`                        | Get the user owning the current session       |
| GET    | `/api/v1/users/:userId/balance`          | Get a user's wallet balance                   |
| GET    | `/api/v1/users/:userId/transactions`     | Get a user's chronological transaction history |
| GET    | `/api/v1/assets/:assetType/search?q=`    | Search assets by ticker or name (assetType: stock, crypto) |
| GET    | `/api/v1/assets/:assetType/popular`      | Get popular assets of that type               |

Responses include a `_links` map of related endpoint URLs (HATEOAS), and
errors are always shaped as `{'error': {'message': str, 'code': str}}`.

The four routes that move money — `deposit`, `withdraw`, `buy`, `sell` —
accept an optional `Idempotency-Key` header so a retry can't do the work
twice. The first request to claim a key does the work and its response is
stored; a repeat carrying the same key gets that response back without
re-executing. Reusing a key for a *different* request is a 409 rather than
a wrong replay, and a rejected request releases its key so the caller can
correct it and retry with the same one. Omitting the header keeps the old
behaviour.

Every `/users/:userId/...` route is session-scoped: logging in sets a signed
httpOnly cookie, and a request without one gets a 401 while a request for a
different user's `:userId` gets a 403. Set `SECRET_KEY` in `.env` to sign
those cookies — without it the app falls back to a per-process random key,
so sessions won't survive a restart. The asset quote/search routes stay
public.

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
