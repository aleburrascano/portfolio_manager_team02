/**
 * Where the backend lives.
 *
 * Normally empty, in development *and* in production. Locally Vite's proxy
 * forwards `/api` and `/socket.io` to localhost:5000; deployed, vercel.json
 * rewrites the same two paths to the Railway service. Either way a relative
 * URL reaches the right place and the browser only ever talks to its own
 * origin, which is what keeps the session cookie first-party. Setting this
 * points the client straight at the backend and reintroduces the
 * third-party-cookie 401 the deploy was moved off (see the README).
 *
 * It stays as an escape hatch for pointing a local client at some other
 * backend. Both the HTTP client and the socket read it from here rather
 * than each reading the environment, so there is one answer to "which
 * backend" and one place that decides what a trailing slash means.
 */
export const API_ORIGIN = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')
