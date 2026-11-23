// Renders mockup HTML files to PNG next to docs/ui/. Usage: node shoot.mjs [name-prefix ...]
// Needs Playwright with Chromium. Each page is shot at 1440 px wide, 2x, full height.
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const only = process.argv.slice(2);
const files = readdirSync(here).filter((f) => f.endsWith(".html") && (only.length === 0 || only.some((p) => f.startsWith(p))));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
for (const f of files) {
  await page.goto("file://" + join(here, f), { waitUntil: "load" });
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: 1440, height: Math.max(900, h) });
  await page.screenshot({ path: join(here, "..", f.replace(/\.html$/, ".png")), fullPage: true });
  console.log("rendered", f);
}
await browser.close();
