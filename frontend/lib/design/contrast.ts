/**
 * Maths couleur pures pour l'audit de contraste WCAG des tokens Verre Clair.
 * Formats supportés = ceux réellement présents dans globals.css :
 * hex 3/6, `rgb(r g b / a)` moderne, `transparent`.
 */

export type Rgba = { r: number; g: number; b: number; a: number };

export function parseCssColor(value: string): Rgba | null {
  const v = value.trim();
  if (v === "transparent") return { r: 0, g: 0, b: 0, a: 0 };

  const hex = v.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
      a: 1,
    };
  }

  const rgb = v.match(
    /^rgba?\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:\/\s*([\d.]+%?)\s*)?\)$/i,
  );
  if (rgb) {
    let a = 1;
    if (rgb[4] !== undefined) {
      a = rgb[4].endsWith("%") ? parseFloat(rgb[4]) / 100 : parseFloat(rgb[4]);
    }
    return { r: +rgb[1], g: +rgb[2], b: +rgb[3], a };
  }
  return null;
}

export function composite(fg: Rgba, bg: Rgba): Rgba {
  const a = fg.a + bg.a * (1 - fg.a);
  const mix = (f: number, b: number) =>
    a === 0 ? 0 : (f * fg.a + b * bg.a * (1 - fg.a)) / a;
  return { r: mix(fg.r, bg.r), g: mix(fg.g, bg.g), b: mix(fg.b, bg.b), a };
}

function luminance(c: Rgba): number {
  const lin = (ch: number) => {
    const s = ch / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
}

export function contrastRatio(a: Rgba, b: Rgba): number {
  const l1 = luminance(a);
  const l2 = luminance(b);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}
