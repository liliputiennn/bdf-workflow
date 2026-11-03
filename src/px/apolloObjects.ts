import { P, particles, ptext } from "./common";
import { bayer, col, fbm, Gfx, hash, noise, pen } from "./gfx";

const G = P.grey;
const SILVER = ["#3f4a44", "#8f9a93", "#c9d1cb", "#e6ebe7", "#ffffff"];

/* ───────── Fusée Saturn V (≈150 px de haut) ───────── */
export const drawSaturnV = (g: Gfx, cx: number, by: number, t: number, firing: number) => {
  const top = by - 150;
  // tour de sauvetage
  g.rect(cx, top, 1, 9, G[6]);
  g.rect(cx - 1, top + 9, 3, 3, "#c0392b");
  // capsule et module de service
  for (let j = 0; j < 7; j++) g.rect(cx - 1 - j * 0.5, top + 12 + j, 3 + j, 1, j < 3 ? G[7] : G[6]);
  g.rect(cx - 4, top + 19, 8, 8, G[6]);
  g.rect(cx + 2, top + 19, 2, 8, G[4]);
  // adaptateur conique
  for (let j = 0; j < 12; j++) {
    const w = 8 + Math.round(j / 3);
    g.rect(cx - w / 2, top + 27 + j, w, 1, G[7]);
    g.rect(cx + w / 2 - 2, top + 27 + j, 2, 1, G[5]);
  }
  // 3e étage
  g.rect(cx - 6, top + 39, 12, 22, G[7]);
  g.rect(cx + 3, top + 39, 3, 22, G[5]);
  g.rect(cx - 6, top + 46, 12, 3, P.ink);
  // 2e étage
  g.rect(cx - 7, top + 61, 14, 36, G[7]);
  g.rect(cx + 4, top + 61, 3, 36, G[5]);
  g.rect(cx - 7, top + 61, 14, 2, G[3]);
  g.rect(cx - 7, top + 66, 4, 6, P.ink);
  g.rect(cx + 3, top + 86, 4, 6, P.ink);
  // 1er étage, motif de roulis noir et blanc
  g.rect(cx - 7, top + 97, 14, 46, G[7]);
  g.rect(cx + 4, top + 97, 3, 46, G[5]);
  g.rect(cx - 7, top + 97, 7, 8, P.ink);
  g.rect(cx, top + 105, 7, 8, P.ink);
  g.rect(cx - 7, top + 131, 7, 12, P.ink);
  g.rect(cx, top + 131, 7, 4, P.ink);
  ptext(g, "USA", cx - 5, top + 116, P.alert);
  // ailerons et tuyères
  g.rect(cx - 10, top + 134, 3, 10, G[4]);
  g.rect(cx + 7, top + 134, 3, 10, G[4]);
  for (const dx of [-6, -2, 2]) g.rect(cx + dx, top + 143, 4, 6, G[2]);
  if (firing > 0) {
    const len = Math.round((30 + 22 * hash(Math.floor(t))) * firing);
    for (let j = 0; j < len; j++) {
      const w = Math.max(1, Math.round((10 + j * 0.15) * firing * (0.9 + 0.2 * hash(j + t))));
      const d = j / len;
      const c = d < 0.2 ? "#ffffff" : d < 0.45 ? "#fff2b0" : d < 0.7 ? "#ffc23d" : "#ff7a00";
      for (let i = -w; i <= w; i++) if (bayer(cx + i, by + j) < 1 - d * 0.6 - (Math.abs(i) / (w + 1)) * 0.4) g.set(cx + i, by + j, col(c));
    }
    particles(g, t, { seed: 13, x: cx, y: by + len, rate: 5, life: 28, vx: 0, vy: 1.4, spread: 1.8, ramp: ["#fff2b0", "#ffc23d", "#ff7a00", "#c24400", G[5], G[4]], size: 3, grow: 0.2, jitter: 10 });
  }
};

