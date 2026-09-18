#!/usr/bin/env node
// Audit Lighthouse (LCP, CLS, TBT en navigation ; INP via un flow avec une
// vraie interaction — Lighthouse ne calcule l'INP qu'en mode timespan).
// Prérequis : backend (127.0.0.1:8000) + frontend en PROD (`next build && next start`)
// déjà démarrés — ce script ne les lance pas lui-même.
//
// Usage : node scripts/lighthouse-audit.mjs [baseUrl]

import * as chromeLauncher from "chrome-launcher";
import puppeteer from "puppeteer-core";
import lighthouse, { startTimespan, desktopConfig } from "lighthouse";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE_URL = process.argv[2] ?? "http://127.0.0.1:3000";
const ROUTES = ["/", "/finance"]; // hub (le plus visité) + une page dense (§2.6)
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function metric(audits, id) {
  const a = audits[id];
  if (!a || a.numericValue == null) return null;
  return Math.round(a.numericValue * 10) / 10;
}

async function auditRoute(browser, chromePort, page, route, formFactor) {
  const url = `${BASE_URL}${route}`;
  const config = formFactor === "desktop" ? desktopConfig : undefined;

  // Navigation : LCP, CLS, TBT.
  const nav = await lighthouse(url, { port: chromePort, onlyCategories: ["performance"] }, config, page);
  const navAudits = nav.lhr.audits;

  // Timespan avec une interaction réelle : seul mode où Lighthouse calcule
  // l'INP (web.dev/inp). Sidebar+Dock sont masqués (`hidden md:flex`) en
  // dessous du breakpoint md : sur mobile on ouvre le tiroir de nav (bouton
  // toujours visible), sur desktop on bascule le thème (ThemeToggle Sidebar).
  const selector =
    formFactor === "mobile" ? 'button[aria-label="Ouvrir le menu"]' : 'button[aria-label^="Thème"]';
  await page.goto(url, { waitUntil: "networkidle0" });
  const { endTimespan } = await startTimespan(page, { config });
  await page.waitForSelector(selector, { timeout: 5000, visible: true });
  await page.click(selector);
  await new Promise((r) => setTimeout(r, 500));
  const flow = await endTimespan();
  const inp = metric(flow.lhr.audits, "interaction-to-next-paint");

  return {
    route,
    formFactor,
    lcp_ms: metric(navAudits, "largest-contentful-paint"),
    cls: metric(navAudits, "cumulative-layout-shift"),
    tbt_ms: metric(navAudits, "total-blocking-time"),
    inp_ms: inp,
  };
}

async function main() {
  const chrome = await chromeLauncher.launch({ chromeFlags: ["--headless=new"] });
  const browser = await puppeteer.connect({ browserURL: `http://localhost:${chrome.port}` });
  const results = [];
  for (const route of ROUTES) {
    for (const formFactor of ["mobile", "desktop"]) {
      const page = await browser.newPage();
      try {
        results.push(await auditRoute(browser, chrome.port, page, route, formFactor));
      } finally {
        await page.close();
      }
    }
  }
  await browser.disconnect();
  // chrome.kill() peut échouer sur Windows si Chrome tient encore un verrou sur
  // son dossier temp (rmSync EPERM) — pur nettoyage, ne doit pas perdre les résultats.
  try {
    await chrome.kill();
  } catch (err) {
    console.warn("Nettoyage Chrome ignoré :", err.message);
  }

  const date = new Date().toISOString().slice(0, 10);
  const outPath = path.join(__dirname, "..", "..", "orchestration", "finis", `${date}-audit-lighthouse.json`);
  writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
  console.log(`\nÉcrit : ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
