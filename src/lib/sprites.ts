import { C, rand } from "./theme";

/** Une cellule pixel : x, y, largeur, hauteur (en pixels de sprite), couleur. */
export type Cell = [number, number, number, number, string];
export type SpriteDef = { w: number; h: number; cells: Cell[] };

const R = (x: number, y: number, w: number, h: number, c: string): Cell => [x, y, w, h, c];

/** Disque plein, ligne par ligne, avec ombrage à droite. */
export const disc = (r: number, base: string, shade?: string): Cell[] => {
  const out: Cell[] = [];
  for (let y = -r; y < r; y++) {
    const half = Math.floor(Math.sqrt(r * r - (y + 0.5) * (y + 0.5)) + 0.5);
    if (half <= 0) continue;
    out.push(R(r - half, y + r, half * 2, 1, base));
    if (shade) {
      const s = Math.max(1, Math.round(half * 0.55));
      out.push(R(r + half - s, y + r, s, 1, shade));
    }
  }
  return out;
};

/** Anneau d'épaisseur ~1 pixel. */
export const ring = (r: number, color: string, thick = 1.2): Cell[] => {
  const out: Cell[] = [];
  for (let y = 0; y < r * 2; y++)
    for (let x = 0; x < r * 2; x++) {
      const d = Math.hypot(x + 0.5 - r, y + 0.5 - r);
      if (d <= r && d >= r - thick) out.push(R(x, y, 1, 1, color));
    }
  return out;
};

/** Planète : disque + taches (cratères ou continents) dans le disque. */
export const planet = (r: number, base: string, dark: string, seed: number, spots = 7): SpriteDef => {
  const cells = disc(r, base, dark);
  for (let i = 0; i < spots; i++) {
    const sr = 1 + Math.floor(rand(seed + i) * Math.min(r / 4, 5));
    const a = rand(seed + i * 3) * Math.PI * 2;
    const d = rand(seed + i * 7) * (r - sr - 1);
    const cx = Math.round(r + Math.cos(a) * d);
    const cy = Math.round(r + Math.sin(a) * d);
    for (const c of disc(sr, dark)) cells.push(R(c[0] + cx - sr, c[1] + cy - sr, c[2], c[3], dark));
  }
  return { w: r * 2, h: r * 2, cells };
};

/** Mars Climate Orbiter : un seul panneau solaire (asymétrique, c'est un vrai détail du dossier). */
export const probe = (): SpriteDef => {
  const cells: Cell[] = [
    R(0, 4, 14, 8, C.grey),
    R(1, 5, 12, 6, C.accentDeep),
    R(14, 7, 3, 1, C.grey),
    R(17, 4, 8, 8, C.white),
    R(17, 10, 8, 2, C.grey),
    R(17, 7, 8, 1, C.greyDark),
    R(19, 2, 4, 1, C.white),
    R(18, 1, 6, 1, C.grey),
    R(21, 3, 1, 1, C.grey),
    R(17, 12, 1, 1, C.greyDark),
    R(24, 12, 1, 1, C.greyDark),
  ];
  for (let i = 0; i < 4; i++)
    for (let j = 0; j < 2; j++) cells.push(R(1 + i * 3, 5 + j * 3, 2, 2, C.accent));
  return { w: 26, h: 13, cells };
};

export const rocket = (): SpriteDef => ({
  w: 16,
  h: 34,
  cells: [
    R(7, 0, 2, 1, C.white),
    R(6, 1, 4, 3, C.white),
    R(9, 1, 1, 3, C.grey),
    R(6, 4, 4, 28, C.white),
    R(9, 4, 1, 28, C.grey),
    R(6, 9, 4, 1, C.accentDim),
    R(6, 15, 4, 1, C.accentDim),
    R(3, 21, 3, 11, C.grey),
    R(10, 21, 3, 11, C.grey),
    R(4, 19, 1, 2, C.grey),
    R(11, 19, 1, 2, C.grey),
    R(6, 32, 4, 2, C.greyDark),
    R(3, 32, 3, 1, C.greyDark),
    R(10, 32, 3, 1, C.greyDark),
  ],
});

export const factory = (): SpriteDef => {
  const cells: Cell[] = [R(0, 6, 20, 10, C.grey), R(16, 0, 2, 6, C.greyDark), R(8, 12, 4, 4, C.ink)];
  for (let k = 0; k < 4; k++) for (let s = 0; s < 5; s++) cells.push(R(k * 5 + s, 5 - s, 1, 1 + s, C.white));
  for (let i = 0; i < 5; i++) cells.push(R(1 + i * 4, 8, 2, 2, C.accent));
  return { w: 20, h: 16, cells };
};

