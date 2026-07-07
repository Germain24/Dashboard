// frontend/.lufa_scrape.mjs
// Scrape le marché Lufa (lufa.com) — nécessite un compte connecté avec un
// point relais choisi pour voir prix/dispo, contrairement aux vitrines
// Instacart. Utilise un PROFIL EDGE PERSISTANT (launchPersistentContext) :
// connecte-toi une fois manuellement dans ce profil (voir instructions
// d'exécution), la session est réutilisée par tous les runs suivants.
//
// Usage:  node .lufa_scrape.mjs <sortie.json> <terme1> <terme2> ...
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
// Profil dédié (séparé du profil Edge par défaut), gitignoré comme les caches
// data/imports/*. Créé automatiquement au premier lancement.
const PROFILE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '.lufa_profile');
const MARKET_URL = 'https://montreal.lufa.com/en/marketplace';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/lufa.json');
const TERMS = process.argv.slice(3);

const EXTRACT = () => {
  const cards = [...document.querySelectorAll('[class*="product-card"], [class*="ProductCard"]')];
  const num = (s) => (s ? parseFloat(s.replace(',', '.')) : null);
  return cards.map((c) => {
    const t = (c.innerText || '').replace(/\s+/g, ' ').trim();
    const nameEl = c.querySelector('[class*="product-name"], [class*="title"], h3, h4');
    const name = (nameEl ? nameEl.textContent : t.split('\n')[0] || '').trim();
    const href = (c.querySelector('a') || {}).href || null;
    const cur = t.match(/\$(\d+[.,]\d{2})/);
    const unit = t.match(/\$(\d+[.,]\d{2})\s*\/\s*(kg|lb|g|l|ml|each|ea|un)/i);
    const sale = /(\d+)%\s*off|promo/i.test(t);
    const fmt = (t.match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack|un)\b/i) || [])[0] || '';
    return {
      name, href,
      price: cur ? num(cur[1]) : null,
      price_unit: null,
      unit_price: unit ? num(unit[1]) : null,
      unit: unit ? unit[2].toLowerCase() : null,
      original_price: null,
      on_sale: sale,
      discount_pct: null,
      format: fmt,
    };
  }).filter((x) => x.name && x.price != null);
};

fs.mkdirSync(PROFILE_DIR, { recursive: true });
const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
  executablePath: EDGE, headless: true,
  viewport: { width: 1366, height: 1000 }, locale: 'en-CA',
});
const page = ctx.pages()[0] || await ctx.newPage();

const byKey = new Map();
try {
  await page.goto(MARKET_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(4000);
  if (TERMS.length === 0) {
    const items = await page.evaluate(EXTRACT);
    for (const it of items) byKey.set(it.href || it.name.toLowerCase(), { ...it, query: null });
  } else {
    for (const term of TERMS) {
      try {
        await page.goto(`${MARKET_URL}?search=${encodeURIComponent(term)}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(2600);
        const items = await page.evaluate(EXTRACT);
        for (const it of items) {
          const key = it.href || it.name.toLowerCase();
          if (!byKey.has(key)) byKey.set(key, { ...it, query: term });
        }
        console.error(`[lufa] "${term}" -> ${items.length} (total ${byKey.size})`);
      } catch (e) {
        console.error(`[lufa] "${term}" ERREUR ${String(e).slice(0, 100)}`);
      }
    }
  }
} catch (e) {
  console.error(`[lufa] ERREUR navigation marketplace: ${String(e).slice(0, 200)} — session Lufa probablement non connectée, voir instructions de connexion manuelle`);
}
await ctx.close();

const out = [...byKey.values()].sort((a, b) => (a.name || '').localeCompare(b.name || ''));

if (out.length === 0 && fs.existsSync(OUT)) {
  try {
    const prev = JSON.parse(fs.readFileSync(OUT, 'utf-8'));
    if (Array.isArray(prev.items) && prev.items.length > 0) {
      console.error(`[lufa] 0 items ce run, cache existant (${prev.items.length}) conservé, pas d'écrasement`);
      process.exit(0);
    }
  } catch { /* cache illisible, on écrase normalement */ }
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'lufa.com/marketplace (session persistante)', scraped_at: new Date().toISOString(), count: out.length, items: out }, null, 2));
console.error(`[lufa] ${out.length} items écrits dans ${OUT}`);
