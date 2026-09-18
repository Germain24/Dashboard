// Remplit le panier Super C dans une fenêtre Google Chrome visible.
// Entrée stdin: {items:[{aliment,product_id,product_name,href,qty,a_verifier}]}
// Sortie stdout: événements JSONL consommés par le backend.
import fs from 'fs';
import path from 'path';
import puppeteer from 'puppeteer-core';

const BASE = 'https://www.superc.ca';
const STORE_ID = '572';
const STORE_POSTAL = 'H3J2J4';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PROFILE = process.argv[2] || path.resolve('../data/browser_profiles/superc_chrome');
const DEBUG_PORT = 9223;
const emit = (event) => process.stdout.write(`${JSON.stringify(event)}\n`);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const pacedPause = () => sleep(4500 + Math.floor(Math.random() * 3500));

const input = await new Promise((resolve, reject) => {
  let raw = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => { raw += chunk; });
  process.stdin.on('end', () => {
    try { resolve(JSON.parse(raw || '{}')); } catch (error) { reject(error); }
  });
});
const items = Array.isArray(input.items) ? input.items : [];

async function browserInstance() {
  try {
    return await puppeteer.connect({ browserURL: `http://127.0.0.1:${DEBUG_PORT}` });
  } catch {
    fs.mkdirSync(PROFILE, { recursive: true });
    return puppeteer.launch({
      executablePath: CHROME,
      headless: false,
      userDataDir: PROFILE,
      defaultViewport: null,
      args: [`--remote-debugging-port=${DEBUG_PORT}`, '--remote-debugging-address=127.0.0.1'],
    });
  }
}

async function keepOnlyOneTab(browser, page) {
  // Ce profil Chrome est réservé au panier Super C. D'anciens jobs ou certains
  // liens du site peuvent y laisser des onglets : on les ferme explicitement
  // afin que tout le remplissage reste dans le même onglet visible.
  const pages = await browser.pages();
  for (const other of pages) {
    if (other !== page && !other.isClosed()) {
      await other.close().catch(() => {});
    }
  }
}

async function waitForHumanIfBlocked(page, current, total) {
  const blocked = async () => page.evaluate(() => {
    const text = `${document.title} ${document.body?.innerText || ''}`;
    return /vérification de sécurité|un instant|just a moment|attention required/i.test(text);
  }).catch(() => false);
  if (!(await blocked())) return;
  emit({ type: 'status', status: 'awaiting_user', current, total,
    message: 'Super C demande une vérification de sécurité. Termine-la dans Chrome; le remplissage reprendra automatiquement.' });
  const deadline = Date.now() + 10 * 60 * 1000;
  while (Date.now() < deadline) {
    await sleep(2000);
    if (!(await blocked())) return;
  }
  throw new Error('Action Chrome non terminée après 10 minutes');
}

async function cartQuantities(page) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const cartHref = await page.evaluate(() => {
    const links = [...document.querySelectorAll('a[href]')];
    return links.find((a) => /panier|cart/i.test(`${a.getAttribute('href')} ${a.getAttribute('aria-label')} ${a.textContent}`))
      ?.getAttribute('href') || null;
  });
  if (!cartHref) return { href: null, quantities: {} };
  await page.goto(new URL(cartHref, BASE).href, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(1200);
  const quantities = await page.evaluate(() => {
    const out = {};
    for (const link of document.querySelectorAll('a[href*="/p/"]')) {
      const match = link.getAttribute('href')?.match(/\/p\/(\d+)/);
      if (!match) continue;
      const row = link.closest('li, article, [class*="cart"], [class*="product"]') || link.parentElement;
      const input = row?.querySelector('input[type="number"], input[name*="quantity"]');
      const value = Number(input?.value || input?.getAttribute('value') || 1);
      out[match[1]] = Number.isFinite(value) && value > 0 ? value : 1;
    }
    return out;
  });
  return { href: new URL(cartHref, BASE).href, quantities };
}

async function ensureAtwaterStore(page) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitForHumanIfBlocked(page, 0, items.length);
  const alreadyAtwater = await page.evaluate(() => /atwater/i.test(document.body?.innerText || ''));
  if (alreadyAtwater) return;
  emit({ type: 'status', status: 'running', current: 0, total: items.length,
    message: 'Sélection du magasin Super C Atwater…' });
  const changed = await page.evaluate(() => {
    const candidates = [...document.querySelectorAll('button, a')];
    const element = candidates.find((node) => /changer de magasin/i.test(node.textContent || ''));
    if (element) element.click();
    return !!element;
  });
  if (!changed) throw new Error('Impossible d’ouvrir la sélection du magasin');
  await sleep(1200);
  const postal = await page.$('#postalCode');
  if (!postal) throw new Error('Champ de code postal introuvable');
  await postal.click({ clickCount: 3 });
  await postal.type(STORE_POSTAL, { delay: 100 });
  await page.click('#submit');
  await sleep(2200);
  const selected = await page.evaluate((storeId) => {
    const exact = document.querySelector(`label[for="${storeId}"]`);
    const fallback = [...document.querySelectorAll('label, button, [role="radio"]')]
      .find((node) => /atwater/i.test(node.textContent || ''));
    const element = exact || fallback;
    if (element) element.click();
    return !!element;
  }, STORE_ID);
  if (!selected) throw new Error('Magasin Atwater introuvable');
  await sleep(800);
  const confirmed = await clickByText(page, /confirmer mon magasin/);
  if (!confirmed) throw new Error('Confirmation du magasin introuvable');
  await sleep(2500);
  const ok = await page.evaluate(() => /atwater/i.test(document.body?.innerText || ''));
  if (!ok) throw new Error('Le magasin Atwater n’a pas été confirmé');
}

