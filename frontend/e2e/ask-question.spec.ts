import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

// Pages 53-54 of the AI Act, shared with the backend's parser tests.
const AI_ACT = fileURLToPath(
  new URL('../../backend/tests/fixtures/documents/ai-act-art6-en.pdf', import.meta.url),
)
// The first parse loads the layout and table models.
const PARSING_TIMEOUT_MS = 90_000

async function uploadAiAct(page: Page) {
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('API: ok')
  await page.getByLabel(/upload a document/i).setInputFiles(AI_ACT)
  const document = page.getByRole('listitem').filter({ hasText: 'ai-act-art6-en' })
  await expect(document).toContainText(/\d+ passages · 2 pages/, { timeout: PARSING_TIMEOUT_MS })
  return document
}

test('upload a PDF, ask in Polish and open the English source at its article and page', async ({
  page,
}) => {
  test.setTimeout(PARSING_TIMEOUT_MS + 30_000)
  await uploadAiAct(page)

  await page
    .getByRole('textbox', { name: 'Question' })
    .fill(
      'Kiedy system AI przeznaczony do użycia jako element bezpieczeństwa produktu ' +
        'uznaje się za system wysokiego ryzyka?',
    )
  await page.getByRole('button', { name: 'Ask' }).click()

  await expect(page.getByText(/Answered by fake-extractive/)).toBeVisible()
  const citation = page.getByRole('list', { name: 'Sources' }).getByRole('button').first()
  await expect(citation).toHaveText('ai-act-art6-en · Art. 6(1), p. 1')

  await citation.click()
  const source = page.getByRole('dialog', { name: 'ai-act-art6-en' })
  await expect(source).toContainText('Art. 6(1), p. 1')
  await expect(source).toContainText('Irrespective of whether an AI system')
})

test('a thread of two questions, a marker that opens its source, and the notes tab', async ({
  page,
}) => {
  test.setTimeout(PARSING_TIMEOUT_MS + 30_000)
  await uploadAiAct(page)
  await expect(page.getByText('Offline', { exact: true })).toBeVisible()
  const question = page.getByRole('textbox', { name: 'Question' })

  await question.fill('When is an AI system a safety component considered high-risk?')
  await page.getByRole('button', { name: 'Ask' }).click()
  await expect(page.getByText(/Answered by fake-extractive/)).toBeVisible()
  await expect(question).toHaveValue('')
  await question.fill('Which systems referred to in Annex III are high-risk?')
  await page.getByRole('button', { name: 'Ask' }).click()

  const turns = page.getByRole('article')
  await expect(turns).toHaveCount(2)
  await expect(page.getByText(/Answered by fake-extractive/)).toHaveCount(2)
  await turns.first().getByRole('button', { name: 'Source 1' }).click()
  await expect(page.getByRole('dialog', { name: 'ai-act-art6-en' })).toContainText(
    'Irrespective of whether an AI system',
  )
  await page.keyboard.press('Escape')

  await page.getByRole('tab', { name: 'Notes' }).click()
  await expect(page.getByText(/No notes yet/)).toBeVisible()
})

test('a deleted document is no longer used to answer', async ({ page }) => {
  test.setTimeout(PARSING_TIMEOUT_MS + 30_000)
  const document = await uploadAiAct(page)

  await document.getByRole('button', { name: 'Delete ai-act-art6-en' }).click()
  await document.getByRole('button', { name: 'Confirm deleting ai-act-art6-en' }).click()
  await expect(page.getByText(/no documents yet/i)).toBeVisible()

  await page
    .getByRole('textbox', { name: 'Question' })
    .fill('When is an AI system intended as a safety component considered high-risk?')
  await page.getByRole('button', { name: 'Ask' }).click()

  await expect(
    page.getByText('No relevant passage was found in the uploaded documents.'),
  ).toBeVisible()
  await expect(page.getByRole('list', { name: 'Sources' })).toHaveCount(0)
})

test('markers are easy to hit and the question box stays in view below a long thread', async ({
  page,
}) => {
  test.setTimeout(PARSING_TIMEOUT_MS + 30_000)
  await page.setViewportSize({ width: 1280, height: 720 })
  await uploadAiAct(page)
  const question = page.getByRole('textbox', { name: 'Question' })

  const questions = [
    'When is an AI system a safety component considered high-risk?',
    'Which systems referred to in Annex III are high-risk?',
    'What does Article 6 say about third-party conformity assessment?',
  ]
  for (const [asked, text] of questions.entries()) {
    await question.fill(text)
    await page.getByRole('button', { name: 'Ask' }).click()
    // Each answer finishes before the next question, which would otherwise stop it.
    await expect(page.getByText(/Answered by fake-extractive/)).toHaveCount(asked + 1)
  }

  // WCAG 2.5.8: a target of at least 24 by 24 CSS pixels.
  const marker = await page.getByRole('button', { name: 'Source 1' }).first().boundingBox()
  expect(marker?.width).toBeGreaterThanOrEqual(24)
  expect(marker?.height).toBeGreaterThanOrEqual(24)
  await page.mouse.wheel(0, -10_000)
  await expect(question).toBeInViewport()
})
