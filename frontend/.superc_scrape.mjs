// Scrape le vrai catalogue en ligne Super C (superc.ca, plateforme e-commerce
// Metro) — remplace l'ancien scraper Instacart (marge/frais de service +
// noms anglais, voir orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md).
// Pour chaque terme de recherche : page.goto('/recherche?filter=<terme>'),
// puis lecture des cartes produit directement via leurs attributs data-*
// (noms FR, UPC, prix courant, $/100g) plutôt qu'en parsant le innerText.
//
// Contexte magasin : superc.ca affiche les prix du magasin sélectionné en
// session (pas de cookie dédié rejouable, tout tient au JSESSIONID). Un
// contexte Playwright neuf démarre sur le magasin par défaut ("Marché
// St-Jacques") et affiche "0 produit" tant qu'aucun magasin n'est choisi. On
// rejoue donc une fois par run le flux "Changer de magasin" -> code postal ->
// sélection du magasin -> confirmer ; ça persiste ensuite pour tous les
// pages suivantes (même contexte/cookie de session), un seul aller-retour UI
// par run. Magasin cible : Super C Atwater (H3J 2J4).
//
// Anti-bot : superc.ca (Cloudflare) sert un challenge interactif
// ("Vérification de sécurité en cours") à un Playwright headless nu
// (navigator.webdriver détecté). Masquer navigator.webdriver + UA desktop
// réaliste + --disable-blink-features=AutomationControlled suffit à passer
// sans interaction (validé en conditions réelles sur plusieurs runs) ; on
// garde quand même une détection + un reload de secours au cas où.
//
// Cartes produit : `.default-product-tile[data-product-code]` porte tout en
// attributs data-* (data-product-code = UPC/PLU, data-product-name,
// data-product-brand) — bien plus fiable que parser le texte affiché. Prix
// courant : attribut data-main-price sur le bloc de prix (gère aussi
// nativement les promos "2 pour 5,00 $", où aucun "X,XX $ ch." n'est affiché
// pour le prix soldé mais où data-main-price donne déjà le prix unitaire
// équivalent, ex. 2.50). NB : le site affiche parfois "X,XX $ /100kg" au lieu
// de "/100g" (bug d'affichage Metro/superc.ca) mais le NOMBRE reste toujours
// un $/100g valide (vérifié sur plusieurs produits vs. prix ÷ poids du
// format) — on ne le retraite donc pas, on ignore juste l'unité affichée.
//
// Deux modes :
//
//   node .superc_scrape.mjs <sortie.json> <terme1> <terme2> ...
//       Mode RECHERCHE (historique) : une page /recherche?filter=<terme> par
//       terme, 24 produits au plus chacune.
//
//   node .superc_scrape.mjs <sortie.json> --rayons [rayon1 rayon2 ...]
//       Mode RAYONS : parcourt /allees/<rayon>, puis /allees/<rayon>-page-2,
//       -page-3… jusqu'à épuisement. Sans liste, les 16 rayons alimentaires
//       par défaut sont parcourus (~6 800 produits, ~285 pages).
//
// Pourquoi le mode rayons existe : le robots.txt de superc.ca interdit
// */recherche ainsi que les paramètres *filter=* et *page=* — soit exactement
// le chemin du mode historique. Les pages /allees/ ne sont pas interdites, et
// leur pagination passe par le CHEMIN (« -page-2 »), pas par un paramètre : le
// mode rayons est donc conforme, en plus de couvrir tout le magasin au lieu des
// seuls produits atteints par une liste de mots-clés.
import { chromium } from 'playwright-core';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';

// Navigateur : Chrome (choix utilisateur). Playwright-core ne télécharge aucun
// binaire, on pointe donc une installation existante. Les deux emplacements
// standards sont testés, et CHROME_PATH permet de forcer le chemin.
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
].filter(Boolean);
const CHROME = CHROME_CANDIDATES.find((p) => fs.existsSync(p));

