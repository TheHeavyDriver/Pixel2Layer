import { expect, test, type Page } from '@playwright/test';

const POSTER_PATH = 'e2e/fixtures/poster.png';

async function reconstruct(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /Get started/ }).click();
  const modal = page.getByTestId('upload-modal');
  await expect(modal).toBeVisible();
  await modal.locator('input[type="file"]').setInputFiles(POSTER_PATH);
  await expect(page.getByTestId('upload-preview')).toBeVisible();
  await modal.getByTestId('reconstruct-button').click();

  // give the pipeline the whole progress spray, land on the editor
  await expect(page.getByTestId('overall-progress')).toBeVisible();
  await expect(page.getByTestId('editor-screen')).toBeVisible({ timeout: 90_000 });
}

test('full flow: upload → editor loads layers → edit → export → reopen .p2l', async ({ page }) => {
  await reconstruct(page);

  // editor surfaced the reconstructed layers
  await expect(page.getByRole('option', { name: /Background/ })).toBeVisible();
  await expect(page.getByRole('option', { name: /Circle/ })).toBeVisible();

  // select the background rectangle layer, then change its fill color
  await page.getByRole('option', { name: /Background/ }).click();
  const fillHex = page.getByLabel('fill hex');
  await expect(fillHex).toBeVisible();
  await fillHex.fill('#112233');
  await fillHex.press('Enter');

  // the color change lands (undo becomes available)
  await expect(page.getByTestId('undo-btn')).toBeEnabled();

  // undo restores the original color
  await page.getByTestId('undo-btn').click();
  await expect(page.getByTestId('redo-btn')).toBeEnabled();

  // export PNG + SVG
  const png = page.waitForEvent('download');
  await page.getByRole('button', { name: 'PNG' }).click();
  const pngDownload = await png;
  expect(pngDownload.suggestedFilename()).toBe('design.png');

  const svg = page.waitForEvent('download');
  await page.getByRole('button', { name: 'SVG' }).click();
  const svgDownload = await svg;
  expect(svgDownload.suggestedFilename()).toBe('design.svg');

  // save a .p2l project file
  const p2l = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save' }).click();
  const p2lDownload = await p2l;
  expect(p2lDownload.suggestedFilename()).toBe('design.p2l');

  // reopen that .p2l through the Open control
  const savedPath = `/tmp/opencode/${p2lDownload.suggestedFilename()}`;
  await p2lDownload.saveAs(savedPath);
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Open' }).click();
  await (await chooserPromise).setFiles(savedPath);

  // scene reloaded with the same layers
  await expect(page.getByRole('option', { name: /Background/ })).toBeVisible();
});