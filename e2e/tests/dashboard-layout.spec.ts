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

type Box = { top: number; bottom: number; left: number; right: number }

async function boxOf(page: Page, selector: string): Promise<Box> {
  const box = await page.locator(selector).boundingBox()
  if (!box) throw new Error(`${selector} is not on the page`)
  return { top: box.y, bottom: box.y + box.height, left: box.x, right: box.x + box.width }
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

      const holdings = await boxOf(page, '.holdings-card')

      const panels = await page.locator('.dashboard-row > .card').evaluateAll((nodes) =>
        nodes.map((node) => {
          const rect = node.getBoundingClientRect()
          return {
            label: node.querySelector('.section-title')?.textContent ?? node.className,
            top: rect.top,
            bottom: rect.bottom,
            left: rect.left,
            right: rect.right,
          }
        }),
      )
      expect(panels.length, 'the row above holdings has no panels to check').toBeGreaterThan(0)

      for (const panel of panels) {
        expect(
          overlap(panel, holdings),
          `"${panel.label}" runs ${overlap(panel, holdings)}px into the holdings card`,
        ).toBe(0)
      }

      // Nothing may spill out of the dashboard's own box either.
      const content = await boxOf(page, '#dashboard-content')
      expect(
        holdings.bottom - content.bottom,
        'the holdings card hangs below the dashboard',
      ).toBeLessThanOrEqual(1)
    })
  }

  test('the dashboard uses the width it is given', async ({ page }) => {
    await page.setViewportSize({ width: 2560, height: 1440 })
    await registerNewUser(page, uniqueUsername('width'))
    await expect(page.locator('.holdings-card')).toBeVisible()

    const panel = await boxOf(page, '.app-page')
    const content = await boxOf(page, '#dashboard-content')

    // Capped for readability, but the leftover falls either side rather
    // than piling up to the right of the content.
    const leftGap = content.left - panel.left
    const rightGap = panel.right - content.right
    expect(Math.abs(leftGap - rightGap), 'the content is not centred in the panel').toBeLessThan(2)
    expect(content.right - content.left).toBeGreaterThan(1240)
  })
})