const BASE = 'https://www.superc.ca';
const STORE_ID = '572';           // Super C Atwater, 147 av. Atwater, Montréal
const STORE_NAME = 'Super C - Atwater';
const STORE_POSTAL = 'H3J2J4';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/superc.json');
// Les checkpoints vivent à part : une collecte interrompue par Cloudflare ne
// doit jamais remplacer le dernier catalogue complet et rendre la génération
// de repas inutilisable.
const PARTIAL_OUT = `${OUT}.partial`;
const PROFILE = path.resolve('../data/browser_profiles/superc_prices_chrome');
const ARGS = process.argv.slice(3);
const RAYON_MODE = ARGS[0] === '--rayons';
const CIRCULAIRE_MODE = ARGS[0] === '--circulaire';
const TERMS = (RAYON_MODE || CIRCULAIRE_MODE) ? [] : ARGS;
const MAX_PER_TERM = 24;

// Rayons alimentaires de superc.ca (les non-alimentaires — entretien, pharmacie,
// loterie, bières et vins… — sont volontairement exclus : ils n'ont rien à faire
// dans un catalogue nutritionnel et coûteraient 400 pages de plus).
const DEFAULT_RAYONS = [
  'fruits-et-legumes', 'viandes-et-volailles', 'poissons-et-fruits-de-mer',
  'produits-laitiers-et-oeufs', 'garde-manger', 'pains-et-patisseries',
  'produits-surgeles', 'collations', 'boissons', 'charcuteries-et-plats-prepares',
  'plats-cuisines', 'cuisine-du-monde', 'epicerie-biologique',
  'aliments-vegetariens-et-vegetaliens', 'format-economique', 'bebe',
];
const RAYONS = RAYON_MODE ? (ARGS.slice(1).length ? ARGS.slice(1) : DEFAULT_RAYONS) : [];
const CIRCULAIRE_QUERY = '?sortOrder=relevance&filter=%3Arelevance%3Adeal%3ACirculaire+et+promotions';
// Garde-fou : le plus gros rayon (garde-manger) fait ~1 850 produits, soit ~78
// pages. 150 laisse de la marge sans risquer une boucle infinie si le site
// renvoyait indéfiniment la même page.
const MAX_PAGES_PER_RAYON = 150;
const TILES_PER_PAGE = 200;   // plafond large : on prend toute la page en mode rayons
// Super C déclenche maintenant sa vérification après seulement 2–3 pages. On
// adopte donc un rythme humain : 15–25 s entre pages et une vraie pause après
// chaque paire. Tous les délais restent configurables pour les ajuster sans
// toucher au code.
const PAGE_DELAY_MS = Number(process.env.SUPERC_PAGE_DELAY_MS || 15000);
const PAGE_JITTER_MS = Number(process.env.SUPERC_PAGE_JITTER_MS || 10000);
const PAGES_PER_COOLDOWN = Math.max(1, Number(process.env.SUPERC_PAGES_PER_COOLDOWN || 2));
const COOLDOWN_MS = Number(process.env.SUPERC_COOLDOWN_MS || 60000);
const COOLDOWN_JITTER_MS = Number(process.env.SUPERC_COOLDOWN_JITTER_MS || 30000);
let pagesSinceCooldown = 0;
let challengeBackoff = 1;
const politeDelay = async (page) => {
  const jitter = Math.floor(Math.random() * Math.max(0, PAGE_JITTER_MS));
  await page.waitForTimeout((PAGE_DELAY_MS + jitter) * challengeBackoff);
  pagesSinceCooldown++;
  if (pagesSinceCooldown >= PAGES_PER_COOLDOWN) {
    const cooldownJitter = Math.floor(Math.random() * Math.max(0, COOLDOWN_JITTER_MS));
    const duration = (COOLDOWN_MS + cooldownJitter) * challengeBackoff;
    console.error(`[superc] pause anti-débit ${Math.round(duration / 1000)} s`);
    await page.waitForTimeout(duration);
    pagesSinceCooldown = 0;
  }
};

const CF_CHALLENGE_RE = /un instant|just a moment|attention required|v[ée]rification de s[ée]curit[ée]/i;

