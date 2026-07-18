import { test, expect, type Page } from '@playwright/test';

const smokePassword = process.env.DSA_WEB_SMOKE_PASSWORD;

const MOBILE_PAGES = [
  { name: 'home', path: '/', requiresAuth: true },
  { name: 'chat', path: '/chat', requiresAuth: true },
  { name: 'screening', path: '/screening', requiresAuth: true },
  { name: 'portfolio', path: '/portfolio', requiresAuth: true },
  { name: 'decision-signals', path: '/decision-signals', requiresAuth: true },
  { name: 'login', path: '/login', requiresAuth: false },
];

for (const page of MOBILE_PAGES) {
  test.describe(`${page.name} page mobile smoke`, () => {
    test('loads without console errors', async ({ page: browserPage }) => {
      if (page.requiresAuth) {
        await login(browserPage);
      }
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
    await login(browserPage);
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

async function login(page: Page) {
  test.skip(!smokePassword, 'Set DSA_WEB_SMOKE_PASSWORD to run mobile drawer smoke tests.');

  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  const homeLink = page.getByRole('link', { name: '首页' });
  const isAlreadyAuthenticated =
    page.url().endsWith('/') ||
    (await homeLink.isVisible({ timeout: 2_000 }).catch(() => false));

  if (isAlreadyAuthenticated) {
    await page.waitForLoadState('domcontentloaded');
    return;
  }

  const passwordInput = page.locator('#password');
  const submitButton = page.getByRole('button', { name: /授权进入工作台|完成设置并登录/ });
  await expect(passwordInput).toBeVisible({ timeout: 10_000 });
  await passwordInput.fill(smokePassword!);
  await expect(submitButton).toBeVisible();

  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes('/api/v1/auth/login') && response.status() === 200,
      { timeout: 15_000 }
    ),
    submitButton.click(),
  ]);

  await page.waitForURL('/', { timeout: 15_000 });
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1000);
}

test.describe('mobile drawer/sidebar smoke', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('Shell drawer opens on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/');
    await browserPage.waitForLoadState('domcontentloaded');

    const menuButton = browserPage.getByTestId('mobile-menu-button');
    await expect(menuButton).toBeVisible();
    await menuButton.click();

    const drawer = browserPage.getByRole('dialog');
    await expect(drawer).toBeVisible();
    await expect(drawer.locator('nav')).toBeVisible();
  });

  test('ChatPage mobile sidebar opens', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const toggleButton = browserPage.getByTestId('chat-sidebar-toggle');
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    await expect(browserPage.locator('.page-drawer-overlay').first()).toBeVisible();
  });

  test('HomePage mobile sidebar opens', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/');
    await browserPage.waitForLoadState('domcontentloaded');

    const toggleButton = browserPage.getByTestId('home-sidebar-toggle');
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    await expect(browserPage.locator('.page-drawer-overlay').first()).toBeVisible();
  });
});

const OVERFLOW_PAGES = [
  { name: 'login', path: '/login', requiresAuth: false },
  { name: 'backtest', path: '/backtest', requiresAuth: true },
  { name: 'alerts', path: '/alerts', requiresAuth: true },
  { name: 'portfolio', path: '/portfolio', requiresAuth: true },
  { name: 'usage', path: '/usage', requiresAuth: true },
  { name: 'settings', path: '/settings', requiresAuth: true },
];

for (const page of OVERFLOW_PAGES) {
  test(`${page.name} no horizontal overflow on mobile`, async ({ page: browserPage }) => {
    if (page.requiresAuth) {
      await login(browserPage);
    }
    await browserPage.goto(page.path);
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const scrollWidth = await browserPage.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await browserPage.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });
}

test.describe('ChatPage mobile interactions', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('chat page has no horizontal overflow on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const scrollWidth = await browserPage.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await browserPage.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });

  test('quick questions render in 2-column grid on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const firstQuickBtn = browserPage.getByText('用缠论分析茅台');
    const container = firstQuickBtn.locator('..');
    await expect(container).toHaveClass(/grid-cols-2/);
  });

  test('composer + button toggles expansion drawer', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const expandBtn = browserPage.getByLabel('展开更多选项');
    await expect(expandBtn).toBeVisible();
    await expandBtn.click();

    const drawer = browserPage.getByTestId('chat-composer-drawer');
    await expect(drawer).toBeVisible();
  });

  test('session sidebar drawer width is 85vw on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const toggleButton = browserPage.getByTestId('chat-sidebar-toggle');
    await toggleButton.click();

    const drawer = browserPage.locator('.fixed.inset-0.z-40 .relative.h-full');
    await expect(drawer).toBeVisible();
    const box = await drawer.boundingBox();
    expect(box?.width).toBeGreaterThan(320);
    expect(box?.width).toBeLessThanOrEqual(332);
  });

  test('message list renders without horizontal overflow', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const scrollArea = browserPage.locator('[data-testid="chat-message-scroll"]');
    const scrollWidth = await scrollArea.evaluate((el) => el.scrollWidth);
    const clientWidth = await scrollArea.evaluate((el) => el.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });
});
