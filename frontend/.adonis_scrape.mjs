// Scrape les fruits & légumes Adonis (prix + unité) depuis la vitrine
// "Adonis powered by Instacart" — groupeadonis.ca n'affiche pas de prix.
// Pendant : .sameday_scrape.mjs (Costco). Fruits/légumes chez Adonis, reste chez Costco.
//
// Recherche par terme (comme le scraper Costco) : les pages de rayon sont
// plafonnées à 24 items, alors que la recherche n'a pas de limite et trouve
// chaque produit précis. On agrège tous les résultats dans un JSON plat ;
// le backend (app/services/sante/adonis_pricing.py) re-tarife aliments.csv.
//
// Usage:  node .adonis_scrape.mjs [sortie.json]
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const STORE = 'https://www.instacart.ca/store/adonis';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/adonis_fruits_legumes.json');

// Termes de recherche = fruits & légumes du catalogue nutrition (en anglais).
const TERMS = [
  'banana', 'apple', 'orange', 'avocado', 'red grapes', 'green grapes', 'blueberries',
  'strawberries', 'raspberries', 'cherries', 'medjool dates', 'pineapple', 'kiwi',
  'clementine', 'pear', 'peach', 'mango', 'pomegranate', 'grapefruit', 'plum',
  'prunes', 'dried cranberries', 'broccoli', 'spinach', 'carrots', 'red bell pepper',
  'onion', 'tomato', 'sweet potato', 'white mushrooms', 'cauliflower', 'cucumber',
  'celery', 'asparagus', 'zucchini', 'eggplant', 'arugula', 'green beans',
  'green peas', 'black olives', 'bell pepper',
];

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
// Warm-up : la 1re navigation initialise la session Instacart (sinon les 1res
// recherches renvoient 0 résultat le temps que le storefront s'amorce).
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
    if (items.length === 0) {  // cold/slow : on retente une fois avec plus d'attente
      await page.waitForTimeout(3500);
      items = await page.evaluate(EXTRACT);
    }
    for (const it of items) {
      const key = it.id || it.name.toLowerCase();
      if (!byKey.has(key)) byKey.set(key, { ...it, query: term });
    }
    console.error(`[adonis] "${term}" -> ${items.length} (total ${byKey.size})`);
  } catch (e) {
    console.error(`[adonis] "${term}" ERREUR ${String(e).slice(0, 100)}`);
  }
}
await b.close();

const out = [...byKey.values()].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'instacart.ca/store/adonis (search)', scraped_at: new Date().toISOString(), count: out.length, items: out }, null, 2));
console.error(`[adonis] ${out.length} items écrits dans ${OUT}`);
