// Renders every diagram module in this folder to ../<name>.svg and ../<name>.png (2x).
// Usage: node docs/diagrams/source/render.mjs [name ...]
import { readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createDiagram } from './lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, '..');
const only = process.argv.slice(2);
const names = readdirSync(here).filter((f) => f.endsWith('.mjs') && !['lib.mjs', 'render.mjs'].includes(f))
  .map((f) => f.replace(/\.mjs$/, '')).filter((n) => !only.length || only.includes(n));

let chromium = null;
try { chromium = createRequire(import.meta.url)('playwright').chromium; } catch { console.warn('playwright not found: writing SVG only'); }
const browser = chromium ? await chromium.launch() : null;
const page = browser ? await browser.newPage({ deviceScaleFactor: 2 }) : null;
for (const n of names) {
  const mod = await import(pathToFileURL(join(here, `${n}.mjs`)).href);
  const d = createDiagram(n);
  mod.default(d);
  const svg = d.render();
  writeFileSync(join(out, `${n}.svg`), svg);
  if (page) {
    await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
    await page.locator('svg').first().screenshot({ path: join(out, `${n}.png`) });
  }
  console.log('rendered', n);
}
await browser?.close();
