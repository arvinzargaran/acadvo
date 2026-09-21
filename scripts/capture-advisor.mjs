import { chromium } from 'playwright';

const BASE = 'http://localhost:3000';
const OUT = 'docs/screenshots/ai-advisor.png';
const QUESTION = process.env.Q ?? "I'm targeting a backend internship. Which course should I add for Fall 2026, and why that one?";

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: 'light',
  reducedMotion: 'reduce',
});
const page = await context.newPage();

page.on('console', (m) => { if (m.type() === 'error') console.log('  [console error]', m.text().slice(0, 160)); });

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.fill('input[type="email"]', 'demo@acadvo.app');
await page.fill('input[type="password"]', 'DemoStudent2026!');
await page.click('button:has-text("Sign in")');
await page.waitForURL('**/dashboard', { timeout: 15000 });
await page.evaluate(() => localStorage.setItem('acadvo_tour_complete', 'true'));
await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

await page.click('[aria-label="Open the AI advisor chat"]');
await page.waitForTimeout(900);

// Start a clean conversation. Re-running this script otherwise appends to the
// previous transcript, and a capture that opens on four identical questions
// from earlier attempts documents the attempts rather than the product.
const newChat = page.locator('[title="New chat"]');
if (await newChat.count()) {
  await newChat.first().click();
  await page.waitForTimeout(1200);
}

const box = page.locator('textarea').last();
await box.fill(QUESTION);
await box.press('Enter');
console.log('sent, waiting for the model...');

// Poll until the assistant has actually answered, rather than screenshotting a
// spinner. Watches message count so a tool-call round trip still counts.
const started = Date.now();
let lastLen = 0;
while (Date.now() - started < 120000) {
  await page.waitForTimeout(2000);
  const state = await page.evaluate(() => {
    const t = document.body.innerText;
    return { len: t.length, tail: t.slice(-400) };
  });
  if (state.len !== lastLen) {
    lastLen = state.len;
    console.log(`  ...${Math.round((Date.now() - started) / 1000)}s, page text ${state.len}`);
  }
  const done = await page.evaluate(() => {
    const txt = document.body.innerText.toLowerCase();
    return !txt.includes('thinking') && !txt.includes('typing');
  });
  if (done && lastLen > 0 && Date.now() - started > 8000) break;
}

await page.waitForTimeout(2500);

// Frame the question with the opening of the answer. Left alone the transcript
// sits at the bottom, showing the model signing off and nothing about what was
// asked; scrolled to the top it shows the question and no answer.
await page.evaluate((question) => {
  const panels = [...document.querySelectorAll('div')].filter(
    (d) => d.scrollHeight > d.clientHeight + 40 && d.clientHeight > 200
  );
  if (!panels.length) return;
  const panel = panels[panels.length - 1];
  // Exact match, not `includes`. The answer quotes the question's own words
  // back ("Direct relevance to a backend internship"), so a substring match
  // scrolls to the middle of the reply and leaves the question off-screen.
  const asked = [...panel.querySelectorAll('*')]
    .filter((e) => e.children.length === 0 && e.textContent.trim() === question)
    .shift();
  if (!asked) return;
  const offset =
    asked.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop;
  panel.scrollTop = Math.max(0, offset - 10);
}, QUESTION);
await page.waitForTimeout(700);

await page.screenshot({ path: OUT });
console.log(`captured ${OUT}`);

const tail = await page.evaluate(() => document.body.innerText.slice(-900));
console.log('\n--- end of page text ---\n' + tail);

await browser.close();