/* ───────── Vaisseau Apollo : module de service + capsule + module lunaire amarré (horizontal) ───────── */
export const STACK_W = 52;
export const drawStack = (g: Gfx, cx: number, cy: number, u: number, t: number, damaged = 0, withLM = true) => {
  const x0 = Math.round(cx - (STACK_W * u) / 2);
  const y0 = Math.round(cy - 6 * u);
  const r = pen(g, x0, y0, u);
  // tuyère principale
  r(0, 3, 4, 6, G[3]);
  r(1, 4, 3, 4, G[2]);
  // module de service
  r(4, 0, 18, 12, SILVER[2]);
  r(4, 0, 18, 2, SILVER[3]);
  r(4, 10, 18, 2, SILVER[1]);
  for (let k = 0; k < 4; k++) r(6 + k * 4, 0, 1, 12, SILVER[1]);
  r(16, 3, 4, 3, "#c0392b");
  if (damaged > 0) {
    r(8, 0, 7, 5, P.ink);
    r(9, 1, 5, 3, "#261005");
    r(15, 1, 1, 2, SILVER[1]);
    r(7, 2, 1, 1, SILVER[1]);
  }
  // capsule
  for (let i = 0; i < 10; i++) {
    const h = 12 - Math.round(i * 1.0);
    r(22 + i, (12 - h) / 2, 1, h, i < 1 ? "#7a5414" : i < 6 ? SILVER[3] : SILVER[2]);
  }
  r(27, 4, 1, 1, P.ink);
  r(32, 5, 2, 2, G[5]);
  if (withLM) {
    // module lunaire amarré (vu de côté)
    r(34, 3, 7, 6, G[6]);
    r(35, 4, 2, 2, P.ink);
    r(41, 1, 10, 10, "#c9952a");
    r(41, 1, 10, 2, "#ffd23d");
    r(41, 9, 10, 2, "#7a5414");
    for (let j = 0; j < 10; j++)
      for (let i = 0; i < 10; i++) if (hash(i * 7 + j * 13) > 0.85) r(41 + i, 1 + j, 1, 1, "#fff2b0");
    r(51, -1, 1, 4, G[5]);
    r(51, 9, 1, 4, G[5]);
  }
  if (damaged > 0) {
    // oxygène qui fuit dans le vide
    particles(g, t, { seed: 71, x: x0 + 11 * u, y: y0, rate: 3 * damaged, life: 40, vx: -0.3, vy: -1.1, spread: 1.4, ramp: ["#ffffff", "#e9fff2", "#c9d1cb", "#8f9a93", "#3f4a44"], size: 2, grow: 0.12, jitter: 4 });
  }
};

/* ───────── Module lunaire vertical (le « canot de sauvetage ») ───────── */
export const drawLM = (g: Gfx, cx: number, cy: number, u: number, t: number) => {
  const r = pen(g, Math.round(cx - 14 * u), Math.round(cy - 14 * u), u);
  // étage de remontée (cabine)
  r(9, 0, 10, 2, G[6]);
  r(7, 2, 14, 9, G[6]);
  r(7, 2, 14, 2, G[7]);
  r(19, 4, 2, 7, G[4]);
  r(9, 4, 3, 3, P.ink);
  r(16, 4, 3, 3, P.ink);
  r(10, 5, 1, 1, Math.floor(t / 10) % 2 ? P.accent : "#11472a");
  r(13, -2, 1, 2, G[5]);
  r(6, 6, 1, 2, G[5]);
  r(21, 6, 1, 2, G[5]);
  // étage de descente doré
  r(5, 11, 18, 8, "#c9952a");
  r(5, 11, 18, 2, "#ffd23d");
  r(5, 17, 18, 2, "#7a5414");
  for (let j = 0; j < 8; j++) for (let i = 0; i < 18; i++) if (hash(i * 5 + j * 11) > 0.86) r(5 + i, 11 + j, 1, 1, "#fff2b0");
  // pieds
  g.line(cx - 9 * u, cy + 5 * u, cx - 14 * u, cy + 13 * u, G[5]);
  g.line(cx + 9 * u, cy + 5 * u, cx + 14 * u, cy + 13 * u, G[5]);
  g.line(cx - 4 * u, cy + 5 * u, cx - 6 * u, cy + 13 * u, G[4]);
  g.line(cx + 4 * u, cy + 5 * u, cx + 6 * u, cy + 13 * u, G[4]);
  r(-2, 26, 5, 1, G[6]);
  r(25, 26, 5, 1, G[6]);
};

/* ───────── Lune ───────── */
export const drawMoon = (g: Gfx, cx: number, cy: number, r: number, rot: number) => {
  g.glow(cx, cy, Math.round(r * 1.12), "#3f4a44", 0.4);
  g.sphere(cx, cy, r, ["#151b18", "#3f4a44", "#5d6862", "#8f9a93", "#c9d1cb", "#e6ebe7"], {
    rot,
    rim: "#ffffff",
    tex: (lon, lat) => {
      const maria = fbm(lon * 1.8 + 3, lat * 2.2, 6, 3) > 0.58 ? -0.55 : 0;
      const crater = noise(lon * 11, lat * 11, 2) > 0.8 ? -0.35 : 0;
      return maria + crater + (fbm(lon * 4, lat * 4, 9, 2) - 0.5) * 0.4;
    },
  });
};

