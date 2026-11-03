import { explosion, P, particles, ptext, ptextWidth, smoke, space, speedLines } from "./common";
import { bayer, col, Gfx, H, hash, W } from "./gfx";
import { drawArchivist, drawEarth } from "./objects";
import {
  drawAstronaut,
  drawBag,
  drawCapsuleChutes,
  drawCardboard,
  drawCartridge,
  drawCrewBust,
  drawGauge,
  drawHose,
  drawLM,
  drawMailbox,
  drawMissionControl,
  drawMoon,
  drawOcean,
  drawSaturnV,
  drawShip,
  drawSocket,
  drawStack,
  drawTapeRoll,
} from "./apolloObjects";
import type { PxScene, SceneCtx } from "./Stage";

const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = (v: number) => 1 - Math.pow(1 - clamp(v), 3);
const easeIn = (v: number) => Math.pow(clamp(v), 3);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const prog = (t: number, a: number, b: number) => clamp((t - a) / Math.max(1, b - a));
const SKIN = ["#e8b48a", "#d9a77c", "#f2cfa8"];

/** Vignette rouge pulsée (alerte). */
const redPulse = (g: Gfx, t: number, k: number) => {
  const p = (0.5 + 0.5 * Math.sin(t * 0.5)) * k;
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const d = Math.max(Math.abs(x - W / 2) / (W / 2), Math.abs(y - H / 2) / (H / 2));
      if (d > 0.7 && bayer(x, y) < (d - 0.7) * 3 * p) g.set(x, y, col("#8a231c"));
    }
};

/** Gaz carbonique : nuage tramé qui épaissit. */
const co2Cloud = (g: Gfx, t: number, density: number, x0 = 0, y0 = 100, w = W, h = 230) => {
  for (let y = y0; y < y0 + h; y++)
    for (let x = x0; x < x0 + w; x++) {
      const n = 0.5 + 0.5 * Math.sin(x / 13 + t * 0.05) * Math.cos(y / 17 - t * 0.04);
      if (bayer(x, y) < density * n * 0.55) g.set(x, y, col(n > 0.75 ? "#5d6a3a" : "#3a4426"));
    }
};

/** Ondes radio entre deux points. */
const radio = (g: Gfx, t: number, x0: number, y0: number, x1: number, y1: number) => {
  for (let k = 0; k < 4; k++) {
    const p = ((t * 0.02 + k / 4) % 1);
    const x = lerp(x0, x1, p);
    const y = lerp(y0, y1, p);
    g.ring(Math.round(x), Math.round(y), 3 + Math.round(p * 6), p < 0.85 ? P.accent : P.green[2]);
  }
  g.dashed(x0, y0, x1, y1, P.green[2], 2, 4, Math.floor(t / 2));
};

