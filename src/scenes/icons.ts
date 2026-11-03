import { P } from "../px/common";
import type { Gfx } from "../px/gfx";
import type { Icon } from "./schema";

/**
 * Stock d'icônes pixel art réutilisables (banque, billets, boutique…).
 * Une icône = un sprite (lignes de caractères) ou une petite fonction animée.
 */

/** Couleurs des sprites ; `a` / `d` = accent / accent sombre de la palette de l'épisode. */
const BASE: Record<string, string> = {
  k: P.ink,
  w: P.white,
  g: "#8f9a93",
  G: "#3f4a44",
  y: "#ffd23d",
  o: "#c9952a",
  r: "#e8433a",
  R: "#8a231c",
  m: "#5fd16a",
  n: "#2e8a3e",
  s: "#e8b48a",
  b: "#86562e",
  B: "#5e3a1e",
  c: "#4f9fd8",
  p: "#ff9ec4",
};

const BANK_BODY = [
  ".....kkk.....",
  "...kkyyykk...",
  ".kkyyyyyyykk.",
  "kkkkkkkkkkkkk",
  ".wg.wg.wg.wg.",
  ".wg.wg.wg.wg.",
  ".wg.wg.wg.wg.",
  ".wg.wg.wg.wg.",
  "kkkkkkkkkkkkk",
  "kgggggggggggk",
  "kkkkkkkkkkkkk",
];