/* ───────── Astronaute (combinaison blanche, visière dorée) ───────── */
export const drawAstronaut = (g: Gfx, cx: number, by: number, u: number, t: number, phase = 0) => {
  const bob = Math.round(Math.sin((t + phase) / 14) * u);
  const r = pen(g, Math.round(cx - 6 * u), Math.round(by - 16 * u) + bob, u);
  r(1, 5, 2, 6, G[5]); // sac à dos
  r(2, 0, 8, 7, G[7]); // casque
  r(2, 0, 8, 1, "#ffffff");
  r(4, 2, 5, 3, "#c9952a"); // visière
  r(5, 2, 2, 1, "#fff2b0");
  r(3, 7, 7, 6, G[7]); // corps
  r(8, 7, 2, 6, G[5]);
  r(4, 8, 2, 2, "#c0392b"); // drapeau
  r(4, 10, 3, 1, "#1f5585");
  r(1, 8, 2, 4, G[6]); // bras
  r(10, 8, 2, 4, G[6]);
  r(3, 13, 3, 3, G[6]); // jambes
  r(7, 13, 3, 3, G[6]);
  r(3, 15, 3, 1, G[4]);
  r(7, 15, 3, 1, G[4]);
};

/* ───────── Portrait d'astronaute (casque ouvert) ───────── */
export const drawCrewBust = (g: Gfx, cx: number, by: number, u: number, t: number, hair: string, skin: string) => {
  const r = pen(g, Math.round(cx - 10 * u), Math.round(by - 24 * u), u);
  const blink = (t + Math.floor(cx)) % 80 < 4;
  r(0, 14, 20, 10, G[7]); // épaules
  r(15, 14, 5, 10, G[5]);
  r(4, 16, 3, 2, "#c0392b");
  r(8, 15, 4, 4, G[4]); // col
  r(2, 0, 16, 15, G[6]); // anneau du casque
  r(4, 2, 12, 12, skin); // visage
  r(4, 2, 12, 3, hair);
  r(4, 2, 2, 7, hair);
  r(7, 7, 2, blink ? 1 : 2, P.ink);
  r(12, 7, 2, blink ? 1 : 2, P.ink);
  r(9, 11, 3, 1, "#7a4f33");
  r(14, 4, 2, 10, "#c08a62");
};

/* ───────── Salle de contrôle de Houston ───────── */
export const drawMissionControl = (g: Gfx, t: number, people = true) => {
  g.vgrad(0, 0, 216, 384, ["#05080c", "#0a1420", "#0f1a24"]);
  // grand écran mural avec la trajectoire
  g.rect(16, 96, 184, 84, "#0a1f2e");
  g.rect(16, 96, 184, 2, G[4]);
  for (let x = 20; x < 196; x += 12) g.rect(x, 98, 1, 82, "#0f2c40");
  for (let y = 102; y < 178; y += 10) g.rect(16, y, 184, 1, "#0f2c40");
  const p = (t % 160) / 160;
  for (let k = 0; k < 60 * p; k++) {
    const a = (k / 60) * Math.PI * 1.6 - 0.3;
    g.set(108 + Math.cos(a) * 70, 138 + Math.sin(a) * 26, col(k % 2 ? P.accent : "#1f7a45"));
  }
  g.disc(40, 138, 7, "#1b7a8f");
  g.disc(176, 138, 5, G[5]);
  // rangées de pupitres
  for (let row = 0; row < 3; row++) {
    const y = 210 + row * 52;
    g.rect(0, y + 18, 216, 26, "#3f4a44");
    g.rect(0, y + 18, 216, 3, "#5d6862");
    for (let k = 0; k < 5; k++) {
      const x = 8 + k * 42 + (row % 2) * 10;
      g.rect(x, y + 4, 26, 16, "#151b18");
      g.rect(x + 2, y + 6, 22, 12, "#031208");
      for (let l = 0; l < 3; l++) g.rect(x + 4, y + 8 + l * 3, 6 + Math.round(hash(k + l + row * 9 + Math.floor(t / 9)) * 12), 1, P.accent);
      if (people && (k + row) % 2 === 0) {
        // ingénieur en chemise blanche, de dos
        g.rect(x + 8, y + 22, 12, 14, "#e6ebe7");
        g.disc(x + 14, y + 18, 4, "#3d2412");
        g.rect(x + 13, y + 26, 2, 8, P.ink);
      }
    }
  }
};

