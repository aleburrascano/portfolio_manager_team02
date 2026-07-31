import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const serverDir = path.join(rootDir, 'server')
const clientDir = path.join(rootDir, 'client')
const dbPath = path.join(serverDir, 'e2e.db')
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
      reuseExistingServer: !process.env.CI,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
        SECRET_KEY: 'e2e-test-secret',
        CORS_ORIGINS: 'http://localhost:5173',
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
