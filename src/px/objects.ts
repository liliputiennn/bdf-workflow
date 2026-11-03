import { P, particles, ptext } from "./common";
import { bayer, col, fbm, Gfx, hash, noise, pen } from "./gfx";

/* ───────── Mars Climate Orbiter (un seul panneau solaire, isolant doré) ───────── */
export const PROBE_W = 44;
export const PROBE_H = 26;
export const drawProbe = (g: Gfx, cx: number, cy: number, u: number, t: number, heat = 0) => {
  const x0 = Math.round(cx - (PROBE_W * u) / 2);
  const y0 = Math.round(cy - (PROBE_H * u) / 2);
  const r = pen(g, x0, y0, u);
  const G = P.grey;
  // panneau solaire
  r(0, 8, 20, 10, G[5]);
  r(0, 17, 20, 1, G[3]);
  for (let i = 0; i < 4; i++)
    for (let j = 0; j < 2; j++) {
      r(1 + i * 5, 9 + j * 4, 4, 3, P.green[2]);
      r(1 + i * 5, 9 + j * 4, 4, 1, P.green[3]);
    }
  const glint = Math.floor((t / 2) % 40);
  if (glint < 20) r(glint, 9 + (glint % 2) * 4, 1, 1, P.green[6]);
  // bras
  r(20, 12, 4, 2, G[5]);
  r(20, 14, 4, 1, G[3]);
  // bus doré
  r(24, 4, 14, 18, P.gold[2]);
  r(24, 4, 3, 18, P.gold[3]);
  r(35, 4, 3, 18, P.gold[1]);
  for (let j = 0; j < 18; j++)
    for (let i = 0; i < 14; i++) {
      const h = hash(i * 13 + j * 7);
      if (h > 0.86) r(24 + i, 4 + j, 1, 1, P.gold[4]);
      else if (h < 0.1) r(24 + i, 4 + j, 1, 1, P.gold[1]);
    }
  r(24, 21, 14, 1, P.gold[0]);
  r(24, 3, 14, 1, G[6]);
  // antenne grand gain
  r(28, 0, 6, 1, G[7]);
  r(26, 1, 10, 1, G[6]);
  r(27, 2, 8, 1, G[4]);
  r(30, 2, 2, 2, G[5]);
  // moteur
  r(28, 22, 6, 1, G[4]);
  r(27, 23, 8, 3, G[3]);
  r(27, 23, 2, 3, G[5]);
  r(24, 21, 1, 1, G[2]);
  r(37, 21, 1, 1, G[2]);
  // antenne fouet
  r(38, 10, 4, 1, G[5]);
  r(42, 6, 1, 9, G[6]);
  if (Math.floor(t / 12) % 2 === 0) r(42, 6, 1, 1, P.alert);
  if (heat > 0) {
    // échauffement : plasma tramé sur le bord d'attaque
    for (let j = 0; j < PROBE_H * u + 6 * u; j++)
      for (let i = 0; i < PROBE_W * u; i++) {
        const d = j / (PROBE_H * u + 6 * u);
        if (bayer(x0 + i, y0 + j) < heat * d * d * (0.6 + 0.4 * noise(i / 3, (j + t) / 3))) {
          g.set(x0 + i, y0 + j, col(d > 0.85 ? "#fff2b0" : d > 0.6 ? "#ffc23d" : "#ff7a00"));
        }
      }
  }
};

