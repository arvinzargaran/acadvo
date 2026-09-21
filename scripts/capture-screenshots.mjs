/**
 * Capture the README screenshots from a running local instance.
 *
 * Screenshots go stale silently: the UI moves, the images do not, and the
 * README ends up advertising a product that no longer exists. This script
 * regenerates all of them in one pass so refreshing them is a command rather
 * than an afternoon.
 *
 * Needs a seeded demo account and both servers running:
 *
 *   python -m app.scripts.seed_demo          # from backend/, DEBUG=True
 *   npm run dev --prefix frontend            # or the launch.json config
 *   node scripts/capture-screenshots.mjs
 *
 * Playwright is deliberately NOT a dependency of this project — it is a
 * 150MB browser download used a handful of times a year, and adding it to
 * package.json would put it in every install and every audit. Provide it at
 * run time instead:
 *
 *   npx playwright install chromium
 *   npm install --no-save playwright
 */

import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';

const BASE = process.env.BASE_URL ?? 'http://localhost:3000';
const EMAIL = process.env.DEMO_EMAIL ?? 'demo@acadvo.app';
const PASSWORD = process.env.DEMO_PASSWORD ?? 'DemoStudent2026!';
const OUT = 'docs/screenshots';

const SHOTS = [
  { path: '/dashboard', file: 'dashboard.png', wait: 'Welcome back' },
  { path: '/degree', file: 'degree.png', wait: 'Degree Plan' },
  { path: '/career', file: 'career.png', wait: 'Career' },
  { path: '/projects', file: 'projects.png', wait: 'Projects' },
  { path: '/courses', file: 'course-advisor.png', wait: null },
];

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: 'light',
  reducedMotion: 'reduce', // entrance animations settle instantly, so no half-faded captures
});
const page = await context.newPage();

await mkdir(OUT, { recursive: true });

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.fill('input[type="email"]', EMAIL);
await page.fill('input[type="password"]', PASSWORD);
await page.click('button:has-text("Sign in")');
await page.waitForURL('**/dashboard', { timeout: 15000 });

// The product tour opens over the dashboard on a first visit and would sit in
// the middle of every capture.
await page.evaluate(() => localStorage.setItem('acadvo_tour_complete', 'true'));

for (const shot of SHOTS) {
  await page.goto(`${BASE}${shot.path}`, { waitUntil: 'networkidle' });
  if (shot.wait) {
    await page.getByText(shot.wait, { exact: false }).first().waitFor({ timeout: 15000 });
  }
  await page.waitForTimeout(1200);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${OUT}/${shot.file}` });
  console.log(`captured ${OUT}/${shot.file}`);
}

await browser.close();
console.log('\ndone');
