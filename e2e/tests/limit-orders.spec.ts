import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

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
  await expect(row).toContainText('≤ $0.01')
})

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

test('a limit order that crosses fills, and says so', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  await page.getByLabel('Limit price').fill('2000')
  await page.getByRole('button', { name: 'Review limit buy' }).click()
  await page.getByRole('button', { name: 'Place order' }).click()
  await expect(page.getByText(/Limit order placed/)).toBeVisible()

  await expect(page.getByText('Limit order filled')).toBeVisible({ timeout: 15000 })
  await expect(page.getByText(/Bought 1\.00 AAPL at/)).toBeVisible()

  await page.getByRole('button', { name: '← Back' }).click()
  await page.getByRole('link', { name: 'Orders' }).click()
  await expect(page.getByText(/don't have any open orders/)).toBeVisible()

  await page.getByRole('button', { name: 'Filled' }).click()
  await expect(page.getByRole('row', { name: /AAPL/ })).toBeVisible()
})

test('a stop order fills when the price crosses the other way', async ({ page }) => {
  await page.getByRole('button', { name: 'Stop' }).click()
  await page.getByLabel('Stop price').fill('0.01')
  await page.getByRole('button', { name: 'Review stop buy' }).click()
  await page.getByRole('button', { name: 'Place order' }).click()

  await expect(page.getByText('Stop order filled')).toBeVisible({ timeout: 15000 })
})

test('a fill updates the balance without a reload', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  await page.getByLabel('Limit price').fill('2000')
  await page.getByRole('button', { name: 'Review limit buy' }).click()
  await page.getByRole('button', { name: 'Place order' }).click()

  await expect(page.getByText('Limit order filled')).toBeVisible({ timeout: 15000 })
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.locator('.wallet-balance')).not.toHaveText('$5,000.00')
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

  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByText(/don't have any open orders/)).toBeVisible()

  await page.getByRole('button', { name: 'Cancelled' }).click()
  await expect(page.getByRole('row', { name: /AAPL/ })).toBeVisible()
})

test('an invalid limit price is blocked before the review step', async ({ page }) => {
  await page.getByRole('button', { name: 'Limit' }).click()
  await page.getByLabel('Limit price').fill('0')
  await page.getByRole('button', { name: 'Review limit buy' }).click()

  await expect(page.getByRole('alertdialog')).not.toBeVisible()
})