/* ───────── Lanceur Delta II ───────── */
export const drawRocket = (g: Gfx, cx: number, by: number, t: number, firing: number) => {
  // by = base des tuyères ; fusée ~92 px de haut
  const top = by - 92;
  const G = P.grey;
  const teal = ["#06263d", "#0d4a6b", "#1b7a8f", "#3fa7b5"];
  // coiffe
  const fairing = [2, 4, 6, 8, 10, 10, 10];
  for (let j = 0; j < 22; j++) {
    const w = fairing[Math.min(fairing.length - 1, j)];
    g.rect(cx - w / 2, top + j, w, 1, G[7]);
    g.rect(cx + w / 2 - 2, top + j, 2, 1, G[5]);
  }
  g.rect(cx - 5, top + 21, 10, 1, G[4]);
  // second étage
  g.rect(cx - 4, top + 22, 8, 12, G[6]);
  g.rect(cx + 2, top + 22, 2, 12, G[4]);
  g.rect(cx - 4, top + 27, 8, 2, G[2]);
  // premier étage bleu Delta
  g.rect(cx - 4, top + 34, 8, 54, teal[2]);
  g.rect(cx - 4, top + 34, 2, 54, teal[3]);
  g.rect(cx + 2, top + 34, 2, 54, teal[1]);
  for (let k = 0; k < 5; k++) g.rect(cx - 4, top + 40 + k * 10, 8, 1, teal[0]);
  ptext(g, "USA", cx - 1, top + 42, G[7]);
  // propulseurs d'appoint
  for (const s of [-1, 1]) {
    const bx = cx + s * 7 - 2;
    g.rect(bx, top + 58, 4, 30, G[7]);
    g.rect(bx + (s > 0 ? 2 : 0), top + 58, 2, 30, G[5]);
    g.rect(bx + 1, top + 55, 2, 3, G[7]);
    g.rect(bx + 1, top + 88, 2, 3, G[3]);
  }
  g.rect(cx - 2, top + 62, 4, 26, G[6]);
  g.rect(cx - 1, top + 59, 2, 3, G[6]);
  // tuyères
  g.rect(cx - 3, top + 88, 6, 4, G[2]);
  g.rect(cx - 2, top + 88, 1, 4, G[4]);
  if (firing > 0) {
    const fl = 0.7 + 0.3 * hash(Math.floor(t));
    const len = Math.round((22 + 18 * fl) * firing);
    for (let j = 0; j < len; j++) {
      const w = Math.max(1, Math.round((9 - j * 0.12) * firing * (0.9 + 0.2 * hash(j + t))));
      const d = j / len;
      const c = d < 0.25 ? "#ffffff" : d < 0.5 ? "#fff2b0" : d < 0.75 ? "#ffc23d" : "#ff7a00";
      for (let i = -w; i <= w; i++)
        if (bayer(cx + i, by + j) < 1 - d * 0.6 - Math.abs(i) / (w + 1) * 0.4) g.set(cx + i, by + j, col(c));
    }
    particles(g, t, {
      seed: 5,
      x: cx,
      y: by + len,
      rate: 4,
      life: 26,
      vx: 0,
      vy: 1.4,
      spread: 1.6,
      ramp: ["#fff2b0", "#ffc23d", "#ff7a00", "#c24400", "#5d6862", "#3f4a44"],
      size: 2,
      grow: 0.18,
      jitter: 6,
    });
  }
};

/* ───────── Pas de tir de nuit ───────── */
export const drawPad = (g: Gfx, cx: number, gy: number, t: number) => {
  const G = P.grey;
  // projecteurs (faisceaux tramés)
  for (const s of [-1, 1]) {
    for (let j = 0; j < 140; j++)
      for (let i = 0; i < j * 0.45; i++) {
        const x = cx + s * (50 - j * 0.25) - s * i;
        const y = gy - 10 - j;
        if (bayer(x, y) < 0.1 * (1 - j / 140)) g.set(x, y, col("#b6ffd3"));
      }
  }
  // tour ombilicale en treillis
  const tx = cx + 14;
  for (let y = gy - 100; y < gy; y++) {
    g.set(tx, y, col(G[4]));
    g.set(tx + 8, y, col(G[4]));
    if ((y - gy) % 8 === 0) g.rect(tx, y, 9, 1, G[4]);
    const k = ((y - gy) % 8 + 8) % 8;
    g.set(tx + k, y, col(G[3]));
  }
  g.rect(tx - 4, gy - 72, 4, 1, G[4]);
  g.rect(tx - 4, gy - 40, 4, 1, G[4]);
  if (Math.floor(t / 10) % 2 === 0) {
    g.rect(tx + 3, gy - 103, 3, 3, P.alert);
    g.glow(tx + 4, gy - 102, 6, P.alert, 0.5);
  }
  // sol
  g.rect(0, gy, 216, 60, "#0b1210");
  g.dither(0, gy, 216, 60, "#151b18", 0.5);
  g.rect(cx - 30, gy - 3, 60, 3, G[3]);
  g.rect(cx - 30, gy - 3, 60, 1, G[5]);
  for (let i = 0; i < 6; i++) g.rect(cx - 28 + i * 11, gy - 2, 2, 1, Math.floor(t / 6 + i) % 3 ? "#ffc23d" : G[2]);
};

