import React from "react";
import { useCurrentFrame } from "remotion";
import { fmt, Stamp } from "../lib/components";
import { C, PIXEL, TITLE, tw } from "../lib/theme";
import { P } from "../px/common";
import { Gfx, H, hash, W } from "../px/gfx";
import type { SceneCtx } from "../px/Stage";
import { dataBackdrop, decorBackdrop } from "./backdrops";
import { drawIcon } from "./icons";
import { drawMax } from "./mascot";
import type { Pace, Pal } from "./palettes";
import type { Planned } from "./plan";
import type { Icon, SceneParams, SceneType, Side } from "./schema";
import { Badge, Big, Bubble, Card, euro, outline } from "./ui";

/**
 * Le stock de scènes : chaque type = un dessin pixel (fond, icônes, animation) + une couche de texte net.
 * Coordonnées du texte en pixels vidéo (1080 × 1920) ; le pixel art est 5 fois plus petit (216 × 384).
 * Zone utile : sous les sous-titres (y > 460) et au-dessus de la description TikTok (y < 1650).
 */

/** `talking` : la voix parle-t-elle à cette image (pour animer la bouche de Max) ? */
export type Env = { p: Planned; pal: Pal; pace: Pace; talking?: (f: number) => boolean };
export type SceneImpl = {
  draw: (g: Gfx, s: SceneCtx, env: Env) => void;
  Overlay: React.FC<Env>;
};

const px = (v: number) => Math.round(v / 5);
const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = (v: number) => 1 - Math.pow(1 - clamp(v), 3);
const params = <T extends SceneType>(p: Planned) => p.scene.params as SceneParams[T];
/** images depuis l'apparition k, relatives à la scène (pour le dessin pixel) */
const since = (env: Env, s: SceneCtx, k: number) => s.f - (env.p.reveals[k] ?? env.p.from);
const ip = (pal: Pal) => ({ accent: pal.accent, dim: pal.dim });
const SERIES = (pal: Pal) => [pal.accent, "#ffd23d", "#4fd8ff", "#e8433a", "#c08aff"].filter((c, i, a) => a.indexOf(c) === i);
const num = (v?: string) => {
  const n = parseFloat((v ?? "").replace(/\s/g, "").replace(/[^\d,.-]/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
};
/** moment « fin de démonstration » : après la dernière apparition */
const lateAt = (p: Planned) => Math.max(p.reveals[p.reveals.length - 1] ?? p.from, p.from + (p.to - p.from) * 0.55) + 18;

/** Point d'interrogation pixel. */
const QMARK = [".aaaaa.", "aa...aa", "....aa.", "...aa..", "...aa..", ".......", "...aa.."];

const fillPanel = (g: Gfx, x: number, y: number, w: number, h: number, pal: Pal) => {
  g.rect(x, y, w, h, pal.light ? "#fffaf0" : "#06100b");
  g.rect(x, y, w, 1, pal.light ? P.ink : pal.dim);
  g.rect(x, y + h - 1, w, 1, pal.light ? P.ink : pal.dim);
  g.rect(x, y, 1, h, pal.light ? P.ink : pal.dim);
  g.rect(x + w - 1, y, 1, h, pal.light ? P.ink : pal.dim);
};

/* ───────── Perso : Max, la mascotte, vit l'histoire ───────── */

const persoLayout = (variant: string) =>
  variant === "zoom" ? { cx: 108, by: 470, u: 9 } : variant === "duo" ? { cx: 58, by: 332, u: 4 } : { cx: 108, by: 332, u: 5 };

const perso: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    const { pose, icone, decor } = params<"perso">(p);
    if (decor) decorBackdrop(g, decor, s.f, s.t, pal, false);
    else dataBackdrop(g, s.f, pal);
    const L = persoLayout(p.variant);
    g.glow(L.cx, L.by - 70, p.variant === "zoom" ? 110 : 70, pal.accent, 0.25 + 0.05 * Math.sin(s.f / 8));
    // l'objet de la phrase : à côté de lui (duo) ou au-dessus de sa main
    if (icone && p.variant === "duo") drawIcon(g, icone, 154, 215 + Math.round(Math.sin(s.f / 10) * 3), 6, s.t - 6, ip(pal));
    else if (icone && p.variant === "centre") drawIcon(g, icone, 170, 170 + Math.round(Math.sin(s.f / 9) * 3), 3, s.t - 8, ip(pal));
    const talk = pose !== "choc" && pose !== "content" && !!env.talking?.(s.f);
    drawMax(g, L.cx, L.by, L.u, pose, s.t, { accent: pal.accent, talking: talk });
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { bulle, texte } = params<"perso">(p);
    const k = f - p.from - 6;
    const slam = k < 0 ? 0 : k < 6 ? [2.2, 1.6, 1.15, 0.95, 1.03, 1][k] : 1 + 0.02 * Math.sin(k / 6);
    const textY = p.variant === "zoom" ? 760 : 1470;
    const textX = p.variant === "duo" ? 770 : 540;
    return (
      <>
        {bulle ? <Bubble at={p.from + 4} x={p.variant === "duo" ? 600 : 540} y={p.variant === "zoom" ? 560 : 650} text={bulle} pal={pal} tail={p.variant === "duo" ? "left" : "down"} /> : null}
        {texte && k >= 0 ? (
          <div
            style={{
              position: "absolute", left: textX, top: textY, translate: "-50% -50%", scale: String(slam), rotate: "-3deg",
              fontFamily: TITLE, fontSize: texte.length > 12 ? 92 : 120, lineHeight: 1, color: pal.accent, whiteSpace: "nowrap",
              textShadow: `${outline(9)}, 0 0 40px ${pal.accent}99`,
            }}
          >
            {texte.toUpperCase()}
          </div>
        ) : null}
      </>
    );
  },
};

/* ───────── Accroche ───────── */

