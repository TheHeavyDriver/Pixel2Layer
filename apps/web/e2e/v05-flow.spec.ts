import { expect, test, type Page } from '@playwright/test';

const POSTER_PATH = 'e2e/fixtures/poster.png';

const email = () => `e2e-${Date.now()}@example.com`;

async function reconstruct(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Upload an image' }).click();
  const modal = page.getByTestId('upload-modal');
  await expect(modal).toBeVisible();
  await modal.locator('input[type="file"]').setInputFiles(POSTER_PATH);
  await expect(page.getByTestId('upload-preview')).toBeVisible();
  await modal.getByTestId('reconstruct-button').click();
  await expect(page.getByTestId('overall-progress')).toBeVisible();
  await expect(page.getByTestId('editor-screen')).toBeVisible({ timeout: 90_000 });
}

async function signup(page: Page) {
  await page.goto('/signup');
  await page.getByTestId('signup-form').locator('input[type="text"]').fill('E2E User');
  await page.getByTestId('signup-form').locator('input[type="email"]').fill(email());
  await page.getByTestId('signup-form').locator('input[type="password"]').fill('password123');
  await page.getByTestId('signup-form').getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByRole('heading', { name: 'Your projects' })).toBeVisible();
}

test('sharing: create link → open shared → revoke (v0.5)', async ({ page }) => {
  await signup(page);
  await reconstruct(page);

  // save as a project so sharing has something to point at
  page.once('dialog', (dialog) => dialog.accept('Share Me'));
  await page.getByTestId('save-project-btn').click();
  await expect(page).toHaveURL(/\/editor\?project=/);

  // create an edit share link
  await page.getByTestId('share-btn').click();
  await expect(page.getByTestId('share-menu')).toBeVisible();
  await page.getByRole('button', { name: 'Can edit' }).click();
  const shareResponse = page.waitForResponse(
    (r) => r.url().includes('/share') && r.request().method() === 'POST',
  );
  await page.getByTestId('create-share-btn').click();
  const shareJson = (await shareResponse).json();
  const token = (await shareJson).token;
  expect(token).toBeTruthy();
  await expect(page.getByTestId('share-menu')).toContainText(/Edit ·/);

  await page.goto(`/share/${token}`);
  await expect(page.getByTestId('editor-screen')).toBeVisible();
  await expect(page.getByText(/Shared · edit/)).toBeVisible();

  // revoke from the owner view, then the link 404s
  await page.goto('/dashboard');
  await page.getByRole('button', { name: /Share Me/ }).click();
  await expect(page.getByTestId('editor-screen')).toBeVisible();
  await page.getByTestId('share-btn').click();
  await page.getByTestId('share-menu').getByRole('button', { name: 'Revoke' }).click();
  await expect(page.getByTestId('share-menu')).toContainText(/revoked/i);

  await page.goto(`/share/${token}`);
  await expect(page.getByText(/Could not open this design/)).toBeVisible();
});

test('templates: save as template → gallery reuse + PDF export (v0.5)', async ({ page }) => {
  await signup(page);
  await reconstruct(page);

  // save as template
  page.once('dialog', (dialog) => dialog.accept('Launch Poster'));
  await page.getByTestId('save-template-btn').click();
  await expect(page.getByText('Saved as template')).toBeVisible();

  // PDF export produces a download
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'PDF' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/pdf$/);

  // gallery shows the template and can be reused
  await page.goto('/templates');
  await expect(page.getByTestId('template-grid')).toBeVisible();
  await expect(page.getByText('Launch Poster')).toBeVisible();

  const openRequest = page.waitForResponse(
    (r) => r.url().includes('/api/templates') && r.request().method() === 'GET',
  );
  await page.getByTestId('use-template-btn').click();
  await openRequest;
  await expect(page.getByTestId('editor-screen')).toBeVisible();
});