export const SPRITES: Partial<Record<Icon, string[]>> = {
  banque: BANK_BODY,
  etat: ["......kcwr...", "......kcwr...", "......k......", ...BANK_BODY],
  billets: [
    "kkkkkkkkkkkkkk",
    "kmnmmmwwmmmnmk",
    "kmmmmwnnwmmmmk",
    "kmnmmmwwmmmnmk",
    "kkkkkkkkkkkkkk",
    "kmmmmmmmmmmmmk",
    "kkkkkkkkkkkkkk",
    "kmmmmmmmmmmmmk",
    "kkkkkkkkkkkkkk",
  ],
  piece: [
    "..kkkkkk..",
    ".kyyyyyyk.",
    "kywwyyyyok",
    "kywyyyyyok",
    "kyyyyyyyok",
    "kyyyyyyyok",
    "kyyyyyyook",
    ".kyyyyook.",
    "..kkkkkk..",
  ],
  tirelire: [
    "...kkkkkkk...",
    ".kkpppkkppkk.",
    "kpppppppppppk",
    "kpkpppppppppk",
    "kpppppppppRpk",
    "kpppppppppppk",
    ".kpppppppppk.",
    ".kpk.....kpk.",
    ".kkk.....kkk.",
  ],
  maison: [
    ".....kk.....",
    "....krrk....",
    "...krrrrk...",
    "..krrrrrrk..",
    ".krrrrrrrrk.",
    "kkkkkkkkkkkk",
    ".kwwwwwwwwk.",
    ".kccwwwwbbk.",
    ".kccwwwwbbk.",
    ".kwwwwwwbbk.",
    ".kkkkkkkkkk.",
  ],
  immeuble: [
    "kkkkkkkkkk",
    "kggggggggk",
    "kgcgcgcgck",
    "kggggggggk",
    "kgcgcgcgck",
    "kggggggggk",
    "kgcgcgcgck",
    "kggggggggk",
    "kgcgcgcgck",
    "kggggggggk",
    "kggkbbkggk",
    "kggkbbkggk",
    "kkkkkkkkkk",
  ],
  usine: [
    ".kk...........",
    ".kGk..k...k...",
    ".kGk.kGk.kGk..",
    ".kGkkGGGkGGGk.",
    "kkGGGGGGGGGGGk",
    "kggggggggggggk",
    "kgyygyygyygggk",
    "kggggggggggggk",
    "kgyygyyggbbggk",
    "kggggggggbbggk",
    "kkkkkkkkkkkkkk",
  ],
  boutique: [
    "kkkkkkkkkkkkkk",
    "krwrwrwrwrwrwk",
    "krwrwrwrwrwrwk",
    ".kkkkkkkkkkkk.",
    "kwwwwwwwwwwwwk",
    "kwccccwkbbkwwk",
    "kwccccwkbbkwwk",
    "kwccccwkbbkwwk",
    "kwwwwwwkbbkwwk",
    "kkkkkkkkkkkkkk",
  ],
  camion: [
    "kkkkkkkkkk......",
    "kwwwwwwwwkkkkk..",
    "kwwwwwwwwkcccck.",
    "kwwwwwwwwkcccckk",
    "kwwwwwwwwkrrrrrk",
    "kkkkkkkkkkkkkkkk",
    "..kGk.....kGk...",
    "..kkk.....kkk...",
  ],
  carton: [
    "kkkkkkkkkkkk",
    "kbbbbyybbbbk",
    "kbbbbyybbbbk",
    "kkkkkkkkkkkk",
    "kbbbbbbbbbbk",
    "kbbbbbbbbbbk",
    "kbbbBBBBbbbk",
    "kbbbbbbbbbbk",
    "kkkkkkkkkkkk",
  ],
  telephone: [
    "kkkkkkkk",
    "kGGGGGGk",
    "kcccccck",
    "kcwcccck",
    "kcccccck",
    "kcccccck",
    "kcccccck",
    "kcccccck",
    "kGGGGGGk",
    "kGGwwGGk",
    "kkkkkkkk",
  ],
  cafe: [
    "...w..w.....",
    "..w..w......",
    "...w..w.....",
    "kkkkkkkkk...",
    "kbbbbbbbk...",
    "kwwwwwwwkkk.",
    "kwwwwwwwk.k.",
    "kwwwwwwwk.k.",
    "kwwwwwwwkkk.",
    ".kwwwwwk....",
    "..kkkkk.....",
  ],
  burger: [
    "...kkkkkk...",
    ".kkookookk..",
    "koowoooowook",
    "kooooooooook",
    "kkkkkkkkkkkk",
    "kmmmmmmmmmmk",
    "kBBBBBBBBBBk",
    "kyyyyyyyyyyk",
    "kooooooooook",
    ".kkkkkkkkkk.",
  ],
  hotdog: [
    "..kkkkkkkkkk..",
    ".kooooooooook.",
    "kRRRRRRRRRRRRk",
    "kRyRRyRRyRRyRk",
    "kooooooooooook",
    ".kooooooooook.",
    "..kkkkkkkkkk..",
  ],
  caddie: [
    "kk...........",
    ".k...........",
    ".kkkkkkkkkkkk",
    "..kwkwkwkwkwk",
    "..kkkkkkkkkkk",
    "...kwkwkwkwk.",
    "...kkkkkkkkk.",
    "...k.........",
    "...kkkkkkkk..",
    "....kGk..kGk.",
    "....kkk..kkk.",
  ],
  cadenas: [
    "..kkkkkk..",
    ".kk....kk.",
    ".kk....kk.",
    ".kk....kk.",
    "kkkkkkkkkk",
    "kyyyyyyyyk",
    "kyyykkyyyk",
    "kyyykkyyyk",
    "kyyyyyyyyk",
    "kkkkkkkkkk",
  ],
  etoile: [
    ".....k.....",
    "....kyk....",
    "....kyk....",
    "kkkkyyykkkk",
    ".kyyyyyyyk.",
    "..kyyyyyk..",
    "...kyyyk...",
    "..kyykyyk..",
    ".kyk...kyk.",
    ".kk.....kk.",
  ],
  homme: [
    "..kkkkk..",
    ".kBBBBBk.",
    ".kBsssBk.",
    ".ksksksk.",
    ".ksssssk.",
    "..ksssk..",
    ".kccrcck.",
    "kcccrccck",
    "kcccrccck",
    "kccccccck",
    ".kcc.cck.",
    ".kGG.GGk.",
  ],
  femme: [
    "..kkkkk..",
    ".kbbbbbk.",
    "kbbsssbbk",
    "kbsksksbk",
    "kbsssssbk",
    "kbbsssbbk",
    ".krrrrrk.",
    "krrrrrrrk",
    "krrrrrrrk",
    ".krrrrrk.",
    "..ks.sk..",
    "..kk.kk..",
  ],
  ampoule: [
    "..kkkkk..",
    ".kyyyyyk.",
    "kyywyyyyk",
    "kywyyyyyk",
    "kyyyyyyyk",
    "kyyyyyyyk",
    ".kyyyyyk.",
    "..kyyyk..",
    "..kgggk..",
    "..kGGGk..",
    "..kgggk..",
    "...kkk...",
  ],
  avion: [
    "kk.............",
    "kwk............",
    "kwwkkkkkkkkkk..",
    "kwwwwwcwcwcwwkk",
    "kkkkwwwwwwwwwwk",
    ".....kwwwk.....",
    "......kkk......",
  ],
  voiture: [
    "....kkkkk.....",
    "...kcckcck....",
    "kkkkkkkkkkkkk.",
    "krrrrrrrrrrrrk",
    "krrrrrrrrrrryk",
    "kkkkkkkkkkkkkk",
    "..kGk....kGk..",
    "..kkk....kkk..",
  ],
  cadeau: [
    "...kk.kk...",
    "..kyykyyk..",
    "...kkykk...",
    "kkkkkykkkkk",
    "krrrryrrrrk",
    "kkkkkykkkkk",
    "krrrryrrrrk",
    "krrrryrrrrk",
    "krrrryrrrrk",
    "kkkkkkkkkkk",
  ],
  carte: [
    "kkkkkkkkkkkkkk",
    "kcccccccccccck",
    "kcyyccccccccck",
    "kcyyccccccccck",
    "kcccccccccccck",
    "kcwwcwwcwwccck",
    "kcccccccccccck",
    "kkkkkkkkkkkkkk",
  ],
};

