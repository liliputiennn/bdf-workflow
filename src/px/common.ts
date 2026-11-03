import { bayer, col, fbm, Gfx, H, hash, Ramp, W } from "./gfx";

/** Palettes : un accent vert, des neutres, et des rampes « naturelles » pour les objets. */
export const P = {
  night: ["#020604", "#04100a", "#071a10", "#0b2617", "#0f3320"] as Ramp,
  green: ["#03140b", "#0a2a18", "#11472a", "#1f7a45", "#2fbf6a", "#3dff8f", "#b6ffd3"] as Ramp,
  grey: ["#07090a", "#151b18", "#262f2a", "#3f4a44", "#5d6862", "#8f9a93", "#c9d1cb", "#f2f0e6"] as Ramp,
  mars: ["#140403", "#2e0907", "#561310", "#8a231c", "#c0392b", "#e8573a", "#ff8a5c", "#ffc29e"] as Ramp,
  earth: ["#020c14", "#06263d", "#0d4a6b", "#1b7a8f", "#2fbf6a", "#8ff0b0", "#e9fff2"] as Ramp,
  fire: ["#2a0a00", "#6e1d00", "#c24400", "#ff7a00", "#ffc23d", "#fff2b0", "#ffffff"] as Ramp,
  gold: ["#3d2606", "#7a5414", "#c9952a", "#ffd23d", "#fff2b0"] as Ramp,
  skin: ["#3b2416", "#7a4f33", "#c08a62", "#e8b48a", "#f7d6b5"] as Ramp,
  wood: ["#1f1209", "#3d2412", "#5e3a1e", "#86562e", "#b07a44"] as Ramp,
  accent: "#3dff8f",
  alert: "#e8433a",
  white: "#f2f0e6",
  ink: "#040a07",
};

/** Fond spatial : dégradé tramé, nébuleuse verte, 3 couches d'étoiles en parallaxe qui scintillent. */
export const space = (g: Gfx, f: number, opts: { dx?: number; dy?: number; nebula?: number; ramp?: Ramp } = {}) => {
  const { dx = 0, dy = 0, nebula = 0.5, ramp = P.night } = opts;
  const ox = g.ox;
  const oy = g.oy;
  g.ox = 0;
  g.oy = 0;
  g.vgrad(0, 0, W, H, [...ramp].reverse().slice(1).concat([ramp[0]]).reverse());
  if (nebula > 0) {
    for (let y = 0; y < H; y += 1)
      for (let x = 0; x < W; x += 1) {
        const n = fbm((x + dx * 0.15) / 46, (y + dy * 0.15) / 46 + f * 0.002, 3);
        const v = (n - 0.52) * 2.4 * nebula;
        if (v > 0 && bayer(x, y) < v) g.set(x, y, col(v > 0.45 ? "#11472a" : "#0a2a18"));
      }
  }
  const layers: [number, number, number][] = [
    [90, 0.15, 1],
    [50, 0.4, 1],
    [18, 0.9, 2],
  ];
  layers.forEach(([n, par, size], li) => {
    for (let i = 0; i < n; i++) {
      const sx = (((hash(i * 3.1 + li * 99) * W - dx * par) % W) + W) % W;
      const sy = (((hash(i * 7.7 + li * 51) * H - dy * par) % H) + H) % H;
      const tw = hash(i + li * 17 + Math.floor(f / (6 + (i % 5)))) > 0.25;
      const c = li === 2 ? (tw ? "#f2f0e6" : "#8f9a93") : tw ? "#8f9a93" : "#3f4a44";
      g.rect(sx, sy, size, size, c);
      if (li === 2 && tw && hash(i + Math.floor(f / 9)) > 0.7) {
        g.set(sx - 1, sy, col("#5d6862"));
        g.set(sx + size, sy, col("#5d6862"));
        g.set(sx, sy - 1, col("#5d6862"));
        g.set(sx, sy + size, col("#5d6862"));
      }
    }
  });
  g.ox = ox;
  g.oy = oy;
};

