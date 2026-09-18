import { chromium } from "playwright";

const [url, query] = process.argv.slice(2);
if (!url || !query) throw new Error("usage: node inspect-etf-site.mjs URL ISIN");

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ locale: "en-GB" });
const seen = new Set();
page.on("response", async (response) => {
  const target = response.url();
  if (/token|oauth|authorize/i.test(target)) return;
  if (!/api|json|jsn|search|product|holding/i.test(target) || seen.has(target)) return;
  seen.add(target);
  const type = response.headers()["content-type"] || "";
  let preview = "";
  if (/json|text/.test(type)) {
    try { preview = (await response.text()).slice(0, 250).replaceAll("\n", " "); } catch {}
  }
  console.log(JSON.stringify({ status: response.status(), type, url: target, preview }));
});

await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(5_000);
const inputs = page.locator("input");
for (let index = 0; index < await inputs.count(); index += 1) {
  const input = inputs.nth(index);
  const descriptor = `${await input.getAttribute("placeholder")} ${await input.getAttribute("aria-label")} ${await input.getAttribute("name")}`;
  if (/fund|ticker|isin|search|recher/i.test(descriptor)) {
    console.log(JSON.stringify({ input: index, descriptor }));
    try {
      await input.fill(query);
      await page.waitForTimeout(5_000);
    } catch {}
  }
}
await browser.close();