/* ───────── Planètes ───────── */
export const drawMars = (g: Gfx, cx: number, cy: number, r: number, rot: number, atmos = true) => {
  if (atmos) g.glow(cx, cy, Math.round(r * 1.18), "#8a231c", 0.55);
  g.sphere(cx, cy, r, P.mars, {
    rot,
    rim: "#ff8a5c",
    tex: (lon, lat) => {
      const n = fbm(lon * 2.2 + 10, lat * 2.6 + 3, 2, 3) - 0.5;
      const crater = noise(lon * 9, lat * 9, 8) > 0.82 ? -0.5 : 0;
      const cap = lat < -1.25 ? 0.9 : 0;
      return n * 1.6 + crater + cap;
    },
  });
};

export const drawEarth = (g: Gfx, cx: number, cy: number, r: number, rot: number) => {
  g.glow(cx, cy, Math.round(r * 1.15), "#1b7a8f", 0.5);
  const ocean = ["#020c14", "#06263d", "#0d4a6b", "#1b7a8f", "#3fa7b5"];
  const land = ["#03140b", "#0a2a18", "#11472a", "#1f7a45", "#2fbf6a", "#8ff0b0"];
  g.sphere(cx, cy, r, ocean, { rot, rim: "#8ff0b0" });
  // continents et nuages en 2e passe
  for (let y = -r; y <= r; y++)
    for (let x = -r; x <= r; x++) {
      if (x * x + y * y > r * r) continue;
      const nx = x / r;
      const ny = y / r;
      const nz = Math.sqrt(1 - nx * nx - ny * ny);
      const lon = Math.atan2(nx, nz) + rot;
      const lat = Math.asin(ny);
      const l = Math.max(0, nx * -0.55 + ny * -0.45 + nz * 0.7);
      const h = fbm(lon * 1.6 + 4, lat * 2 + 1, 4, 3);
      const cl = fbm(lon * 2.5 + rot * 0.6, lat * 3.2, 9, 3);
      if (cl > 0.62 && bayer(cx + x, cy + y) < (cl - 0.6) * 5) g.set(cx + x, cy + y, col(l > 0.4 ? "#e9fff2" : "#8f9a93"));
      else if (h > 0.56) {
        const k = Math.min(land.length - 1, Math.floor(l * land.length));
        g.set(cx + x, cy + y, col(land[k]));
      }
    }
};

/* ───────── Usine (Lockheed Martin, Denver) ───────── */
export const drawFactory = (g: Gfx, x: number, y: number, t: number) => {
  const G = P.grey;
  particles(g, t, { seed: 31, x: x + 37, y: y - 22, rate: 0.5, life: 50, vx: 0.25, vy: -0.5, spread: 0.5, ramp: [G[6], G[5], G[4], G[3]], size: 3, grow: 0.08 });
  g.rect(x + 34, y - 22, 6, 22, G[3]);
  g.rect(x + 34, y - 22, 2, 22, G[4]);
  g.rect(x, y, 48, 26, G[4]);
  for (let k = 0; k < 4; k++) for (let s = 0; s < 8; s++) g.rect(x + k * 12 + s, y - s, 1, s + 1, s === 7 ? G[7] : G[5]);
  for (let i = 0; i < 6; i++) {
    const on = hash(i + Math.floor(t / 20)) > 0.3;
    g.rect(x + 3 + i * 7, y + 8, 4, 5, on ? "#ffc23d" : G[2]);
    g.rect(x + 3 + i * 7, y + 16, 4, 5, hash(i * 3 + Math.floor(t / 26)) > 0.4 ? "#ffc23d" : G[2]);
  }
  g.rect(x + 20, y + 18, 8, 8, G[1]);
};

