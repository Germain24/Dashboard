import { chromium } from 'playwright-core';
import fs from 'fs';
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const queries = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8')); // [{key, q}]
const out = {};
const b = await chromium.launch({ executablePath: edge, headless: true });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'fr-CA' });
const page = await ctx.newPage();
async function searchOne(q) {
  await page.goto('https://sameday.costco.ca/store/costco-canada/storefront', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2200);
  const box = await page.$('input[type="search"], input[placeholder*="Rech" i], input[placeholder*="Search" i]');
  if (!box) return [];
  await box.click(); await box.fill(q); await page.keyboard.press('Enter');
  await page.waitForTimeout(4200);
  return await page.evaluate(() => {
    const out = []; const re = /(\d+[.,]\d{2})\s*\$/;
    document.querySelectorAll('li, article, [role="group"]').forEach(el => {
      const t = (el.innerText || '').replace(/\n+/g, ' | ').trim();
      const m = t.match(re);
      if (m && t.length < 220) {
        const np = t.match(/(\d+[.,]\d{2})\s*\$\s*pour non-Instacart/);
        const price = parseFloat((np ? np[1] : m[1]).replace(',', '.'));
        const segs = t.split(' | ').filter(s => /[A-Za-zÀ-ÿ]{4}/.test(s) && !/Prix|Instacart|Ajouter|pour non|TPS|TVQ/i.test(s));
        const name = segs.sort((a, b) => b.length - a.length)[0] || '';
        const fmt = (t.match(/\b(\d+(?:[.,]\d+)?\s*(?:x\s*\d+(?:[.,]\d+)?\s*)?(?:kg|g|l|ml|unités?|u)\b)/i) || [])[0] || '';
        out.push({ name, price, fmt });
      }
    });
    // dédupe par nom
    const seen = new Set();
    return out.filter(o => { const k = o.name + o.price; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 10);
  });
}
for (const { key, q } of queries) {
  try { out[key] = await searchOne(q); } catch (e) { out[key] = [{ err: String(e).slice(0, 80) }]; }
}
fs.writeFileSync(process.argv[3], JSON.stringify(out, null, 1));
console.log('scrapé', Object.keys(out).length, 'requêtes');
await b.close();