const accroche: SceneImpl = {
  draw: (g, s, { p, pal }) => {
    dataBackdrop(g, s.f, pal);
    const { icone } = params<"accroche">(p);
    if (p.variant === "zoom") {
      for (let k = 0; k < 36; k++) {
        const a = (k / 36) * Math.PI * 2 + hash(k) * 0.2;
        const r0 = 30 + ((s.t * 4 + hash(k * 3) * 120) % 140);
        g.line(108 + Math.cos(a) * r0, 200 + Math.sin(a) * r0, 108 + Math.cos(a) * (r0 + 14), 200 + Math.sin(a) * (r0 + 14), pal.dim);
      }
      if (icone) drawIcon(g, icone, 108, 200, Math.round(tw(s.t, [0, 40], [3, 7])), s.t, ip(pal));
    } else if (icone) drawIcon(g, icone, 108, p.variant === "tampon" ? 140 : 292, p.variant === "tampon" ? 4 : 5, s.t - 10, ip(pal));
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { titre } = params<"accroche">(p);
    if (p.variant === "tampon") {
      const k = f - p.from - 6;
      if (k < 0) return null;
      const sc = k < 6 ? [2.2, 1.7, 1.25, 1, 0.95, 1][k] : 1;
      return (
        <div
          style={{
            position: "absolute", left: 540, top: 1020, width: 920, translate: "-50% -50%", rotate: "-4deg", scale: String(sc),
            fontFamily: TITLE, fontSize: titre.length > 26 ? 84 : 104, lineHeight: 1.05, color: pal.accent, textAlign: "center",
            textShadow: `${outline(8)}, 0 0 40px ${pal.accent}88`,
          }}
        >
          {titre.toUpperCase()}
        </div>
      );
    }
    return (
      <Card at={p.from + 4} x={540} y={p.variant === "zoom" ? 1440 : 880} pal={pal} size={titre.length > 26 ? 70 : 86} width={920}>
        {titre}
      </Card>
    );
  },
};

/* ───────── Chiffre-choc ───────── */

const counterValue = (f: number, at: number, valeur: number) => tw(f, [at, at + 40], [0, valeur]);
const chiffre: SceneImpl = {
  draw: (g, s, { p, pal }) => {
    dataBackdrop(g, s.f, pal);
    const { icone, valeur } = params<"chiffre-choc">(p);
    const t = s.t - 8;
    if (p.variant === "barre") {
      fillPanel(g, 16, 196, 184, 26, pal);
      const fill = Math.round(180 * ease(t / 40));
      for (let x = 0; x < fill; x += 6) g.rect(18 + x, 198, Math.min(5, fill - x), 22, pal.accent);
      if (icone) drawIcon(g, icone, 18 + fill, 180, 3, t, ip(pal));
    } else if (p.variant === "pile") {
      const n = Math.max(3, Math.min(14, Math.round(Math.log10(Math.abs(valeur) + 1) * 2.4)));
      const shown = Math.min(n, Math.floor(t / 3));
      for (let k = 0; k < shown; k++) drawIcon(g, icone === "piece" ? "piece" : "billets", 108 + (k % 2 ? 3 : -3), 330 - k * 10, 4, 20, ip(pal));
    } else if (icone) drawIcon(g, icone, 108, 300, 5, t - 12, ip(pal));
    // pluie de pièces pendant que le chiffre monte
    if (t > 0 && t < 70)
      for (let k = 0; k < 10; k++) {
        const y = ((t * 3 + k * 41) % 260) + 60;
        drawIcon(g, k % 3 ? "piece" : "billets", 12 + ((k * 53) % 192), y, 1, 20, ip(pal));
      }
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { valeur, prefixe = "", suffixe = "", decimales = 0, etiquette } = params<"chiffre-choc">(p);
    const at = p.from + 8;
    const text = `${prefixe}${fmt(counterValue(f, at, valeur), decimales)}${suffixe}`;
    const full = `${prefixe}${fmt(valeur, decimales)}${suffixe}`;
    const size = Math.min(210, Math.round(1500 / Math.max(4, full.length)));
    const y = p.variant === "pile" ? 640 : p.variant === "barre" ? 820 : 860;
    return (
      <>
        <Big at={at} x={540} y={y} size={size} color={pal.accent}>
          {text}
        </Big>
        <Card at={at + 30} x={540} y={p.variant === "barre" ? 1220 : y + size * 0.5 + 110} pal={pal} size={48} width={860}>
          {etiquette}
        </Card>
      </>
    );
  },
};

/* ───────── Liste (encadrés, podium, cartes) ───────── */