/* ───────── Antenne Deep Space Network (JPL) ───────── */
export const drawDish = (g: Gfx, cx: number, by: number, t: number) => {
  const G = P.grey;
  for (let k = 0; k < 3; k++) {
    const r = ((t * 0.8 + k * 14) % 42) + 4;
    g.ring(cx + 6, by - 52, Math.round(r), r < 30 ? P.green[4] : P.green[2]);
  }
  g.rect(cx - 6, by - 6, 12, 6, G[3]);
  g.rect(cx - 3, by - 22, 6, 16, G[4]);
  g.rect(cx - 3, by - 22, 2, 16, G[5]);
  const rows = [26, 24, 21, 17, 12, 6];
  rows.forEach((w, j) => {
    g.rect(cx - w / 2 + 3, by - 40 + j * 3, w, 3, j === 0 ? G[7] : j < 3 ? G[6] : G[5]);
  });
  g.line(cx - 8, by - 40, cx + 6, by - 52, G[5]);
  g.line(cx + 16, by - 40, cx + 6, by - 52, G[5]);
  g.rect(cx + 5, by - 54, 3, 3, Math.floor(t / 8) % 2 ? P.accent : G[6]);
};

/* ───────── Écran CRT rétro ───────── */
export const drawMonitor = (g: Gfx, x: number, y: number, w: number, h: number, t: number) => {
  const G = P.grey;
  g.rect(x - 8, y - 8, w + 16, h + 22, "#b8ad94");
  g.rect(x - 8, y - 8, w + 16, 2, "#d9cfb5");
  g.rect(x - 8, y + h + 12, w + 16, 2, "#8a8170");
  g.rect(x - 2, y - 2, w + 4, h + 4, G[1]);
  g.rect(x, y, w, h, "#031208");
  for (let j = 0; j < h; j += 2) g.rect(x, y + j, w, 1, "#05190c");
  const roll = Math.floor((t * 2) % (h + 20)) - 10;
  g.dither(x, y + roll, w, 6, "#0a2a18", 0.5);
  g.rect(x + w - 12, y + h + 4, 6, 3, Math.floor(t / 15) % 2 ? P.accent : G[3]);
  g.rect(x + w / 2 - 14, y + h + 14, 28, 6, "#8a8170");
  g.rect(x + w / 2 - 22, y + h + 20, 44, 3, "#6b6457");
};

/* ───────── Ampoule (idée de génie) ───────── */
export const drawBulb = (g: Gfx, cx: number, cy: number, t: number, on: number) => {
  if (on > 0) {
    g.glow(cx, cy, 46, "#ffc23d", 0.45 * on);
    for (let k = 0; k < 10; k++) {
      const a = (k / 10) * Math.PI * 2 + t * 0.03;
      const r0 = 26 + (Math.floor(t / 3) % 2) * 2;
      g.line(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0, cx + Math.cos(a) * (r0 + 8), cy + Math.sin(a) * (r0 + 8), "#ffc23d");
    }
  }
  g.sphere(cx, cy, 16, on > 0 ? ["#7a5414", "#c9952a", "#ffd23d", "#fff2b0", "#ffffff"] : P.grey.slice(2, 7), { rim: "#ffffff" });
  g.rect(cx - 4, cy - 2, 1, 8, on ? "#ffffff" : P.grey[3]);
  g.rect(cx + 3, cy - 2, 1, 8, on ? "#ffffff" : P.grey[3]);
  g.rect(cx - 4, cy - 2, 8, 1, on ? "#ffffff" : P.grey[3]);
  g.rect(cx - 7, cy + 15, 14, 4, P.grey[5]);
  g.rect(cx - 7, cy + 19, 14, 2, P.grey[3]);
  g.rect(cx - 7, cy + 21, 14, 3, P.grey[5]);
  g.rect(cx - 4, cy + 24, 8, 3, P.grey[2]);
};

