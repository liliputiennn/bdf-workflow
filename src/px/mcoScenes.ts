import { explosion, P, particles, ptext, ptextWidth, smoke, space, speedLines } from "./common";
import { bayer, col, fbm, Gfx, H, hash, noise, W } from "./gfx";
import {
  drawApple,
  drawArchivist,
  drawBoard,
  drawBulb,
  drawDish,
  drawDoc,
  drawEarth,
  drawFactory,
  drawLander,
  drawMars,
  drawMonitor,
  drawPad,
  drawProbe,
  drawRadar,
  drawRocket,
  drawWeight,
} from "./objects";
import type { PxScene, SceneCtx } from "./Stage";

const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = (v: number) => 1 - Math.pow(1 - clamp(v), 3);
const easeIn = (v: number) => Math.pow(clamp(v), 3);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const prog = (t: number, a: number, b: number) => clamp((t - a) / Math.max(1, b - a));

/** Cadre de fenêtre pixel (bordure + barre de titre). */
const frame = (g: Gfx, x: number, y: number, w: number, h: number, hex = P.accent) => {
  g.rect(x - 2, y - 2, w + 4, h + 4, hex);
  g.rect(x, y, w, h, "#020604");
  g.rect(x - 2, y - 8, w + 4, 7, hex);
  for (let k = 0; k < 3; k++) g.rect(x + w - 6 - k * 6, y - 6, 3, 3, "#020604");
};

/** Vignette rouge pulsée (alerte). */
const redPulse = (g: Gfx, t: number, k: number) => {
  const p = (0.5 + 0.5 * Math.sin(t * 0.5)) * k;
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const d = Math.max(Math.abs(x - W / 2) / (W / 2), Math.abs(y - H / 2) / (H / 2));
      if (d > 0.7 && bayer(x, y) < (d - 0.7) * 3 * p) g.set(x, y, col("#8a231c"));
    }
};

/** Neige de télé (signal perdu). */
const staticNoise = (g: Gfx, f: number, k: number) => {
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) if (hash(x * 1.3 + y * 7.1 + f * 13.7) < k) g.set(x, y, col(hash(x + y + f) > 0.5 ? "#c9d1cb" : "#3f4a44"));
};