export const dish = (): SpriteDef => ({
  w: 20,
  h: 20,
  cells: [
    R(9, 0, 2, 1, C.white),
    R(5, 1, 1, 1, C.grey),
    R(14, 1, 1, 1, C.grey),
    R(2, 2, 16, 1, C.white),
    R(3, 3, 14, 1, C.grey),
    R(4, 4, 12, 1, C.grey),
    R(6, 5, 8, 1, C.greyDark),
    R(8, 6, 4, 1, C.greyDark),
    R(9, 7, 2, 5, C.grey),
    R(7, 12, 6, 6, C.grey),
    R(8, 13, 2, 2, C.accent),
    R(5, 18, 10, 2, C.greyDark),
  ],
});

export const lander = (): SpriteDef => ({
  w: 18,
  h: 12,
  cells: [
    R(9, 0, 1, 1, C.grey),
    R(8, 1, 2, 2, C.grey),
    R(5, 3, 8, 1, C.grey),
    R(4, 4, 10, 4, C.white),
    R(0, 5, 4, 2, C.accent),
    R(14, 5, 4, 2, C.accent),
    R(3, 8, 1, 3, C.grey),
    R(14, 8, 1, 3, C.grey),
    R(8, 8, 2, 3, C.grey),
    R(2, 11, 2, 1, C.greyDark),
    R(14, 11, 2, 1, C.greyDark),
    R(7, 11, 4, 1, C.greyDark),
  ],
});

export const bulb = (): SpriteDef => ({
  w: 12,
  h: 16,
  cells: [
    ...disc(6, C.white, C.grey),
    R(4, 4, 1, 4, C.accent),
    R(7, 4, 1, 4, C.accent),
    R(5, 7, 2, 1, C.accent),
    R(4, 11, 4, 1, C.grey),
    R(4, 12, 4, 1, C.greyDark),
    R(4, 13, 4, 1, C.grey),
    R(5, 14, 2, 1, C.greyDark),
  ],
});

export const envelope = (): SpriteDef => {
  const cells: Cell[] = [R(0, 0, 16, 11, C.white)];
  for (let i = 0; i < 8; i++) {
    const y = Math.floor(i * 0.75);
    cells.push(R(i, y, 1, 1, C.grey), R(15 - i, y, 1, 1, C.grey));
  }
  return { w: 16, h: 11, cells };
};

export const puff = (): SpriteDef => ({
  w: 5,
  h: 5,
  cells: [R(1, 0, 3, 5, C.white), R(0, 1, 5, 3, C.white), R(1, 1, 2, 2, C.grey)],
});

export const signalBars = (on: number): SpriteDef => ({
  w: 15,
  h: 12,
  cells: [0, 1, 2, 3].map((i) => R(i * 4, 12 - (i + 1) * 3, 3, (i + 1) * 3, i < on ? C.accent : C.greyDark)),
});

/** La mascotte : l'archiviste à visière verte et lunettes rondes, dossier sous le bras. */
export const archivist = (blink = false): SpriteDef => ({
  w: 22,
  h: 26,
  cells: [
    R(6, 1, 10, 1, C.accent),
    R(5, 2, 12, 2, C.accent),
    R(3, 4, 16, 1, C.accentDim),
    R(6, 5, 10, 10, C.skin),
    R(5, 5, 1, 7, C.grey),
    R(16, 5, 1, 7, C.grey),
    R(6, 7, 4, 3, C.ink),
    R(12, 7, 4, 3, C.ink),
    R(10, 8, 2, 1, C.ink),
    R(7, 8, 2, 1, blink ? C.ink : C.white),
    R(13, 8, 2, 1, blink ? C.ink : C.white),
    R(8, 11, 6, 1, C.grey),
    R(9, 13, 4, 1, C.greyDark),
    R(9, 15, 4, 1, C.skin),
    R(3, 16, 16, 10, C.accentDeep),
    R(9, 16, 4, 4, C.white),
    R(10, 17, 2, 5, C.accent),
    R(8, 16, 1, 5, C.accentDim),
    R(13, 16, 1, 5, C.accentDim),
    R(12, 18, 4, 1, "#c9a86a"),
    R(12, 19, 10, 7, "#c9a86a"),
    R(14, 21, 6, 1, C.ink),
    R(11, 22, 3, 3, C.accentDeep),
  ],
});