/* ───────── Tableau noir de collège ───────── */
export const drawBoard = (g: Gfx, x: number, y: number, w: number, h: number) => {
  g.rect(x - 5, y - 5, w + 10, h + 10, P.wood[2]);
  g.rect(x - 5, y - 5, w + 10, 2, P.wood[4]);
  g.rect(x - 5, y + h + 3, w + 10, 2, P.wood[1]);
  g.rect(x, y, w, h, "#0f3320");
  g.dither(x, y, w, h, "#11472a", 0.18);
  g.rect(x + 6, y + h + 5, 12, 3, P.white);
  g.rect(x + 22, y + h + 5, 10, 3, "#3d2412");
};

/* ───────── Poids impérial et pomme de Newton ───────── */
export const drawWeight = (g: Gfx, cx: number, by: number, s = 1) => {
  const G = P.grey;
  g.ring(cx, by - 26 * s, 6 * s, G[4], 3 * s);
  g.rect(cx - 13 * s, by - 20 * s, 26 * s, 20 * s, G[3]);
  g.rect(cx - 13 * s, by - 20 * s, 26 * s, 3 * s, G[5]);
  g.rect(cx - 15 * s, by - 3 * s, 30 * s, 3 * s, G[2]);
  ptext(g, "LB", cx - 4 * s, by - 13 * s, P.alert, s * 2);
};
export const drawApple = (g: Gfx, cx: number, cy: number, s = 1) => {
  g.sphere(cx, cy, 9 * s, ["#3d0d0a", "#8a231c", "#c0392b", "#e8573a", "#ff8a5c"], { rim: "#ffc29e" });
  g.rect(cx, cy - 12 * s, 2 * s, 5 * s, P.wood[2]);
  g.rect(cx + 2 * s, cy - 12 * s, 6 * s, 3 * s, P.green[4]);
};

/* ───────── Atterrisseur Mars Polar Lander ───────── */
export const drawLander = (g: Gfx, cx: number, cy: number, u: number, t: number, chute = 0) => {
  const r = pen(g, Math.round(cx - 12 * u), Math.round(cy - 8 * u), u);
  const G = P.grey;
  if (chute > 0) {
    const cw = 30;
    for (let j = 0; j < 9; j++) r(12 - (cw - j * 2) / 2, -30 + j, cw - j * 2 > 0 ? cw - j * 2 : 1, 1, j % 3 === 0 ? P.white : "#e8573a");
    r(-3, -22, 30, 1, P.white);
    g.line(cx - 15 * u, cy - 22 * u, cx - 6 * u, cy - 8 * u, G[5]);
    g.line(cx + 15 * u, cy - 22 * u, cx + 6 * u, cy - 8 * u, G[5]);
  }
  r(10, 0, 4, 2, G[5]);
  r(6, 2, 12, 2, G[6]);
  r(4, 4, 16, 6, "#c9952a");
  r(4, 4, 4, 6, "#ffd23d");
  r(0, 5, 4, 3, P.green[3]);
  r(20, 5, 4, 3, P.green[3]);
  r(5, 10, 2, 5, G[5]);
  r(17, 10, 2, 5, G[5]);
  r(11, 10, 2, 5, G[5]);
  r(3, 15, 5, 1, G[4]);
  r(16, 15, 5, 1, G[4]);
  r(9, 15, 6, 1, G[4]);
  if (Math.floor(t / 10) % 2 === 0) r(11, 0, 1, 1, P.alert);
};

