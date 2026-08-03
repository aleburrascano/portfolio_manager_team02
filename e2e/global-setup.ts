import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const serverDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../server')

/**
 * Migrate this run's throwaway SQLite database, and clear away older ones.
 *
 * Migrated through real Alembic revisions rather than Base.metadata
 * .create_all so the bond catalog migration seeds - several specs trade
 * bonds, which are priced from that catalog.
 *
 * The file is this run's own (playwright.config puts the path on the
 * environment), so there is nothing here to delete first: the server is
 * already up by the time this runs, and it holds whichever database it was
 * pointed at.
 */
export default function globalSetup(): void {
  const dbPath = process.env.E2E_DB_PATH
  if (!dbPath) throw new Error('E2E_DB_PATH is not set; playwright.config should have set it')

  sweepOldDatabases(path.basename(dbPath))

  execFileSync('alembic', ['upgrade', 'head'], {
    cwd: serverDir,
    env: { ...process.env, DATABASE_URL: `sqlite:///${dbPath.replace(/\\/g, '/')}` },
    stdio: 'inherit',
    shell: true,
  })
}

/** Best effort: a file another run still holds is skipped, not fatal. */
function sweepOldDatabases(keep: string): void {
  for (const name of fs.readdirSync(serverDir)) {
    if (!/^e2e-\d+\.db/.test(name) || name.startsWith(keep)) continue
    try {
      fs.unlinkSync(path.join(serverDir, name))
    } catch {
    }
  }
}
