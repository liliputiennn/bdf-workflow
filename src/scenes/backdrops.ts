import { P, smoke } from "../px/common";
import { col, Gfx, H, hash, W } from "../px/gfx";
import { drawMonitor } from "../px/objects";
import { drawIcon } from "./icons";
import type { Pal } from "./palettes";
import type { Decor } from "./schema";

/** Fonds pixel réutilisables : grille « données », papier, et décors de coulisses. */

/** Fond des scènes de données : dégradé, sol en perspective qui défile, poussière lumineuse. */
export const dataBackdrop = (g: Gfx, f: number, pal: Pal) => {
  if (pal.light) return paper(g, f, pal);
  g.vgrad(0, 0, W, H, pal.sky);
  const horizon = 250;
  for (let k = 0; k < 9; k++) {
    const z = ((k + (f / 40) % 1) / 9) ** 2;
    const y = Math.round(horizon + z * (H - horizon));
    g.rect(0, y, W, 1, pal.grid);
  }
  for (let k = -8; k <= 8; k++) g.line(W / 2 + k * 4, horizon, W / 2 + k * 40, H, pal.grid);
  for (let k = 0; k < 24; k++) {
    const x = Math.floor(hash(k * 3.1) * W);
    const y = Math.floor((hash(k * 7.7) * H + f * (0.2 + hash(k) * 0.4)) % H);
    if (hash(k + Math.floor(f / 6)) > 0.3) g.set(x, H - 1 - y, col(pal.dim));
  }
};

/** Papier quadrillé (hommage tableau blanc) : fond crème, grille fine, grain. */
const paper = (g: Gfx, f: number, pal: Pal) => {
  g.vgrad(0, 0, W, H, pal.sky);
  for (let x = 6; x < W; x += 12) g.rect(x, 0, 1, H, pal.grid);
  for (let y = 6; y < H; y += 12) g.rect(0, y, W, 1, pal.grid);
  g.dither(0, 0, W, H, "#d9cdb0", 0.06 + 0.01 * Math.sin(f / 9));
};

/** « Jour » reste vert (identité de la chaîne) : un ciel vert plus clair que la nuit. */
const day = (pal: Pal) => [pal.sky[3], pal.deep, pal.dim, pal.dim];

const sky = (g: Gfx, f: number, pal: Pal, night: boolean) => {
  if (pal.light) return paper(g, f, pal);
  g.vgrad(0, 0, W, 300, night ? pal.sky : day(pal));
  if (night)
    for (let k = 0; k < 40; k++) {
      const x = Math.floor(hash(k * 5.3) * W);
      const y = Math.floor(hash(k * 9.1) * 200);
      if (hash(k + Math.floor(f / 10)) > 0.25) g.rect(x, y, 1, 1, P.white);
    }
};

const ground = (g: Gfx, pal: Pal, y = 300) => {
  g.rect(0, y, W, H - y, pal.light ? "#cfc19c" : "#141a17");
  g.rect(0, y, W, 2, pal.light ? "#8a7d5c" : "#2b332e");
};

const skyline = (g: Gfx, f: number, night: boolean) => {
  for (let k = 0; k < 9; k++) {
    const w = 18 + Math.floor(hash(k * 2.2) * 16);
    const h = 50 + Math.floor(hash(k * 4.4) * 90);
    const x = k * 26 - 6;
    g.rect(x, 300 - h, w, h, night ? "#0b100e" : "#0f2a1c");
    for (let wy = 300 - h + 6; wy < 292; wy += 8)
      for (let wx = x + 3; wx < x + w - 3; wx += 6)
        if (hash(wx * 1.3 + wy * 0.7 + Math.floor(f / 50)) > (night ? 0.55 : 0.8)) g.rect(wx, wy, 2, 3, night ? "#ffd23d" : "#b6ffd3");
  }
};

/** Décor de coulisses. `t` = images depuis le début de la scène. */
export const decorBackdrop = (g: Gfx, decor: Decor, f: number, t: number, pal: Pal, night: boolean) => {
  sky(g, f, pal, night);
  if (decor !== "bureau") skyline(g, f, night && !pal.light);
  ground(g, pal);
  const ip = { accent: pal.accent, dim: pal.dim };
  switch (decor) {
    case "usine": {
      drawIcon(g, "usine", 108, 262, 6, t + 6, ip);
      smoke(g, f, 76, 210, 3, 14);
      // tapis roulant et cartons
      g.rect(10, 318, 196, 6, "#3f4a44");
      for (let k = 0; k < 5; k++) drawIcon(g, "carton", ((k * 48 + f * 0.8) % 240) - 12, 308, 2, 20, ip);
      break;
    }
    case "boutique": {
      drawIcon(g, "boutique", 108, 255, 9, t + 6, ip);
      const walk = (f * 0.7) % 260;
      drawIcon(g, "femme", Math.round(walk - 20), 318, 3, 20, ip);
      drawIcon(g, "homme", Math.round(240 - ((walk + 120) % 260)), 322, 3, 20, ip);
      break;
    }
    case "entrepot": {
      for (let s = 0; s < 3; s++) {
        g.rect(14, 160 + s * 46, 188, 3, "#5d6862");
        for (let k = 0; k < 6; k++) if (hash(s * 9 + k) > 0.2) drawIcon(g, "carton", 30 + k * 31, 146 + s * 46, 2, 20, ip);
      }
      drawIcon(g, "camion", Math.round(Math.min(108, -40 + t * 3)), 320, 4, 20, ip);
      break;
    }
    case "bureau": {
      g.rect(0, 0, W, 300, pal.light ? pal.sky[1] : "#0b100e");
      g.rect(30, 50, 156, 110, night ? "#06121c" : pal.dim);
      skyline(g, f, night);
      g.rect(30, 50, 156, 4, "#2b332e");
      g.rect(106, 50, 4, 110, "#2b332e");
      g.rect(0, 160, W, 140, pal.light ? pal.sky[2] : "#10161a");
      ground(g, pal, 300);
      g.rect(20, 270, 176, 8, "#5e3a1e");
      drawMonitor(g, 70, 222, 76, 48, f);
      break;
    }
    case "banque": {
      drawIcon(g, "banque", 108, 250, 10, t + 6, ip);
      for (let k = 0; k < 6; k++) {
        const y = ((f * 2 + k * 60) % 300) + 20;
        drawIcon(g, "piece", 20 + k * 36, y, 1, 20, ip);
      }
      break;
    }
    case "rue": {
      drawIcon(g, "boutique", 60, 268, 5, t + 6, ip);
      drawIcon(g, "immeuble", 160, 250, 5, t + 6, ip);
      drawIcon(g, "voiture", Math.round(((f * 1.6) % 300) - 40), 330, 3, 20, ip);
      break;
    }
  }
};
