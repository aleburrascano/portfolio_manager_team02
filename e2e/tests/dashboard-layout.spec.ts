import { expect, test, type Page } from '@playwright/test'
import { registerNewUser, uniqueUsername } from './fixtures'

/**
 * The dashboard fills the viewport without its panels running into one
 * another.
 *
 * Above 1000x780 the dashboard stops being a column of cards and becomes a
 * grid sized to the window, which is the layout that can go wrong: the
 * wallet and the watchlist take whatever height they need, and the two
 * rows underneath divide what's left. When that leftover is smaller than
 * the panels' own content, nothing clips it - a grid item simply paints
 * outside its row, and the holdings table ends up drawn over the
 * performance and composition cards above it.
 *
 * Reproduced by height rather than by content: a window just over the
 * threshold turns the grid on and leaves the least room underneath, which
 * is the same squeeze a long watchlist produces on a taller screen.
 */
const VIEWPORTS = [
  { label: 'just over the grid threshold', width: 1440, height: 800 },
  { label: 'a laptop', width: 1512, height: 900 },
  { label: 'fullscreen 1080p', width: 1920, height: 1080 },
  { label: 'fullscreen 1440p', width: 2560, height: 1440 },
]

type Box = { label: string; top: number; bottom: number; left: number; right: number }

/**
 * Every box the assertions need, read in one pass in the page.
 *
 * One pass because two are not comparable: a second call is a second
 * layout, and anything that moved between them - a pushed quote
 * re-rendering a tile, the column scrolling - shows up as geometry that
 * never existed. Mixing Playwright's boundingBox() with
 * getBoundingClientRect() compounds it, since the page began scrolling
 * and the two no longer share an origin.
 */
async function measure(page: Page) {
  return page.evaluate(() => {
    const read = (node: Element, label: string) => {
      const r = node.getBoundingClientRect()
      return { label, top: r.top, bottom: r.bottom, left: r.left, right: r.right }
    }
    const one = (sel: string, label: string) => {
      const node = document.querySelector(sel)
      return node ? read(node, label) : null
    }
    return {
      panels: [...document.querySelectorAll('.dashboard-row > .card')].map((node) =>
        read(node, node.querySelector('.section-title')?.textContent ?? node.className),
      ),
      holdings: one('.holdings-card', 'holdings'),
      content: one('#dashboard-content', 'dashboard'),
      page: one('.app-page', 'panel'),
    }
  })
}

function overlap(a: Box, b: Box): number {
  const vertical = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
  const horizontal = Math.min(a.right, b.right) - Math.max(a.left, b.left)
  return vertical > 0 && horizontal > 0 ? vertical : 0
}

test.describe('dashboard layout', () => {
  for (const viewport of VIEWPORTS) {
    test(`panels do not overlap at ${viewport.width}x${viewport.height} (${viewport.label})`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await registerNewUser(page, uniqueUsername('layout'))

      await expect(page.locator('.holdings-card')).toBeVisible()
      await expect(page.locator('.performance-card')).toBeVisible()
      // The chart is lazy-loaded behind a shorter placeholder; measuring
      // before it lands reads the layout it is about to replace.
      await expect(page.locator('#dashboard-content [aria-busy="true"]')).toHaveCount(0)

      const { panels, holdings, content } = await measure(page)
      expect(panels.length, 'the row above holdings has no panels to check').toBeGreaterThan(0)
      expect(holdings, 'no holdings card on the page').not.toBeNull()

      for (const panel of panels) {
        expect(
          overlap(panel, holdings!),
          `"${panel.label}" runs ${overlap(panel, holdings!)}px into the holdings card`,
        ).toBe(0)
      }

      // Nothing may spill out of the dashboard's own box either.
      expect(
        holdings!.bottom - content!.bottom,
        'the holdings card hangs below the dashboard',
      ).toBeLessThanOrEqual(1)
    })
  }

  test('the dashboard uses the width it is given', async ({ page }) => {
    await page.setViewportSize({ width: 2560, height: 1440 })
    await registerNewUser(page, uniqueUsername('width'))
    await expect(page.locator('.holdings-card')).toBeVisible()
    await expect(page.locator('#dashboard-content [aria-busy="true"]')).toHaveCount(0)

    const { page: panel, content } = await measure(page)

    // Capped for readability, but the leftover falls either side rather
    // than piling up to the right of the content.
    const leftGap = content!.left - panel!.left
    const rightGap = panel!.right - content!.right
    expect(Math.abs(leftGap - rightGap), 'the content is not centred in the panel').toBeLessThan(2)
    expect(content!.right - content!.left).toBeGreaterThan(1240)
  })
})
