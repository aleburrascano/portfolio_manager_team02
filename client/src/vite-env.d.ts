/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Origin of the deployed backend, e.g. `https://portfolio.up.railway.app`.
   * Left unset in development, where Vite's proxy forwards `/api` and
   * `/socket.io` to the local server instead.
   */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
