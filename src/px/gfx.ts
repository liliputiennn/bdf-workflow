/**
 * Moteur pixel art : tout est dessiné dans un tampon basse résolution (W×H),
 * puis agrandi au plus proche voisin. Déterministe (aucun Math.random).
 */

export const W = 216;
export const H = 384;
export const SCALE = 5;

const colorCache = new Map<string, number>();
/** '#rrggbb' → entier ABGR (ordre mémoire d'ImageData en little-endian). */
export const col = (hex: string): number => {
  let c = colorCache.get(hex);
  if (c === undefined) {
    const n = parseInt(hex.slice(1), 16);
    c = ((255 << 24) | ((n & 0xff) << 16) | (n & 0xff00) | ((n >> 16) & 0xff)) >>> 0;
    colorCache.set(hex, c);
  }
  return c;
};

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);
export const bayer = (x: number, y: number) => BAYER[(y & 3) * 4 + (x & 3)];

export const hash = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
export const hash2 = (x: number, y: number, s = 0) => hash(x * 57.3 + y * 113.1 + s * 7.7);

/** Bruit de valeur 2D lissé, [0,1]. */
export const noise = (x: number, y: number, s = 0) => {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi, s);
  const b = hash2(xi + 1, yi, s);
  const c = hash2(xi, yi + 1, s);
  const d = hash2(xi + 1, yi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
};
export const fbm = (x: number, y: number, s = 0, oct = 3) => {
  let t = 0;
  let amp = 0.5;
  let f = 1;
  for (let i = 0; i < oct; i++) {
    t += noise(x * f, y * f, s + i * 13) * amp;
    f *= 2;
    amp *= 0.5;
  }
  return t / (1 - Math.pow(0.5, oct));
};

export type Ramp = string[];

export class Gfx {
  buf: Uint32Array;
  /** décalage caméra appliqué à toutes les primitives */
  ox = 0;
  oy = 0;
  constructor(public w = W, public h = H) {
    this.buf = new Uint32Array(w * h);
  }

  set(x: number, y: number, c: number) {
    x = Math.round(x + this.ox);
    y = Math.round(y + this.oy);
    if (x < 0 || y < 0 || x >= this.w || y >= this.h) return;
    this.buf[y * this.w + x] = c;
  }
  get(x: number, y: number) {
    if (x < 0 || y < 0 || x >= this.w || y >= this.h) return 0;
    return this.buf[y * this.w + x];
  }

  fill(hex: string) {
    this.buf.fill(col(hex));
  }

  rect(x: number, y: number, w: number, h: number, hex: string) {
    const c = col(hex);
    const x0 = Math.round(x);
    const y0 = Math.round(y);
    for (let j = 0; j < Math.round(h); j++) for (let i = 0; i < Math.round(w); i++) this.set(x0 + i, y0 + j, c);
  }

  /** Remplissage tramé : densité 0..1. */
  dither(x: number, y: number, w: number, h: number, hex: string, density: number) {
    const c = col(hex);
    const x0 = Math.round(x);
    const y0 = Math.round(y);
    for (let j = 0; j < Math.round(h); j++)
      for (let i = 0; i < Math.round(w); i++) {
        const px = x0 + i;
        const py = y0 + j;
        if (bayer(px, py) < density) this.set(px, py, c);
      }
  }

  /** Dégradé vertical tramé à travers une rampe de couleurs. */
  vgrad(x: number, y: number, w: number, h: number, ramp: Ramp) {
    const n = ramp.length - 1;
    for (let j = 0; j < h; j++) {
      const t = (j / Math.max(1, h - 1)) * n;
      const k = Math.floor(t);
      const fr = t - k;
      for (let i = 0; i < w; i++) {
        const idx = bayer(x + i, y + j) < fr ? Math.min(n, k + 1) : k;
        this.set(x + i, y + j, col(ramp[idx]));
      }
    }
  }

  disc(cx: number, cy: number, r: number, hex: string) {
    const c = col(hex);
    for (let y = -r; y <= r; y++)
      for (let x = -r; x <= r; x++) if (x * x + y * y <= r * r + r * 0.6) this.set(cx + x, cy + y, c);
  }

  ring(cx: number, cy: number, r: number, hex: string, th = 1) {
    const c = col(hex);
    const R = r + 0.5;
    for (let y = -r - 1; y <= r + 1; y++)
      for (let x = -r - 1; x <= r + 1; x++) {
        const d = Math.sqrt(x * x + y * y);
        if (d <= R && d > R - th) this.set(cx + x, cy + y, c);
      }
  }