const liste: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    dataBackdrop(g, s.f, pal);
    const { items } = params<"liste">(p);
    if (p.variant === "podium") {
      const places = [
        { x: 108, w: 54, h: 80 },
        { x: 50, w: 54, h: 56 },
        { x: 166, w: 54, h: 38 },
      ];
      items.slice(0, 3).forEach((it, k) => {
        const t = since(env, s, k);
        if (t < 0) return;
        const pl = places[k];
        const h = Math.round(pl.h * ease(t / 10));
        g.rect(pl.x - pl.w / 2, 330 - h, pl.w, h, k === 0 ? pal.accent : pal.dim);
        g.rect(pl.x - pl.w / 2, 330 - h, pl.w, 2, P.white);
        if (it.icone) drawIcon(g, it.icone, pl.x, 330 - h - 20, 3, t - 8, ip(pal));
      });
    } else if (p.variant === "cartes") {
      items.forEach((it, k) => {
        if (!it.icone) return;
        const { x, y } = cardPos(k, items.length);
        drawIcon(g, it.icone, px(x), px(y - 70), 3, since(env, s, k) - 2, ip(pal));
      });
    } else {
      const rows = rowsLayout(items.length, !!params<"liste">(p).titre);
      items.forEach((it, k) => it.icone && drawIcon(g, it.icone, px(975), px(rows[k]), 2, since(env, s, k), ip(pal)));
    }
  },
  Overlay: ({ p, pal }) => {
    const { items, titre } = params<"liste">(p);
    const head = titre ? (
      <Card at={p.from + 2} x={540} y={520} pal={pal} size={44} hot font="pixel">
        {titre.toUpperCase()}
      </Card>
    ) : null;
    if (p.variant === "podium") {
      const pos = [
        [540, 1650 - 400 - 260],
        [250, 1650 - 280 - 260],
        [830, 1650 - 190 - 260],
      ];
      return (
        <>
          {head}
          {items.slice(0, 3).map((it, k) => (
            <React.Fragment key={k}>
              <Badge at={p.reveals[k]} x={pos[k][0]} y={1580} pal={pal} size={40}>
                {k + 1}
              </Badge>
              <Card at={p.reveals[k] + 8} x={pos[k][0]} y={pos[k][1]} pal={pal} size={34} width={300}>
                {it.texte}
              </Card>
            </React.Fragment>
          ))}
          {items.slice(3).map((it, k) => (
            <Card key={k} at={p.reveals[k + 3]} x={540} y={(titre ? 640 : 540) + k * 100} pal={pal} size={30} font="pixel">
              {`${k + 4}. ${it.texte}`}
            </Card>
          ))}
        </>
      );
    }
    if (p.variant === "cartes")
      return (
        <>
          {head}
          {items.map((it, k) => {
            const { x, y } = cardPos(k, items.length);
            return (
              <div key={k} style={{ position: "absolute", inset: 0, rotate: `${k % 2 ? 2 : -2}deg`, transformOrigin: `${x}px ${y}px` }}>
                <Card at={p.reveals[k]} x={x} y={y + 90} pal={pal} size={38} width={440} from="right">
                  {it.texte}
                  {it.valeur ? <div style={{ color: pal.light ? pal.accent : pal.accent, marginTop: 6 }}>{it.valeur}</div> : null}
                </Card>
              </div>
            );
          })}
        </>
      );
    const rows = rowsLayout(items.length, !!titre);
    return (
      <>
        {head}
        {items.map((it, k) => (
          <React.Fragment key={k}>
            <Badge at={p.reveals[k]} x={115} y={rows[k]} pal={pal} size={46}>
              {k + 1}
            </Badge>
            <Card at={p.reveals[k] + 3} x={540} y={rows[k]} pal={pal} size={items.length > 4 ? 38 : 44} width={680} from="right">
              {it.texte}
              {it.valeur ? <span style={{ color: pal.accent }}>{` · ${it.valeur}`}</span> : null}
            </Card>
          </React.Fragment>
        ))}
      </>
    );
  },
};
const rowsLayout = (n: number, title: boolean) => {
  const top = title ? 690 : 600;
  const step = Math.min(240, (1560 - top) / Math.max(1, n - 1));
  return Array.from({ length: n }, (_, k) => Math.round(top + k * step));
};
const cardPos = (k: number, n: number) => {
  const rows = Math.ceil(n / 2);
  const step = Math.min(380, 1100 / rows);
  const lone = n % 2 === 1 && k === n - 1;
  return { x: lone ? 540 : k % 2 ? 790 : 290, y: Math.round(620 + Math.floor(k / 2) * step) };
};

/* ───────── Comparaison (duel, balance, barres) ───────── */

const sideBlock = (side: Side, x: number, y: number, at: number, pal: Pal, dim = false) => (
  <div style={{ opacity: dim ? 0.45 : 1 }}>
    <Card at={at} x={x} y={y} pal={pal} size={side.titre.length > 12 ? 38 : 46} width={440}>
      {side.titre}
    </Card>
  </div>
);