async function clickByText(page, pattern) {
  const handle = await page.evaluateHandle((source) => {
    const re = new RegExp(source, 'i');
    return [...document.querySelectorAll('button')].find((button) =>
      !button.disabled && re.test(`${button.innerText} ${button.getAttribute('aria-label') || ''}`)) || null;
  }, pattern.source);
  const element = handle.asElement();
  if (!element) { await handle.dispose(); return false; }
  await element.click();
  await handle.dispose();
  return true;
}

async function clickAndConfirmCartChange(page, pattern, productId) {
  // L'ancien code considérait le clic comme un ajout réussi immédiatement.
  // Ici on attend soit la requête panier confirmée par Super C, soit
  // l'apparition du sélecteur de quantité sur la fiche produit.
  const networkConfirmation = page.waitForResponse((response) => {
    const request = response.request();
    return request.method() !== 'GET'
      && /cart|panier|basket|order|commerce/i.test(response.url())
      && response.status() >= 200 && response.status() < 400;
  }, { timeout: 20000 }).then(() => true);
  const domConfirmation = page.waitForFunction((id) => {
    const tagged = [...document.querySelectorAll('*')].find((node) =>
      [...node.attributes].some((attr) => String(attr.value).includes(String(id))));
    const root = tagged?.closest('article, [class*="product"], main')
      || document.querySelector('main') || document.body;
    const numericQuantity = [...root.querySelectorAll('input[type="number"], input[name*="quantity"]')]
      .some((input) => Number(input.value || input.getAttribute('value') || 0) > 0);
    const hasQuantityControls = [...root.querySelectorAll('button')].some((button) =>
      /augmenter|diminuer|retirer|ajouter une unité/i.test(
        `${button.innerText || ''} ${button.getAttribute('aria-label') || ''}`));
    return numericQuantity || hasQuantityControls;
  }, { timeout: 20000, polling: 300 }, productId).then(() => true);

  const clicked = await clickByText(page, pattern);
  if (!clicked) return false;
  try {
    await Promise.any([networkConfirmation, domConfirmation]);
    return true;
  } catch {
    return false;
  }
}

let browser;
try {
  emit({ type: 'status', status: 'running', current: 0, total: items.length,
    message: 'Ouverture de Google Chrome…' });
  browser = await browserInstance();
  const pages = await browser.pages();
  const page = pages.find((candidate) => candidate.url().includes('superc.ca')) || pages[0] || await browser.newPage();
  await keepOnlyOneTab(browser, page);
  await ensureAtwaterStore(page);
  const cart = await cartQuantities(page);
  await waitForHumanIfBlocked(page, 0, items.length);

  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    const baseResult = { aliment: item.aliment, product_name: item.product_name,
      requested_qty: item.qty, a_verifier: !!item.a_verifier };
    if (!item.product_id || !item.href) {
      emit({ type: 'item', result: { ...baseResult, status: 'not_found', added_qty: 0,
        message: 'Aucune correspondance produit.' } });
      continue;
    }
    const currentQty = Number(cart.quantities[item.product_id] || 0);
    const missing = Math.max(0, Number(item.qty || 1) - currentQty);
    if (missing === 0) {
      emit({ type: 'item', result: { ...baseResult, status: 'already_present', added_qty: 0,
        message: `Quantité déjà suffisante (${currentQty}).` } });
      continue;
    }
    try {
      emit({ type: 'status', status: 'running', current: index, total: items.length,
        message: `Ajout de ${item.product_name || item.aliment}…` });
      if (index > 0) await pacedPause();
      await page.goto(new URL(item.href, BASE).href, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitForHumanIfBlocked(page, index, items.length);
      await sleep(1400);
      await keepOnlyOneTab(browser, page);
      if (!(await clickAndConfirmCartChange(page, /ajouter(?: au panier)?/, item.product_id))) {
        throw new Error('Ajout non confirmé par Super C');
      }
      for (let n = 1; n < missing; n += 1) {
        await sleep(900);
        if (!(await clickAndConfirmCartChange(page, /augmenter|plus|ajouter une unité/, item.product_id))) {
          throw new Error(`Quantité non confirmée après ${n} unité(s)`);
        }
      }
      await keepOnlyOneTab(browser, page);
      cart.quantities[item.product_id] = currentQty + missing;
      emit({ type: 'item', result: { ...baseResult, status: 'added', added_qty: missing,
        message: `${missing} unité(s) ajoutée(s).` } });
    } catch (error) {
      emit({ type: 'item', result: { ...baseResult, status: 'failed', added_qty: 0,
        message: String(error?.message || error) } });
    }
  }
  if (cart.href) await page.goto(cart.href, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
  emit({ type: 'done', message: 'Panier prêt dans Google Chrome.' });
  await browser.disconnect(); // laisse la fenêtre Chrome ouverte pour vérification
} catch (error) {
  emit({ type: 'status', status: 'failed', current: 0, total: items.length,
    message: String(error?.message || error) });
  if (browser) await browser.disconnect().catch(() => {});
  process.exitCode = 1;
}
