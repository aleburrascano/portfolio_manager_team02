import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('wallet'))
})

test('deposits cash and reflects the new balance', async ({ page }) => {
  await expect(page.locator('.balance')).toHaveText('$0.00')

  await page.getByRole('button', { name: 'Deposit' }).click()
  await page.getByLabel('Amount').fill('250')
  await page.getByRole('button', { name: 'Submit Transaction' }).click()

  await expect(page.getByText('Deposit submitted successfully.')).toBeVisible()
  await expect(page.locator('.balance')).toHaveText('$250.00')
})

test('withdraws cash and reflects the new balance', async ({ page }) => {
  await page.getByRole('button', { name: 'Deposit' }).click()
  await page.getByLabel('Amount').fill('250')
  await page.getByRole('button', { name: 'Submit Transaction' }).click()
  await expect(page.locator('.balance')).toHaveText('$250.00')
  // The modal closes itself on success, half a second after the message.
  await expect(page.getByRole('dialog')).not.toBeVisible()

  await page.getByRole('button', { name: 'Withdraw' }).click()
  await page.getByLabel('Amount').fill('100')
  await page.getByRole('button', { name: 'Submit Transaction' }).click()

  await expect(page.getByText('Withdrawal submitted successfully.')).toBeVisible()
  await expect(page.locator('.balance')).toHaveText('$150.00')
})

test('shows the transaction in the history page', async ({ page }) => {
  await page.getByRole('button', { name: 'Deposit' }).click()
  await page.getByLabel('Amount').fill('75')
  await page.getByRole('button', { name: 'Submit Transaction' }).click()
  await expect(page.locator('.balance')).toHaveText('$75.00')

  await page.getByRole('button', { name: 'Transaction History' }).click()
  await expect(page.getByText('Cash Deposit')).toBeVisible()
  await expect(page.getByText('+$75.00')).toBeVisible()
})