const comparaison: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    dataBackdrop(g, s.f, pal);
    const { gauche, droite, gagnant } = params<"comparaison">(p);
    const late = s.f >= lateAt(p);
    if (p.variant === "balance") {
      const target = gagnant === "gauche" ? 0.22 : gagnant === "droite" ? -0.22 : 0;
      const a = late ? target * ease((s.f - lateAt(p)) / 14) + Math.sin(s.f / 6) * 0.01 : Math.sin(s.t / 9) * 0.06 * Math.max(0, 1 - s.t / 60);
      const cx = 108;
      const cy = 150;
      for (let y = cy; y < 320; y++) g.rect(cx - 2, y, 4, 1, P.grey[4]);
      g.rect(cx - 24, 318, 48, 6, P.grey[3]);
      const ex = Math.cos(a) * 76;
      const ey = Math.sin(a) * 76;
      g.line(cx - ex, cy - ey, cx + ex, cy + ey, P.white);
      g.line(cx - ex, cy - ey + 1, cx + ex, cy + ey + 1, P.white);
      [
        [-1, gauche],
        [1, droite],
      ].forEach(([sg, sd], k) => {
        const px0 = cx + (sg as number) * ex;
        const py0 = cy + (sg as number) * ey;
        g.line(px0, py0, px0 - 14, py0 + 40, P.grey[5]);
        g.line(px0, py0, px0 + 14, py0 + 40, P.grey[5]);
        g.rect(px0 - 20, py0 + 40, 40, 3, P.grey[5]);
        const icon = (sd as Side).icone;
        if (icon) drawIcon(g, icon, px0, py0 + 28, 2, since(env, s, k), ip(pal));
      });
      g.disc(cx, cy, 4, pal.accent);
      return;
    }
    if (p.variant === "barres") {
      const a = num(gauche.valeur);
      const b = num(droite.valeur);
      const max = Math.max(a, b);
      const hs = [a, b].map((v) => (Number.isFinite(max) && max > 0 && Number.isFinite(v) ? Math.max(0.08, v / max) : 0.6));
      [54, 162].forEach((x, k) => {
        const t = since(env, s, k);
        if (t < 0) return;
        const h = Math.round(170 * hs[k] * ease(t / 24));
        const win = (gagnant === "gauche" && k === 0) || (gagnant === "droite" && k === 1);
        g.rect(x - 26, 300 - h, 52, h, late && !win && gagnant && gagnant !== "egalite" ? P.grey[3] : k === 0 ? pal.accent : pal.dim);
        g.rect(x - 26, 300 - h, 52, 2, P.white);
        const icon = (k === 0 ? gauche : droite).icone;
        if (icon) drawIcon(g, icon, x, 300 - h - 22, 3, t - 10, ip(pal));
      });
      g.rect(10, 300, 196, 2, P.white);
      return;
    }
    // duel : écran coupé, éclair au milieu
    g.dither(0, 90, 108, 270, pal.deep, 0.35);
    for (let y = 90; y < 360; y++) g.rect(106 + Math.round(Math.sin(y / 6 + s.f / 3) * 2), y, 3, 1, hash(y + Math.floor(s.f / 2)) > 0.15 ? pal.accent : P.white);
    [gauche, droite].forEach((sd, k) => sd.icone && drawIcon(g, sd.icone, k ? 162 : 54, 186, 4, since(env, s, k), ip(pal)));
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { gauche, droite, gagnant } = params<"comparaison">(p);
    const late = lateAt(p);
    const lost = (k: number) => f >= late && !!gagnant && gagnant !== "egalite" && (gagnant === "gauche") !== (k === 0);
    const sides: [Side, number][] = [
      [gauche, 270],
      [droite, 810],
    ];
    const titleY = p.variant === "balance" ? 1330 : 580;
    const valY = p.variant === "balance" ? 1460 : p.variant === "barres" ? 1550 : 1200;
    return (
      <>
        {sides.map(([sd, x], k) => (
          <React.Fragment key={k}>
            {sideBlock(sd, x, titleY, p.reveals[k], pal, lost(k))}
            {sd.valeur ? (
              <div style={{ opacity: lost(k) ? 0.45 : 1 }}>
                <Big at={p.reveals[k] + 10} x={x} y={valY} size={sd.valeur.length > 7 ? 64 : 84} color={k ? C.white : pal.accent}>
                  {sd.valeur}
                </Big>
              </div>
            ) : null}
            {p.variant === "duel" &&
              sd.points?.map((pt, i) => (
                <Card key={i} at={p.reveals[k] + 16 + i * 8} x={x} y={1330 + i * 92} pal={pal} size={26} width={440} font="pixel">
                  {pt}
                </Card>
              ))}
          </React.Fragment>
        ))}
        {p.variant === "duel" ? (
          <Badge at={p.from + 6} x={540} y={930} pal={pal} size={56} round>
            VS
          </Badge>
        ) : null}
        {gagnant ? (
          <Stamp
            text={gagnant === "egalite" ? "ÉGALITÉ" : "GAGNANT"}
            at={Math.round(late)}
            x={gagnant === "droite" ? 810 : gagnant === "gauche" ? 270 : 540}
            y={p.variant === "duel" ? 760 : 470 + 260}
            size={58}
            color={pal.accent}
            rotate={-8}
          />
        ) : null}
      </>
    );
  },
};

/* ───────── Flux d'argent (tuyaux, camembert, ticket) ───────── */

const parts = (etapes: { part?: number }[]) => {
  const given = etapes.map((e) => e.part ?? NaN);
  const known = given.filter(Number.isFinite).reduce((a, b) => a + b, 0);
  const missing = given.filter((v) => !Number.isFinite(v)).length;
  return given.map((v) => (Number.isFinite(v) ? v : Math.max(0, (100 - known) / Math.max(1, missing))));
};

