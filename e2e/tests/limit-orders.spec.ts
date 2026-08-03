import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

// Limit orders are stocks-only, and stocks are priced from live yfinance
// data (unlike bonds), so there is no deterministic price to assert a fill
// against here. This spec covers placement and cancellation only - whether
// a crossed order actually fills is covered by the backend service test
// (services.limit_orders.evaluate_pending_orders) with a stubbed price.

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('limit'))

  await page.getByRole('button', { name: 'Deposit', exact: true }).click()
  await page.getByLabel('Amount').fill('5000')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Deposit $5,000.00' }).click()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$5,000.00')

  await page.getByRole('link', { name: 'Trade' }).click()
  await page.getByLabel('Search assets').fill('Apple')
  await page.getByRole('button', { name: /AAPL/ }).click()
  await expect(page.getByRole('heading', { name: 'Apple Inc.' })).toBeVisible()
})

test('places a limit order without touching the cash balance', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  // Priced far below any real quote, so it stays pending for the rest of
  // this test regardless of where AAPL actually trades right now.
  await page.getByLabel('Limit price').fill('0.01')
  await page.getByRole('button', { name: 'Review limit buy' }).click()

  await expect(page.getByRole('alertdialog')).toContainText('Pending until the price is met')
  await page.getByRole('button', { name: 'Place order' }).click()

  await expect(
    page.getByText(/Limit order placed: buy 1.00 AAPL if the price falls to or below \$0.01/),
  ).toBeVisible()

  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$5,000.00')
})

test('a placed order shows up under Open orders', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  await page.getByLabel('Limit price').fill('0.01')
  await page.getByRole('button', { name: 'Review limit buy' }).click()
  await page.getByRole('button', { name: 'Place order' }).click()
  await expect(page.getByText(/Limit order placed/)).toBeVisible()

  await page.getByRole('button', { name: '← Back' }).click()
  await page.getByRole('link', { name: 'Orders' }).click()

  const row = page.getByRole('row', { name: /AAPL/ })
  await expect(row).toContainText('buy')
  await expect(row).toContainText('limit')
  await expect(row).toContainText('1.00')
  // A limit buy waits for a fall, so the trigger reads as a ceiling.
  await expect(row).toContainText('≤ $0.01')
})

// The whole point of putting the asset type and the symbol in the address:
// this is a place, so it survives being opened cold.
test('an asset opens directly from its own address', async ({ page }) => {
  await page.goto('/trade/stock/AAPL')
  await expect(page.getByRole('heading', { name: 'Apple Inc.' })).toBeVisible()
})

test('the orders view has its own address', async ({ page }) => {
  await page.goto('/orders/stock')
  await expect(page.getByRole('button', { name: 'Open' })).toBeVisible()
})

test('an unknown address falls back to the dashboard', async ({ page }) => {
  await page.goto('/nowhere')
  await expect(page.locator('.wallet-balance')).toBeVisible()
})

test('cancelling an open order removes it from the list', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  await page.getByLabel('Limit price').fill('0.01')
  await page.getByRole('button', { name: 'Review limit buy' }).click()
  await page.getByRole('button', { name: 'Place order' }).click()
  await expect(page.getByText(/Limit order placed/)).toBeVisible()

  await page.getByRole('button', { name: '← Back' }).click()
  await page.getByRole('link', { name: 'Orders' }).click()
  await expect(page.getByRole('row', { name: /AAPL/ })).toBeVisible()

  // Exact, or it also matches the "Cancelled" status filter beside it.
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByText(/don't have any open orders/)).toBeVisible()

  // The order isn't gone, it moved - which is the point of the filter.
  await page.getByRole('button', { name: 'Cancelled' }).click()
  await expect(page.getByRole('row', { name: /AAPL/ })).toBeVisible()
})

test('an invalid limit price is blocked before the review step', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  await page.getByLabel('Limit price').fill('0')
  await page.getByRole('button', { name: 'Review limit buy' }).click()

  await expect(page.getByRole('alertdialog')).not.toBeVisible()
})