/* ───────── Cartouche filtrante et prise ───────── */
export const drawCartridge = (g: Gfx, cx: number, cy: number, u: number, sat: number) => {
  const r = pen(g, Math.round(cx - 9 * u), Math.round(cy - 9 * u), u);
  const body = sat > 0.6 ? "#8a7a3a" : G[6];
  r(0, 0, 18, 18, body);
  r(0, 0, 18, 2, G[7]);
  r(16, 0, 2, 18, G[4]);
  for (let j = 0; j < 4; j++) for (let i = 0; i < 4; i++) r(2 + i * 4, 4 + j * 3, 2, 2, sat > 0.6 ? "#5a4a1a" : G[3]);
  ptext(g, "LIOH", cx - 7 * u, cy + 6 * u, P.ink, u);
};
export const drawSocket = (g: Gfx, cx: number, cy: number, u: number) => {
  g.rect(cx - 16 * u, cy - 16 * u, 32 * u, 32 * u, G[3]);
  g.rect(cx - 16 * u, cy - 16 * u, 32 * u, 2 * u, G[5]);
  // ouverture étroite : pas la même forme que la cartouche
  g.rect(cx - 4 * u, cy - 12 * u, 8 * u, 24 * u, P.ink);
  g.rect(cx - 4 * u, cy - 12 * u, 8 * u, 1 * u, G[2]);
};

/* ───────── Les objets du bricolage ───────── */
export const drawBag = (g: Gfx, cx: number, cy: number, u: number) => {
  for (let j = 0; j < 22 * u; j++)
    for (let i = 0; i < 20 * u; i++) if (bayer(cx + i, cy + j) < 0.45) g.set(cx - 10 * u + i, cy - 11 * u + j, col("#c9d1cb"));
  g.rect(cx - 10 * u, cy - 11 * u, 20 * u, u, "#ffffff");
  g.rect(cx - 10 * u, cy - 11 * u, u, 22 * u, "#ffffff");
  g.rect(cx + 9 * u, cy - 11 * u, u, 22 * u, "#8f9a93");
};
export const drawCardboard = (g: Gfx, cx: number, cy: number, u: number) => {
  g.rect(cx - 12 * u, cy - 8 * u, 24 * u, 16 * u, "#b07a44");
  g.rect(cx - 12 * u, cy - 8 * u, 24 * u, 2 * u, "#d9a66a");
  for (let k = 0; k < 4; k++) g.rect(cx - 9 * u, cy - 3 * u + k * 3 * u, 18 * u, u, "#86562e");
};
export const drawHose = (g: Gfx, cx: number, cy: number, u: number, t: number) => {
  for (let k = 0; k < 26; k++) {
    const a = k / 26;
    const x = cx - 18 * u + a * 36 * u;
    const y = cy + Math.sin(a * Math.PI * 1.5 + t * 0.05) * 7 * u;
    g.disc(x, y, 3 * u, k % 2 ? G[4] : G[5]);
  }
  g.rect(cx - 20 * u, cy - 3 * u, 4 * u, 6 * u, "#1f5585");
  g.rect(cx + 16 * u, cy - 3 * u, 4 * u, 6 * u, "#1f5585");
};
export const drawTapeRoll = (g: Gfx, cx: number, cy: number, r: number, t: number, strip = 0) => {
  g.disc(cx, cy, r, G[5]);
  g.ring(cx, cy, r, G[6], 2);
  for (let k = 0; k < 3; k++) g.ring(cx, cy, Math.round(r * (0.55 + k * 0.12)), G[4]);
  g.disc(cx, cy, Math.round(r * 0.45), "#3d2412");
  g.disc(cx, cy, Math.round(r * 0.35), "#020604");
  const a = t * 0.08;
  g.rect(cx + Math.cos(a) * r * 0.8 - 1, cy + Math.sin(a) * r * 0.8 - 1, 3, 3, "#ffffff");
  if (strip > 0) {
    g.rect(cx - 1, cy + r - 2, Math.round(strip), Math.max(3, Math.round(r * 0.5)), G[6]);
    g.rect(cx - 1, cy + r - 2, Math.round(strip), 1, G[7]);
  }
};