/**
 * Système de particules déterministe.
 * Chaque particule naît à intervalle régulier, vit `life` images, suit une vitesse + gravité.
 */
export const particles = (
  g: Gfx,
  t: number,
  o: {
    seed: number;
    x: number;
    y: number;
    rate: number; // particules par image
    life: number;
    vx: number;
    vy: number;
    spread: number;
    gravity?: number;
    ramp: Ramp; // de la naissance à la mort
    size?: number;
    grow?: number;
    start?: number;
    stop?: number;
    jitter?: number;
  },
) => {
  const { seed, rate, life, ramp, gravity = 0, size = 1, grow = 0, start = 0, stop = 1e9, jitter = 4 } = o;
  const first = Math.max(Math.floor((t - life) * rate), Math.floor(start * rate));
  const last = Math.min(Math.floor(t * rate), Math.floor(stop * rate));
  for (let i = first; i <= last; i++) {
    const born = i / rate;
    const age = t - born;
    if (age < 0 || age > life) continue;
    const a = (hash(i * 1.37 + seed) - 0.5) * o.spread;
    const sp = 0.6 + hash(i * 2.11 + seed) * 0.8;
    const vx = (o.vx * Math.cos(a) - o.vy * Math.sin(a)) * sp;
    const vy = (o.vx * Math.sin(a) + o.vy * Math.cos(a)) * sp;
    const px = o.x + (hash(i * 3.3 + seed) - 0.5) * jitter + vx * age;
    const py = o.y + (hash(i * 4.4 + seed) - 0.5) * jitter + vy * age + 0.5 * gravity * age * age;
    const k = Math.min(ramp.length - 1, Math.floor((age / life) * ramp.length));
    const s = Math.max(1, Math.round(size + grow * age));
    g.rect(px - s / 2, py - s / 2, s, s, ramp[k]);
  }
};

/** Nuage de fumée tramé (boules qui gonflent). */
export const smoke = (g: Gfx, t: number, x: number, y: number, seed: number, n = 14, ramp: Ramp = P.grey) => {
  for (let i = 0; i < n; i++) {
    const a = hash(i + seed) * Math.PI * 2;
    const r0 = 4 + hash(i * 3 + seed) * 6;
    const grow = Math.min(1, t / 40);
    const px = x + Math.cos(a) * (8 + t * 0.9 * hash(i * 5 + seed)) * (0.4 + grow);
    const py = y - Math.abs(Math.sin(a)) * t * 0.25 + hash(i * 7 + seed) * 6;
    const r = Math.round(r0 * (0.5 + grow * 1.2));
    g.disc(px, py, r, ramp[3]);
    g.disc(px - r * 0.25, py - r * 0.25, Math.max(1, r - 2), ramp[5]);
    g.disc(px - r * 0.4, py - r * 0.4, Math.max(1, Math.round(r * 0.45)), ramp[6]);
  }
};

/** Explosion pixel : anneau de choc + éclats + flash. */
export const explosion = (g: Gfx, t: number, x: number, y: number, seed: number, scale = 1) => {
  if (t < 0) return;
  const r = Math.round((4 + t * 2.2) * scale);
  if (t < 14) g.ring(x, y, r, t < 6 ? "#fff2b0" : "#ff7a00", t < 8 ? 2 : 1);
  if (t < 8) g.disc(x, y, Math.round((10 - t) * 1.6 * scale), t < 3 ? "#ffffff" : "#ffc23d");
  particles(g, t + 20, {
    seed,
    x,
    y,
    rate: 3,
    life: 30,
    vx: 0,
    vy: -1.8 * scale,
    spread: Math.PI * 2,
    gravity: 0.05,
    ramp: ["#ffffff", "#ffc23d", "#ff7a00", "#c24400", "#6e1d00"],
    size: 2,
    start: 20,
    stop: 26,
  });
};

