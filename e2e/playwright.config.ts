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
      reuseExistingServer: false,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
        SECRET_KEY: 'e2e-test-secret',
        CORS_ORIGINS: 'http://localhost:5173',
        MARKET_DATA: 'fake',
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
