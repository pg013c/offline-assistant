import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

// Pages 53-54 of the AI Act, shared with the backend's parser tests.
const AI_ACT = fileURLToPath(
  new URL('../../backend/tests/fixtures/documents/ai-act-art6-en.pdf', import.meta.url),
)
// The first parse loads the layout and table models.
const PARSING_TIMEOUT_MS = 90_000

test('upload a PDF, ask a question and open the source at its article and page', async ({
  page,
}) => {
  test.setTimeout(PARSING_TIMEOUT_MS + 30_000)
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('API: ok')

  await page.getByLabel(/upload a document/i).setInputFiles(AI_ACT)
  const document = page.getByRole('listitem').filter({ hasText: 'ai-act-art6-en' })
  await expect(document).toContainText('ai-act-art6-en.pdf · Processing…')
  await expect(document).toContainText(/\d+ passages · 2 pages/, { timeout: PARSING_TIMEOUT_MS })

  await page
    .getByRole('textbox', { name: 'Question' })
    .fill('When is an AI system intended as a safety component considered high-risk?')
  await page.getByRole('button', { name: 'Ask' }).click()

  await expect(page.getByText(/Answered by fake-extractive/)).toBeVisible()
  const citation = page.getByRole('list', { name: 'Sources' }).getByRole('button').first()
  await expect(citation).toHaveText('ai-act-art6-en · Art. 6(1), p. 1')

  await citation.click()
  const source = page.getByRole('dialog', { name: 'ai-act-art6-en' })
  await expect(source).toContainText('Art. 6(1), p. 1')
  await expect(source).toContainText('Irrespective of whether an AI system')
})
