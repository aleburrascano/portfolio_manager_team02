import { expect, test } from '@playwright/test'
import { logOut, registerNewUser, uniqueUsername } from './fixtures'

test('registers a new account and lands on the dashboard', async ({ page }) => {
  await registerNewUser(page, uniqueUsername('reg'))
  await expect(page.locator('#dashboard-content')).toBeVisible()
})

test('rejects registration with a duplicate username', async ({ page }) => {
  const username = uniqueUsername('dup')
  await registerNewUser(page, username)
  await logOut(page)

  await page.getByRole('button', { name: 'Need an account? Sign up' }).click()
  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill('password123')
  await page.getByPlaceholder('First Name').fill('Someone')
  await page.getByPlaceholder('Last Name').fill('Else')
  await page.getByRole('button', { name: 'Sign Up' }).click()

  await expect(page.getByText('That username is already taken')).toBeVisible()
})

test('logs out and back in with the same credentials', async ({ page }) => {
  const username = uniqueUsername('login')
  await registerNewUser(page, username)
  await logOut(page)

  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill('password123')
  await page.getByRole('button', { name: 'Log In' }).click()

  await expect(page.getByText('Hello, Ada')).toBeVisible()
})

test('rejects an incorrect password', async ({ page }) => {
  const username = uniqueUsername('badpw')
  await registerNewUser(page, username)
  await logOut(page)

  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill('wrong-password')
  await page.getByRole('button', { name: 'Log In' }).click()

  await expect(page.getByText('Incorrect username or password')).toBeVisible()
})

test('restores the session on reload', async ({ page }) => {
  await registerNewUser(page, uniqueUsername('reload'))
  await page.reload()
  await expect(page.getByText('Hello, Ada')).toBeVisible()
})