// Exécuté dans la page (un argument sérialisable : le plafond d'items).
// Lit chaque carte produit via ses attributs data-* (voir commentaire de
// tête), ignore les cartes "Commandité" (sponsorisées) et déduplique par
// UPC/PLU (data-product-code).
const EXTRACT = (maxItems) => {
  const num = (s) => {
    if (s == null) return null;
    const m = String(s).trim().replace(',', '.').match(/-?\d+(?:\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  };
  const tiles = [...document.querySelectorAll('.default-product-tile[data-product-code]')];
  const seen = new Set();
  const out = [];
  for (const tile of tiles) {
    if (tile.classList.contains('sponsoredTile')) continue;
    if (tile.querySelector('.head__sponsored')) continue;
    if (/commandité/i.test(tile.innerText || '')) continue;

    const upc = tile.getAttribute('data-product-code');
    if (!upc || seen.has(upc)) continue;
    seen.add(upc);

    const brand = (tile.getAttribute('data-product-brand') || '').trim();
    const baseName = (tile.getAttribute('data-product-name') || '').trim();
    const name = [brand, baseName].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();

    const link = tile.querySelector('a.product-details-link[href*="/p/"]')
      || tile.querySelector('a[href*="/allees/"][href*="/p/"]');
    const href = link ? link.getAttribute('href') : null;

    const format = (tile.querySelector('.head__unit-details')?.textContent || '').trim();

    const priceEl = tile.querySelector('.content__pricing [data-main-price]');
    let price = priceEl ? num(priceEl.getAttribute('data-main-price')) : null;
    if (price == null) {
      // Repli si l'attribut manque un jour : prix affiché "X,XX $ ... ch."
      const saleTxt = tile.querySelector('.pricing__sale-price')?.innerText || '';
      price = num((saleTxt.match(/(\d+[.,]\d{2})\s*\$/) || [])[1]);
    }

    const beforeEl = tile.querySelector('.pricing__before-price');
    const original_price = beforeEl
      ? num((beforeEl.innerText.match(/(\d+[.,]\d{2})\s*\$/) || [])[1])
      : null;

    // "$ /100g" direct (garde-manger), sinon dérivé de "$ /kg" (fruits et
    // légumes vendus au poids, ex. banane : pas de /100g affiché du tout).
    const secondaryTxt = (tile.querySelector('.pricing__secondary-price')?.innerText || '').replace(/\s+/g, ' ');
    // Pas de \b après "kg" : le span $/kg est parfois collé sans séparateur
    // au span $/lb suivant (ex. "1,74 $ /kg0,79 $ /lb"), ce qui casse une
    // frontière de mot classique entre "g" et le chiffre suivant.
    let price_per_100g = num((secondaryTxt.match(/(\d+[.,]\d+)\s*\$\s*\/\s*100/) || [])[1]);
    if (price_per_100g == null) {
      const perKg = num((secondaryTxt.match(/(\d+[.,]\d+)\s*\$\s*\/\s*kg/i) || [])[1]);
      if (perKg != null) price_per_100g = Math.round((perKg / 10) * 100) / 100;
    }
    // unit_price/unit : équivalent $/kg — sémantique attendue par les
    // consommateurs existants (adonis_pricing.adonis_price_per_100g_edible
    // fait per_kg = unit_price quand unit === "kg"), dérivé de price_per_100g
    // pour rester cohérent avec la valeur directe ci-dessus.
    const unit_price = price_per_100g != null ? Math.round(price_per_100g * 1000) / 100 : null;
    const unit = price_per_100g != null ? 'kg' : null;

    const stickers = tile.querySelector('.visual__stickers');
    const on_sale = !!(beforeEl || tile.querySelector('.icon--sale')
      || stickers?.getAttribute('data-dimension-8') === 'PROMO');

    out.push({
      name, id: upc, sku: upc, href,
      price, price_per_100g, unit_price, unit,
      original_price, on_sale, format,
    });
    if (out.length >= maxItems) break;
  }
  return out;
};

const isBlocked = async (page) => {
  const text = await page.evaluate(() => `${document.title} ${document.body?.innerText || ''}`).catch(() => '');
  return CF_CHALLENGE_RE.test(text);
};

if (!CHROME) {
  console.error('[superc] Chrome introuvable — installe-le ou définis CHROME_PATH.');
  process.exit(2);
}
fs.mkdirSync(PROFILE, { recursive: true });
// Profil persistant et fenêtre visible : le contexte headless éphémère était
// systématiquement rechallengé par Super C. Les témoins et la validation
// Cloudflare survivent désormais aux générations suivantes, et l'utilisateur
// peut terminer le contrôle dans cette fenêtre dédiée si nécessaire.
const ctx = await chromium.launchPersistentContext(PROFILE, {
  executablePath: CHROME,
  headless: process.env.SUPERC_HEADLESS === '1',
  chromiumSandbox: true,
  viewport: { width: 1366, height: 1000 },
  locale: 'fr-CA',
  args: ['--disable-blink-features=AutomationControlled'],
});
await ctx.addInitScript(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
});
const page = ctx.pages()[0] || await ctx.newPage();
const browser = ctx.browser();
let browserClosed = false;
const closeBrowser = async () => {
  if (browserClosed) return;
  browserClosed = true;
  // Fermer d'abord chaque onglet évite qu'une boîte beforeunload ou une page
  // Cloudflare garde la fenêtre persistante vivante après la collecte.
  await Promise.all(ctx.pages().map((tab) =>
    tab.close({ runBeforeUnload: false }).catch(() => {})));
  await Promise.race([
    ctx.close().catch(() => {}),
    new Promise((resolve) => setTimeout(resolve, 5000)),
  ]);
  if (browser?.isConnected()) {
    await Promise.race([
      browser.close().catch(() => {}),
      new Promise((resolve) => setTimeout(resolve, 5000)),
    ]);
  }
};
const closeAfterSignal = async (code, reason) => {
  console.error(`[superc] arrêt navigateur (${reason})`);
  await closeBrowser();
  process.exit(code);
};
process.once('SIGINT', () => { void closeAfterSignal(130, 'interruption'); });
process.once('SIGTERM', () => { void closeAfterSignal(143, 'terminaison'); });
process.once('uncaughtException', (error) => {
  console.error(`[superc] erreur fatale: ${String(error).slice(0, 300)}`);
  void closeAfterSignal(1, 'erreur fatale');
});
process.once('unhandledRejection', (error) => {
  console.error(`[superc] promesse rejetée: ${String(error).slice(0, 300)}`);
  void closeAfterSignal(1, 'promesse rejetée');
});

const waitForHumanChallenge = async (label) => {
  if (!(await isBlocked(page))) return true;
  console.error(`[superc] ${label} -> vérification visible dans Chrome; attente utilisateur...`);
  // Une vérification peut rester ouverte pendant que l'utilisateur est absent.
  // Une heure par défaut évite l'échec artificiel après dix minutes.
  const waitMinutes = Number(process.env.SUPERC_CHALLENGE_WAIT_MIN || 60);
  const deadline = Date.now() + Math.max(1, waitMinutes) * 60 * 1000;
  while (Date.now() < deadline) {
    await page.waitForTimeout(2000);
    if (!(await isBlocked(page))) {
      challengeBackoff = Math.min(4, challengeBackoff * 2);
      pagesSinceCooldown = 0;
      console.error(`[superc] ${label} -> vérification terminée, reprise`);
      return true;
    }
  }
  return false;
};

// --- Setup une fois par run : passer le challenge Cloudflare (si présent),
// accepter les témoins, sélectionner Super C Atwater. On refuse de collecter
// si le magasin ne peut pas être confirmé : des prix du magasin par défaut ne
// doivent jamais être présentés comme ceux d'Atwater.
let storeConfirmed = false;
const firstUrl = RAYON_MODE
  ? `${BASE}/allees/${RAYONS[0]}`
  : CIRCULAIRE_MODE
    ? `${BASE}/epicerie-en-ligne/circulaire${CIRCULAIRE_QUERY}`
  : `${BASE}/recherche?filter=${encodeURIComponent(TERMS[0] || 'epicerie')}`;
try {
  await page.goto(firstUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(3500);
  if (await isBlocked(page)) {
    console.error('[superc] challenge Cloudflare détecté');
    // Ne pas recharger le challenge : cela annulait parfois la validation que
    // l'utilisateur était justement en train de terminer.
    if (!(await waitForHumanChallenge('initialisation'))) {
      console.error('[superc] vérification de sécurité non terminée dans le délai configuré');
      await closeBrowser();
      process.exit(3);
    }
  }
  console.error(`[superc] page chargée (${await page.title()})`);

  try {
    await page.getByRole('button', { name: /tout accepter/i }).click({ timeout: 4000 });
    console.error('[superc] témoins acceptés');
  } catch { /* pas de bandeau, ou déjà accepté */ }
  await page.waitForTimeout(800);

  try {
    await page.getByText('Changer de magasin', { exact: false }).first().click({ timeout: 5000 });
    await page.waitForTimeout(1200);
    const pc = page.locator('#postalCode');
    await pc.click({ timeout: 3000 });
    await pc.pressSequentially(STORE_POSTAL, { delay: 80 });
    await page.waitForTimeout(400);
    await page.locator('#submit').click({ timeout: 5000 });
    await page.waitForTimeout(2000);
    try {
      await page.locator(`label[for="${STORE_ID}"]`).click({ timeout: 4000 });
    } catch {
      await page.getByText('Atwater', { exact: false }).first().click({ timeout: 4000 });
    }
    await page.waitForTimeout(800);
    await page.getByRole('button', { name: /confirmer mon magasin/i }).click({ timeout: 5000 });
    await page.waitForTimeout(2500);
    const header = await page.evaluate(() => document.body.innerText.match(/Super C[^\n]*/)?.[0] || '');
    console.error(`[superc] magasin sélectionné -> "${header}"`);
  } catch (e) {
    console.error(`[superc] sélection du magasin échouée (best-effort, on continue) : ${String(e).slice(0, 150)}`);
  }
} catch (e) {
  console.error(`[superc] setup initial échoué (best-effort, on continue) : ${String(e).slice(0, 200)}`);
}
storeConfirmed = await page.evaluate(() => /atwater/i.test(document.body?.innerText || '')).catch(() => false);
if (!storeConfirmed) {
  console.error('[superc] magasin Atwater non confirmé; cache existant conservé et arrêt');
  await closeBrowser();
  process.exit(4);
}

// Une collecte de plusieurs centaines de recherches peut être interrompue par
// Cloudflare ou par le délai du processus Python. On recharge donc le dernier
// cache et on écrit un point de reprise après CHAQUE terme réussi. Auparavant,
// tout n'était écrit qu'à la fin : 39 minutes de résultats étaient perdus si le
// processus expirait à la 40e minute.
const collectionInput = CIRCULAIRE_MODE
  ? ['circulaire', CIRCULAIRE_QUERY]
  : RAYON_MODE ? ['rayons', ...RAYONS] : ['recherche', ...TERMS];
const termsSignature = crypto.createHash('sha256').update(JSON.stringify(collectionInput)).digest('hex');

let previous = {};
// Priorité au checkpoint séparé. Compatibilité : un ancien cache canonique
// incomplet peut encore servir une fois de point de reprise.
for (const candidate of [PARTIAL_OUT, OUT]) {
  try {
    const parsed = JSON.parse(fs.readFileSync(candidate, 'utf-8'));
    if (
      String(parsed.store_id || '') === STORE_ID
      && parsed.refresh_complete === false
      && parsed.refresh_signature === termsSignature
    ) {
      previous = parsed;
      break;
    }
  } catch { /* absent ou illisible */ }
}

const resumingCollection = previous.refresh_complete === false
  && previous.refresh_signature === termsSignature;

// Un cache COMPLET sert aux lectures jusqu'à sa péremption, mais une nouvelle
// collecte repart de zéro. Le fusionner à la nouvelle circulaire conservait
// indéfiniment les promotions des semaines précédentes et faussait son total.
const byKey = new Map();
for (const it of resumingCollection && Array.isArray(previous.items) ? previous.items : []) {
  const key = it.sku || it.name?.toLowerCase();
  if (key) byKey.set(key, it);
}

const resuming = !RAYON_MODE
  && resumingCollection;
const completedTerms = new Set(resuming && Array.isArray(previous.completed_terms)
  ? previous.completed_terms : []);
const failedTerms = new Set();
const resumingPages = resumingCollection;
const completedPages = new Set(resumingPages && Array.isArray(previous.completed_pages)
  ? previous.completed_pages : []);
const completedRayons = new Set(resumingPages && Array.isArray(previous.completed_rayons)
  ? previous.completed_rayons : []);

const writeCheckpoint = (complete = false) => {
  const items = [...byKey.values()].sort((a, c) => (a.name || '').localeCompare(c.name || ''));
  const payload = {
    source: CIRCULAIRE_MODE ? 'superc.ca/epicerie-en-ligne/circulaire'
      : RAYON_MODE ? 'superc.ca/allees' : 'superc.ca/recherche',
    store_id: STORE_ID,
    store_name: STORE_NAME,
    store_postal: STORE_POSTAL,
    collection_mode: CIRCULAIRE_MODE ? 'circulaire' : RAYON_MODE ? 'rayons' : 'recherche',
    scraped_at: new Date().toISOString(),
    count: items.length,
    items,
    refresh_complete: complete,
    refresh_signature: termsSignature,
    completed_terms: complete ? [] : [...completedTerms],
    failed_terms: complete ? [] : [...failedTerms],
    terms_total: TERMS.length,
    completed_pages: complete ? [] : [...completedPages],
    completed_rayons: complete ? [] : [...completedRayons],
    rayons_total: RAYONS.length,
  };
  const destination = complete ? OUT : PARTIAL_OUT;
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const temporary = `${destination}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(payload, null, 2));
  fs.renameSync(temporary, destination);
  if (complete && fs.existsSync(PARTIAL_OUT)) {
    fs.unlinkSync(PARTIAL_OUT);
  }
};

const addItems = (items, rayon = '') => {
  let added = 0;
  for (const it of items) {
    const key = it.sku || it.name.toLowerCase();
    if (!byKey.has(key)) added++;
    // Un produit déjà connu doit être remplacé : sinon un rafraîchissement
    // conserverait précisément son ancien prix.
    byKey.set(key, rayon ? { ...it, rayon } : it);
  }
  return added;
};

// ── Mode RAYONS : /allees/<rayon>, puis -page-2, -page-3… ────────────────────
// La pagination de superc.ca est dans le CHEMIN, pas en paramètre de requête
// (« /allees/garde-manger-page-3 ») : on la suit jusqu'à ce qu'une page ne
// rende plus aucune tuile, ou n'apporte plus rien de neuf (garde-fou contre une
// dernière page qui se répéterait indéfiniment).
for (const rayon of RAYONS) {
  if (completedRayons.has(rayon)) continue;
  let total = 0;
  for (let pageNum = 1; pageNum <= MAX_PAGES_PER_RAYON; pageNum++) {
    const pageKey = `${rayon}:${pageNum}`;
    if (completedPages.has(pageKey)) continue;
    const url = pageNum === 1
      ? `${BASE}/allees/${rayon}`
      : `${BASE}/allees/${rayon}-page-${pageNum}`;
    // Une page vide ne signifie « rayon épuisé » qu'après plusieurs tentatives
    // COMPLÈTES : un challenge Cloudflare rend une page sans tuiles, et s'en
    // contenter tronquait les rayons (135 produits ramenés sur les 572 de
    // « fruits-et-legumes », constaté au premier essai). On recharge donc
    // franchement la page avant de conclure.
    let items = [];
    for (let essai = 1; essai <= 3 && items.length === 0; essai++) {
      try {
        if (essai > 1) await page.waitForTimeout(3000 * essai);
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        if (await isBlocked(page)) {
          console.error(`[superc] ${rayon} p${pageNum} -> challenge Cloudflare (essai ${essai})`);
          if (!(await waitForHumanChallenge(`${rayon} p${pageNum}`))) {
            writeCheckpoint(false);
            await closeBrowser();
            process.exit(3);
          }
        }
        await page.waitForSelector('.default-product-tile[data-product-code]', { timeout: 8000 }).catch(() => {});
        items = await page.evaluate(EXTRACT, TILES_PER_PAGE);
      } catch (e) {
        console.error(`[superc] ${rayon} p${pageNum} essai ${essai} ERREUR ${String(e).slice(0, 110)}`);
      }
    }
    if (items.length === 0) break;          // rayon réellement épuisé
    const added = addItems(items, rayon);
    total += items.length;
    if (added === 0 && pageNum > 1) break;  // page répétée : on arrête là
    completedPages.add(pageKey);
    writeCheckpoint(false);
    await politeDelay(page);
  }
  completedRayons.add(rayon);
  writeCheckpoint(false);
  console.error(`[superc] rayon ${rayon} -> ${total} produits (total ${byKey.size})`);
}

// ── Circulaire complète ────────────────────────────────────────────────────
// La grille officielle utilise la même carte produit que les rayons. Sa
// pagination est encodée dans le chemin, comme les pages d'allée.
if (CIRCULAIRE_MODE) {
  const pageFingerprints = new Set();
  let advertisedTotal = null;
  for (let pageNum = 1; pageNum <= MAX_PAGES_PER_RAYON; pageNum++) {
    const pageKey = `circulaire:${pageNum}`;
    if (completedPages.has(pageKey)) continue;
    const pathName = pageNum === 1 ? 'circulaire' : `circulaire-page-${pageNum}`;
    const url = `${BASE}/epicerie-en-ligne/${pathName}${CIRCULAIRE_QUERY}`;
    let items = [];
    for (let essai = 1; essai <= 3 && items.length === 0; essai++) {
      try {
        if (essai > 1) await page.waitForTimeout(4000 * essai);
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        if (await isBlocked(page) && !(await waitForHumanChallenge(`circulaire p${pageNum}`))) {
          writeCheckpoint(false);
          await closeBrowser();
          process.exit(3);
        }
        await page.waitForSelector('.default-product-tile[data-product-code]', { timeout: 10000 }).catch(() => {});
        items = await page.evaluate(EXTRACT, TILES_PER_PAGE);
        if (pageNum === 1) {
          advertisedTotal = await page.evaluate(() => {
            const text = document.body?.innerText || '';
            const match = text.match(/(?:^|\n)\s*([\d\s]+)\s+produits?\b/im);
            return match ? Number(match[1].replace(/\s/g, '')) : null;
          }).catch(() => null);
          if (advertisedTotal) {
            console.error(`[superc] circulaire -> ${advertisedTotal} produits annoncés`);
          }
        }
      } catch (e) {
        console.error(`[superc] circulaire p${pageNum} essai ${essai} ERREUR ${String(e).slice(0, 110)}`);
      }
    }
    if (items.length === 0) break;
    const fingerprint = items.map((item) => item.sku || item.id || item.name).sort().join('|');
    if (pageFingerprints.has(fingerprint)) {
      console.error(`[superc] circulaire p${pageNum} répétée -> arrêt pagination`);
      break;
    }
    pageFingerprints.add(fingerprint);
    const added = addItems(items, 'circulaire');
    if (added === 0 && pageNum > 1) break;
    completedPages.add(pageKey);
    writeCheckpoint(false);
    console.error(`[superc] circulaire p${pageNum} -> ${items.length} (total ${byKey.size})`);
    if (advertisedTotal && byKey.size >= advertisedTotal) {
      console.error('[superc] circulaire complète selon le total annoncé');
      break;
    }
    await politeDelay(page);
  }
}

for (const term of TERMS) {
  if (completedTerms.has(term)) continue;
  try {
    await page.goto(`${BASE}/recherche?filter=${encodeURIComponent(term)}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    if (await isBlocked(page)) {
      console.error(`[superc] "${term}" -> challenge Cloudflare, nouvelle tentative...`);
      await page.waitForTimeout(4000);
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
      await page.waitForTimeout(1500);
      if (!(await waitForHumanChallenge(`"${term}"`))) {
        console.error(`[superc] "${term}" -> vérification non terminée, sauvegarde et arrêt`);
        failedTerms.add(term);
        writeCheckpoint(false);
        await closeBrowser();
        process.exit(3);
      }
    }
    await page.waitForSelector('.default-product-tile[data-product-code]', { timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(800);
    let items = await page.evaluate(EXTRACT, MAX_PER_TERM);
    if (items.length === 0) {
      await page.waitForTimeout(3000);
      items = await page.evaluate(EXTRACT, MAX_PER_TERM);
    }
    addItems(items);
    completedTerms.add(term);
    failedTerms.delete(term);
    writeCheckpoint(false);
    console.error(`[superc] "${term}" -> ${items.length} (total ${byKey.size})`);
  } catch (e) {
    console.error(`[superc] "${term}" ERREUR ${String(e).slice(0, 150)}`);
    failedTerms.add(term);
    writeCheckpoint(false);
  }
}
await closeBrowser();

const out = [...byKey.values()].sort((a, c) => (a.name || '').localeCompare(c.name || ''));

if (out.length === 0 && fs.existsSync(OUT)) {
  try {
    const prev = JSON.parse(fs.readFileSync(OUT, 'utf-8'));
    if (Array.isArray(prev.items) && prev.items.length > 0) {
      console.error(`[superc] 0 items ce run, cache existant (${prev.items.length}) conservé, pas d'écrasement`);
      process.exit(0);
    }
  } catch { /* cache illisible, on écrase normalement */ }
}

const complete = CIRCULAIRE_MODE
  ? completedPages.size > 0
  : RAYON_MODE ? completedRayons.size === RAYONS.length : failedTerms.size === 0;
writeCheckpoint(complete);
console.error(`[superc] ${out.length} items écrits dans ${OUT}`);
