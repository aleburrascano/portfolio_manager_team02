import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('trade'))

  await page.getByRole('button', { name: 'Deposit', exact: true }).click()
  await page.getByLabel('Amount').fill('5000')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Deposit $5,000.00' }).click()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$5,000.00')

  await page.getByRole('link', { name: 'Trade' }).click()
  await page.getByRole('button', { name: 'Bonds' }).click()
  await expect(page.getByText('Most active bonds')).toBeVisible()
})

test('buys a bond and lists it in holdings', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await expect(page.getByRole('heading', { name: 'US Treasury Note 2Y' })).toBeVisible()

  await page.getByRole('button', { name: 'Review buy' }).click()

  await expect(page.getByRole('alertdialog')).toContainText('Cash after')
  await page.getByRole('button', { name: 'Buy 1.00 UST2Y' }).click()

  await expect(page.getByText(/Bought 1\.00 UST2Y for/)).toBeVisible()

  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.getByRole('table').filter({ hasText: 'UST2Y' })).toBeVisible()
})

test('sells a held bond back', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('spinbutton', { name: /Quantity/ }).fill('2')
  await page.getByRole('button', { name: 'Review buy' }).click()
  await page.getByRole('button', { name: 'Buy 2.00 UST2Y' }).click()
  await expect(page.getByText(/Bought 2\.00 UST2Y for/)).toBeVisible()

  await page.getByRole('button', { name: 'Sell', exact: true }).click()
  await page.getByRole('spinbutton', { name: /Quantity/ }).fill('1')
  await page.getByRole('button', { name: 'Review sell' }).click()
  await page.getByRole('button', { name: 'Sell 1.00 UST2Y' }).click()

  await expect(page.getByText(/Sold 1\.00 UST2Y for/)).toBeVisible()
})

test('can back out of a trade at the review step', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Review buy' }).click()

  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(page.getByRole('alertdialog')).not.toBeVisible()
  await expect(page.getByText(/Bought/)).not.toBeVisible()
})

test('rejects selling more than is held, and says how much is held', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Sell', exact: true }).click()
  await page.getByRole('spinbutton', { name: /Quantity/ }).fill('1')
  await page.getByRole('button', { name: 'Review sell' }).click()

  await expect(page.getByText(/You hold 0\.00 UST2Y/)).toBeVisible()
})

test('appears in the transaction history after a purchase', async ({ page }) => {
  await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
  await page.getByRole('button', { name: 'Review buy' }).click()
  await page.getByRole('button', { name: 'Buy 1.00 UST2Y' }).click()
  await expect(page.getByText(/Bought 1\.00 UST2Y for/)).toBeVisible()

  await page.getByRole('link', { name: 'History' }).click()
  await expect(page.getByText('Bought 1.00 UST2Y')).toBeVisible()
})

test('reaches the trade ticket by keyboard alone', async ({ page }) => {
  const row = page.getByRole('button', { name: /US Treasury Note 2Y/ })
  await row.focus()
  await page.keyboard.press('Enter')

  await expect(page.getByRole('heading', { name: 'US Treasury Note 2Y' })).toBeVisible()
})
