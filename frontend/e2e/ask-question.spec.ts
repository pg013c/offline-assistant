import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const POLICY = fileURLToPath(new URL('./fixtures/sample-policy.txt', import.meta.url))

test('upload a document, ask a question and open the source', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('API: ok')

  await page.getByLabel(/upload a document/i).setInputFiles(POLICY)
  await expect(page.getByRole('listitem').filter({ hasText: 'sample-policy' })).toBeVisible()

  await page.getByRole('textbox', { name: 'Question' }).fill('How long are access logs kept?')
  await page.getByRole('button', { name: 'Ask' }).click()

  await expect(
    page.getByText('Access logs are kept for six months.', { exact: false }).first(),
  ).toBeVisible()
  await expect(page.getByText(/Answered by fake-extractive/)).toBeVisible()

  await page
    .getByRole('list', { name: 'Sources' })
    .getByRole('button', { name: 'sample-policy' })
    .click()
  const source = page.getByRole('dialog', { name: 'sample-policy' })
  await expect(source).toContainText('Access logs are kept for six months.')
})
