// Scrape la vitrine "Super C powered by Instacart" (instacart.ca/store/super-c),
// même pattern que .adonis_scrape.mjs. Les termes de recherche sont passés en
// argument (dérivés de la liste de courses de la semaine par le backend) :
// évite une liste figée, reste rapide et à jour avec le plan de repas courant.
//
// Usage:  node .superc_scrape.mjs <sortie.json> <terme1> <terme2> ...
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const STORE = 'https://www.instacart.ca/store/super-c';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/superc.json');
const TERMS = process.argv.slice(3);

const EXTRACT = () => {
  const cards = [...document.querySelectorAll('a[data-item-card-button="true"]')];
  const num = (s) => (s ? parseFloat(s.replace(',', '.')) : null);
  return cards.slice(0, 14).map((c) => {
    const img = c.querySelector('img[data-testid="item-card-image"]');
    const name = img ? (img.getAttribute('alt') || '').trim() : '';
    const t = (c.innerText || '').replace(/\s+/g, ' ').trim();
    const href = (c.getAttribute('href') || '').split('?')[0];
    const id = (href.match(/\/products\/(\d+)/) || [])[1] || null;
    const cur = t.match(/Current price:\s*\$(\d+[.,]\d{2})\s*([a-z]+)?/i) || t.match(/\$(\d+[.,]\d{2})\s*(each|lb|kg|g|ea)?/i);
    const orig = t.match(/Original Price:\s*\$(\d+[.,]\d{2})/i);
    const unit = t.match(/\$(\d+[.,]\d{2})\s*\/\s*(kg|lb|g|l|ml|each|ea)/i);
    const sale = /(\d+)%\s*off/i.exec(t);
    const fmt = (t.match(/About\s+[\d.,]+\s*(kg|lb|g)\s*each/i) || [])[0]
      || (t.match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack)\b/i) || [])[0] || '';
    return {
      name, id, href,
      price: cur ? num(cur[1]) : null,
      price_unit: cur && cur[2] ? cur[2].toLowerCase() : null,
      unit_price: unit ? num(unit[1]) : null,
      unit: unit ? unit[2].toLowerCase() : null,
      original_price: orig ? num(orig[1]) : null,
      on_sale: !!orig || !!sale,
      discount_pct: sale ? parseInt(sale[1], 10) : null,
      format: fmt,
    };
  }).filter((x) => x.name || x.href);
};

const b = await chromium.launch({ executablePath: EDGE, headless: true });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'en-CA' });
const page = await ctx.newPage();
try {
  await page.goto(`${STORE}/storefront`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(6000);
} catch { /* best-effort */ }

const byKey = new Map();
for (const term of TERMS) {
  try {
    await page.goto(`${STORE}/s?k=${encodeURIComponent(term)}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2600);
    let items = await page.evaluate(EXTRACT);
    if (items.length === 0) {
      await page.waitForTimeout(3500);
      items = await page.evaluate(EXTRACT);
    }
    for (const it of items) {
      const key = it.id || it.name.toLowerCase();
      if (!byKey.has(key)) byKey.set(key, { ...it, query: term });
    }
    console.error(`[superc] "${term}" -> ${items.length} (total ${byKey.size})`);
  } catch (e) {
    console.error(`[superc] "${term}" ERREUR ${String(e).slice(0, 100)}`);
  }
}
await b.close();

const out = [...byKey.values()].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'instacart.ca/store/super-c (search)', scraped_at: new Date().toISOString(), count: out.length, items: out }, null, 2));
console.error(`[superc] ${out.length} items écrits dans ${OUT}`);