export const buildApolloScenes = (L: number[], end: number): PxScene[] => {
  const S = (name: string, a: number, b: number | null, draw: (g: Gfx, s: SceneCtx) => void, tin?: PxScene["tin"], tlen?: number): PxScene => ({
    name,
    from: a === 0 ? 0 : L[a],
    to: b === null ? end : L[b],
    draw,
    tin,
    tlen,
  });

  return [
    /* 1 · Le vaisseau blessé perd son oxygène… puis le scotch arrive */
    S("hook", 0, 2, (g, { t, f, at }) => {
      space(g, f, { dx: t * 0.6, dy: t * 0.15 });
      drawEarth(g, 30, 330, 24, f * 0.01);
      drawMoon(g, 188, 92, 20, f * 0.004);
      const tape = at(1, 0.4);
      if (t < tape) {
        drawStack(g, 108 + Math.sin(t / 30) * 3, 208, 3, t, 1);
        redPulse(g, t, 0.9);
      } else {
        const k = t - tape;
        drawStack(g, 108, 208, 3, t, 1);
        const x = lerp(-60, 108, ease(k / 10));
        drawTapeRoll(g, Math.round(x), 210, 34, t, k > 8 ? Math.min(90, (k - 8) * 9) : 0);
      }
    }),

    /* 2 · Décollage de la Saturn V */
    S("launch", 2, 3, (g, { t, f }) => {
      const lift = easeIn(prog(t, 8, 90));
      const climb = lift * 420;
      g.vgrad(0, 0, W, H, climb > 200 ? ["#020604", "#04100a", "#0a1f3a"] : ["#0a1f3a", "#14365e", "#1f5585", "#3b7bb0", "#7fb0d6"]);
      if (climb > 150) space(g, f, { dy: -climb, nebula: 0.2 });
      g.oy = Math.max(0, climb - 100);
      g.rect(0, 336, W, 48, "#1f3a1a");
      g.dither(0, 336, W, 48, "#2f5a26", 0.4);
      g.rect(130, 190, 8, 146, P.grey[3]);
      for (let y = 190; y < 336; y += 8) g.rect(130, y, 8, 1, P.grey[5]);
      if (t > 2) smoke(g, t, 108, 330, 41, 18);
      drawSaturnV(g, 108, 330 - climb, t, Math.min(1, t / 6));
      g.oy = 0;
      if (lift > 0.3) speedLines(g, f, 9, "down", "#3f4a44", Math.round(lift * 26));
    }, "iris", 12),

    /* 3 · L'équipage */
    S("crew", 3, 4, (g, { t, f, at }) => {
      space(g, f, { nebula: 0.4 });
      const crew: [number, string, string, number][] = [
        [42, "#3d2412", SKIN[0], at(3, 0.25)],
        [108, "#c9952a", SKIN[1], at(3, 0.5)],
        [174, "#5e3a1e", SKIN[2], at(3, 0.75)],
      ];
      crew.forEach(([x, hair, skin, a]) => {
        if (t < a - 6) return;
        const y = Math.round(lerp(380, 250, ease((t - a + 6) / 10)));
        drawCrewBust(g, x, y, 3, t, hair, skin);
      });
    }, "dissolve", 10),

    /* 4 · En route vers la Lune, tout va bien */
    S("cruise", 4, 6, (g, { t, f, d }) => {
      space(g, f, { dx: t * 1.2, nebula: 0.4 });
      const p = t / Math.max(1, d);
      drawEarth(g, Math.round(lerp(40, -10, p)), 300, Math.round(lerp(34, 18, p)), f * 0.01);
      drawMoon(g, Math.round(lerp(230, 180, p)), 120, Math.round(lerp(10, 22, p)), f * 0.004);
      drawStack(g, 108, 215 + Math.round(Math.sin(t / 25) * 3), 3, t, 0);
      for (let k = 0; k < 3; k++) g.rect(20, 236 + k * 6 - ((t * 2) % 6), 30, 1, P.grey[3]);
    }, "wipe", 10),

    /* 5 · BANG : le réservoir d'oxygène explose */
    S("bang", 6, 8, (g, { t, f, at }) => {
      const boom = at(6, 0.62);
      space(g, f, { dx: t * 0.4 });
      drawMoon(g, 190, 110, 16, f * 0.004);
      const hit = t >= boom;
      const shake = hit && t < boom + 10 ? Math.round((hash(f) - 0.5) * 8) : 0;
      drawStack(g, 108 + shake, 220, 3, t, hit ? 1 : 0);
      if (hit) {
        explosion(g, t - boom, 108 - 30, 205, 33, 1.6);
        particles(g, t - boom, { seed: 92, x: 80, y: 205, rate: 5, life: 70, vx: 0, vy: -1.4, spread: Math.PI * 2, gravity: 0, ramp: [P.grey[7], P.grey[6], P.grey[5], P.grey[4], P.grey[3]], size: 2, stop: 6 });
        if (t > at(7)) redPulse(g, t, 0.7);
      }
    }, "pixelate", 10),

    /* 6 · « Houston, on a eu un problème » */
    S("houston", 8, 9, (g, { t, f }) => {
      space(g, f, { nebula: 0.3 });
      drawStack(g, 150, 120, 2, t, 1);
      drawEarth(g, 50, 330, 34, f * 0.01);
      radio(g, t, 140, 130, 62, 300);
      // oscilloscope de la voix radio
      g.rect(20, 200, 176, 60, "#031208");
      g.rect(20, 200, 176, 2, P.green[2]);
      for (let x = 0; x < 172; x++) {
        const a = Math.sin(x * 0.3 + t * 0.6) * Math.sin(x * 0.05 + t * 0.1) * 22 * (0.4 + 0.6 * hash(Math.floor(t / 3)));
        g.set(22 + x, 230 + Math.round(a), col(P.accent));
      }
    }, "slide", 8),

    /* 7 · Le vaisseau s'éteint */
    S("power", 9, 10, (g, { t, d }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#151b18"]);
      g.rect(14, 110, 188, 120, P.grey[2]);
      g.rect(14, 110, 188, 3, P.grey[4]);
      const off = Math.floor((t / Math.max(1, d - 10)) * 40);
      for (let j = 0; j < 5; j++)
        for (let i = 0; i < 8; i++) {
          const k = j * 8 + i;
          const on = k >= off && hash(k + Math.floor(t / 5)) > 0.1;
          g.rect(26 + i * 22, 122 + j * 20, 10, 8, on ? (k % 3 ? P.accent : "#ffc23d") : "#0b1210");
        }
      const p = clamp(t / Math.max(1, d - 6));
      ptext(g, "O2", 20, 252, P.white, 2);
      g.rect(48, 252, 150, 10, "#0b1210");
      g.rect(48, 252, Math.round(150 * (1 - p)), 10, p > 0.7 ? P.alert : P.accent);
      ptext(g, "ELEC", 20, 274, P.white, 2);
      g.rect(56, 274, 142, 10, "#0b1210");
      g.rect(56, 274, Math.round(142 * (1 - p * 0.95)), 10, p > 0.6 ? P.alert : "#ffc23d");
      if (p > 0.6) redPulse(g, t, 0.6);
    }, "pixelate", 10),

    /* 8 · Le canot de sauvetage : trois dans un module prévu pour deux */
    S("lifeboat", 10, 12, (g, { t, f, at }) => {
      space(g, f, { nebula: 0.3 });
      const inside = t >= at(11);
      if (!inside) {
        drawLM(g, 140, 200, 4, t);
        for (let k = 0; k < 3; k++) {
          const p = ease(prog(t, k * 10, k * 10 + 40));
          drawAstronaut(g, Math.round(lerp(-20, 120 + k * 4, p)), Math.round(lerp(300, 190, p)), 2, t, k * 20);
        }
        return;
      }
      // coupe de la cabine : trois astronautes serrés
      g.rect(28, 120, 160, 160, P.grey[3]);
      g.rect(34, 126, 148, 148, "#0b1210");
      g.rect(34, 126, 148, 3, P.grey[4]);
      g.rect(80, 140, 56, 20, "#031208");
      for (let k = 0; k < 6; k++) g.rect(84 + k * 9, 146, 5, 3, hash(k + Math.floor(t / 7)) > 0.4 ? P.accent : "#11472a");
      [56, 108, 160].forEach((x, k) => drawAstronaut(g, x + (k === 1 ? Math.round(Math.sin(t / 6) * 2) : 0), 268, 3, t, k * 30));
      for (const x of [56, 160]) g.rect(x - 16, 270, 32, 4, P.accent);
      g.rect(92, 270, 32, 4, P.alert);
    }, "dissolve", 10),

    /* 9 · Chaque souffle rejette un gaz invisible… qui devient mortel */
    S("breath", 12, 14, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#0b1210", "#151b18"]);
      const lvl = clamp(prog(t, 0, at(13, 0.8)) * 0.9);
      co2Cloud(g, t, lvl * 1.6);
      drawAstronaut(g, 90, 300, 7, t);
      for (let k = 0; k < 3; k++) {
        const b = (t - k * 25) % 75;
        if (b > 0 && b < 30) particles(g, b, { seed: k * 9 + Math.floor((t - k * 25) / 75), x: 108, y: 160, rate: 2, life: 30, vx: 1.1, vy: -0.4, spread: 0.8, ramp: ["#8f9a93", "#5d6a3a", "#3a4426"], size: 2, grow: 0.15, stop: 10 });
      }
      drawGauge(g, 176, 110, 20, 180, lvl);
      ptext(g, "CO2", 174, 296, lvl > 0.7 ? P.alert : P.white, 2);
      if (t >= at(13, 0.6)) redPulse(g, t, 1);
    }, "slide", 8),

    /* 10 · Les filtres, trop petits pour trois */
    S("filters", 14, 16, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#0b1210", "#151b18"]);
      const sat = clamp(prog(t, at(15), at(15, 0.8)));
      co2Cloud(g, t, 0.4 + sat * 0.8);
      particles(g, t, { seed: 5, x: 108, y: 120, rate: 2, life: 40, vx: 0, vy: 1.6, spread: 2.4, ramp: ["#5d6a3a", "#3a4426"], size: 2, jitter: 120 });
      drawCartridge(g, 108, 215, 4, sat);
      if (sat > 0.6) ptext(g, "PLEIN", 108 - ptextWidth("PLEIN", 3) / 2, 270, P.alert, 3);
    }, "dissolve", 8),

    /* 11 · Les filtres de rechange ne rentrent pas */
    S("mismatch", 16, 18, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#151b18"]);
      drawSocket(g, 150, 220, 2);
      const a = at(17, 0.2);
      let x = lerp(-30, 60, ease(t / 20));
      if (t > a) {
        const k = (t - a) % 24;
        x = 92 - Math.abs(Math.sin((k / 24) * Math.PI)) * 30;
      }
      drawCartridge(g, Math.round(x), 220, 2, 0);
      if (t > at(17, 0.35)) {
        for (let k = -10; k <= 10; k++) {
          g.rect(150 + k * 2, 220 + k * 2, 4, 4, P.alert);
          g.rect(150 + k * 2, 220 - k * 2, 4, 4, P.alert);
        }
      }
    }, "wipe", 10),

    /* 12 · Houston : une idée folle */
    S("idea", 18, 20, (g, { t, at }) => {
      drawMissionControl(g, t);
      if (t > at(18, 0.6)) {
        g.glow(108, 236, 40, "#ffc23d", 0.5);
        g.disc(108, 236, 8, "#fff2b0");
      }
    }, "iris", 12),

    /* 13 · Le sac, le carton, le tuyau… et le scotch */
    S("items", 20, 22, (g, { t, f, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#151b18"]);
      g.rect(0, 300, W, 84, P.wood[1]);
      g.rect(0, 300, W, 3, P.wood[3]);
      const pop = (a: number) => ease((t - a) / 8);
      const a1 = at(20, 0.05);
      const a2 = at(20, 0.4);
      const a3 = at(20, 0.7);
      if (t >= a1) drawBag(g, 50, Math.round(lerp(-40, 150, pop(a1))), 2);
      if (t >= a2) drawCardboard(g, 160, Math.round(lerp(-40, 150, pop(a2))), 2);
      if (t >= a3) drawHose(g, 108, Math.round(lerp(-40, 230, pop(a3))), 2, t);
      if (t >= L[21] - L[20]) {
        const k = t - (L[21] - L[20]);
        drawTapeRoll(g, Math.round(lerp(260, 108, ease(k / 12))), 300, 30, f, k > 10 ? Math.min(100, (k - 10) * 6) : 0);
      }
    }, "slide", 8),

    /* 14 · Le mode d'emploi par radio, puis le bricolage */
    S("build", 22, 24, (g, { t, f, at }) => {
      space(g, f, { nebula: 0.2 });
      if (t < at(23)) {
        drawEarth(g, 40, 120, 26, f * 0.01);
        drawStack(g, 168, 100, 1, t, 1);
        radio(g, t, 50, 110, 160, 100);
        g.rect(20, 190, 176, 120, "#031208");
        g.rect(20, 190, 176, 3, P.green[2]);
        const steps = ["1 SAC", "2 CARTON", "3 TUYAU", "4 SCOTCH"];
        const n = Math.min(steps.length, Math.floor(t / 14) + 1);
        steps.slice(0, n).forEach((s, i) => ptext(g, s, 30, 202 + i * 24, P.accent, 3));
        return;
      }
      const k = t - at(23);
      const build = Math.min(4, Math.floor(k / 12));
      drawMailbox(g, 108, 220, 3, build, t);
      drawAstronaut(g, 36, 320, 3, t, 0);
      drawAstronaut(g, 180, 320, 3, t, 40);
    }, "pixelate", 10),

    /* 15 · On branche : le gaz baisse. Ça marche. */
    S("plug", 24, 26, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#0b1210", "#151b18"]);
      const drop = clamp(prog(t, at(24, 0.55), L[25] - L[24] + 30));
      const lvl = lerp(0.85, 0.2, drop);
      co2Cloud(g, t, lvl * 1.4);
      drawMailbox(g, 80, 220, 3, 4, t);
      drawGauge(g, 176, 110, 20, 180, lvl);
      ptext(g, "CO2", 174, 296, lvl > 0.7 ? P.alert : P.accent, 2);
      if (t >= L[25] - L[24]) {
        const k = t - (L[25] - L[24]);
        const s = Math.min(1, k / 6);
        for (let i = 0; i < 18 * s; i++) g.rect(60 + i * 2, 120 + i * 2, 6, 6, P.accent);
        for (let i = 0; i < 30 * s; i++) g.rect(96 + i * 2, 156 - i * 3, 6, 6, P.accent);
        g.glow(110, 130, 50, P.accent, 0.3);
      }
    }, "dissolve", 10),

    /* 16 · Amerrissage dans le Pacifique */
    S("splash", 26, 28, (g, { t, at }) => {
      g.vgrad(0, 0, W, 260, ["#14365e", "#1f5585", "#3b7bb0", "#7fb0d6"]);
      drawOcean(g, 260, t);
      drawShip(g, 150, 254);
      const hit = at(26, 0.85);
      if (t < hit) {
        drawCapsuleChutes(g, 90, Math.round(lerp(150, 262, ease(t / hit))), 2, t);
      } else {
        const k = t - hit;
        drawCapsuleChutes(g, 90, 262 + Math.round(Math.sin(t / 12) * 2), 2, t);
        if (k < 30) particles(g, k, { seed: 4, x: 90, y: 270, rate: 6, life: 24, vx: 0, vy: -2.2, spread: 2.6, gravity: 0.15, ramp: ["#ffffff", "#e9fff2", "#8ff0b0", "#1b7a8f"], size: 2, stop: 5 });
        if (t >= at(27)) [58, 78, 98].forEach((x, i) => drawAstronaut(g, x + 60, 300, 2, t, i * 15));
      }
    }, "iris", 12),

    /* 17 · Le plus fou, dans tout ça ? */
    S("question", 28, 29, (g, { t, f }) => {
      space(g, f, { dx: t * 2 });
      const Q = ["01110", "10001", "00001", "00010", "00100", "00000", "00100"];
      Q.forEach((row, j) =>
        [...row].forEach((b, i) => {
          if (b !== "1") return;
          const k = j * 5 + i;
          const p = ease((t - ((hash(k) * 8) | 0)) / 6);
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

    /* 18 · Surnom : « la boîte aux lettres » */
    S("mailbox", 29, 30, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#07090a", "#151b18"]);
      drawMailbox(g, 60, 210, 2, 4, t);
      if (t >= at(29, 0.6)) {
        const p = ease((t - at(29, 0.6)) / 10);
        const x = Math.round(lerp(260, 160, p));
        g.rect(x - 2, 230, 4, 70, P.wood[2]);
        g.rect(x - 22, 186, 44, 44, "#1f5585");
        g.rect(x - 22, 186, 44, 6, "#3b7bb0");
        g.disc(x, 190, 22, "#1f5585");
        g.rect(x - 22, 190, 44, 40, "#1f5585");
        g.rect(x - 14, 200, 28, 3, P.ink);
        const flag = t > at(29, 0.8);
        g.rect(x + 22, flag ? 176 : 196, 3, flag ? 24 : 18, "#e8433a");
        g.rect(x + 22, flag ? 176 : 210, 10, 6, "#e8433a");
      }
    }, "wipe", 10),

    /* 19 · Jack Swigert remplaçait un collègue au dernier moment */
    S("swap", 30, 31, (g, { t, f, at }) => {
      space(g, f, { nebula: 0.3 });
      const s = at(30, 0.45);
      const out = ease((t - s) / 8);
      drawCrewBust(g, Math.round(lerp(108, -70, out)), 270, 4, t, "#3d2412", SKIN[2]);
      if (t > s) drawCrewBust(g, Math.round(lerp(290, 108, ease((t - s) / 8))), 270, 4, t, "#c9952a", SKIN[1]);
    }, "dissolve", 10),

    /* 20 · Dossier classé */
    S("outro", 31, null, (g, { t, at }) => {
      g.vgrad(0, 0, W, H, ["#020604", "#04100a", "#071a10"]);
      for (let s = 0; s < 4; s++) {
        const y = 100 + s * 60;
        g.rect(0, y + 44, W, 4, P.wood[2]);
        for (let i = 0; i < 22; i++) {
          const w = 7 + Math.floor(hash(i + s * 31) * 4);
          const x = i * 10 + (s % 2) * 4;
          const h = 30 + Math.floor(hash(i * 3 + s) * 12);
          g.rect(x, y + 44 - h, w, h, hash(i * 7 + s) > 0.8 ? P.green[1] : hash(i + s) > 0.5 ? "#4a3b25" : "#3a2e1d");
        }
      }
      g.glow(108, 250, 80, P.green[2], 0.5);
      drawTapeRoll(g, 170, 150, 10, t);
      drawArchivist(g, 108, 330, 4, t, t < at(31, 0.95));
    }, "iris", 12),
  ];
};

/** Instants clés (effets et sons). */
export const apolloKeys = (L: number[], at: (line: number, frac: number) => number) => ({
  tape: at(1, 0.4),
  ignition: at(2, 0.1),
  boom: at(6, 0.62),
  houston: L[8],
  lightsOff: L[9],
  squeeze: at(11, 0.55),
  mortal: at(13, 0.6),
  full: at(15, 0.6),
  reject: at(17, 0.35),
  idea: at(18, 0.6),
  tapeRoll: L[21],
  plug: at(24, 0.55),
  works: L[25],
  splash: at(26, 0.85),
  question: L[28],
  flag: at(29, 0.8),
  swap: at(30, 0.45),
  classified: at(31, 0.64),
});
