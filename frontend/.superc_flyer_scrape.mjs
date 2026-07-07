// Scrape la circulaire hebdo Super C (superc.ca/circulaire) pour capter les
// rabais ponctuels non reflétés sur Instacart (ex. items en solde cette
// semaine seulement). Format JSON identique aux autres scrapers cuisine :
// store_pricing.py compare ce cache au prix Instacart courant et retient le
// moins cher (voir _best_price, branche "superc").
//
// Usage:  node .superc_flyer_scrape.mjs <sortie.json>
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const FLYER_URL = 'https://www.superc.ca/circulaire';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/superc_flyer.json');

const EXTRACT = () => {
  const cards = [...document.querySelectorAll('[class*="product-tile"], [class*="flyer-item"]')];
  const num = (s) => (s ? parseFloat(s.replace(',', '.')) : null);
  return cards.map((c) => {
    const t = (c.innerText || '').replace(/\s+/g, ' ').trim();
    const nameEl = c.querySelector('[class*="product-title"], [class*="item-name"], h3, h4');
    const name = (nameEl ? nameEl.textContent : t.split('\n')[0] || '').trim();
    const cur = t.match(/\$(\d+[.,]\d{2})/);
    const unit = t.match(/\$(\d+[.,]\d{2})\s*\/\s*(kg|lb|g|l|ml|each|ea)/i);
    const fmt = (t.match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack)\b/i) || [])[0] || '';
    return {
      name,
      href: null,
      price: cur ? num(cur[1]) : null,
      price_unit: null,
      unit_price: unit ? num(unit[1]) : null,
      unit: unit ? unit[2].toLowerCase() : null,
      original_price: null,
      on_sale: true,   // tout item de circulaire est par définition une promo
      discount_pct: null,
      format: fmt,
    };
  }).filter((x) => x.name && x.price != null);
};

const b = await chromium.launch({ executablePath: EDGE, headless: true });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'fr-CA' });
const page = await ctx.newPage();

let items = [];
try {
  await page.goto(FLYER_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(4000);
  items = await page.evaluate(EXTRACT);
  console.error(`[superc_flyer] ${items.length} items extraits de la circulaire`);
} catch (e) {
  console.error(`[superc_flyer] ERREUR ${String(e).slice(0, 200)}`);
}
await b.close();

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'superc.ca/circulaire', scraped_at: new Date().toISOString(), count: items.length, items }, null, 2));
console.error(`[superc_flyer] ${items.length} items écrits dans ${OUT}`);