/* ───────── La mascotte : l'archiviste ───────── */
export const drawArchivist = (g: Gfx, cx: number, by: number, u: number, t: number, talking = false) => {
  const r = pen(g, Math.round(cx - 15 * u), Math.round(by - 40 * u), u);
  const G = P.grey;
  const S = P.skin;
  const blink = t % 70 < 4;
  const mouth = talking && Math.floor(t / 3) % 2 === 0;
  const bob = Math.floor(t / 16) % 2;
  // corps (gilet vert, chemise, cravate)
  r(4, 26, 22, 14, P.green[1]);
  r(4, 26, 3, 14, P.green[2]);
  r(12, 26, 6, 9, G[7]);
  r(14, 27, 2, 10, P.accent);
  r(11, 26, 1, 8, P.green[3]);
  r(18, 26, 1, 8, P.green[3]);
  // tête
  r(9, 9 + bob, 12, 14, S[3]);
  r(9, 9 + bob, 2, 14, S[4]);
  r(19, 9 + bob, 2, 14, S[2]);
  r(8, 13 + bob, 1, 6, G[5]);
  r(21, 13 + bob, 1, 6, G[5]);
  r(13, 23, 4, 3, S[2]);
  // visière verte
  r(8, 6 + bob, 14, 3, P.green[4]);
  r(8, 6 + bob, 14, 1, P.green[5]);
  r(5, 9 + bob, 20, 2, P.green[3]);
  r(5, 10 + bob, 20, 1, P.green[2]);
  g.dither(cx - 9 * u, by - 29 * u + bob * u, 18 * u, 3 * u, P.green[2], 0.5);
  // lunettes rondes
  r(10, 14 + bob, 4, 4, P.ink);
  r(16, 14 + bob, 4, 4, P.ink);
  r(14, 15 + bob, 2, 1, P.ink);
  r(11, 15 + bob, 2, 2, blink ? S[2] : P.white);
  r(17, 15 + bob, 2, 2, blink ? S[2] : P.white);
  if (!blink) {
    r(12, 16 + bob, 1, 1, P.ink);
    r(18, 16 + bob, 1, 1, P.ink);
  }
  // moustache et bouche
  r(12, 19 + bob, 6, 1, G[5]);
  r(13, 21 + bob, 4, mouth ? 2 : 1, mouth ? "#3d0d0a" : S[1]);
  // dossier sous le bras
  r(16, 30, 13, 9, "#c9a86a");
  r(16, 29, 5, 1, "#c9a86a");
  r(18, 33, 8, 1, G[2]);
  r(18, 35, 6, 1, G[2]);
  r(14, 31, 4, 4, P.green[1]);
};

/* ───────── Radar ───────── */
export const drawRadar = (g: Gfx, cx: number, cy: number, r: number, t: number) => {
  g.disc(cx, cy, r, "#03140b");
  for (let k = 1; k <= 3; k++) g.ring(cx, cy, Math.round((r * k) / 3), P.green[2]);
  g.rect(cx - r, cy, r * 2, 1, P.green[2]);
  g.rect(cx, cy - r, 1, r * 2, P.green[2]);
  const a = t * 0.09;
  for (let k = 0; k < 24; k++) {
    const aa = a - k * 0.035;
    const dens = 1 - k / 24;
    for (let s = 0; s < r; s++) {
      const x = cx + Math.cos(aa) * s;
      const y = cy + Math.sin(aa) * s;
      if (bayer(Math.round(x), Math.round(y)) < dens * 0.8) g.set(x, y, col(k === 0 ? P.green[6] : P.green[3]));
    }
  }
};

/* ───────── Feuille de spécification ───────── */
export const drawDoc = (g: Gfx, x: number, y: number, w: number, h: number) => {
  g.rect(x + 4, y + 4, w, h, "#020604");
  g.rect(x, y, w, h, "#e9e4d4");
  g.rect(x, y, w, 2, "#ffffff");
  g.rect(x + w - 10, y, 10, 10, "#c9c2ae");
  g.rect(x + 6, y + 8, w - 20, 9, P.ink);
};
