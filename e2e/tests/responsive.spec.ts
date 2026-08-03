import { expect, test, type Page } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

/**
 * Issue #66: the app has to work on a phone.
 *
 * The check that matters most is horizontal overflow. A page that scrolls
 * sideways is the tell that something - a table, a grid, a heading - is
 * wider than the viewport it was given, and it is invisible at desktop
 * widths where most of the development happens.
 */
const PHONE = { width: 375, height: 812 }
const TABLET = { width: 768, height: 1024 }

async function expectNoHorizontalScroll(page: Page, label: string) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(
    overflow.scrollWidth,
    `${label} scrolls sideways: content is ${overflow.scrollWidth}px in a ${overflow.clientWidth}px viewport`,
  ).toBeLessThanOrEqual(overflow.clientWidth + 1)
}

async function fundAccount(page: Page, amount: string) {
  await page.getByRole('button', { name: 'Deposit', exact: true }).click()
  await page.getByLabel('Amount').fill(amount)
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: `Deposit $${Number(amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}` }).click()
  await page.getByRole('button', { name: 'Done' }).click()
}

test.describe('phone', () => {
  test.use({ viewport: PHONE })

  test('navigates from a bottom bar, within reach of a thumb', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('mob'))

    const nav = page.locator('.sidebar')
    const navBox = await nav.boundingBox()
    const viewport = page.viewportSize()!

    // The bar sits in the lower half of the screen and spans its width.
    expect(navBox!.y).toBeGreaterThan(viewport.height / 2)
    expect(navBox!.width).toBeGreaterThanOrEqual(viewport.width - 1)

    // Every target clears the 44px minimum.
    for (const name of ['Dashboard', 'Trade', 'History']) {
      const box = await page.getByRole('link', { name }).boundingBox()
      expect(box!.height, `${name} tap target`).toBeGreaterThanOrEqual(44)
    }
  })

  test('no screen scrolls sideways', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('mob'))
    await expectNoHorizontalScroll(page, 'Dashboard')

    await fundAccount(page, '5000')
    await expectNoHorizontalScroll(page, 'Dashboard after funding')

    await page.getByRole('link', { name: 'Trade' }).click()
    await page.getByRole('button', { name: 'Bonds' }).click()
    await expect(page.getByText('Most active bonds')).toBeVisible()
    await expectNoHorizontalScroll(page, 'Trade')

    await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
    await expect(page.getByRole('heading', { name: 'US Treasury Note 2Y' })).toBeVisible()
    await expectNoHorizontalScroll(page, 'Asset detail')

    await page.getByRole('button', { name: 'Review buy' }).click()
    await page.getByRole('button', { name: 'Buy 1.00 UST2Y' }).click()
    await expect(page.getByText(/Bought 1\.00 UST2Y for/)).toBeVisible()

    await page.getByRole('link', { name: 'History' }).click()
    await expect(page.getByText('Bought 1.00 UST2Y')).toBeVisible()
    await expectNoHorizontalScroll(page, 'Transaction history')

    // Account settings live in the header menu now, not the bottom bar.
    await page.getByRole('button', { name: /Ada Lovelace/ }).click()
    await page.getByRole('menuitem', { name: 'Account settings' }).click()
    await expectNoHorizontalScroll(page, 'Account')

    await page.getByRole('link', { name: 'Dashboard' }).click()
    await expect(page.getByRole('table').filter({ hasText: 'UST2Y' })).toBeVisible()
    await expectNoHorizontalScroll(page, 'Dashboard with holdings')
  })

  test('the deposit dialog fits the screen', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('mob'))
    await page.getByRole('button', { name: 'Deposit', exact: true }).click()

    const card = await page.locator('.modal-card').boundingBox()
    expect(card!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
    await expectNoHorizontalScroll(page, 'Deposit dialog')
  })
})

test.describe('desktop', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  // The dashboard is fitted to the viewport above 1000x780: every panel on
  // screen at once, with the long lists scrolling inside their own boxes
  // rather than pushing the page down.
  test('the dashboard fits the screen without the page scrolling', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('desk'))
    await fundAccount(page, '5000')

    await page.getByRole('link', { name: 'Trade' }).click()
    await page.getByRole('button', { name: 'Bonds' }).click()
    await page.getByRole('button', { name: /US Treasury Note 2Y/ }).click()
    await page.getByRole('button', { name: 'Review buy' }).click()
    await page.getByRole('button', { name: 'Buy 1.00 UST2Y' }).click()
    await expect(page.getByText(/Bought 1\.00 UST2Y for/)).toBeVisible()

    await page.getByRole('link', { name: 'Dashboard' }).click()
    await expect(page.getByRole('table').filter({ hasText: 'UST2Y' })).toBeVisible()

    const overflow = await page.evaluate(() => {
      const main = document.querySelector('.app-page')!
      return {
        pageScroll: main.scrollHeight - main.clientHeight,
        docScroll: document.documentElement.scrollHeight - document.documentElement.clientHeight,
      }
    })
    expect(overflow.docScroll).toBeLessThanOrEqual(1)
    expect(overflow.pageScroll, 'the dashboard should fit its column').toBeLessThanOrEqual(1)

    // And every panel is genuinely on screen, not merely not-scrolling.
    for (const name of ['Watchlist', 'Most active today']) {
      const heading = page.getByRole('heading', { name })
      if (await heading.count()) await expect(heading.first()).toBeInViewport()
    }
    await expect(page.getByRole('heading', { name: 'Portfolio performance' })).toBeInViewport()
    await expect(page.getByRole('heading', { name: 'Portfolio composition' })).toBeInViewport()
    await expect(page.getByRole('heading', { name: 'Your holdings' })).toBeInViewport()
    await expect(page.locator('.wallet-balance')).toBeInViewport()
  })
})

test.describe('tablet', () => {
  test.use({ viewport: TABLET })

  test('keeps the side rail and does not scroll sideways', async ({ page }) => {
    await registerNewUser(page, uniqueUsername('tab'))

    // Above the phone breakpoint the rail is back at the side.
    const navBox = await page.locator('.sidebar').boundingBox()
    expect(navBox!.y).toBeLessThan(TABLET.height / 2)

    await expectNoHorizontalScroll(page, 'Dashboard on tablet')

    await page.getByRole('link', { name: 'Trade' }).click()
    await expectNoHorizontalScroll(page, 'Trade on tablet')
  })
})
