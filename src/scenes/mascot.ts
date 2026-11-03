import { P } from "../px/common";
import type { Gfx } from "../px/gfx";
import type { Pose } from "./schema";

/**
 * « Max », la mascotte de la chaîne : un personnage pixel à casquette verte qui vit chaque histoire.
 * Dessiné en code (pas en image) pour pouvoir l'animer : il respire, cligne des yeux, parle,
 * saute quand il est choqué, compte ses billets…
 */

export type { Pose };

const SKIN = "#e8b48a";
const SKIN_D = "#c08a62";
const HAIR = "#5e3a1e";
const HOODIE = "#eef2ec";
const HOODIE_D = "#b9c4bb";
const JEANS = "#2f4a7a";
const JEANS_D = "#22375c";
const SHOE = "#f2f0e6";
const INK = P.ink;

/** Taille de Max en unités (largeur, hauteur) : 18 × 27. */
export const MAX_W = 18;
export const MAX_H = 27;

type Opts = { accent: string; talking?: boolean; flip?: boolean };

/**
 * Dessine Max debout, pieds en (cx, by), à l'échelle u (pixels par unité).
 * t = images depuis le début de la pose (pour les animations).
 */
export const drawMax = (g: Gfx, cx: number, by: number, u: number, pose: Pose, t: number, o: Opts) => {
  const jump = pose === "choc" ? Math.round(Math.max(0, Math.sin(Math.min(1, t / 10) * Math.PI)) * 3) : pose === "content" ? Math.round(Math.abs(Math.sin(t / 5)) * 2) : 0;
  const bob = Math.floor(t / 14) % 2;
  const shake = pose === "choc" && t < 18 ? (t % 2 ? 1 : -1) : 0;
  const ox = Math.round(cx - (MAX_W * u) / 2) + shake * u;
  const oy = Math.round(by - MAX_H * u) - jump * u;
  const fx = (x: number, w = 1) => (o.flip ? MAX_W - x - w : x);
  /** Une pièce du corps : contour encre d'un pixel, puis remplissage. */
  const box = (x: number, y: number, w: number, h: number, fill: string, outline = true) => {
    const X = ox + fx(x, w) * u;
    const Y = oy + y * u;
    if (outline) g.rect(X - 1, Y - 1, w * u + 2, h * u + 2, INK);
    g.rect(X, Y, w * u, h * u, fill);
  };
  const dot = (x: number, y: number, w: number, h: number, fill: string) => box(x, y, w, h, fill, false);

  // jambes et chaussures (immobiles : il respire par le haut du corps)
  const legY = 20;
  box(6, legY, 2, 5, JEANS);
  box(10, legY, 2, 5, JEANS);
  dot(7, legY, 1, 5, JEANS_D);
  dot(11, legY, 1, 5, JEANS_D);
  box(5, 25, 3, 2, SHOE);
  box(10, 25, 3, 2, SHOE);
  dot(5, 26, 3, 1, "#8f9a93");
  dot(10, 26, 3, 1, "#8f9a93");

  const b = bob; // le haut du corps monte d'une unité sur deux temps
  // corps (sweat blanc, cordons verts)
  box(5, 12 - b, 8, 9 + b, HOODIE);
  dot(5, 18, 8, 1, HOODIE_D);
  dot(8, 13 - b, 1, 3, o.accent);
  dot(10, 13 - b, 1, 3, o.accent);

  // bras selon la pose
  const arm = (x: number, y: number, w: number, h: number, hand: [number, number]) => {
    box(x, y, w, h, HOODIE);
    box(hand[0], hand[1], 2, 2, SKIN);
  };
  const wave = Math.round(Math.sin(t / 3));
  switch (pose) {
    case "choc":
      arm(2, 7 - b, 2, 6, [2, 5 - b]);
      arm(14, 7 - b, 2, 6, [14, 5 - b]);
      break;
    case "content":
      arm(2, 8 - b + wave, 2, 5, [1, 6 - b + wave]);
      arm(14, 8 - b - wave, 2, 5, [15, 6 - b - wave]);
      break;
    case "montre":
      arm(3, 13 - b, 2, 6, [3, 19 - b]);
      arm(13, 13 - b, 4, 2, [17, 13 - b]);
      break;
    case "telephone":
      arm(3, 13 - b, 2, 6, [3, 19 - b]);
      arm(12, 13 - b, 2, 3, [11, 15 - b]);
      // téléphone dans la main, écran qui brille
      box(10, 11 - b, 3, 5, "#1b2421");
      dot(10, 12 - b, 3, 3, Math.floor(t / 8) % 2 ? o.accent : "#b6ffd3");
      break;
    case "reflechit":
      arm(3, 13 - b, 2, 6, [3, 19 - b]);
      arm(12, 12 - b, 2, 3, [11, 10 - b]);
      break;
    case "argent": {
      arm(2, 12 - b, 2, 4, [3, 15 - b]);
      arm(14, 12 - b, 2, 4, [13, 15 - b]);
      // éventail de billets qui s'ouvre
      const open = Math.min(3, Math.floor(t / 4));
      for (let k = 0; k <= open; k++) box(6 + k * 2 - open, 13 - b - k, 4, 3, k % 2 ? "#5fd16a" : "#2e8a3e");
      break;
    }
    default:
      arm(3, 13 - b, 2, 6, [3, 19 - b]);
      arm(13, 13 - b, 2, 6, [13, 19 - b]);
  }

  // tête
  const hy = 3 - b;
  box(4, hy, 10, 9, SKIN);
  dot(4, hy + 8, 10, 1, SKIN_D);
  dot(4, hy, 2, 3, HAIR);
  // oreille
  dot(o.flip ? 13 : 4, hy + 4, 1, 2, SKIN_D);

  // yeux : clignement toutes les ~3 s, grands ronds quand il est choqué
  const blink = (t + 7) % 90 < 4;
  if (pose === "choc") {
    box(6, hy + 3, 2, 3, "#ffffff");
    box(10, hy + 3, 2, 3, "#ffffff");
    dot(7, hy + 4, 1, 1, INK);
    dot(11, hy + 4, 1, 1, INK);
  } else if (pose === "content") {
    dot(6, hy + 4, 2, 1, INK);
    dot(10, hy + 4, 2, 1, INK);
    dot(5, hy + 3, 1, 1, INK);
    dot(8, hy + 3, 1, 1, INK);
    dot(9, hy + 3, 1, 1, INK);
    dot(12, hy + 3, 1, 1, INK);
  } else if (blink) {
    dot(6, hy + 4, 2, 1, INK);
    dot(10, hy + 4, 2, 1, INK);
  } else {
    dot(7, hy + 3, 1, 2, INK);
    dot(11, hy + 3, 1, 2, INK);
  }
  // sourcils qui se lèvent quand il réfléchit
  if (pose === "reflechit") {
    dot(6, hy + 1, 2, 1, HAIR);
    dot(10, hy + 2, 2, 1, HAIR);
  }

  // bouche : ouverte en rythme quand la voix parle
  const open = pose === "choc" || (o.talking && Math.floor(t / 4) % 2 === 0);
  if (pose === "content") {
    dot(7, hy + 6, 4, 1, INK);
    dot(8, hy + 7, 2, 1, "#c0392b");
  } else if (open) {
    box(8, hy + 6, 2, 2, "#7a1f1a");
  } else {
    dot(8, hy + 7, 3, 1, INK);
  }

  // casquette verte (la couleur de la chaîne), visière vers l'avant
  box(3, hy - 3, 11, 3, o.accent);
  dot(3, hy - 1, 11, 1, "#0d3a22");
  box(o.flip ? 1 : 12, hy - 1, 5, 1, o.accent);
  dot(8, hy - 3, 2, 1, "#ffffff");

  // petits signes au-dessus de la tête
  const signX = ox + fx(15) * u;
  const signY = oy + (hy - 6) * u;
  if (pose === "choc" && t > 2) {
    g.rect(signX, signY - 4 * u, u, 3 * u, P.alert);
    g.rect(signX, signY, u, u, P.alert);
  }
  if (pose === "reflechit") {
    const k = Math.floor(t / 10) % 2;
    g.rect(signX, signY - 4 * u + k, 2 * u, u, "#ffffff");
    g.rect(signX + 2 * u, signY - 3 * u + k, u, u, "#ffffff");
    g.rect(signX + u, signY - 2 * u + k, u, u, "#ffffff");
    g.rect(signX + u, signY + k, u, u, "#ffffff");
  }
  if (pose === "argent") {
    for (let k = 0; k < 6; k++) {
      const y = ((t * 2 + k * 23) % 60) - 10;
      g.disc(ox + ((k * 37) % (MAX_W * u)), oy - 8 * u + y * (u / 2), Math.max(1, u * 0.8), "#ffd23d");
    }
  }
  if (pose === "content" && t % 12 < 6) {
    g.rect(ox - u, oy + 2 * u, u, u, "#ffd23d");
    g.rect(ox + (MAX_W + 1) * u, oy + 4 * u, u, u, "#ffd23d");
  }
};