export const buildMcoScenes = (L: number[], end: number): PxScene[] => {
  const S = (name: string, a: number, b: number | null, draw: (g: Gfx, s: SceneCtx) => void, tin?: PxScene["tin"], tlen?: number): PxScene => ({
    name,
    from: a === 0 ? 0 : L[a],
    to: b === null ? end : L[b],
    draw,
    tin,
    tlen,
  });

  return [
    /* 1 · La sonde s'embrase au-dessus de Mars */
    S("hook", 0, 2, (g, { t, f, at }) => {
      const boom = at(1, 0.42);
      space(g, f, { dx: t * 0.8, dy: t * 0.2 });
      g.glow(30, 40, 50, "#ffc23d", 0.25);
      drawMars(g, 108, 560, 230, f * 0.004);
      const heat = clamp((t - at(1)) / (boom - at(1)));
      const px = 108 + Math.sin(t / 25) * 4 + heat * 10;
      const py = 205 + Math.cos(t / 30) * 3 + easeIn(heat) * 30;
      if (t < boom) {
        if (heat > 0)
          particles(g, t, { seed: 3, x: px - 20, y: py + 30, rate: 3 * heat, life: 22, vx: -0.6, vy: -1.6, spread: 0.6, ramp: ["#fff2b0", "#ffc23d", "#ff7a00", "#c24400", "#6e1d00"], size: 2, grow: 0.1 });
        drawProbe(g, px, py, 3, t, heat);
        if (heat > 0.5) g.glow(px, py + 30, 40, "#ff7a00", heat * 0.5);
      } else {
        explosion(g, t - boom, px, py, 11, 2.2);
        particles(g, t - boom, { seed: 77, x: px, y: py, rate: 6, life: 60, vx: 0, vy: -1.2, spread: Math.PI * 2, gravity: 0.03, ramp: ["#ffc23d", "#c9952a", "#7a5414", "#3f4a44", "#262f2a"], size: 2, stop: 4 });
      }
    }),

    /* 2 · « bug de génie ? » puis tableau noir */
    S("genius", 2, 4, (g, { t, f, at }) => {
      const cut = at(3);
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#0b1210", "#151b18"]);
      if (t < cut) {
        const flick = t > cut - 8 && Math.floor(t / 2) % 2 === 0 ? 0 : 1;
        drawBulb(g, 108, 200, t, flick * ease(t / 8));
        particles(g, t, { seed: 9, x: 108, y: 200, rate: 0.8, life: 30, vx: 0, vy: -0.8, spread: Math.PI * 2, ramp: ["#fff2b0", "#ffc23d", "#7a5414"], size: 1 });
      } else {
        const k = t - cut;
        // le tableau glisse en place
        const y = Math.round(lerp(-120, 150, ease(k / 10)));
        drawBoard(g, 20, y, 176, 96);
        const txt = "1 LBF = ? N";
        const shown = Math.min(txt.length, Math.floor(k / 3));
        ptext(g, txt.slice(0, shown), 108 - ptextWidth(txt, 3) / 2, y + 38, P.white, 3);
        const wx = 108 - ptextWidth(txt, 3) / 2 + ptextWidth(txt.slice(0, shown), 3);
        if (shown < txt.length) particles(g, k, { seed: 4, x: wx, y: y + 52, rate: 1.5, life: 14, vx: 0, vy: 0.6, spread: 1.2, ramp: ["#f2f0e6", "#8f9a93"], size: 1 });
        // règle et crayon
        g.rect(40, y + 120, 90, 7, "#ffd23d");
        for (let i = 0; i < 18; i++) g.rect(42 + i * 5, y + 120, 1, i % 2 ? 2 : 4, "#7a5414");
        g.rect(140, y + 118, 40, 5, "#ff7a00");
        g.rect(176, y + 118, 6, 5, "#f7d6b5");
        g.rect(180, y + 119, 3, 3, P.grey[2]);
        void f;
      }
    }, "pixelate", 12),

    /* 3 · Lancement en Floride, de nuit */
    S("launch", 4, 6, (g, { t, f, at }) => {
      const ign = at(5);
      const lift = easeIn(prog(t, ign + 8, at(5, 1) + 25));
      const climb = lift * 520;
      const cam = Math.max(0, climb - 120);
      space(g, f, { dy: -cam * 2, nebula: clamp(cam / 300) * 0.6, ramp: cam > 200 ? P.night : ["#05080c", "#0a1420", "#122436", "#1b3550", "#24496a"] });
      g.oy = cam;
      drawPad(g, 108, 330, t);
      const firing = t >= ign ? Math.min(1, (t - ign) / 6) : 0;
      if (firing > 0) smoke(g, t - ign, 108, 322, 21, 16);
      drawRocket(g, 108, 322 - climb, t, firing);
      g.oy = 0;
      if (lift > 0.35) speedLines(g, f, 3, "down", "#3f4a44", Math.round(lift * 30));
    }, "iris", 12),

    /* 4 · Objectif : le climat de Mars */
    S("mars", 6, 7, (g, { t, f }) => {
      space(g, f, { dx: t * 0.3 });
      const r = 74;
      drawMars(g, 108, 215, r, f * 0.012);
      // tempêtes de poussière qui défilent
      for (let k = 0; k < 4; k++) {
        const y = 170 + k * 22;
        const x0 = ((t * (0.8 + k * 0.2) + k * 60) % 220) - 40;
        for (let i = 0; i < 40; i++) {
          const x = x0 + i;
          if ((x - 108) ** 2 + (y - 215) ** 2 < r * r && bayer(x, y) < 0.35 * Math.sin((i / 40) * Math.PI)) g.set(x, y, col("#ffc29e"));
        }
      }
      // viseur qui se resserre
      const c = Math.round(lerp(100, 82, ease(t / 14)));
      for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        g.rect(108 + sx * c - (sx > 0 ? 12 : 0), 215 + sy * c, 13, 2, P.accent);
        g.rect(108 + sx * c - (sx > 0 ? 1 : 0), 215 + sy * c - (sy > 0 ? 12 : 0), 2, 13, P.accent);
      }
      const sy = 215 - r + ((t * 3) % (r * 2));
      g.rect(108 - r, sy, r * 2, 1, P.accent);
      g.dither(108 - r, sy - 6, r * 2, 6, P.green[3], 0.3);
    }, "dissolve", 10),

    /* 5 · 9 mois de transfert Terre → Mars */
    S("trip", 7, 8, (g, { t, f, d }) => {
      space(g, f, { nebula: 0.3 });
      const cx = 108;
      const cy = 215;
      g.glow(cx, cy, 22, "#ffc23d", 0.6);
      g.disc(cx, cy, 7, "#ffd23d");
      g.disc(cx - 2, cy - 2, 3, "#fff2b0");
      g.ring(cx, cy, 46, P.green[2]);
      g.ring(cx, cy, 84, P.mars[2]);
      const p = ease(t / Math.max(1, d - 6));
      const ae = -2.3 + p * 1.1;
      const am = -0.5 + p * 0.55;
      const ex = cx + Math.cos(ae) * 46;
      const ey = cy + Math.sin(ae) * 46;
      // arc de transfert (demi-ellipse) tracé progressivement
      const a0 = -2.3;
      for (let k = 0; k <= 60 * p; k++) {
        const a = a0 + (k / 60) * Math.PI;
        const rr = 46 + (84 - 46) * (k / 60);
        if (k % 3 !== 2) g.set(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, col(P.accent));
      }
      const a = a0 + p * Math.PI;
      const rr = 46 + 38 * p;
      g.glow(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 7, P.accent, 0.8);
      g.rect(cx + Math.cos(a) * rr - 1, cy + Math.sin(a) * rr - 1, 3, 3, P.white);
      drawEarth(g, Math.round(ex), Math.round(ey), 9, f * 0.05);
      drawMars(g, Math.round(cx + Math.cos(am + Math.PI) * 84), Math.round(cy + Math.sin(am + Math.PI) * 84), 8, f * 0.03, false);
    }, "wipe", 10),

    /* 6 · Deux équipes : Denver et la Californie */
    S("teams", 8, 11, (g, { t, f, at }) => {
      space(g, f, { nebula: 0.2 });
      const split = at(9);
      if (t < split) {
        drawEarth(g, 108, 215, 70, 1.2 + f * 0.006);
        for (const [x, y, k] of [[78, 186, 0], [62, 200, 8]]) {
          if (t < k) continue;
          const pr = ((t - k) * 1.2) % 22;
          g.ring(x, y, Math.round(pr), pr < 14 ? P.accent : P.green[2]);
          g.rect(x - 2, y - 2, 5, 5, Math.floor(t / 4) % 2 ? P.white : P.accent);
        }
        return;
      }
      const k = t - split;
      const off1 = Math.round(lerp(-240, 0, ease(k / 9)));
      g.ox = off1;
      frame(g, 16, 96, 184, 96);
      // Denver : montagnes + usine
      for (let x = 16; x < 200; x++) {
        const hgt = 30 + Math.round(fbm(x / 30, 2, 5, 2) * 30);
        for (let y = 192 - hgt; y < 192; y++) g.set(x, y, col(y < 192 - hgt + 4 ? "#c9d1cb" : "#262f2a"));
      }
      drawFactory(g, 74, 162, t);
      g.ox = 0;
      if (t >= at(10)) {
        const k2 = t - at(10);
        g.ox = Math.round(lerp(240, 0, ease(k2 / 9)));
        frame(g, 16, 222, 184, 96);
        for (let x = 16; x < 200; x++) g.rect(x, 300 + Math.round(Math.sin(x / 14) * 2), 1, 18, "#3d2412");
        drawDish(g, 92, 304, t);
        g.ox = 0;
      }
    }, "pixelate", 12),

    /* 7 · Petits coups de propulseur */
    S("thrusters", 11, 12, (g, { t, f }) => {
      space(g, f, { dx: t * 0.4 });
      const wob = Math.sin(t / 9) * 3;
      drawProbe(g, 108 + wob, 210, 3, t);
      const PUFF = [0, 16, 30, 42, 52, 60, 68];
      PUFF.forEach((p, i) => {
        const d = t - p;
        if (d < 0 || d > 16) return;
        const left = i % 2 === 0;
        const x = left ? 108 + wob + 6 : 108 + wob + 48;
        const y = 210 + 30;
        g.glow(x, y, 10, "#ffffff", 1 - d / 16);
        particles(g, d, { seed: i * 7, x, y, rate: 3, life: 14, vx: left ? -1.2 : 1.2, vy: 0.8, spread: 0.7, ramp: [P.white, P.grey[6], P.grey[5], P.grey[4]], size: 2, grow: 0.15, stop: 5 });
      });
      // flèche de rotation
      const a0 = t * 0.06;
      for (let k = 0; k < 36; k++) {
        const a = a0 + (k / 36) * Math.PI * 1.3;
        g.rect(108 + Math.cos(a) * 92, 210 + Math.sin(a) * 92, 2, 2, k > 30 ? P.white : P.green[3]);
      }
    }, "slide", 10),

    /* 8 · Le logiciel du constructeur */
    S("software", 12, 14, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#05080c", "#0b1210"]);
      g.rect(0, 300, W, 84, P.wood[1]);
      g.rect(0, 300, W, 3, P.wood[3]);
      drawMonitor(g, 26, 120, 164, 128, t);
      const lines = ["> SM_FORCES", "> POUSSEE...", "> IMPULSION", "> UNITE :"];
      const shown = Math.min(lines.length, Math.floor(t / 10) + 1);
      lines.slice(0, shown).forEach((l, i) => ptext(g, l.replace("_", "-"), 34, 130 + i * 14, P.accent, 2));
      const red = t >= at(13);
      if (red) {
        const k = t - at(13);
        ptext(g, "LBF.S", 34, 196, Math.floor(k / 3) % 2 && k < 18 ? P.white : P.alert, 5);
        if (k > 8) ptext(g, "IMPERIAL", 34, 228, P.mars[6], 2);
        g.glow(108, 210, 60, P.alert, 0.25);
      } else if (Math.floor(t / 8) % 2 === 0) g.rect(34 + 9 * 8, 130 + (shown - 1) * 14, 6, 10, P.accent);
      // clavier
      g.rect(40, 312, 136, 26, "#b8ad94");
      for (let j = 0; j < 3; j++) for (let i = 0; i < 12; i++) g.rect(44 + i * 11, 316 + j * 7, 9, 5, hash(i + j * 12 + Math.floor(t / 2)) > 0.9 && !red ? P.accent : "#d9cfb5");
    }, "pixelate", 10),

    /* 9 · Impérial contre métrique */
    S("duel", 14, 15, (g, { t, f, at }) => {
      const mid = 108;
      for (let y = 0; y < H; y++) {
        g.rect(0, y, mid, 1, y % 4 < 2 ? "#1a0605" : "#140403");
        g.rect(mid, y, mid, 1, y % 4 < 2 ? "#03140b" : "#020c08");
      }
      const k = t;
      const wy = Math.round(lerp(-60, 230, ease(k / 10))) + (k > 10 ? Math.round(Math.abs(Math.sin(k / 3)) * 4 * Math.max(0, 1 - (k - 10) / 20)) : 0);
      drawWeight(g, 54, wy, 2);
      ptext(g, "LBF", 54 - ptextWidth("LBF", 3) / 2, 270, P.alert, 3);
      if (t >= at(14, 0.35)) {
        const k2 = t - at(14, 0.35);
        const ay = Math.round(lerp(60, 200, easeIn(Math.min(1, k2 / 10))));
        drawApple(g, 162, ay, 2);
        ptext(g, "N", 162 - 4, 270, P.accent, 3);
      }
      // éclair central
      if (t >= at(14, 0.45)) {
        let x = mid;
        for (let y = 60; y < 330; y += 6) {
          const nx = mid + Math.round((hash(y + Math.floor(f / 2)) - 0.5) * 14);
          g.line(x, y, nx, y + 6, Math.floor(f / 2) % 2 ? P.white : "#ffc23d");
          x = nx;
        }
        g.glow(mid, 200, 30, "#ffffff", 0.3);
      }
    }, "slide", 8),

    /* 10 · 1 lbf = 4,45 N sur une balance */
    S("balance", 15, 16, (g, { t, d }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#04100a", "#071a10"]);
      const n = Math.min(5, Math.floor(t / Math.max(6, (d - 20) / 5)) + 1);
      const tilt = lerp(0.35, 0, Math.min(1, (n - 1) / 4 + (n >= 5 ? 0 : 0)));
      const cx = 108;
      const cy = 210;
      g.rect(cx - 3, cy, 6, 90, P.grey[5]);
      g.rect(cx - 30, cy + 90, 60, 6, P.grey[4]);
      const dx = Math.cos(tilt) * 80;
      const dy = Math.sin(tilt) * 80;
      g.line(cx - dx, cy + dy, cx + dx, cy - dy, P.grey[6]);
      g.line(cx - dx, cy + dy + 1, cx + dx, cy - dy + 1, P.grey[6]);
      g.disc(cx, cy, 4, "#ffd23d");
      const pans: [number, number][] = [[cx - dx, cy + dy], [cx + dx, cy - dy]];
      pans.forEach(([px, py]) => {
        g.line(px, py, px - 18, py + 40, P.grey[5]);
        g.line(px, py, px + 18, py + 40, P.grey[5]);
        g.rect(px - 22, py + 40, 44, 4, P.grey[6]);
      });
      drawWeight(g, Math.round(pans[0][0]), Math.round(pans[0][1] + 40), 1);
      for (let i = 0; i < n; i++) {
        const bx = Math.round(pans[1][0] - 18 + (i % 3) * 13);
        const by = Math.round(pans[1][1] + 40 - 10 - Math.floor(i / 3) * 11);
        g.rect(bx, by, 11, 10, i === 4 ? P.green[3] : P.green[4]);
        g.rect(bx, by, 11, 2, P.green[6]);
        ptext(g, "N", bx + 4, by + 3, P.ink);
      }
    }, "dissolve", 8),

    /* 11 · Poussée réelle contre poussée calculée */
    S("bars", 16, 17, (g, { t, f }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#04100a"]);
      const grow = ease(t / 22);
      const nozzle = (y: number, len: number, label: string, c: string) => {
        g.rect(14, y - 8, 22, 16, P.grey[4]);
        g.rect(36, y - 6, 6, 12, P.grey[3]);
        for (let j = 0; j < len; j++) {
          const w = Math.max(1, Math.round(7 * (1 - j / (len + 1)) * (0.85 + 0.3 * hash(j + f))));
          const dd = j / Math.max(1, len);
          const cc = dd < 0.2 ? "#ffffff" : dd < 0.45 ? "#fff2b0" : dd < 0.7 ? "#ffc23d" : "#ff7a00";
          for (let i = -w; i <= w; i++) if (bayer(42 + j, y + i) < 1 - Math.abs(i) / (w + 1) * 0.5) g.set(42 + j, y + i, col(cc));
        }
        ptext(g, label, 14, y + 16, c, 2);
      };
      nozzle(150, Math.round(150 * grow), "REELLE", P.accent);
      nozzle(250, Math.round((150 / 4.45) * grow), "CALCULEE", P.grey[5]);
    }, "wipe", 10),

    /* 12 · 10 à 14 fois plus souvent */
    S("many", 17, 18, (g, { t, f, d }) => {
      space(g, f, { dx: -t });
      drawProbe(g, 108, 190, 2, t);
      const n = Math.min(14, Math.floor((t / Math.max(1, d - 10)) * 14) + 1);
      for (let i = 0; i < n; i++) {
        const age = t - (i * (d - 10)) / 14;
        if (age >= 0 && age < 10) {
          const left = i % 2 === 0;
          particles(g, age, { seed: i * 13, x: left ? 70 : 146, y: 210, rate: 3, life: 12, vx: left ? -1.5 : 1.5, vy: 0.5, spread: 0.8, ramp: [P.white, P.grey[6], P.grey[4]], size: 2, stop: 4 });
        }
        const gx = 16 + (i % 7) * 27;
        const gy = 262 + Math.floor(i / 7) * 26;
        g.rect(gx, gy, 20, 20, P.green[1]);
        g.disc(gx + 10, gy + 10, 5, P.white);
        g.disc(gx + 8, gy + 8, 2, P.grey[5]);
      }
    }, "pixelate", 10),

    /* 13 · L'erreur s'accumule en silence */
    S("drift", 18, 19, (g, { t, f, d }) => {
      space(g, f, { nebula: 0.4 });
      drawMars(g, 160, 300, 42, f * 0.01);
      const p = ease(t / Math.max(1, d - 4));
      for (let k = 0; k <= 70 * p; k++) {
        const s = k / 70;
        const x = lerp(20, 150, s);
        const yPlan = lerp(70, 238, s * s);
        const yReal = lerp(70, 268, Math.pow(s, 1.6));
        if (k % 2 === 0) g.set(x, yPlan, col(P.grey[5]));
        g.rect(x, yReal, 2, 2, P.accent);
      }
      // jauge d'erreur
      g.rect(20, 96, 176, 8, "#2e0907");
      g.rect(20, 96, Math.round(176 * p), 8, P.alert);
      if (Math.floor(t / 6) % 2 === 0) ptext(g, "!", 200, 96, P.alert, 2);
    }, "dissolve", 10),

    /* 14 · Les navigateurs voient un écart */
    S("radar", 19, 20, (g, { t, f }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#04100a"]);
      drawRadar(g, 108, 215, 84, t);
      g.rect(140, 170, 4, 4, P.grey[6]);
      ptext(g, "PREVU", 132, 160, P.grey[6]);
      const on = Math.floor(f / 5) % 2 === 0;
      g.rect(126, 200, 5, 5, on ? P.accent : P.green[3]);
      g.glow(128, 202, 9, P.accent, 0.6);
      if (t > 14) {
        g.dashed(142, 174, 129, 201, P.alert, 2, 2, Math.floor(t / 2));
        ptext(g, "ECART", 150, 192, P.alert);
      }
    }, "iris", 10),

    /* 15 · Alerte hors procédure */
    S("mail", 20, 21, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#0b1210"]);
      // classeur « PROCÉDURE »
      g.rect(130, 150, 60, 110, "#1f3a8a");
      g.rect(130, 150, 8, 110, "#14275e");
      g.rect(142, 180, 42, 14, P.white);
      ptext(g, "PROC.", 146, 184, P.ink);
      const hit = at(20, 0.55);
      const k = t;
      let ex = lerp(-40, 110, ease(k / Math.max(1, hit)));
      let ey = 200 + Math.sin(k / 4) * 6;
      if (t > hit) {
        const b = t - hit;
        ex = 110 - b * 3;
        ey = 200 + b * b * 0.25 - b * 3;
      }
      g.rect(ex - 18, ey - 12, 36, 24, P.white);
      for (let i = 0; i < 18; i++) {
        g.set(ex - 18 + i, ey - 12 + Math.floor(i * 0.65), col(P.grey[5]));
        g.set(ex + 17 - i, ey - 12 + Math.floor(i * 0.65), col(P.grey[5]));
      }
      g.disc(ex + 16, ey - 12, 7, P.alert);
      ptext(g, "!", ex + 15, ey - 15, P.white);
      if (t > hit && t < hit + 10) g.glow(130, 205, 30, P.alert, 0.6);
    }, "slide", 8),

    /* 16 · TCM-5 : le bouton jamais pressé */
    S("tcm", 21, 23, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#151b18"]);
      g.rect(20, 150, 176, 150, P.grey[2]);
      g.rect(20, 150, 176, 4, P.grey[4]);
      for (let i = 0; i < 8; i++) g.rect(30 + i * 20, 162, 12, 6, hash(i + Math.floor(t / 7)) > 0.5 ? P.accent : P.green[1]);
      ptext(g, "TCM-5", 108 - ptextWidth("TCM-5", 3) / 2, 182, P.white, 3);
      const dead = t >= at(22);
      const blink = !dead && Math.floor(t / 6) % 2 === 0;
      g.disc(108, 245, 30, P.grey[1]);
      g.disc(108, 243, 24, dead ? "#3d0d0a" : blink ? "#ff5a4a" : P.alert);
      g.disc(100, 236, 6, dead ? "#561310" : "#ff8a6a");
      if (!dead) g.glow(108, 243, 40, P.alert, blink ? 0.5 : 0.25);
      // couvercle de sécurité qui se referme
      const lid = dead ? ease((t - at(22)) / 6) : 0;
      if (lid > 0) {
        const h = Math.round(56 * lid);
        g.dither(78, 215, 60, h, P.grey[6], 0.55);
        g.rect(78, 215 + h - 2, 60, 2, P.grey[7]);
      }
      ptext(g, dead ? "ANNULE" : "PRET", 108 - ptextWidth(dead ? "ANNULE" : "PRET", 2) / 2, 284, dead ? P.alert : P.accent, 2);
    }, "pixelate", 10),

    /* 17 · Arrivée : 80 km minimum, 57 km réels, puis le silence */
    S("arrival", 23, 28, (g, { t, f, at }) => {
      space(g, f, { dx: t * 0.2, nebula: 0.3 });
      const R = 190;
      const mcx = 108;
      const mcy = 300 + R;
      const altY = (km: number) => 300 - km * 1.05;
      const lowAt = at(25, 0.6);
      const lost = at(27);
      // trajectoire de la sonde
      const p1 = ease(prog(t, 0, lowAt));
      const p2 = prog(t, at(26), at(26, 0.9));
      const px = lerp(-10, 120, p1) + p2 * 130;
      const py = lerp(altY(170), altY(57), p1) + p2 * 70;
      const low = t >= lowAt;
      if (t < at(26, 0.9)) {
        if (low) particles(g, t, { seed: 8, x: px, y: py + 8, rate: 3, life: 18, vx: -1.4, vy: -0.4, spread: 0.5, ramp: ["#fff2b0", "#ffc23d", "#ff7a00", "#8a231c"], size: 2, grow: 0.1 });
        drawProbe(g, px, py, 1, t, low ? 0.8 : 0);
      }
      drawMars(g, mcx, mcy, R, f * 0.003);
      // règle d'altitude
      if (t >= at(24)) {
        g.rect(14, altY(140), 2, altY(0) - altY(140), P.grey[5]);
        for (let km = 0; km <= 140; km += 20) {
          g.rect(10, altY(km), 10, 1, P.grey[5]);
          ptext(g, String(km), 22, altY(km) - 2, P.grey[6]);
        }
        g.dashed(14, altY(80), 216, altY(80), P.alert, 4, 3, Math.floor(t / 2));
      }
      if (low && t < lost) redPulse(g, t, 1);
      if (t >= lost) {
        staticNoise(g, f, Math.min(0.5, (t - lost) / 40));
        const bars = Math.max(0, 4 - Math.floor((t - lost) / 5));
        for (let i = 0; i < 4; i++) g.rect(78 + i * 16, 190 - i * 10, 12, 20 + i * 10, i < bars ? P.accent : P.grey[2]);
      }
    }, "pixelate", 12),

    /* 18 · Le plus fou ? */
    S("question", 28, 29, (g, { t, f }) => {
      space(g, f, { dx: t * 2 });
      const Q = ["01110", "10001", "00001", "00010", "00100", "00000", "00100"];
      Q.forEach((row, j) =>
        [...row].forEach((b, i) => {
          if (b !== "1") return;
          const k = j * 5 + i;
          const delay = (hash(k) * 8) | 0;
          const p = ease((t - delay) / 6);
          const tx = 108 - 50 + i * 20;
          const ty = 140 + j * 20;
          const sx = tx + (hash(k * 3) - 0.5) * 300 * (1 - p);
          const sy = ty + (hash(k * 7) - 0.5) * 400 * (1 - p);
          g.rect(sx, sy, 18, 18, P.accent);
          g.rect(sx, sy, 18, 3, P.green[6]);
          g.rect(sx, sy + 15, 18, 3, P.green[3]);
        }),
      );
    }, "pixelate", 8),

    /* 19 · La spécification exigeait des newtons */
    S("spec", 29, 30, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#0b1210"]);
      drawDoc(g, 34, 100, 148, 220);
      ptext(g, "SPEC. INTERFACE", 44, 110, P.white);
      for (let i = 0; i < 12; i++) if (i !== 6) g.rect(44, 132 + i * 14, 70 + hash(i) * 50, 3, "#8f9a93");
      const hl = t >= at(29, 0.45);
      if (hl) g.rect(40, 214, 134, 16, P.accent);
      ptext(g, "UNITE : N.S", 46, 217, P.ink, 2);
      const p = ease(prog(t, 4, at(29, 0.45)));
      const mx = lerp(170, 100, p);
      const my = lerp(300, 222, p);
      g.ring(Math.round(mx), Math.round(my), 22, P.grey[3], 4);
      g.dither(mx - 18, my - 18, 36, 36, "#b6ffd3", 0.12);
      for (let k = 0; k < 18; k++) g.rect(mx + 16 + k, my + 16 + k, 5, 5, P.grey[2]);
    }, "wipe", 10),

    /* 20 · Mars Polar Lander disparaît à son tour */
    S("sister", 30, 31, (g, { t, f, at }) => {
      g.vgrad(0, 0, W, H, ["#2e0907", "#561310", "#8a231c", "#c0392b", "#e8573a"]);
      for (let x = 0; x < W; x++) {
        const hz = 290 + Math.round(fbm(x / 40, 1, 3, 2) * 20);
        for (let y = hz; y < H; y++) g.set(x, y, col(bayer(x, y) < 0.3 + (y - hz) / 200 ? "#561310" : "#8a231c"));
      }
      particles(g, t, { seed: 2, x: 230, y: 200, rate: 2, life: 120, vx: -1.8, vy: 0.1, spread: 0.3, ramp: ["#ffc29e", "#ff8a5c", "#e8573a"], size: 1, jitter: 300 });
      const gone = at(30, 0.86);
      const y = lerp(40, 230, ease(t / Math.max(1, gone)));
      if (t < gone) drawLander(g, 108 + Math.sin(t / 12) * 6, y, 2, t, 1);
      else {
        const k = t - gone;
        if (k < 14 && k % 3 !== 0) drawLander(g, 108 + (hash(f) - 0.5) * 20, y, 2, t, 1);
        staticNoise(g, f, Math.max(0, 0.35 - k / 40));
      }
    }, "dissolve", 10),

    /* 21 · Le bureau des archives : dossier classé */
    S("outro", 31, null, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#04100a", "#071a10"]);
      // étagères d'archives
      for (let s = 0; s < 4; s++) {
        const y = 100 + s * 60;
        g.rect(0, y + 44, W, 4, P.wood[2]);
        for (let i = 0; i < 22; i++) {
          const w = 7 + Math.floor(hash(i + s * 31) * 4);
          const x = i * 10 + (s % 2) * 4;
          const h = 30 + Math.floor(hash(i * 3 + s) * 12);
          g.rect(x, y + 44 - h, w, h, hash(i * 7 + s) > 0.8 ? P.green[1] : hash(i + s) > 0.5 ? "#4a3b25" : "#3a2e1d");
          g.rect(x + 1, y + 44 - h + 4, w - 2, 1, "#6b5638");
        }
      }
      g.glow(108, 250, 80, P.green[2], 0.5);
      drawArchivist(g, 108, 330, 4, t, t < at(31, 0.95));
    }, "iris", 12),
  ];
};

/* Points clés réutilisés par les effets et le son */
export const mcoKeys = (L: number[], at: (line: number, frac: number) => number) => ({
  boom: at(1, 0.42),
  ignition: L[5],
  genius: L[3],
  imperial: L[13],
  lightning: at(14, 0.45),
  hit: at(20, 0.55),
  never: L[22],
  low: at(25, 0.6),
  behind: at(26, 0.9),
  lost: L[27],
  lander: at(30, 0.86),
  classified: at(31, 0.64),
});
void noise;
