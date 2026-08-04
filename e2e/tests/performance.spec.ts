import { expect, test } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

/**
 * The performance chart's benchmark: what the portfolio is measured
 * against, and whether that line is drawn at all.
 *
 * The picker searches the whole catalog rather than a fixed list of
 * indices, so the case worth covering is picking something that is not the
 * default and having it still be there on the way back.
 */
test.describe('benchmark comparison', () => {
  test('the chosen benchmark survives a reload', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('bench'))

    const choice = page.locator('.benchmark-choice')
    await expect(choice).toHaveText('S&P 500')

    await choice.click()
    await page.getByLabel('Asset type').selectOption('crypto')
    await page.getByRole('button', { name: /Bitcoin/ }).click()
    await expect(choice).toHaveText(/Bitcoin/)

    await page.reload()
    await expect(page.locator('.benchmark-choice')).toHaveText(/Bitcoin/)
  })

  test('the comparison toggle survives a reload', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('bench'))

    const toggle = page.getByRole('checkbox', { name: 'Compare against' })
    await expect(toggle).toBeChecked()
    await toggle.uncheck()

    // Turned off, the asset is not something the user can still change.
    await expect(page.locator('.benchmark-choice')).toBeDisabled()

    await page.reload()
    await expect(page.getByRole('checkbox', { name: 'Compare against' })).not.toBeChecked()
  })
})
