/**
 * Génère une image PNG partageable du plan macros du jour (#71).
 *
 * Rendu via <canvas> (aucune dépendance) : titre, date, et une barre par macro
 * (consommé/cible). Partage via Web Share API si dispo, sinon téléchargement.
 */

import { MACRO_KEYS, MACRO_UNITS, INTENSITY_LABELS, type PlanResponse } from "./sante";

const W = 720;
const PAD = 40;
const ROW_H = 64;

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export function renderMacrosCanvas(plan: PlanResponse): HTMLCanvasElement {
  const totals = plan.totals ?? {};
  const targets = plan.targets ?? {};
  const rows = MACRO_KEYS.filter((k) => (targets[k] ?? 0) > 0);

  const H = PAD * 2 + 90 + rows.length * ROW_H;
  const canvas = document.createElement("canvas");
  const dpr = Math.min(2, typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(dpr, dpr);

  // Fond
  ctx.fillStyle = "#0b0f17";
  ctx.fillRect(0, 0, W, H);

  // En-tête
  ctx.fillStyle = "#f8fafc";
  ctx.font = "700 26px system-ui, sans-serif";
  ctx.fillText("🥗 Mes macros du jour", PAD, PAD + 22);

  ctx.fillStyle = "#94a3b8";
  ctx.font = "400 15px system-ui, sans-serif";
  const sub = `${new Date(plan.date).toLocaleDateString("fr-CA")} · ${plan.poids_used.toFixed(1)} kg · ${
    INTENSITY_LABELS[plan.intensite] ?? plan.intensite
  }`;
  ctx.fillText(sub, PAD, PAD + 48);

  // Lignes macros
  let y = PAD + 90;
  for (const k of rows) {
    const cur = totals[k] ?? 0;
    const tgt = targets[k] ?? 0;
    const pct = tgt > 0 ? Math.min(1, cur / tgt) : 0;
    const unit = MACRO_UNITS[k] ?? "";

    ctx.fillStyle = "#e2e8f0";
    ctx.font = "600 16px system-ui, sans-serif";
    ctx.fillText(k, PAD, y + 4);

    ctx.fillStyle = "#94a3b8";
    ctx.font = "400 14px system-ui, sans-serif";
    const label = `${Math.round(cur)} / ${Math.round(tgt)} ${unit}`;
    ctx.textAlign = "right";
    ctx.fillText(label, W - PAD, y + 4);
    ctx.textAlign = "left";

    // Barre
    const barY = y + 16;
    const barW = W - PAD * 2;
    ctx.fillStyle = "#1e293b";
    roundRect(ctx, PAD, barY, barW, 12, 6);
    ctx.fill();
    ctx.fillStyle = pct >= 0.999 ? "#22c55e" : "#6366f1";
    roundRect(ctx, PAD, barY, Math.max(6, barW * pct), 12, 6);
    ctx.fill();

    y += ROW_H;
  }

  // Pied
  ctx.fillStyle = "#475569";
  ctx.font = "400 12px system-ui, sans-serif";
  ctx.fillText("Mission Control", PAD, H - PAD + 10);

  return canvas;
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob a échoué"))), "image/png"),
  );
}

export async function exportMacrosImage(plan: PlanResponse): Promise<void> {
  const canvas = renderMacrosCanvas(plan);
  const blob = await canvasToBlob(canvas);
  const filename = `macros-${plan.date}.png`;
  const file = new File([blob], filename, { type: "image/png" });

  // Partage natif si supporté (mobile surtout)
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
  if (nav.share && nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], title: "Mes macros du jour" });
      return;
    } catch {
      // annulé / non supporté → on retombe sur le téléchargement
    }
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
