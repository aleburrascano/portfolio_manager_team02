# Client

The TreeTop Trading front end: React + TypeScript, built with Vite.

```bash
npm install
npm run dev      # http://localhost:5173
npm test         # vitest
npm run lint
npm run build    # tsc -b && vite build
```

The dev server proxies `/api` and `/socket.io` to the server on port 5000, so
run that too. See the root [README](../README.md) for both processes, and
[ARCHITECTURE.md](../ARCHITECTURE.md) for the environment variables and how the
deployed client reaches the backend.

## Layout

```
src/
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

Each component keeps its stylesheet and its test beside it. Styles shared
across screens (the type scale, buttons, `.card`, `.skeleton`) live in
`index.css`; a page's own stylesheet scopes its layout rules under that page's
root id rather than reaching into components globally.