/** Icônes animées, dessinées en code (taille ~12 px de base). */
const CODED: Partial<Record<Icon, (g: Gfx, cx: number, cy: number, s: number, t: number, accent: string) => void>> = {
  graphique: (g, cx, cy, s, t, accent) => {
    const x0 = cx - 6 * s;
    const y0 = cy + 6 * s;
    g.rect(x0, y0, 13 * s, s, P.ink);
    g.rect(x0, cy - 6 * s, s, 12 * s, P.ink);
    [3, 5, 8, 11].forEach((h, i) => {
      const hh = Math.min(h, Math.max(1, Math.floor(((t - i * 4) / 6) * h)));
      g.rect(x0 + (2 + i * 3) * s, y0 - hh * s, 2 * s, hh * s, accent);
    });
  },
  baisse: (g, cx, cy, s, t) => {
    const x0 = cx - 6 * s;
    const y0 = cy + 6 * s;
    g.rect(x0, y0, 13 * s, s, P.ink);
    g.rect(x0, cy - 6 * s, s, 12 * s, P.ink);
    [11, 8, 5, 2].forEach((h, i) => {
      const hh = Math.min(h, Math.max(1, Math.floor(((t - i * 4) / 6) * h)));
      g.rect(x0 + (2 + i * 3) * s, y0 - hh * s, 2 * s, hh * s, P.alert);
    });
  },
  cible: (g, cx, cy, s) => {
    g.disc(cx, cy, 6 * s, P.ink);
    g.disc(cx, cy, 5 * s, P.alert);
    g.disc(cx, cy, 3.6 * s, P.white);
    g.disc(cx, cy, 2.2 * s, P.alert);
    g.disc(cx, cy, 0.9 * s, P.white);
  },
  horloge: (g, cx, cy, s, t) => {
    g.disc(cx, cy, 6 * s, P.ink);
    g.disc(cx, cy, 5 * s, P.white);
    const a = (t / 30) * Math.PI * 2;
    g.line(cx, cy, Math.round(cx + Math.sin(a) * 4 * s), Math.round(cy - Math.cos(a) * 4 * s), P.ink);
    g.line(cx, cy, Math.round(cx + Math.sin(a / 12) * 2.6 * s), Math.round(cy - Math.cos(a / 12) * 2.6 * s), P.alert);
  },
  feu: (g, cx, cy, s, t) => {
    for (let k = 0; k < 3; k++) {
      const flick = Math.sin(t / 3 + k * 2) * 0.6;
      const r = (5 - k * 1.4 + flick) * s;
      g.disc(cx, cy + k * s - k * 1.5 * s, r, P.fire[2 + k * 1]);
    }
    g.rect(cx - 5 * s, cy + 4 * s, 10 * s, s, "#3d2412");
  },
};

/** Taille (en pixels de sprite) d'une icône, pour la centrer et la poser. */
export const iconSize = (icon: Icon) => {
  const sp = SPRITES[icon];
  return sp ? { w: sp[0].length, h: sp.length } : { w: 13, h: 13 };
};

/** Dessine une icône centrée en (cx, cy), à l'échelle s, avec un petit rebond à l'apparition (t = images depuis l'apparition). */
export const drawIcon = (g: Gfx, icon: Icon, cx: number, cy: number, s: number, t: number, pal: { accent: string; dim: string }) => {
  if (t < 0) return;
  const pop = t < 6 ? [0.4, 0.8, 1.15, 1.1, 1.03, 1][t] : 1;
  const sc = Math.max(1, Math.round(s * pop));
  const code = CODED[icon];
  if (code) return code(g, cx, cy, sc, t, pal.accent);
  const rows = SPRITES[icon];
  if (!rows) return;
  const bob = t > 6 ? Math.round(Math.sin(t / 14) * 0.6) : 0;
  g.sprite(rows, { ...BASE, a: pal.accent, d: pal.dim }, Math.round(cx - (rows[0].length * sc) / 2), Math.round(cy - (rows.length * sc) / 2) + bob, sc);
};