const flux: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    dataBackdrop(g, s.f, pal);
    const { etapes, depart } = params<"flux-argent">(p);
    if (p.variant === "camembert") {
      const ps = parts(etapes);
      const tot = ps.reduce((a, b) => a + b, 0) || 1;
      const cols = SERIES(pal);
      const cx = 108;
      const cy = 180;
      const r = 62;
      let acc = 0;
      const bounds = ps.map((v, k) => {
        const a0 = acc;
        acc += (v / tot) * Math.PI * 2;
        return { a0, a1: a0 + (acc - a0) * ease(since(env, s, k) / 14), on: since(env, s, k) >= 0, col: cols[k % cols.length] };
      });
      g.disc(cx, cy, r + 3, P.ink);
      for (let y = -r; y <= r; y++)
        for (let x = -r; x <= r; x++) {
          if (x * x + y * y > r * r) continue;
          const a = (Math.atan2(x, -y) + Math.PI * 2) % (Math.PI * 2);
          const b = bounds.find((q) => q.on && a >= q.a0 && a < q.a1);
          g.rect(cx + x, cy + y, 1, 1, b ? b.col : pal.light ? "#e6dbbf" : "#0d1712");
        }
      bounds.forEach((q) => q.on && g.line(cx, cy, cx + Math.sin(q.a0) * r, cy - Math.cos(q.a0) * r, P.ink));
      if (depart.icone) drawIcon(g, depart.icone, cx, cy, 3, s.t - 4, ip(pal));
      return;
    }
    if (p.variant === "ticket") {
      g.rect(38, 92, 140, 18, P.grey[3]);
      g.rect(42, 106, 132, 4, P.ink);
      if (depart.icone) drawIcon(g, depart.icone, 108, 82, 2, s.t, ip(pal));
      return;
    }
    // tuyaux : un tuyau principal à gauche, une branche par étape, des pièces qui coulent
    const rows = fluxRows(etapes.length);
    const x0 = px(150);
    const last = px(rows[rows.length - 1]);
    if (depart.icone) drawIcon(g, depart.icone, x0, px(560), 3, s.t, ip(pal));
    g.rect(x0 - 3, px(640), 7, last - px(640), P.grey[3]);
    g.rect(x0 - 1, px(640), 3, last - px(640), P.grey[2]);
    rows.forEach((y, k) => {
      const t = since(env, s, k);
      if (t < 0) return;
      const len = Math.round(24 * ease(t / 8));
      g.rect(x0, px(y) - 3, len, 7, P.grey[3]);
      for (let c = 0; c < 3; c++) {
        const yy = px(640) + ((s.f * 2 + c * 37 + k * 13) % (px(y) - px(640) + 1));
        drawIcon(g, "piece", x0, yy, 1, 20, ip(pal));
      }
    });
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { etapes, depart } = params<"flux-argent">(p);
    const ps = parts(etapes);
    const pct = (v: number) => `${Math.round(v)} %`;
    if (p.variant === "camembert") {
      const cols = SERIES(pal);
      return (
        <>
          <Card at={p.from + 2} x={540} y={520} pal={pal} size={40} hot font="pixel">
            {depart.texte.toUpperCase()}
          </Card>
          {etapes.map((e, k) => {
            const x = etapes.length > 3 ? (k % 2 ? 790 : 290) : 540;
            const y = etapes.length > 3 ? 1330 + Math.floor(k / 2) * 110 : 1330 + k * 110;
            return (
              <Card key={k} at={p.reveals[k]} x={x} y={y} pal={pal} size={34} width={etapes.length > 3 ? 470 : 760} font="title">
                <span style={{ display: "inline-block", width: 26, height: 26, background: cols[k % cols.length], border: `4px solid ${C.ink}`, marginRight: 14, verticalAlign: "middle" }} />
                {e.texte} <span style={{ color: pal.accent }}>{pct(ps[k])}</span>
              </Card>
            );
          })}
        </>
      );
    }
    if (p.variant === "ticket") {
      const shown = p.reveals.filter((r) => f >= r).length;
      const op = (k: number) => clamp((f - p.reveals[k]) / 4);
      return (
        <div
          style={{
            position: "absolute", left: 540, top: 560, translate: "-50% 0", width: 700, padding: "30px 40px 40px",
            background: "#fffaf0", color: C.ink, fontFamily: PIXEL, fontSize: 34, lineHeight: 1.5,
            boxShadow: `10px 10px 0 ${pal.light ? "#00000033" : pal.deep}`,
            clipPath: `inset(0 0 ${Math.max(0, 100 - 22 - shown * (78 / etapes.length))}% 0)`,
            borderBottom: `14px dotted ${pal.light ? "#e6dbbf" : C.bg}`,
          }}
        >
          <div style={{ textAlign: "center", fontWeight: 700, fontSize: 40 }}>{euro(depart.texte.toUpperCase())}</div>
          <div style={{ borderTop: `4px dashed ${C.ink}`, margin: "14px 0" }} />
          {etapes.map((e, k) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", opacity: op(k), gap: 20 }}>
              <span>{euro(e.texte)}</span>
              <span style={{ color: k === etapes.length - 1 ? C.alert : C.ink, fontWeight: 700 }}>{pct(ps[k])}</span>
            </div>
          ))}
          <div style={{ borderTop: `4px dashed ${C.ink}`, margin: "14px 0" }} />
          <div style={{ textAlign: "center", fontSize: 26, opacity: op(etapes.length - 1) }}>MERCI DE VOTRE VISITE</div>
        </div>
      );
    }
    const rows = fluxRows(etapes.length);
    return (
      <>
        <Card at={p.from + 2} x={560} y={560} pal={pal} size={42} width={640} hot>
          {depart.texte}
        </Card>
        {etapes.map((e, k) => (
          <React.Fragment key={k}>
            <Card at={p.reveals[k] + 4} x={600} y={rows[k]} pal={pal} size={40} width={640} from="right">
              {e.texte}
            </Card>
            <Badge at={p.reveals[k]} x={150} y={rows[k]} pal={pal} size={34} round>
              {pct(ps[k])}
            </Badge>
          </React.Fragment>
        ))}
      </>
    );
  },
};
const fluxRows = (n: number) => Array.from({ length: n }, (_, k) => Math.round(780 + k * Math.min(200, 820 / Math.max(1, n - 1))));

/* ───────── Frise (route, calendrier, ascenseur) ───────── */

const friseY = (n: number) => Array.from({ length: n }, (_, k) => Math.round(1560 - k * (1000 / Math.max(1, n - 1))));
const roadX = (y: number) => 108 + Math.sin(y / 34) * 8;

