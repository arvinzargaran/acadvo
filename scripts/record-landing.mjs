/**
 * Record a scroll-through of the landing page for the README.
 *
 * Scrolling is driven with real wheel events rather than window.scrollTo. The
 * page runs a smooth-scroll library that owns the scroll position, and setting
 * scrollTop underneath it produces a jerky fight between the two; wheel events
 * are what it is built to ease.
 *
 * Needs the frontend dev server running, and Playwright provided at run time
 * (see capture-screenshots.mjs for why it is not a dependency):
 *
 *   npm install --no-save playwright && npx playwright install chromium
 *   node scripts/record-landing.mjs
 *
 * Produces docs/media/landing.webm. convert-landing.sh turns that into the GIF
 * the README embeds and an mp4 for anywhere that can play one.
 */

import { chromium } from 'playwright';
import { mkdir, rename, readdir } from 'node:fs/promises';
import { join } from 'node:path';

const BASE = process.env.BASE_URL ?? 'http://localhost:3000';
const OUT = 'docs/media';
const WIDTH = 1280;
const HEIGHT = 800;

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: WIDTH, height: HEIGHT },
  colorScheme: 'light',
  recordVideo: { dir: OUT, size: { width: WIDTH, height: HEIGHT } },
});
const page = await context.newPage();

await page.goto(BASE, { waitUntil: 'networkidle' });
// The hero animates itself in on load. Opening the video mid-animation shows a
// half-faded headline, so wait for it to finish rather than guessing short.
await page.waitForTimeout(5000);

const pageHeight = await page.evaluate(() => document.body.scrollHeight);
const distance = pageHeight - HEIGHT;

// Scroll a screenful at a time and pause. Sections reveal themselves as they
// enter the viewport, and scrolling straight past at a constant rate catches
// every one of them mid-fade — the pause is what lets each finish, and it also
// reads like someone actually reading the page.
const CHAPTER = Math.round(HEIGHT * 0.72);
const TICK = 40;
const PAUSE_BETWEEN_CHAPTERS = 620;

console.log(`page height ${pageHeight}px, scrolling ${distance}px`);

let scrolled = 0;
while (scrolled < distance) {
  const target = Math.min(CHAPTER, distance - scrolled);
  for (let moved = 0; moved < target; moved += TICK) {
    await page.mouse.wheel(0, TICK);
    await page.waitForTimeout(16);
  }
  scrolled += target;
  await page.waitForTimeout(PAUSE_BETWEEN_CHAPTERS);
}

// Rest on the footer so the last frame is a finished page, not a blur.
await page.waitForTimeout(1500);

await context.close();
await browser.close();

// Playwright names the file after the page's guid; give it a stable name.
const files = (await readdir(OUT)).filter((f) => f.endsWith('.webm') && f !== 'landing.webm');
if (files.length) {
  await rename(join(OUT, files[0]), join(OUT, 'landing.webm'));
  console.log(`wrote ${OUT}/landing.webm`);
} else {
  console.error('no video produced');
  process.exit(1);
}
