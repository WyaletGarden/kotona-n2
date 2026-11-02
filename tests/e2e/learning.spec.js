import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test.beforeAll(async ({ request }) => {
  const marker = await request.get('/api/test-environment');
  expect(marker.status()).toBe(200);
  expect(await marker.json()).toEqual({ isolated: true });
});

async function register(page) {
  await page.goto('/');
  await page.locator('#auth-toggle').click();
  await page.locator('#auth-name').fill('E2E learner');
  await page.locator('#auth-email').fill(`e2e-${randomUUID()}@example.com`);
  await page.locator('#auth-password').fill('test-password-123');
  await page.locator('#auth-submit').click();
  await expect(page.locator('.shell')).toBeVisible();
  await expect(page.locator('#study-panel .flash-card')).toBeVisible();
}

test('resumes learning across mode changes and reloads', async ({ page }) => {
  await register(page);
  await page.locator('[data-action="reveal"]').first().click();
  await page.locator('[data-action="rate-correct"]').click();
  await expect(page.locator('#progress-count')).toHaveText('1 / 10 từ');
  await page.locator('#quiz-mode').click();
  await expect(page.locator('.quiz-options')).toBeVisible();
  await page.locator('#flash-mode').click();
  await expect(page.locator('#progress-count')).toHaveText('1 / 10 từ');
  await page.reload();
  await expect(page.locator('#progress-count')).toHaveText('1 / 10 từ');
});