const frise: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    const { etapes } = params<"frise">(p);
    const ys = friseY(etapes.length).map(px);
    const cur = p.reveals.filter((r) => s.f >= r).length - 1;
    if (p.variant === "calendrier") {
      dataBackdrop(g, s.f, pal);
      const t = cur >= 0 ? s.f - p.reveals[cur] : -1;
      // page qui part, page qui arrive
      if (cur > 0 && t < 10) {
        const drop = Math.round(t * t * 0.9);
        fillPanel(g, 48, 110 + drop, 120, 112, pal);
      }
      if (cur >= 0) {
        g.rect(48, 110, 120, 112, "#fffaf0");
        g.rect(48, 110, 120, 22, P.alert);
        for (let k = 0; k < 5; k++) g.rect(60 + k * 22, 104, 6, 12, P.grey[3]);
        g.rect(48, 221, 120, 2, P.grey[4]);
      }
      return;
    }
    if (p.variant === "ascenseur") {
      dataBackdrop(g, s.f, pal);
      g.rect(80, 70, 56, 300, pal.light ? "#d6c9a6" : "#0f1714");
      g.rect(80, 70, 2, 300, P.grey[3]);
      g.rect(134, 70, 2, 300, P.grey[3]);
      ys.forEach((y) => g.rect(70, y + 14, 76, 2, P.grey[3]));
      const target = cur >= 0 ? ys[cur] : ys[0] + 30;
      const prev = cur > 0 ? ys[cur - 1] : ys[0] + 30;
      const y = Math.round(prev + (target - prev) * ease((s.f - (p.reveals[Math.max(0, cur)] ?? 0)) / 16));
      g.rect(88, y - 14, 40, 28, pal.accent);
      g.rect(92, y - 10, 14, 20, P.ink);
      g.rect(110, y - 10, 14, 20, P.ink);
      g.line(108, 70, 108, y - 14, P.grey[5]);
      return;
    }
    // route
    dataBackdrop(g, s.f, pal);
    for (let y = 90; y < 340; y++) {
      const x = roadX(y);
      g.rect(Math.round(x - 9), y, 18, 1, pal.light ? "#8a7d5c" : "#2b332e");
      if ((y + Math.floor(s.f / 2)) % 10 < 5) g.rect(Math.round(x), y, 1, 1, P.white);
    }
    ys.forEach((y, k) => {
      if (k > cur) return;
      const x = Math.round(roadX(y));
      g.rect(x + 10, y - 18, 1, 18, P.white);
      g.rect(x + 11, y - 18, 9, 6, k === cur ? pal.accent : pal.dim);
    });
    if (cur >= 0) {
      const y = ys[cur];
      drawIcon(g, "voiture", Math.round(roadX(y)), y, 2, 20, ip(pal));
    }
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { etapes } = params<"frise">(p);
    if (p.variant === "calendrier") {
      const cur = p.reveals.filter((r) => f >= r).length - 1;
      if (cur < 0) return null;
      const e = etapes[cur];
      return (
        <>
          <div key={cur} style={{ position: "absolute", left: 540, top: 880, translate: "-50% -50%", fontFamily: TITLE, fontSize: e.date.length > 6 ? 96 : 140, color: C.ink, whiteSpace: "nowrap" }}>
            {e.date}
          </div>
          <Card key={`t${cur}`} at={p.reveals[cur] + 4} x={540} y={1230} pal={pal} size={46} width={860}>
            {e.texte}
          </Card>
          <div style={{ position: "absolute", left: 540, top: 1440, translate: "-50% 0", display: "flex", gap: 14 }}>
            {etapes.slice(0, cur).map((x, k) => (
              <div key={k} style={{ padding: "8px 14px", background: pal.deep, color: C.white, fontFamily: PIXEL, fontSize: 26, border: `3px solid ${pal.accent}` }}>
                {x.date}
              </div>
            ))}
          </div>
        </>
      );
    }
    const ys = friseY(etapes.length);
    return (
      <>
        {etapes.map((e, k) => {
          const left = p.variant === "ascenseur" ? false : k % 2 === 0;
          const x = p.variant === "ascenseur" ? 800 : left ? 270 : 810;
          return (
            <React.Fragment key={k}>
              <Badge at={p.reveals[k]} x={p.variant === "ascenseur" ? 210 : x} y={ys[k] - 70} pal={pal} size={30}>
                {e.date}
              </Badge>
              <Card at={p.reveals[k] + 4} x={x} y={ys[k] + 30} pal={pal} size={32} width={p.variant === "ascenseur" ? 440 : 420} from={left ? "left" : "right"}>
                {e.texte}
              </Card>
            </React.Fragment>
          );
        })}
      </>
    );
  },
};

/* ───────── Schéma à flèches (ligne, cercle) ───────── */

type Node = { x: number; y: number; icon?: Icon | "max"; text: string };
const schemaNodes = (p: Planned): { nodes: Node[]; res?: { x: number; y: number } } => {
  const { personnage, etapes, resultat } = params<"schema-fleches">(p);
  const head: Node = { x: 0, y: 0, icon: personnage.icone ?? "max", text: personnage.nom };
  if (p.variant === "cercle") {
    const n = etapes.length;
    const nodes = [
      { ...head, x: 540, y: 960 },
      ...etapes.map((e, k) => {
        const a = -Math.PI / 2 + ((k + 0.5) / n) * Math.PI * 2 - Math.PI / n / 2;
        return { x: Math.round(540 + Math.cos(a) * 330), y: Math.round(960 + Math.sin(a) * 330), icon: e.icone, text: e.texte };
      }),
    ];
    return { nodes, res: resultat ? { x: 540, y: 1520 } : undefined };
  }
  const rows = etapes.length + 1 + (resultat ? 1 : 0);
  const step = Math.min(250, 1020 / Math.max(1, rows - 1));
  const nodes = [{ ...head, x: 300, y: 600 }, ...etapes.map((e, k) => ({ x: k % 2 ? 300 : 780, y: Math.round(600 + (k + 1) * step), icon: e.icone, text: e.texte }))];
  return { nodes, res: resultat ? { x: 540, y: Math.round(600 + (rows - 1) * step) } : undefined };
};
const resultAt = (p: Planned) => Math.round(lateAt(p));

