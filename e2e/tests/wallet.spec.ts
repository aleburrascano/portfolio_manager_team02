import { expect, test, type Page } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

/**
 * Money never moves on one click: the dialog takes an amount, shows what
 * the balance will be afterwards, and only then commits.
 */
async function moveCash(page: Page, action: 'Deposit' | 'Withdraw', amount: string) {
  await page.getByRole('button', { name: action, exact: true }).click()
  await page.getByLabel('Amount').fill(amount)
  await page.getByRole('button', { name: 'Continue' }).click()
}

test.beforeEach(async ({ page }) => {
  await registerNewUser(page, uniqueUsername('wallet'))
})

test('deposits cash and reflects the new balance', async ({ page }) => {
  await expect(page.locator('.wallet-balance')).toHaveText('$0.00')

  await moveCash(page, 'Deposit', '250')

  // The review step states the outcome before anything is committed.
  await expect(page.getByRole('heading', { name: 'Review deposit' })).toBeVisible()
  await expect(page.getByRole('dialog')).toContainText('Balance after')
  await expect(page.getByRole('dialog')).toContainText('$250.00')

  await page.getByRole('button', { name: 'Deposit $250.00' }).click()
  await expect(page.getByText('Deposit submitted successfully.')).toBeVisible()

  // The confirmation stays until it is dismissed, rather than vanishing on
  // a timer before it can be read.
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.locator('.wallet-balance')).toHaveText('$250.00')
})

test('withdraws cash and reflects the new balance', async ({ page }) => {
  await moveCash(page, 'Deposit', '250')
  await page.getByRole('button', { name: 'Deposit $250.00' }).click()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$250.00')

  await moveCash(page, 'Withdraw', '100')
  await page.getByRole('button', { name: 'Withdraw $100.00' }).click()

  await expect(page.getByText('Withdrawal submitted successfully.')).toBeVisible()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$150.00')
})

test('can step back from the review without moving any money', async ({ page }) => {
  await moveCash(page, 'Deposit', '250')
  await page.getByRole('button', { name: 'Back' }).click()

  await expect(page.getByLabel('Amount')).toHaveValue('250')
  await page.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$0.00')
})

test('refuses a withdrawal larger than the balance', async ({ page }) => {
  await moveCash(page, 'Deposit', '50')
  await page.getByRole('button', { name: 'Deposit $50.00' }).click()
  await page.getByRole('button', { name: 'Done' }).click()

  await page.getByRole('button', { name: 'Withdraw', exact: true }).click()
  await page.getByLabel('Amount').fill('500')
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(
    page.getByText('Withdrawal amount exceeds current balance of $50.00.'),
  ).toBeVisible()
})

test('closes the dialog on Escape', async ({ page }) => {
  await page.getByRole('button', { name: 'Deposit', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
})

test('shows the transaction in the history page', async ({ page }) => {
  await moveCash(page, 'Deposit', '75')
  await page.getByRole('button', { name: 'Deposit $75.00' }).click()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.wallet-balance')).toHaveText('$75.00')

  await page.getByRole('button', { name: 'History' }).click()
  await expect(page.getByText('Deposited cash')).toBeVisible()
  await expect(page.getByText('+$75.00')).toBeVisible()
})
