import { test, expect } from '@playwright/test';

const MOBILE_PAGES = [
  { name: 'home', path: '/' },
  { name: 'chat', path: '/chat' },
  { name: 'screening', path: '/screening' },
  { name: 'portfolio', path: '/portfolio' },
  { name: 'decision-signals', path: '/decision-signals' },
  { name: 'login', path: '/login' },
];

for (const page of MOBILE_PAGES) {
  test.describe(`${page.name} page mobile smoke`, () => {
    test('loads without console errors', async ({ page: browserPage }) => {
      const errors: string[] = [];
      browserPage.on('console', (msg) => {
        if (msg.type() === 'error') errors.push(msg.text());
      });
      await browserPage.goto(page.path);
      await browserPage.waitForLoadState('domcontentloaded');
      expect(errors).toEqual([]);
    });
  });
}

const TABLE_PAGES = [
  { name: 'alerts', path: '/alerts' },
  { name: 'portfolio', path: '/portfolio' },
  { name: 'screening', path: '/screening' },
];

for (const page of TABLE_PAGES) {
  test(`${page.name} table visibility by viewport`, async ({ page: browserPage }) => {
    await browserPage.goto(page.path);
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const tableCount = await browserPage.locator('table').count();
    const viewportWidth = browserPage.viewportSize()?.width ?? 0;
    if (viewportWidth < 640) {
      expect(tableCount).toBe(0);
    } else {
      expect(tableCount).toBeGreaterThan(0);
    }
  });
}