const schema: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    dataBackdrop(g, s.f, pal);
    const { nodes, res } = schemaNodes(p);
    const sc = nodes.length > 4 && p.variant !== "cercle" ? 2 : 3;
    nodes.forEach((nd, k) => {
      const t = k === 0 ? s.t - 4 : since(env, s, k - 1);
      if (t < 0) return;
      if (k > 0) {
        const from = p.variant === "cercle" ? nodes[0] : nodes[k - 1];
        const len = ease(t / 10);
        const [x0, y0, x1, y1] = [px(from.x), px(from.y), px(nd.x), px(nd.y)];
        g.dashed(x0, y0, x0 + (x1 - x0) * len, y0 + (y1 - y0) * len, pal.light ? P.ink : pal.accent, 3, 2, -s.f / 2);
      }
      if (nd.icon === "max") drawMax(g, px(nd.x), px(nd.y) + 26, 2, "montre", t, { accent: pal.accent, talking: env.talking?.(s.f) });
      else if (nd.icon) drawIcon(g, nd.icon, px(nd.x), px(nd.y), k === 0 ? sc + 1 : sc, t, ip(pal));
    });
    if (res && s.f >= resultAt(p)) {
      const { resultat } = params<"schema-fleches">(p);
      const last = nodes[nodes.length - 1];
      g.dashed(px(last.x), px(last.y), px(res.x), px(res.y) - 14, pal.light ? P.ink : pal.accent, 3, 2, -s.f / 2);
      drawIcon(g, resultat?.ton === "mauvais" ? "feu" : "etoile", px(res.x), px(res.y) - 12, 2, s.f - resultAt(p), ip(pal));
    }
  },
  Overlay: ({ p, pal }) => {
    const { resultat } = params<"schema-fleches">(p);
    const { nodes, res } = schemaNodes(p);
    const cercle = p.variant === "cercle";
    return (
      <>
        <Badge at={p.from + 6} x={nodes[0].x} y={nodes[0].y + (cercle ? 120 : 110)} pal={pal} size={30}>
          {nodes[0].text.toUpperCase()}
        </Badge>
        {nodes.slice(1).map((nd, k) => (
          <Card
            key={k}
            at={p.reveals[k] + 6}
            x={cercle ? nd.x : nd.x === 300 ? 700 : 380}
            y={cercle ? nd.y + 105 : nd.y}
            pal={pal}
            size={cercle ? 30 : 36}
            width={cercle ? 380 : 470}
            from={nd.x < 540 ? "left" : "right"}
          >
            {nd.text}
          </Card>
        ))}
        {res && resultat ? (
          <Card at={resultAt(p)} x={res.x} y={res.y + 40} pal={pal} size={44} width={760} hot={resultat.ton !== "mauvais"} color={resultat.ton === "mauvais" ? C.alert : undefined}>
            {resultat.texte}
          </Card>
        ) : null}
      </>
    );
  },
};

/* ───────── Tableau (lignes, écran) ───────── */

const tableau: SceneImpl = {
  draw: (g, s, { p, pal }) => {
    dataBackdrop(g, s.f, pal);
    if (p.variant === "ecran") {
      g.rect(10, 96, 196, 236, P.grey[3]);
      g.rect(14, 100, 188, 228, "#03100a");
      for (let y = 100; y < 328; y += 2) g.rect(14, y, 188, 1, "#06160e");
      g.rect(96, 332, 24, 10, P.grey[3]);
      g.rect(76, 342, 64, 4, P.grey[4]);
    }
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { titre, colonnes, lignes, surligner } = params<"tableau">(p);
    const ecran = p.variant === "ecran";
    const top = ecran ? 580 : titre ? 650 : 560;
    const rowH = Math.min(130, (ecran ? 980 : 1040) / (lignes.length + 1));
    const cell = (txt: React.ReactNode, w: number, st: React.CSSProperties = {}) => (
      <div style={{ width: w, padding: "0 18px", display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", ...st }}>{txt}</div>
    );
    const W1 = ecran ? 420 : 430;
    const W2 = ecran ? 420 : 430;
    const typed = (txt: string, at: number) => (ecran ? txt.slice(0, Math.max(0, Math.floor((f - at) * 1.5))) : txt);
    const hot = (k: number) => surligner === k + 1 && f >= p.reveals[k] + 10;
    return (
      <>
        {titre && !ecran ? (
          <Card at={p.from + 2} x={540} y={540} pal={pal} size={42} hot font="pixel">
            {titre.toUpperCase()}
          </Card>
        ) : null}
        <div style={{ position: "absolute", left: 540, top, translate: "-50% 0", fontFamily: ecran ? PIXEL : TITLE, fontSize: ecran ? 34 : 40 }}>
          <div
            style={{
              display: "flex", height: rowH, background: ecran ? "transparent" : pal.accent, color: ecran ? C.white : C.ink,
              border: ecran ? "none" : `5px solid ${C.ink}`, opacity: f >= p.from + 4 ? 1 : 0,
            }}
          >
            {cell(colonnes[0], W1)}
            {cell(colonnes[1], W2, { borderLeft: `4px solid ${ecran ? pal.dim : C.ink}` })}
          </div>
          {lignes.map((l, k) => {
            const k0 = f - p.reveals[k];
            if (k0 < 0) return <div key={k} style={{ height: rowH }} />;
            const slide = ecran ? 0 : (1 - ease(k0 / 8)) * 300;
            const h = hot(k);
            return (
              <div
                key={k}
                style={{
                  display: "flex", height: rowH, translate: `${slide}px 0`,
                  background: ecran ? (h ? pal.deep : "transparent") : h ? pal.accent : pal.light ? "#fffaf0" : C.ink,
                  color: ecran ? (h ? C.white : pal.accent) : h ? C.ink : pal.light ? C.ink : C.white,
                  border: ecran ? "none" : `5px solid ${pal.light ? C.ink : pal.dim}`, borderTop: "none",
                  scale: h ? String(1 + 0.03 * Math.max(0, Math.sin((f - p.reveals[k]) / 5))) : "1",
                  boxShadow: h && !ecran ? `0 0 40px ${pal.accent}` : "none",
                }}
              >
                {cell(euro(typed(l[0], p.reveals[k])), W1)}
                {cell(euro(typed(l[1], p.reveals[k] + 6)), W2, { borderLeft: `4px solid ${ecran ? pal.dim : pal.light ? C.ink : pal.dim}` })}
              </div>
            );
          })}
        </div>
      </>
    );
  },
};

/* ───────── Coulisses (décor + bulle) ───────── */

const coulisses: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    const { decor, icone } = params<"coulisses">(p);
    decorBackdrop(g, decor, s.f, s.t, pal, p.variant === "nuit");
    if (icone) drawIcon(g, icone, 182, 90 + Math.round(Math.sin(s.f / 12) * 2), 3, s.t - 20, ip(pal));
    drawMax(g, 46, 352, 3, "parle", s.t, { accent: pal.accent, talking: env.talking?.(s.f) });
  },
  Overlay: ({ p, pal }) => <Bubble at={p.from + 10} x={540} y={720} text={params<"coulisses">(p).bulle} pal={pal} tail="left" />,
};

