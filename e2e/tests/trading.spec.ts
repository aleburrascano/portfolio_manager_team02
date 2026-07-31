import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

// Bonds are priced from their own terms (services/bond_pricing.py) rather
// than a live feed, so trading one is a deterministic, network-free path
// through buy/sell - unlike stocks and crypto, which hit real yfinance.

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('trade'))
  await page.getByRole('button', { name: 'Deposit' }).click()
  await page.getByLabel('Amount').fill('5000')
  await page.getByRole('button', { name: 'Submit Transaction' }).click()
  await expect(page.locator('.balance')).toHaveText('$5,000.00')

  await page.getByRole('button', { name: 'Trade Assets' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await expect(page.getByText('Most Active Bonds')).toBeVisible()
})

test('buys a bond and shows it on the dashboard', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await expect(page.getByRole('heading', { name: 'US Treasury Note 2Y' })).toBeVisible()

  await page.getByRole('button', { name: 'Submit' }).click()
  await expect(page.getByText('Purchase successful!')).toBeVisible()

  await page.getByRole('button', { name: 'Dashboard' }).click()
  await expect(page.locator('#dashboard-content')).not.toContainText('No holdings to display.')
})

test('sells a held bond back', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('spinbutton', { name: /Quantity/ }).fill('2')
  await page.getByRole('button', { name: 'Submit' }).click()
  await expect(page.getByText('Purchase successful!')).toBeVisible()

  await page.getByRole('button', { name: 'Sell' }).click()
  await page.getByRole('spinbutton', { name: /Quantity/ }).fill('1')
  await page.getByRole('button', { name: 'Submit' }).click()

  await expect(page.getByText('Sale successful!')).toBeVisible()
})

test('rejects selling more than is held', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Sell' }).click()
  await page.getByRole('spinbutton', { name: /Quantity/ }).fill('1')
  await page.getByRole('button', { name: 'Submit' }).click()

  await expect(page.getByText('Not enough shares!')).toBeVisible()
})

test('appears in the transaction history after a purchase', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Submit' }).click()
  await expect(page.getByText('Purchase successful!')).toBeVisible()

  await page.getByRole('button', { name: 'Transaction History' }).click()
  await expect(page.getByText('Bought 1 UST2Y')).toBeVisible()
})
