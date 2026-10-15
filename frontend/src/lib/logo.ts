// Analyse des logos (PNG transparents) : un logo sombre (texte noir…) est posé sur un
// fronton clair, un logo clair sur un fronton sombre. Résultat mis en cache par URL.

export type LogoTone = 'dark' | 'light';

const KEY = 'naomox.logo-tones.v1';
let cache: Record<string, LogoTone> = {};
try {
  cache = JSON.parse(localStorage.getItem(KEY) ?? '{}');
} catch {
  cache = {};
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;
function persist() {
  if (saveTimer) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    try {
      localStorage.setItem(KEY, JSON.stringify(cache));
    } catch {
      /* quota ou stockage indisponible */
    }
  }, 500);
}

export const cachedTone = (url: string): LogoTone | undefined => cache[url];

/** Luminance moyenne pondérée par l'opacité des pixels visibles du logo. */
export function analyse(img: HTMLImageElement): LogoTone {
  const cached = cache[img.src] ?? cache[new URL(img.src).pathname];
  if (cached) return cached;
  let tone: LogoTone = 'light';
  try {
    const w = 48;
    const h = Math.max(1, Math.round((img.naturalHeight / img.naturalWidth) * w));
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (ctx) {
      ctx.drawImage(img, 0, 0, w, h);
      const d = ctx.getImageData(0, 0, w, h).data;
      let lum = 0;
      let weight = 0;
      for (let i = 0; i < d.length; i += 4) {
        const a = d[i + 3] / 255;
        if (a < 0.2) continue;
        lum += a * (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]);
        weight += a;
      }
      // Logos sans transparence (fond blanc) : on les traite comme sombres → fronton clair.
      const opaque = weight / (w * h) > 0.92;
      tone = opaque || (weight && lum / weight < 85) ? 'dark' : 'light';
    }
  } catch {
    tone = 'light';
  }
  cache[new URL(img.src).pathname] = tone;
  persist();
  return tone;
}
