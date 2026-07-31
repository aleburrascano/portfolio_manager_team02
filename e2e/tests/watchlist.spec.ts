import { expect, test, type Page } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

// Bonds are priced from their own terms rather than a live feed, so they
// are the deterministic, network-free way through this flow.

/** Open the bond used throughout these tests. */
async function openBond(page: Page) {
  await page.getByRole('button', { name: 'Trade' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
}

/**
 * Save (or unsave) and wait for the request to land.
 *
 * The button is optimistic - it flips before the server has answered, so
 * that a bookmark doesn't cost a spinner. That means the label alone is
 * not evidence of persistence, and a test that reloads on the label is
 * testing a race rather than the feature.
 */
async function toggleSave(page: Page, from: 'Save for later' | 'Saved') {
  const method = from === 'Save for later' ? 'PUT' : 'DELETE'
  const settled = page.waitForResponse(
    (response) =>
      response.url().includes('/watchlist/') && response.request().method() === method,
  )
  await page.getByRole('button', { name: from, exact: true }).click()
  await settled
}

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('watch'))
})

test('a new account is offered most-active rather than an empty box', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Most active today' })).toBeVisible()
  await expect(page.getByText(/Nothing saved yet/)).toBeVisible()
})

test('saving an asset moves it onto the dashboard watchlist', async ({ page }) => {
  await openBond(page)

  const save = page.getByRole('button', { name: 'Save for later' })
  await expect(save).toHaveAttribute('aria-pressed', 'false')
  await toggleSave(page, 'Save for later')
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await expect(page.getByRole('heading', { name: 'Watchlist' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Most active today' })).not.toBeVisible()
  await expect(page.getByRole('button', { name: /UST2Y/ })).toBeVisible()
})

test('the saved state survives a reload', async ({ page }) => {
  await openBond(page)
  await toggleSave(page, 'Save for later')

  await page.reload()
  await expect(page.getByRole('button', { name: /UST2Y/ })).toBeVisible()
})

test('unsaving removes it again', async ({ page }) => {
  await openBond(page)
  await toggleSave(page, 'Save for later')
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()

  await toggleSave(page, 'Saved')
  await expect(page.getByRole('button', { name: 'Save for later' })).toBeVisible()

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await expect(page.getByRole('heading', { name: 'Most active today' })).toBeVisible()
})

test('a watchlist tile opens the asset it stands for', async ({ page }) => {
  await openBond(page)
  await toggleSave(page, 'Save for later')

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await page.getByRole('button', { name: /UST2Y/ }).click()

  await expect(page.getByRole('heading', { name: 'US Treasury Note 2Y' })).toBeVisible()
})