  line(x0: number, y0: number, x1: number, y1: number, hex: string) {
    const c = col(hex);
    x0 = Math.round(x0);
    y0 = Math.round(y0);
    x1 = Math.round(x1);
    y1 = Math.round(y1);
    const dx = Math.abs(x1 - x0);
    const dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (let k = 0; k < 2000; k++) {
      this.set(x0, y0, c);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) {
        err += dy;
        x0 += sx;
      }
      if (e2 <= dx) {
        err += dx;
        y0 += sy;
      }
    }
  }

  /** Ligne pointillée (on, off en pixels). */
  dashed(x0: number, y0: number, x1: number, y1: number, hex: string, on = 3, off = 3, phase = 0) {
    const len = Math.hypot(x1 - x0, y1 - y0);
    const c = col(hex);
    for (let s = 0; s <= len; s++) {
      if ((s + phase) % (on + off) < on) this.set(x0 + ((x1 - x0) * s) / len, y0 + ((y1 - y0) * s) / len, c);
    }
  }

  /**
   * Sphère ombrée et tramée, avec texture optionnelle (u,v en radians, rotation incluse).
   * tex renvoie un décalage de teinte (-1..1) ajouté à l'éclairage.
   */
  sphere(
    cx: number,
    cy: number,
    r: number,
    ramp: Ramp,
    opts: { lx?: number; ly?: number; rot?: number; tex?: (lon: number, lat: number) => number; rim?: string } = {},
  ) {
    const { lx = -0.55, ly = -0.45, rot = 0, tex, rim } = opts;
    const lz = Math.sqrt(Math.max(0, 1 - lx * lx - ly * ly));
    const n = ramp.length - 1;
    for (let y = -r; y <= r; y++)
      for (let x = -r; x <= r; x++) {
        const d2 = x * x + y * y;
        if (d2 > r * r + r * 0.6) continue;
        const nx = x / r;
        const ny = y / r;
        const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
        let l = Math.max(0, nx * lx + ny * ly + nz * lz);
        l = 0.12 + l * 0.95;
        if (tex) {
          const lat = Math.asin(Math.max(-1, Math.min(1, ny)));
          const lon = Math.atan2(nx, nz) + rot;
          l += tex(lon, lat) * 0.35;
        }
        const t = Math.max(0, Math.min(n, l * n));
        const k = Math.floor(t);
        const idx = bayer(cx + x, cy + y) < t - k ? Math.min(n, k + 1) : k;
        this.set(cx + x, cy + y, col(ramp[idx]));
        if (rim && d2 > (r - 1.2) * (r - 1.2) && nx * lx + ny * ly > -0.2) this.set(cx + x, cy + y, col(rim));
      }
  }

  /** Halo tramé autour d'un point (densité décroissante). */
  glow(cx: number, cy: number, r: number, hex: string, strength = 0.6) {
    const c = col(hex);
    for (let y = -r; y <= r; y++)
      for (let x = -r; x <= r; x++) {
        const d = Math.sqrt(x * x + y * y) / r;
        if (d > 1) continue;
        if (bayer(cx + x, cy + y) < (1 - d) * (1 - d) * strength) this.set(cx + x, cy + y, c);
      }
  }

  /** Sprite ASCII : rows de caractères, palette char→couleur, '.' transparent. */
  sprite(rows: string[], pal: Record<string, string>, x: number, y: number, s = 1, flip = false) {
    const w = rows[0].length;
    for (let j = 0; j < rows.length; j++)
      for (let i = 0; i < w; i++) {
        const ch = rows[j][flip ? w - 1 - i : i];
        if (ch === "." || ch === " ") continue;
        const hex = pal[ch];
        if (!hex) continue;
        const c = col(hex);
        for (let b = 0; b < s; b++) for (let a = 0; a < s; a++) this.set(x + i * s + a, y + j * s + b, c);
      }
  }

  /** Copie d'un autre tampon (pour les transitions). */
  copyFrom(o: Gfx) {
    this.buf.set(o.buf);
  }
}

/** Petit helper : dessin en unités d'un sprite procédural (u = taille d'un « pixel » de sprite). */
export const pen = (g: Gfx, ox: number, oy: number, u: number) => (x: number, y: number, w: number, h: number, hex: string) =>
  g.rect(ox + x * u, oy + y * u, w * u, h * u, hex);
