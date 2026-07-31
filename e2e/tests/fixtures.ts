import { expect, type Page } from '@playwright/test'

/** A username unique to this test run, so parallel specs never collide. */
export function uniqueUsername(prefix: string): string {
  return `${prefix}${Date.now()}${Math.floor(Math.random() * 100000)}`
}

/** Register a fresh account through the real UI and land on the dashboard. */
export async function registerNewUser(page: Page, username: string) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Need an account? Sign up' }).click()
  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill('password123')
  await page.getByPlaceholder('First Name').fill('Ada')
  await page.getByPlaceholder('Last Name').fill('Lovelace')
  await page.getByRole('button', { name: 'Sign Up' }).click()
  await expect(page.getByText('Hello, Ada')).toBeVisible()
}

/** Log out through the sidebar's confirm-before-logout flow. */
export async function logOut(page: Page) {
  await page.getByRole('button', { name: /Log Out/ }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Log Out' }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
}