test('reload uses one bootstrap request and keeps login hidden while loading', async ({ page }) => {
  await register(page);
  const hold = async (pattern) => {
    let release, requested;
    const gate = new Promise((resolve) => (release = resolve));
    const started = new Promise((resolve) => (requested = resolve));
    await page.route(pattern, async (route) => {
      requested();
      await gate;
      await route.continue();
    });
    return { release, started };
  };
  const bootstrap = await hold('**/api/bootstrap');
  const extra = [];
  page.on('request', (request) => {
    if (/\/api\/(auth\/me|workspace|catalogue)$/.test(request.url())) extra.push(request.url());
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await bootstrap.started;
  await expect(page.locator('#startup-screen')).toBeVisible();
  await expect(page.locator('#auth-screen')).toBeHidden();
  await expect(page.locator('.shell')).toBeHidden();
  bootstrap.release();
  await expect(page.locator('.shell')).toBeVisible();
  await expect(page.locator('#startup-screen')).toBeHidden();
  await expect(page.locator('#auth-screen')).toBeHidden();
  expect(extra).toEqual([]);
});

test('login appears only after the session is confirmed unauthenticated', async ({ page }) => {
  let release;
  const gate = new Promise((resolve) => (release = resolve));
  const requested = page.waitForRequest('**/api/bootstrap');
  await page.route('**/api/bootstrap', async (route) => {
    await gate;
    const response = await route.fetch();
    await route.fulfill({ response });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await requested;
  await expect(page.locator('#startup-screen')).toBeVisible();
  await expect(page.locator('#auth-screen')).toBeHidden();
  release();
  await expect(page.locator('#auth-screen')).toBeVisible();
  await expect(page.locator('#startup-screen')).toBeHidden();
  await expect(page.locator('.shell')).toBeHidden();
});

test('startup connection errors offer retry without showing login', async ({ page }) => {
  await register(page);
  await page.route('**/api/bootstrap', (route) => route.abort());
  await page.reload();
  await expect(page.locator('#startup-message')).toContainText('Không kết nối được máy chủ');
  await expect(page.locator('#startup-retry')).toBeVisible();
  await expect(page.locator('#auth-screen')).toBeHidden();
  await expect(page.locator('.shell')).toBeHidden();
  await page.unroute('**/api/bootstrap');
  await page.locator('#startup-retry').click();
  await expect(page.locator('.shell')).toBeVisible();
  await expect(page.locator('#startup-screen')).toBeHidden();
  await expect(page.locator('#auth-screen')).toBeHidden();
});

test('review finds new mistakes after an empty or completed session', async ({ page }) => {
  await register(page);
  await page.locator('[data-view="review"]').click();
  await expect(page.locator('#study-panel')).toContainText('Chưa có từ nào đến lượt ôn');

  await page.locator('[data-view="flash"]').click();
  await page.locator('[data-action="reveal"]').first().click();
  await page.locator('[data-action="rate-wrong"]').click();
  await expect(page.locator('#nav-wrong')).toHaveText('1');

  await page.locator('[data-view="review"]').click();
  await expect(page.locator('#study-panel .flash-card')).toBeVisible();
  await expect(page.locator('#progress-count')).toHaveText('0 / 1 từ');
  await page.locator('[data-action="reveal"]').first().click();
  await page.locator('[data-action="rate-wrong"]').click();
  await expect(page.locator('#study-panel')).toContainText('Bạn đã hoàn thành phiên học!');
  await expect(page.locator('#nav-wrong')).toHaveText('1');

  await page.locator('[data-action="review"]').click();
  await expect(page.locator('#study-panel .flash-card')).toBeVisible();
  await expect(page.locator('#progress-count')).toHaveText('0 / 1 từ');
});

test('paginates the library and safely renders added content', async ({ page }) => {
  await register(page);
  await page.locator('[data-view="words"]').click();
  await expect(page.locator('#word-rows tr')).toHaveCount(50);
  await page.locator('#word-next').click();
  await expect(page.locator('#word-count')).toContainText('51–100');
  await page.locator('.add-trigger').click();
  await page.locator('#word-kanji').fill('記憶');
  await page.locator('#word-reading').fill('きおく');
  await page.locator('#word-meaning').fill('Trí nhớ <script>alert(1)</script>');
  await page.locator('#word-form button[type="submit"]').click();
  await expect(page.locator('#word-dialog')).not.toBeVisible();
  await page.locator('#search').fill('tri nho');
  await expect(page.locator('#word-rows')).toContainText('記憶');
  await expect(page.locator('#word-rows')).toContainText('<script>alert(1)</script>');
});

test('imports previewed words and exports attribution', async ({ page }) => {
  await register(page);
  await page.locator('[data-view="words"]').click();
  await page.locator('#import-open').click();
  await page.locator('#import-text').fill('記憶,きおく,Trí nhớ\n記憶,きおく,Trùng\n誤り,,Lỗi');
  await page.locator('#import-check').click();
  await expect(page.locator('#import-preview')).toContainText('1 từ mới');
  await expect(page.locator('#import-preview')).toContainText('1 dòng lỗi');
  await page.locator('#import-confirm').click();
  await expect(page.locator('#stat-total')).toHaveText('1618');
  const downloading = page.waitForEvent('download');
  await page.locator('#export').click();
  const stream = await (await downloading).createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  expect(data.words).toHaveLength(1618);
  expect(data.attribution.license).toBe('CC BY-SA 4.0');
});

test('network errors preserve confirmed state and permit retry', async ({ page }) => {
  await register(page);
  await page.route('**/api/study/actions', (route) => route.abort());
  await page.locator('[data-action="reveal"]').first().click();
  await expect(page.locator('#save-indicator')).toContainText('chưa được lưu');
  await expect(page.locator('[data-action="rate-correct"]')).toHaveCount(0);
  await page.unroute('**/api/study/actions');
  await page.locator('[data-action="reveal"]').first().click();
  await expect(page.locator('[data-action="rate-correct"]')).toBeVisible();
});

test('patches a visible word without reloading an unfiltered page', async ({ page }) => {
  await register(page);
  await page.locator('[data-view="words"]').click();
  await expect(page.locator('#word-rows tr')).toHaveCount(50);
  const pages = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/words?')) pages.push(request.url());
  });
  const toggle = page.locator('#word-rows [data-word-action="toggle"]').first();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-label', /^Bỏ đánh dấu ôn/);
  expect(pages).toEqual([]);
});

test('refreshes review statistics at their deadline without a revision change', async ({
  page,
}) => {
  await register(page);
  await page.route('**/api/bootstrap', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.workspace.stats.valid_until = new Date(Date.now() + 1000).toISOString();
    body.workspace.stats.refresh_after_ms = 1000;
    await route.fulfill({ json: body });
  });
  let refreshes = 0;
  await page.route('**/api/workspace', async (route) => {
    refreshes++;
    const response = await route.fetch();
    const body = await response.json();
    body.stats.review = 1;
    body.stats.valid_until = null;
    body.stats.refresh_after_ms = null;
    await route.fulfill({ json: body });
  });
  await page.reload();
  await expect(page.locator('#nav-wrong')).toHaveText('1');
  expect(refreshes).toBe(1);
});

test('focus reuses recent state but a cross-tab change forces refresh', async ({ page }) => {
  await register(page);
  const refreshes = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/workspace')) refreshes.push(request.url());
  });
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  // A storage notification represents a confirmed mutation in another tab.
  await page.evaluate(() =>
    window.dispatchEvent(new StorageEvent('storage', { key: 'kotoba:changed' })),
  );
  await expect.poll(() => refreshes.length).toBe(1);
});

test('a workspace failure after registration offers retry without resubmitting', async ({
  page,
}) => {
  await page.goto('/');
  await page.locator('#auth-toggle').click();
  await page.locator('#auth-name').fill('Retry learner');
  await page.locator('#auth-email').fill(`retry-${randomUUID()}@example.com`);
  await page.locator('#auth-password').fill('test-password-123');
  await page.route('**/api/workspace', (route) => route.abort());
  await page.locator('#auth-submit').click();
  await expect(page.locator('#startup-retry')).toBeVisible();
  await expect(page.locator('#auth-screen')).toBeHidden();
  await page.unroute('**/api/workspace');
  await page.locator('#startup-retry').click();
  await expect(page.locator('.shell')).toBeVisible();
});
