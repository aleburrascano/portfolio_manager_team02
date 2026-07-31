import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

// Bonds are priced from their own terms rather than a live feed, so they
// are the deterministic, network-free way through this flow.

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('watch'))
})

test('a new account is offered most-active rather than an empty box', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Most active today' })).toBeVisible()
  await expect(page.getByText(/Nothing saved yet/)).toBeVisible()
})

test('saving an asset moves it onto the dashboard watchlist', async ({ page }) => {
  await page.getByRole('button', { name: 'Trade' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()

  const save = page.getByRole('button', { name: 'Save for later' })
  await expect(save).toHaveAttribute('aria-pressed', 'false')
  await save.click()
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await expect(page.getByRole('heading', { name: 'Watchlist' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Most active today' })).not.toBeVisible()
  await expect(page.getByRole('button', { name: /UST2Y/ })).toBeVisible()
})

test('the saved state survives a reload', async ({ page }) => {
  await page.getByRole('button', { name: 'Trade' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Save for later' }).click()
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()

  await page.reload()
  await expect(page.getByRole('button', { name: /UST2Y/ })).toBeVisible()
})

test('unsaving removes it again', async ({ page }) => {
  await page.getByRole('button', { name: 'Trade' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()

  await page.getByRole('button', { name: 'Save for later' }).click()
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()
  await page.getByRole('button', { name: 'Saved' }).click()
  await expect(page.getByRole('button', { name: 'Save for later' })).toBeVisible()

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await expect(page.getByRole('heading', { name: 'Most active today' })).toBeVisible()
})

test('a watchlist tile opens the asset it stands for', async ({ page }) => {
  await page.getByRole('button', { name: 'Trade' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Save for later' }).click()
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await page.getByRole('button', { name: /UST2Y/ }).click()

  await expect(page.getByRole('heading', { name: 'US Treasury Note 2Y' })).toBeVisible()
})
