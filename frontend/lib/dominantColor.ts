/**
 * Détection de la couleur dominante d'une image, côté navigateur (#75).
 *
 * Aucune dépendance / aucun traitement serveur : on dessine l'image dans un
 * petit canvas, on quantifie les pixels en buckets et on retourne le bucket le
 * plus fréquent au format hex. Les pixels quasi transparents sont ignorés.
 */

function toHex(n: number): string {
  return n.toString(16).padStart(2, "0");
}

export async function dominantColorFromFile(file: File): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const url = URL.createObjectURL(file);
  try {
    const img = await loadImage(url);
    return dominantColorFromImage(img);
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("image load failed"));
    img.src = src;
  });
}

function dominantColorFromImage(img: HTMLImageElement): string | null {
  const size = 48;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(img, 0, 0, size, size);

  let data: Uint8ClampedArray;
  try {
    data = ctx.getImageData(0, 0, size, size).data;
  } catch {
    return null; // canvas "tainted" (cross-origin) — peu probable pour un upload local
  }

  const buckets = new Map<string, { count: number; r: number; g: number; b: number }>();
  const Q = 24; // taille de bucket par canal
  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3];
    if (a < 128) continue;
    const r = data[i], g = data[i + 1], b = data[i + 2];
    const key = `${Math.round(r / Q)}-${Math.round(g / Q)}-${Math.round(b / Q)}`;
    const cur = buckets.get(key);
    if (cur) {
      cur.count++; cur.r += r; cur.g += g; cur.b += b;
    } else {
      buckets.set(key, { count: 1, r, g, b });
    }
  }

  let best: { count: number; r: number; g: number; b: number } | null = null;
  for (const v of buckets.values()) {
    if (!best || v.count > best.count) best = v;
  }
  if (!best) return null;
  const r = Math.round(best.r / best.count);
  const g = Math.round(best.g / best.count);
  const b = Math.round(best.b / best.count);
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}
