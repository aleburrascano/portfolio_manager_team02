# Architecture and operations

Everything behind [the README](README.md): how the code is arranged, what the API
guarantees, how to configure it, and what deployment expects.

- [Stack](#stack)
- [How the server is layered](#how-the-server-is-layered)
- [API conventions](#api-conventions)
- [Idempotency](#idempotency)
- [Sessions and authorization](#sessions-and-authorization)
- [Market data](#market-data)
- [The live quote feed](#the-live-quote-feed)
- [The background poller](#the-background-poller)
- [How bonds are priced](#how-bonds-are-priced)
- [How the client is arranged](#how-the-client-is-arranged)
- [Configuration](#configuration)
- [Database and migrations](#database-and-migrations)
- [Testing](#testing)
- [Deployment](#deployment)
- [Observability](#observability)

## Stack

Flask + SQLAlchemy on the server (MySQL in production, SQLite locally), live
prices from `yfinance` pushed over Socket.IO; React + TypeScript on the client,
built with Vite; Alembic for schema history; pytest, Vitest and Playwright for
tests.

```
server/
  app.py        entry point, wires the app together
  api/          everything that speaks HTTP: schemas and validation, the
                error envelope, sessions, idempotency, HATEOAS links, the
                OpenAPI setup, request logging, the Socket.IO feed
    routes/     blueprints: HTTP only, no business logic
  services/     business logic, market data, domain exceptions
  db/           SQLAlchemy models, engine, request-scoped session
  migrations/   Alembic revisions, the source of schema history
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

## How the server is layered

Layering runs one way: `api/ → services/ → db/`.

- Routes never touch the database or `yfinance`.
- Services never import Flask.
- A service raises from [`services/exceptions.py`](server/services/exceptions.py)
  to reject a request, and each exception carries the HTTP status it surfaces as,
  so routes carry no `try`/`except`.
- All market data access lives in
  [`services/market_data.py`](server/services/market_data.py), which is why
  swapping or stubbing the feed is a one-file change.

Everything type-specific about an asset lives behind an `AssetProvider` in
[`services/asset_providers.py`](server/services/asset_providers.py): how to
search it, quote it, chart it, price a trade in it, and whether it takes
conditional orders. Routes and the buy/sell service never branch on asset type,
so adding a kind of asset means adding a provider class and registering it.

The client reads that registry too. `GET /assets/types` is deliberately the first
call it makes: the tabs, the labels, which types show a live indicator and which
offer limit orders all come from the server, so an asset type added on one side
does not need a matching edit on the other.

## API conventions

Routes are served under `/api/v1`.

- **Errors** are always `{'error': {'message': str, 'code': str}}`, whether the
  route returned them or raised.
- **Responses carry `_links`**, a map of related endpoints. Most are an
  affordance; two are load-bearing: the client follows `cancel` on a limit order
  and `export` on the transaction history rather than building either URL.
- **Docs** are browsable at `/apidocs`, with the raw spec at `/apispec_1.json`.
  flask-smorest builds that spec from the same marshmallow schemas that parse
  incoming requests, so it cannot describe a body the code would reject. One
  declaration, used twice. Routes and their path parameters come from the
  blueprints, so a new endpoint is documented as soon as it is registered.
- **Request shapes** live in [`api/schemas.py`](server/api/schemas.py); the rules
  behind them stay in [`api/validation.py`](server/api/validation.py), which each
  field defers to. Adding a field means adding it to the schema; the docs and
  the parser both follow from that.
- **Amounts parse to `Decimal`**, not float, so the value stored is exactly the
  value sent. The client's own checks are a convenience for the person typing,
  never a guarantee; everything is re-checked here.

## Idempotency

A client that never gets a response has no way to know whether its deposit or
trade landed. Retrying blind risks doing it twice; not retrying risks not doing
it at all.

Every money-moving route accepts an optional `Idempotency-Key` header. The first
request to claim a key does the work and its response is stored; any later
request carrying the same key gets that same response back without the work
happening again. Claiming is atomic: the composite primary key on
`IdempotentRequests` means two concurrent requests race to insert and exactly one
wins. A rejected request releases its key, so you can correct the input and retry
with the same one. Records are swept per user on the next request, so nothing
needs a cron job to stay bounded.

On the client, [`hooks/idempotency.ts`](client/src/hooks/idempotency.ts) mints one
key per *intent*: resubmitting the same amount reuses it, while depositing the
same amount twice on purpose is a new intent and a new key.

## Sessions and authorization

The signed session cookie is the only thing that establishes identity. A
`user_id` in a route is a claim about *which* user is being addressed, never
proof of who is asking. `require_user` checks that the caller is logged in and
that the ID in the path is their own. The cookie is httpOnly, so the client holds
no token at all and every call is made with `credentials: 'include'`.

## Market data

[`services/market_data.py`](server/services/market_data.py) is the one place
`yfinance` is called, and therefore the only sensible place to cache it. Every
lookup goes through a TTL cache sized to how fast the thing it holds actually
moves:

| Cached | For | Why |
| --- | --- | --- |
| Prices | 5s | Moves constantly; also means a trade books at the price the user was just shown |
| Daily closes | 15m | A year of history per ticker, refetched on every dashboard load without this |
| Analyst ratings | 1h | Changes on the analysts' schedule, not the market's |
| Searches | 5m | |
| Most-active screen | 60s | |
| Names, asset classification | 24h | A company's name and exchange do not change |

Callers are unaware of it: they ask for what they need as often as they need it,
and the fan-out that used to follow collapses onto shared entries. Lookups are
batched: one call quotes a whole watchlist or holdings table rather than one call
per row. A failure is never cached, so an outage is retried rather than
remembered.

Two levels of strictness, on purpose: `trade_price` raises
`MarketDataUnavailable` rather than let a trade book against a guessed price,
while `valuation_price` is best-effort, because a portfolio breakdown should
still render when one ticker can't be quoted.

## The live quote feed

[`api/realtime.py`](server/api/realtime.py) pushes a `quote` event to clients
subscribed to that symbol. Only symbols with at least one subscriber are fetched,
so an idle server does no upstream work at all.

Re-prices come from two places:

1. **The stream.** [`services/live_prices.py`](server/services/live_prices.py)
   owns one upstream connection on its own asyncio loop in its own thread, and
   pushes a symbol the moment it moves. Every upstream send is scheduled onto
   that loop rather than made from the calling thread, because subscriptions
   arrive on Socket.IO handler threads while the loop is reading messages.
2. **A five-second poll**, which covers whatever hasn't streamed recently. It is
   not a leftover: it handles a shut market, a symbol the stream doesn't carry,
   and a stream that has quietly died, none of which announce themselves. An
   open market makes the poll nearly free, since a streamed symbol is filtered
   out before anything is fetched.

Quotes are public, matching the REST asset routes. The exception is
`orderFilled` and `bondRedeemed`: each session joins a room named for its
logged-in user on connect, identified from the same signed cookie the REST routes
trust, so a fill reaches its owner's tabs and nobody else's.

Only the fields that changed are sent, so the client merges an update over what
it already has rather than replacing it.

## The background poller

[`limit_order_poller.py`](server/limit_order_poller.py) runs work that has to
happen whether or not anyone is watching: a limit order has to keep being checked
against the market, and a bond matures on a date rather than when someone next
signs in. Each tick opens its own Flask app context so services can use
`get_session()` exactly as a request would.

Filling is deliberately not in the poller module. `evaluate_pending_orders()`
lives in [`services/limit_orders.py`](server/services/limit_orders.py), which
makes it unit-testable the same way buy and sell are, with the sleep loop as a
thin wrapper around it.

How a fill works:

- One batched quote call screens every pending ticker. On any given tick nearly
  all of them can't fill, and those cost nothing further.
- Tickers that look like they've crossed are then priced individually through
  `trade_price` (the same call a market order books at), so a fill executes at
  the authoritative price, not the indicative one used to screen it.
- Each candidate is locked and resolved independently, so one slow or stuck fill
  never blocks another user's.
- If the cash or the shares are no longer there at fill time, the order is left
  **pending** rather than cancelled. There is no reservation system, so
  "temporarily can't afford it" and "never will" look identical from here, and
  the safer default for a good-till-cancelled order is to keep trying.

Exactly one process should run it. Under `python app.py` the Werkzeug reloader
imports the module twice and only the child holds the sockets, so the parent is
excluded, otherwise both race for the same orders and a fill committed by the
parent has nobody to announce it to.

## How bonds are priced

Bonds are reference data, not a feed. A bond's price is the present value of its
remaining coupon payments plus face value, discounted at its fixed market yield.
See [`services/bond_pricing.py`](server/services/bond_pricing.py). That price
converges to par as maturity approaches, which is why a matured position stops
moving and is redeemed at face value rather than left sitting in the holdings
table forever.

Because they're priced from local terms, bonds have no volume, no intraday range,
no analyst coverage and nothing to stream, so the provider returns nulls for
those rather than inventing them.

## How the client is arranged

- **One module per resource** under `api/`, behind a shared fetch helper that
  unwraps the JSON and throws the server's own error message, carrying the status
  for the callers that need to tell "not signed in" from "server is broken".
- **Every screen the address bar can reach is a page.** The asset type, the
  selected symbol, and whether the orders view is showing are all read from the
  URL rather than held in state, so each is shareable, bookmarkable and reachable
  with the back button.
- **Session-wide state is context**: the balance (refreshed whenever a fill or a
  redemption arrives) and the asset-type registry.
- **The shell mounts once.** Header, sidebar and the toast layer sit outside the
  router outlet, so navigating doesn't drop socket subscriptions or a notice
  currently on screen.
- **Each component keeps its stylesheet and its test beside it.** Shared styles
  (the type scale, buttons, `.card`, `.skeleton`) live in `index.css`; a page's
  own stylesheet scopes its layout rules under that page's root id rather than
  reaching into components globally.
- **Timestamps are rendered deliberately.** The API speaks UTC and the browser
  mangles it two different ways, so [`lib/dates.ts`](client/src/lib/dates.ts)
  supplies the missing intent: calendar days render in UTC so a chart point is
  the same day for every viewer, and trade times render in US market time so a
  trade reads at the hour the exchange saw it.

## Configuration

Server configuration lives in `server/.env` (not committed; copy `.env.example`).

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `sqlite:///dev.db`, or `mysql+mysqlconnector://user:pass@host/db`. Falls back to the `DB_*` variables if unset. |
| `SECRET_KEY` | Signs the session cookie. Without it sessions don't survive a restart. |
| `CORS_ORIGINS` | Comma-separated browser origins. Defaults to `http://localhost:5173`. Deployed, it must name the **frontend's** origin. See [Deployment](#deployment). |
| `CROSS_SITE_COOKIE` | Set to `1` only where the client is on a different domain than the server. Sends the session cookie as `SameSite=None; Secure`, which needs HTTPS, so it breaks local sign-in. |
| `LOG_LEVEL` | Defaults to `INFO`, which logs one line per request with its status and duration. `WARNING` keeps only the slow ones, the 500s, and background work that failed. |
| `START_LIMIT_ORDER_POLLER` | Set to `false` to stop the background thread that fills conditional orders and redeems matured bonds. The only switch that keeps this process off the market data feed on a timer, which is why the test suite sets it. Leave it alone otherwise, or nothing ever fills. |
| `POLL_INTERVAL_SECONDS` | How often that thread ticks. Defaults to 5. |
| `MARKET_DATA` | Set to `fake` to replace the upstream feed with the deterministic stand-in in [`services/fake_feed.py`](server/services/fake_feed.py). Used by the e2e suite. |

MySQL needs its (empty) database to exist first; SQLite doesn't.

The client reads one variable, `VITE_API_URL`, from `client/.env`. **Leave it
unset**, in development *and* in production. Locally Vite's proxy forwards
`/api` and `/socket.io` to port 5000; deployed, `vercel.json` rewrites the same
two paths to Railway. Either way the browser only ever talks to its own origin,
which is what keeps the session cookie first-party. It exists as an escape hatch
for pointing a local client at some other backend.

## Database and migrations

Which database is used is decided entirely by `DATABASE_URL`, so the same code
runs against MySQL in production and SQLite locally. Timestamps are UTC
everywhere: the MySQL session timezone is pinned on connect so the database's own
`now()` agrees with what Python writes.

Balance-affecting requests take a row lock on the user (`SELECT ... FOR UPDATE`),
serializing concurrent buys, sells and withdrawals for that user so the balance
and holdings checks can't race. SQLite has no such clause and serializes writers
itself, so the lock is skipped there.

### Changing the schema

Edit `db/models.py`, generate the migration, and read what it wrote before
committing it:

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

`alembic check` fails when the models and the migration history disagree. Every
persistent database, MySQL and SQLite files alike, is built and updated this
way, so there is one schema history rather than two ways to build a schema.

## Testing

```bash
cd server && pytest              # services and routes
cd client && npm test            # components and API layer
cd e2e    && npx playwright test # full stack, real browser
```

The e2e suite starts its own server and client against a throwaway SQLite
database (migrated through real Alembic revisions, so the bond catalog seeds),
with `MARKET_DATA=fake` so prices come from
[`services/fake_feed.py`](server/services/fake_feed.py) rather than from Yahoo.

That stand-in is installed over `market_data`'s fetch primitives only, so the
caching, batching, classification and error handling under test are the real
ones. Prices are a pure function of (symbol, date): stable within a run, stable
across runs, and different enough per symbol that a test asserting on one is
asserting on something. That is what lets the suite trade stocks and crypto and
watch a conditional order actually fill, without depending on a third party being
up or on a company keeping its name.

CI runs all three on every push to `main` and every pull request, with the e2e
job gated behind the unit suites and a Playwright report uploaded on failure.

## Deployment

The server runs on Railway (with its MySQL), the client on Vercel. Pushing to
`main` deploys both.

### The browser never addresses Railway directly

`client/vercel.json` rewrites `/api` and `/socket.io` to the Railway service, so
every request the client makes goes to its own origin, mirroring what Vite's
proxy does locally. That is not a detail: the session cookie has to be
first-party, and a cookie set by another domain is a third-party cookie, which
Safari blocks outright and Chrome is retiring. Pointed straight at Railway,
signing in worked and then every following request came back 401, in Safari and
in any browser with third-party cookies turned off.

The last rewrite in that file is the one client-side routing needs: anything that
isn't `/api`, `/socket.io`, or a real file is an address this app resolves
itself, so it has to be served `index.html`. Without it, opening
`/trade/stock/NVDA` directly (or reloading on it) 404s at the edge before the
app ever loads. (`vercel.json` is schema-validated and JSON has no comments,
which is why this note lives here rather than beside the rule.)

The one cost is that Vercel's rewrites don't carry a WebSocket upgrade, so the
quote feed settles on Socket.IO's long-polling transport. It was already falling
back to polling before this, so nothing was lost. A custom domain
(`app.example.com` and `api.example.com`) would make both first-party and keep
the upgrade, if the project ever gets one.

### CORS_ORIGINS has to name the Vercel origins

The proxy forwards the browser's `Origin` header unchanged, so what arrives is
the domain the page was loaded from, not the one serving the request. Getting
this wrong breaks the quote feed and very little else, in a way that reads as a
network fault rather than a config one: Engine.IO checks `Origin` only when the
browser sends one, which it does on long-polling's POSTs and not on its GETs, so
exactly half the `/socket.io` requests answer `400 Not an accepted origin`, the
feed reconnects forever, and every price tile sits under "Reconnecting". The boot
log prints the parsed list, so `railway logs` says what the server will actually
accept.

Listing origins one by one is not enough, which is how this last went wrong.
Vercel serves each deployment on its own hostname
(`<project>-<hash>-<team>.vercel.app`) and each branch on another, so a list that
is right today is stale on the next push. Opening the app from the dashboard's
Visit button, which uses the per-deployment URL, hit the 400 every time. Entries
therefore accept `*`:

```
CORS_ORIGINS=https://treetop.vercel.app,https://treetop-*.vercel.app
```

Scoped to the project's own prefix rather than `*.vercel.app`, so it doesn't
admit every site on the platform.

### Migrations run on boot

The server starts with `alembic upgrade head` (see `server/Procfile`), so a
merged migration reaches the deployed database without anyone remembering to
apply it. Forgetting had already broken production twice, which is a worse
failure than the one being guarded against: a single service with one worker
gives concurrent upgrades little room to race, and `upgrade head` is a no-op once
there.

A failing migration stops the container from starting, and the previous
deployment keeps serving until a good one replaces it. The cost is that a
rollback is no longer just redeploying an older commit: the schema has already
moved, so going back means `alembic downgrade`.

## Observability

`GET /` answers 200 while the process can serve at all, and says separately
whether the database is reachable, checked with an actual query, because a pool
that has lost its connection looks identical to a healthy one until something
asks it for a row. A 503 there would tell a platform to replace a container that
is merely waiting on its database. The same response reports market-data cache
sizes and hit rates.

Requests are logged one line each, after the response, with the status and how
long it took; anything over two seconds is logged at `WARNING` and a 500 at
`ERROR`. Deliberately not a structured logging library: one line per request is
what a single-service deployment reads through `railway logs`.
