import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const serverDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../server')
const dbPath = path.join(serverDir, 'e2e.db')

/**
 * Rebuild a throwaway SQLite database via the real Alembic migrations
 * (rather than Base.metadata.create_all) so the bond catalog migration
 * seeds - e2e trades against bonds, which need no live market data.
 */
export default function globalSetup(): void {
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath)

  const databaseUrl = `sqlite:///${dbPath.replace(/\\/g, '/')}`
  execFileSync('alembic', ['upgrade', 'head'], {
    cwd: serverDir,
    env: { ...process.env, DATABASE_URL: databaseUrl },
    stdio: 'inherit',
    shell: true,
  })
}
