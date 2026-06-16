// Keep Playwright's browser binaries INSIDE this folder's node_modules so the
// entire test setup is removable by deleting testing/rm-e2e/.
process.env.PLAYWRIGHT_BROWSERS_PATH = process.env.PLAYWRIGHT_BROWSERS_PATH || '0';

const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,                       // tests share one running Flask app + bank.db
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  globalTeardown: require.resolve('./global-teardown.js'),
  use: {
    baseURL: 'http://127.0.0.1:5000',
    headless: false,                // run headed so you can watch it in action
    viewport: { width: 1440, height: 900 },
    video: 'on',
    trace: 'on',
    screenshot: 'only-on-failure',
    actionTimeout: 20_000,
    launchOptions: { slowMo: 650 }, // slow it down so the run is watchable
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], headless: false } },
  ],
});