/* ───────── Avant / après (coupe, volet) ───────── */

const avantApres: SceneImpl = {
  draw: (g, s, env) => {
    const { p, pal } = env;
    dataBackdrop(g, s.f, pal);
    const { avant, apres } = params<"avant-apres">(p);
    if (p.variant === "volet") {
      const t = since(env, s, 1);
      const cut = t < 0 ? -1 : Math.round(W * ease(t / 12));
      if (t < 0 || cut < W) {
        g.dither(0, 0, W, H, "#000000", 0.35);
        if (avant.icone) drawIcon(g, avant.icone, 108, 180, 6, since(env, s, 0), ip(pal));
      }
      if (t >= 0) {
        g.rect(0, 0, cut, H, pal.light ? pal.sky[0] : pal.sky[1]);
        if (apres.icone && cut > 60) drawIcon(g, apres.icone, 108, 180, 6, t - 6, ip(pal));
        g.rect(cut - 2, 0, 4, H, pal.accent);
      }
      return;
    }
    g.dither(0, 88, W, 140, "#000000", 0.45);
    g.rect(0, 228, W, 2, pal.accent);
    if (avant.icone) drawIcon(g, avant.icone, 40, 165, 3, since(env, s, 0), ip(pal));
    if (apres.icone) drawIcon(g, apres.icone, 40, 300, 3, since(env, s, 1), ip(pal));
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { avant, apres } = params<"avant-apres">(p);
    const block = (sd: Side, y: number, at: number, label: string, hotLabel: boolean, x = 640, w = 640) => (
      <>
        <Badge at={at} x={x === 540 ? 540 : 160} y={x === 540 ? 560 : y - 150} pal={pal} size={30}>
          {label}
        </Badge>
        <Card at={at + 4} x={x} y={y} pal={pal} size={46} width={w} hot={hotLabel}>
          {sd.titre}
        </Card>
        {sd.valeur ? (
          <Big at={at + 10} x={x} y={y + 130} size={76} color={hotLabel ? pal.accent : C.white}>
            {sd.valeur}
          </Big>
        ) : null}
        {sd.points?.map((pt, i) => (
          <Card key={i} at={at + 16 + i * 8} x={x} y={y + 230 + i * 80} pal={pal} size={26} width={w} font="pixel">
            {pt}
          </Card>
        ))}
      </>
    );
    if (p.variant === "volet") {
      const after = f >= p.reveals[1] + 6;
      return after ? block(apres, 1150, p.reveals[1] + 6, "APRÈS", true, 540, 860) : block(avant, 1150, p.reveals[0], "AVANT", false, 540, 860);
    }
    return (
      <>
        {block(avant, 650, p.reveals[0], "AVANT", false)}
        {block(apres, 1330, p.reveals[1], "APRÈS", true)}
      </>
    );
  },
};

/* ───────── Question finale (simple, vote) ───────── */

const question: SceneImpl = {
  draw: (g, s, { p, pal }) => {
    dataBackdrop(g, s.f, pal);
    drawMax(g, 108, 372, 3, "reflechit", s.t, { accent: pal.accent });
    if (p.variant === "vote") return;
    const on = Math.floor(s.f / 12) % 2 === 0;
    g.sprite(QMARK, { a: on ? pal.accent : pal.dim }, 108 - 21, 104, 6);
  },
  Overlay: ({ p, pal }) => {
    const f = useCurrentFrame();
    const { question: q, choix } = params<"question-finale">(p);
    const pulse = (k: number) => String(1 + 0.05 * Math.max(0, Math.sin((f - p.from) / 6 + k * Math.PI)));
    return (
      <>
        <Card at={p.from + 4} x={540} y={p.variant === "vote" ? 700 : 1000} pal={pal} size={q.length > 40 ? 56 : 66} width={920}>
          {q}
        </Card>
        {p.variant === "vote" && choix
          ? choix.map((c, k) => (
              <div key={k} style={{ position: "absolute", left: 0, top: 0, scale: pulse(k), transformOrigin: `${k ? 790 : 290}px 1080px` }}>
                <Card at={p.reveals[k]} x={k ? 790 : 290} y={1080} pal={pal} size={48} width={420} hot={k === 0}>
                  <div style={{ fontFamily: PIXEL, fontSize: 34, opacity: 0.8 }}>{k ? "B" : "A"}</div>
                  {c}
                </Card>
              </div>
            ))
          : null}
        <Badge at={p.from + 20} x={540} y={p.variant === "vote" ? 1360 : 1290} pal={pal} size={30}>
          RÉPONDS EN COMMENTAIRE
        </Badge>
      </>
    );
  },
};

/** Le stock. « sur-mesure » est résolu à part (src/scenes/custom). */
export const LIBRARY: Record<Exclude<SceneType, "sur-mesure">, SceneImpl> = {
  perso,
  accroche,
  "chiffre-choc": chiffre,
  liste,
  comparaison,
  "flux-argent": flux,
  frise,
  "schema-fleches": schema,
  tableau,
  coulisses,
  "avant-apres": avantApres,
  "question-finale": question,
};

/** Tampon commun à toutes les scènes (« tampon » dans scenes.json). */
export const SceneStamp: React.FC<Env> = ({ p, pal }) => {
  const t = p.scene.tampon;
  if (!t || p.stampAt < 0) return null;
  return <Stamp text={t.texte.toUpperCase()} at={p.stampAt} x={540} y={1500} size={Math.min(110, Math.round(1300 / Math.max(5, t.texte.length)))} color={t.ton === "mauvais" ? C.alert : pal.accent} rotate={-6} />;
};

