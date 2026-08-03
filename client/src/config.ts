/**
 * Where the backend lives.
 *
 * Empty in development: Vite's proxy forwards `/api` and `/socket.io` to
 * localhost:5000, so a relative URL reaches the right place. Deployed, the
 * frontend and the backend are on different domains and no proxy sits
 * between them, so the origin has to be named outright.
 *
 * Both the HTTP client and the socket read it from here rather than each
 * reading the environment, so there is one answer to "which backend" and
 * one place that decides what a trailing slash means.
 */
export const API_ORIGIN = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')