/** Lignes de vitesse (sensation de mouvement). */
export const speedLines = (g: Gfx, f: number, seed: number, dir: "down" | "up" | "left", hex = "#3f4a44", n = 26) => {
  for (let i = 0; i < n; i++) {
    const len = 8 + hash(i + seed) * 26;
    const v = 6 + hash(i * 3 + seed) * 8;
    if (dir === "left") {
      const y = hash(i * 7 + seed) * H;
      const x = W - (((f * v + hash(i * 5 + seed) * W * 2) % (W + 60)) - 30);
      g.rect(x, y, len, 1, hex);
    } else {
      const x = hash(i * 7 + seed) * W;
      const p = ((f * v + hash(i * 5 + seed) * H * 2) % (H + 60)) - 30;
      const y = dir === "down" ? p : H - p;
      g.rect(x, y, 1, len, hex);
    }
  }
};

/** Texte pixel minimaliste 3×5 (chiffres et quelques lettres) pour les écrans dessinés. */
const FONT: Record<string, string[]> = {
  "0": ["111", "101", "101", "101", "111"],
  "1": ["010", "110", "010", "010", "111"],
  "2": ["111", "001", "111", "100", "111"],
  "3": ["111", "001", "111", "001", "111"],
  "4": ["101", "101", "111", "001", "001"],
  "5": ["111", "100", "111", "001", "111"],
  "6": ["111", "100", "111", "101", "111"],
  "7": ["111", "001", "010", "010", "010"],
  "8": ["111", "101", "111", "101", "111"],
  "9": ["111", "101", "111", "001", "111"],
  ":": ["000", "010", "000", "010", "000"],
  ".": ["000", "000", "000", "000", "010"],
  ",": ["000", "000", "000", "010", "100"],
  " ": ["000", "000", "000", "000", "000"],
  "-": ["000", "000", "111", "000", "000"],
  "=": ["000", "111", "000", "111", "000"],
  "?": ["111", "001", "011", "000", "010"],
  "!": ["010", "010", "010", "000", "010"],
  "x": ["000", "101", "010", "101", "000"],
  "%": ["101", "001", "010", "100", "101"],
  A: ["111", "101", "111", "101", "101"],
  B: ["110", "101", "110", "101", "110"],
  C: ["111", "100", "100", "100", "111"],
  D: ["110", "101", "101", "101", "110"],
  E: ["111", "100", "110", "100", "111"],
  F: ["111", "100", "110", "100", "100"],
  G: ["111", "100", "101", "101", "111"],
  H: ["101", "101", "111", "101", "101"],
  I: ["111", "010", "010", "010", "111"],
  K: ["101", "101", "110", "101", "101"],
  L: ["100", "100", "100", "100", "111"],
  M: ["101", "111", "111", "101", "101"],
  N: ["110", "101", "101", "101", "101"],
  O: ["111", "101", "101", "101", "111"],
  P: ["111", "101", "111", "100", "100"],
  R: ["110", "101", "110", "101", "101"],
  S: ["111", "100", "111", "001", "111"],
  T: ["111", "010", "010", "010", "010"],
  U: ["101", "101", "101", "101", "111"],
  V: ["101", "101", "101", "101", "010"],
  W: ["101", "101", "111", "111", "101"],
  Y: ["101", "101", "010", "010", "010"],
  "·": ["000", "000", "010", "000", "000"],
};
export const ptext = (g: Gfx, s: string, x: number, y: number, hex: string, scale = 1) => {
  let cx = x;
  for (const ch of s.toUpperCase()) {
    const glyph = FONT[ch] ?? FONT[" "];
    glyph.forEach((row, j) =>
      [...row].forEach((b, i) => {
        if (b === "1") g.rect(cx + i * scale, y + j * scale, scale, scale, hex);
      }),
    );
    cx += 4 * scale;
  }
};
export const ptextWidth = (s: string, scale = 1) => s.length * 4 * scale - scale;
