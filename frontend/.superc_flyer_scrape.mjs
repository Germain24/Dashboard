// Scrape la circulaire hebdo Super C pour capter les rabais ponctuels (promos
// de la semaine, non reflétés sur Instacart). store_pricing.py compare ce cache
// au prix Instacart courant et retient le moins cher (voir _best_price).
//
// La circulaire (circulaire.superc.ca) est une visionneuse d'images, MAIS les
// produits sont servis en JSON par l'API digital-flyer de Metro : chaque page
// (`/api/pages/<pubId>/<storeId>/bil/`) contient des `blocks[].products[]` avec
// productEn/Fr, salePrice, regularPrice. On lit cette réponse au vol (pas de
// scraping d'image / OCR). Schéma de sortie identique aux autres scrapers.
//
// Usage:  node .superc_flyer_scrape.mjs <sortie.json> [storeId=847]
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/superc_flyer.json');
const STORE_ID = process.argv[3] || '847';   // 847 = Super C Marché St-Jacques (MTL)

const num = (s) => {
  const m = (s || '').toString().replace(',', '.').match(/\d+(?:\.\d+)?/);
  return m ? parseFloat(m[0]) : null;
};

const b = await chromium.launch({ executablePath: EDGE, headless: true });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'fr-CA' });
const page = await ctx.newPage();

// La réponse "pages" (avec les blocks/products) est chargée par la visionneuse ;
// on la capte au vol plutôt que de rejouer l'API (clé APIM + pubId à deviner).
let pagesBody = null;
page.on('response', async (r) => {
  if (/\/api\/pages\/\d+\/\d+\/bil\/?$/i.test(r.url())) {
    try { pagesBody = await r.json(); } catch { /* best-effort */ }
  }
});

let items = [];
try {
  await page.goto(`https://circulaire.superc.ca/?storeId=${STORE_ID}&language=fr`,
    { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(6000);

  const seen = new Set();
  for (const pg of (pagesBody || [])) {
    for (const bl of (pg.blocks || [])) {
      for (const p of (bl.products || [])) {
        const name = (p.productEn || p.productFr || '').trim();
        const price = num(p.salePrice);
        if (!name || price == null) continue;
        // Prix/format unitaires depuis regularPrice ("4,49/lb - 9,90/kg") + contents.
        const rp = `${p.regularPrice || ''} ${p.contents || ''}`;
        const um = rp.match(/(\d+[.,]\d+)\s*\/\s*(kg|lb|g|l|ml|each|ea)/i);
        const fm = (p.contents || '').match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack)\b/i);
        const key = `${name.toLowerCase()}|${price}`;
        if (seen.has(key)) continue;
        seen.add(key);
        items.push({
          name, href: null,
          price,
          price_unit: null,
          unit_price: um ? num(um[1]) : null,
          unit: um ? um[2].toLowerCase() : null,
          original_price: num(p.regularPrice),
          on_sale: true,   // tout item de circulaire est une promo
          discount_pct: null,
          format: fm ? fm[0] : '',
          sku: p.sku || null,
        });
      }
    }
  }
  console.error(`[superc_flyer] ${items.length} produits extraits de la circulaire (API)`);
} catch (e) {
  console.error(`[superc_flyer] ERREUR ${String(e).slice(0, 200)}`);
}
await b.close();

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(
  { source: 'circulaire.superc.ca (digital-flyer API)', scraped_at: new Date().toISOString(), count: items.length, items },
  null, 2));
console.error(`[superc_flyer] ${items.length} items écrits dans ${OUT}`);
