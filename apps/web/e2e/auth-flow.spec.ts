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

test('auth flow: signup → save project → versions → dashboard reopen → logout', async ({
  page,
}) => {
  const userEmail = email();
  const password = 'password123';

  // -- signup -----------------------------------------------------------------
  await page.goto('/signup');
  await page.getByTestId('signup-form').locator('input[type="text"]').fill('E2E User');
  await page.getByTestId('signup-form').locator('input[type="email"]').fill(userEmail);
  await page.getByTestId('signup-form').locator('input[type="password"]').fill(password);
  await page.getByTestId('signup-form').getByRole('button', { name: /Create account/ }).click();

  // lands on the dashboard (empty state)
  await expect(page.getByRole('heading', { name: 'Your projects' })).toBeVisible();
  await expect(page.getByTestId('logout-btn')).toBeVisible();

  // -- reconstruct a poster, then save it as a cloud project ------------------
  await reconstruct(page);
  await expect(page.getByRole('option', { name: /Background/ })).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept('E2E Project'));
  await page.getByTestId('save-project-btn').click();

  // first save creates the project and pivots the URL + button label
  await expect(page).toHaveURL(/\/editor\?project=/);
  await expect(page.getByTestId('save-project-btn')).toHaveText(/Update project/);

  // -- version snapshot + restore ---------------------------------------------
  await page.getByTestId('versions-btn').click();
  await expect(page.getByTestId('versions-menu')).toBeVisible();
  await page.getByTestId('versions-menu').getByRole('button', { name: /Save current as version/ }).click();
  // status toast + version count increments
  await expect(page.getByTestId('versions-btn')).toHaveText(/Versions \(1\)/);

  await page.getByTestId('versions-btn').click();
  await expect(page.getByTestId('versions-menu')).toBeVisible();
  const restored = page.waitForResponse(
    (r) => r.url().includes('/versions/1/restore') && r.request().method() === 'POST',
  );
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByTestId('versions-menu').getByRole('button', { name: /Version 1/ }).click();
  await restored;
  await expect(page.getByRole('status')).toContainText('Restored version 1');

  // -- reopen from the dashboard ----------------------------------------------
  await page.getByTestId('dashboard-btn').click();
  await expect(page.getByRole('heading', { name: 'Your projects' })).toBeVisible();
  await expect(page.getByTestId('project-list')).toBeVisible();
  await expect(page.getByRole('button', { name: /E2E Project/ })).toBeVisible();

  await page.getByRole('button', { name: /E2E Project/ }).click();
  await expect(page.getByTestId('editor-screen')).toBeVisible();
  await expect(page.getByText(/E2E Project/).first()).toBeVisible();
  await expect(page.getByTestId('save-project-btn')).toHaveText(/Update project/);

  // -- logout ------------------------------------------------------------------
  await page.getByTestId('dashboard-btn').click();
  await page.getByTestId('logout-btn').click();
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('button', { name: /Sign in/ })).toBeVisible();
});