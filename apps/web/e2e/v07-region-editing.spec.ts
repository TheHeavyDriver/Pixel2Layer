import { expect, test, type Page } from '@playwright/test';

const PHOTO_PATH = 'e2e/fixtures/photo-regions.png';

async function reconstructPhoto(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Upload an image' }).click();
  const modal = page.getByTestId('upload-modal');
  await expect(modal).toBeVisible();
  await modal.locator('input[type="file"]').setInputFiles(PHOTO_PATH);
  await expect(page.getByTestId('upload-preview')).toBeVisible();
  await modal.getByTestId('reconstruct-button').click();
  await expect(page.getByTestId('overall-progress')).toBeVisible();
  await expect(page.getByTestId('editor-screen')).toBeVisible({ timeout: 90_000 });
}

async function selectFirstImageLayer(page: Page) {
  const imageOption = page.getByRole('option', { name: /Cutout|Image/ }).first();
  await expect(imageOption).toBeVisible({ timeout: 90_000 });
  await imageOption.click();
  await expect(page.getByRole('button', { name: 'Remove background' })).toBeVisible();
}

test('image layer: detect regions, crop, keep, and cut', async ({ page }) => {
  await reconstructPhoto(page);
  await selectFirstImageLayer(page);

  // detect regions from the image element's source blob
  await page.getByTestId('detect-regions-btn').click();
  await expect(page.getByTestId('detect-regions-btn')).toBeEnabled({ timeout: 30_000 });
  const regionRows = page.locator('li', { hasText: /#0|#1|#2|#3/ });
  await expect(regionRows.first()).toBeVisible({ timeout: 30_000 });
  const rowCount = await regionRows.count();
  expect(rowCount).toBeGreaterThan(0);

  // crop to the first region: image element gains updated src metadata (undo enables)
  await page.getByTestId('region-crop-0').click();
  await expect(page.getByTestId('undo-btn')).toBeEnabled({ timeout: 30_000 });

  // undo the crop to restore the source layer, re-detect, then keep region 0
  await page.getByTestId('undo-btn').click();
  await page.getByTestId('detect-regions-btn').click();
  await expect(page.getByTestId('region-keep-0')).toBeEnabled({ timeout: 30_000 });
  await page.getByTestId('region-keep-0').click();
  await expect(page.getByTestId('undo-btn')).toBeEnabled({ timeout: 30_000 });

  // undo keep, re-detect, then cut region 0
  await page.getByTestId('undo-btn').click();
  await page.getByTestId('detect-regions-btn').click();
  await expect(page.getByTestId('region-remove-0')).toBeEnabled({ timeout: 30_000 });
  await page.getByTestId('region-remove-0').click();
  await expect(page.getByTestId('undo-btn')).toBeEnabled({ timeout: 30_000 });
});