/** La « boîte aux lettres » : la cartouche emballée dans le carton, le sac et le scotch, avec le tuyau. */
export const drawMailbox = (g: Gfx, cx: number, cy: number, u: number, build: number, t: number) => {
  const step = (k: number) => build >= k;
  if (step(0)) drawCartridge(g, cx, cy, u, 0);
  if (step(1)) {
    for (let j = 0; j < 24 * u; j++)
      for (let i = 0; i < 26 * u; i++) if (bayer(i, j) < 0.35) g.set(cx - 13 * u + i, cy - 12 * u + j, col("#e6ebe7"));
  }
  if (step(2)) {
    g.rect(cx - 15 * u, cy + 8 * u, 30 * u, 6 * u, "#b07a44");
    g.rect(cx - 15 * u, cy + 8 * u, 30 * u, u, "#d9a66a");
  }
  if (step(3)) {
    for (let k = 0; k < 14; k++) g.disc(cx + 15 * u + k * 2 * u, cy + 11 * u + Math.sin(k * 0.6 + t * 0.06) * 3 * u, 2 * u, k % 2 ? G[4] : G[5]);
  }
  if (step(4)) {
    for (const [dx, dy, w, h] of [[-15, -2, 30, 3], [-15, 6, 30, 3], [-6, -12, 3, 26], [5, -12, 3, 26]])
      g.rect(cx + dx * u, cy + dy * u, w * u, h * u, G[6]);
    for (const [dx, dy] of [[-15, -2], [-15, 6]]) g.rect(cx + dx * u, cy + dy * u, 30 * u, u, G[7]);
  }
};

/* ───────── Jauge de gaz carbonique ───────── */
export const drawGauge = (g: Gfx, x: number, y: number, w: number, h: number, v: number) => {
  g.rect(x - 2, y - 2, w + 4, h + 4, G[5]);
  g.rect(x, y, w, h, "#020604");
  const fill = Math.round(h * Math.max(0, Math.min(1, v)));
  const c = v > 0.7 ? "#e8433a" : v > 0.4 ? "#ffc23d" : "#3dff8f";
  g.rect(x, y + h - fill, w, fill, c);
  for (let k = 1; k < 10; k++) g.rect(x + w - 4, y + (h * k) / 10, 4, 1, G[3]);
  g.rect(x - 6, y + h * 0.3, w + 12, 1, "#e8433a");
};

/* ───────── Capsule sous parachutes, océan, navire ───────── */
export const drawCapsuleChutes = (g: Gfx, cx: number, cy: number, u: number, t: number) => {
  const sway = Math.sin(t / 20) * 3;
  for (const [dx, dy] of [[-22, -60], [0, -68], [22, -60]]) {
    const px = cx + dx * u + sway;
    const py = cy + dy * u;
    for (let j = 0; j < 12 * u; j++) {
      const w = Math.round(Math.sqrt(Math.max(0, 1 - ((12 * u - j) / (12 * u)) ** 2)) * 14 * u);
      for (let i = -w; i <= w; i++) g.set(px + i, py + j, col(Math.floor((i + 40) / (4 * u)) % 2 ? "#e8433a" : "#f2f0e6"));
    }
    g.line(px - 14 * u, py + 12 * u, cx - 3 * u, cy - 6 * u, G[6]);
    g.line(px + 14 * u, py + 12 * u, cx + 3 * u, cy - 6 * u, G[6]);
  }
  for (let j = 0; j < 12; j++) g.rect(cx - (2 + j * 0.7) * u, cy - 6 * u + j * u, (4 + j * 1.4) * u, u, j < 2 ? G[6] : "#c9d1cb");
  g.rect(cx - 10 * u, cy + 6 * u, 20 * u, 2 * u, "#7a5414");
};
export const drawOcean = (g: Gfx, horizon: number, t: number) => {
  for (let y = horizon; y < 384; y++) {
    const d = (y - horizon) / (384 - horizon);
    for (let x = 0; x < 216; x++) {
      const band = Math.floor((y - horizon) / (2 + d * 6));
      const w = Math.sin(x / (10 + d * 14) + t * 0.06 + band * 2.3) + 0.5 * Math.sin(x / 31 - t * 0.04 + band);
      const c = w > 1.35 ? "#e9fff2" : w > 1.0 ? "#3fa7b5" : d > 0.55 ? "#06263d" : "#0d4a6b";
      g.set(x, y, col(c));
    }
  }
};
export const drawShip = (g: Gfx, x: number, y: number) => {
  g.rect(x, y, 46, 5, G[3]);
  g.rect(x + 4, y + 5, 38, 3, G[2]);
  g.rect(x + 28, y - 8, 8, 8, G[4]);
  g.rect(x + 31, y - 14, 2, 6, G[4]);
};
