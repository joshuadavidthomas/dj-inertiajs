import { expect, test } from '@playwright/test'

test('uses Django partial-reload and once-prop responses with the v3 client', async ({ page }) => {
  await page.goto('/v3/nested/')
  await expect(page.getByTestId('props')).toContainText('en-US')
  await expect(page.getByTestId('props')).toContainText('UTC')

  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) => candidate.request().headers()['x-inertia-partial-data'] === 'config.locale',
    ),
    page.getByRole('button', { name: 'Reload locale' }).click(),
  ])
  expect(response.status()).toBe(200)
  await expect(response.json()).resolves.toMatchObject({
    props: { config: { locale: 'en-US' } },
  })

  await expect(page.getByTestId('props')).toContainText('en-US')
  await expect(page.getByTestId('props')).toContainText('UTC')
})

test('sends the CSRF token with the v3 client defaults', async ({ page }) => {
  await page.goto('/v3/nested/')

  const [visit] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/v3/post/')),
    page.getByRole('button', { name: 'Post visit' }).click(),
  ])
  expect(visit.status()).toBe(302)
  await expect(page.getByTestId('props')).toContainText('en-US')

  const [http] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/v3/post/')),
    page.getByRole('button', { name: 'Post with useHttp' }).click(),
  ])
  expect(http.status()).toBe(200)
  await expect(http.json()).resolves.toEqual({ saved: true })
})
