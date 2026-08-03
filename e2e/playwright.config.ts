import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const serverDir = path.join(rootDir, 'server')
const clientDir = path.join(rootDir, 'client')

/**
 * A database file of this run's own.
 *
 * Not a fixed name that gets deleted and rebuilt: Playwright brings the web
 * server up before globalSetup, and the health check the server is probed
 * with queries the database - so by the time setup wanted to delete the
 * file, the server already had it open, which on Windows is an unlink
 * error rather than a warning. A unique name means there is nothing to
 * delete and nothing to race. global-setup sweeps the old ones.
 *
 * Put on the environment so global-setup and the server agree on it
 * without either recomputing it.
 */
const dbPath = path.join(serverDir, `e2e-${Date.now()}.db`)
process.env.E2E_DB_PATH = dbPath
const databaseUrl = `sqlite:///${dbPath.replace(/\\/g, '/')}`

export default defineConfig({
  testDir: './tests',
  // Serialized rather than parallel: every test shares one SQLite file
  // through one Flask process, and SQLite has no statement busy-timeout
  // configured, so concurrent writers would intermittently hit "database
  // is locked" instead of a real failure.
  workers: 1,
  reporter: 'list',
  globalSetup: './global-setup.ts',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'python app.py',
      cwd: serverDir,
      url: 'http://localhost:5000/',
      // Never reused: a leftover server from a previous run is bound to
      // that run's database file, so every test would then be writing
      // somewhere this run never migrated.
      reuseExistingServer: false,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
        SECRET_KEY: 'e2e-test-secret',
        CORS_ORIGINS: 'http://localhost:5173',
        // Deterministic prices from services.fake_feed instead of live
        // Yahoo. Without it this suite could only trade bonds, asserted on
        // a real company's name ("Apple Inc.") staying put, and could never
        // watch a conditional order actually fill - which is the one thing
        // about them worth testing end to end.
        MARKET_DATA: 'fake',
        // Prices are a pure function of the date here, so a tick is cheap
        // and a test shouldn't wait five seconds to see a fill.
        POLL_INTERVAL_SECONDS: '1',
      },
    },
    {
      command: 'npm run dev',
      cwd: clientDir,
      url: 'http://localhost:5173/',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
