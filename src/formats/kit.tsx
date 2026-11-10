// Briques communes des formats « créateur » : polices libres (OFL), maillage de couleurs animé, grain, ressorts, étincelles.
import React from "react";
import { Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont as loadBricolage } from "@remotion/google-fonts/BricolageGrotesque";
import { loadFont as loadFraunces } from "@remotion/google-fonts/Fraunces";
import { loadFont as loadLexend } from "@remotion/google-fonts/Lexend";

// Toutes sous licence SIL OFL (Google Fonts).
export const DISPLAY = loadBricolage("normal", { weights: ["800"], subsets: ["latin", "latin-ext"] }).fontFamily;
export const SERIF = loadFraunces("normal", { weights: ["300", "400"], subsets: ["latin", "latin-ext"] } as never).fontFamily;
export const TEXT = loadLexend("normal", { weights: ["400", "600"], subsets: ["latin", "latin-ext"] }).fontFamily;

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const out = Easing.bezier(0.22, 1, 0.36, 1);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Temps courant en secondes. */
export const useSeconds = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { t: f / fps, f, fps };
};

/** Ressort à retardement : 0 -> 1 avec un petit rebond, démarre à `debut` (secondes). */
export const pop = (t: number, debut: number, fps: number, raideur = 170, amorti = 13) =>
  spring({ frame: Math.max(0, (t - debut) * fps), fps, config: { damping: amorti, stiffness: raideur, mass: 0.7 } });

export const hexRgb = (h: string): [number, number, number] => {
  const c = h.replace("#", "");
  return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)];
};
export const rgba = (h: string, a: number) => {
  const [r, g, b] = hexRgb(h);
  return `rgba(${r},${g},${b},${a})`;
};

const GRAIN =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")";

export const Grain: React.FC<{ opacite?: number }> = ({ opacite = 0.07 }) => (
  <div style={{ position: "absolute", inset: 0, backgroundImage: GRAIN, backgroundSize: "220px 220px", opacity: opacite, mixBlendMode: "overlay", pointerEvents: "none" }} />
);

export const Vignette: React.FC<{ force?: number }> = ({ force = 0.55 }) => (
  <div style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 40%, rgba(0,0,0,${force}) 100%)`, pointerEvents: "none" }} />
);

/** Maillage de couleurs vivant : grandes taches radiales qui dérivent (boucle parfaite si `boucle` est donné en secondes). */
export const Maillage: React.FC<{ fond: string; taches: string[]; boucle?: number; vitesse?: number; w: number; h: number }> = ({ fond, taches, boucle, vitesse = 1, w, h }) => {
  const { t } = useSeconds();
  const ph = boucle ? (t / boucle) * Math.PI * 2 : t * 0.35 * vitesse;
  return (
    <div style={{ position: "absolute", inset: 0, background: fond, overflow: "hidden" }}>
      {taches.map((c, i) => {
        const a = random(`m${i}a`) * 6.28;
        const k = boucle ? 1 + (i % 2) : 1;
        const x = 50 + 36 * Math.sin(ph * k + a);
        const y = 50 + 36 * Math.cos(ph * (k === 1 ? 0.8 : 1) + a * 1.7);
        const r = Math.max(w, h) * (0.55 + 0.12 * random(`m${i}r`));
        return <div key={i} style={{ position: "absolute", inset: 0, background: `radial-gradient(circle ${r}px at ${x}% ${y}%, ${c} 0%, ${rgba(c, 0)} 70%)`, opacity: 0.9 }} />;
      })}
    </div>
  );
};

/** Formes qui flottent (anneaux, croix, pastilles) : décor vivant sans photo. */
export const Flottants: React.FC<{ couleurs: string[]; n?: number; w: number; h: number; boucle?: number }> = ({ couleurs, n = 16, w, h, boucle }) => {
  const { t } = useSeconds();
  return (
    <>
      {Array.from({ length: n }, (_, i) => {
        const bx = random(`fx${i}`) * w;
        const vit = 0.02 + random(`fv${i}`) * 0.05;
        const cyc = boucle ? Math.max(1, Math.round(vit * boucle)) / boucle : vit;
        const y = (((random(`fy${i}`) - t * cyc) % 1) + 1) % 1;
        const taille = 26 + random(`fs${i}`) * 70;
        const c = couleurs[i % couleurs.length];
        const forme = i % 3;
        const rot = t * (boucle ? 360 / boucle : 20) * (i % 2 ? 1 : -1);
        const dx = Math.sin((t / (boucle ?? 12)) * 6.28 + i) * 30;
        const base: React.CSSProperties = { position: "absolute", left: bx + dx, top: y * (h + 200) - 100, width: taille, height: taille, opacity: 0.22 + random(`fo${i}`) * 0.25, transform: `rotate(${rot}deg)` };
        if (forme === 0) return <div key={i} style={{ ...base, borderRadius: "50%", border: `${Math.max(4, taille / 9)}px solid ${c}` }} />;
        if (forme === 1) return <div key={i} style={{ ...base, borderRadius: "50%", background: c, width: taille / 2.2, height: taille / 2.2 }} />;
        return (
          <div key={i} style={base}>
            <div style={{ position: "absolute", left: "42%", top: 0, width: "16%", height: "100%", background: c, borderRadius: 99 }} />
            <div style={{ position: "absolute", top: "42%", left: 0, height: "16%", width: "100%", background: c, borderRadius: 99 }} />
          </div>
        );
      })}
    </>
  );
};

/** Étincelles qui jaillissent d'un point (confettis déterministes). */
export const Etincelles: React.FC<{ depuis: number; x: number; y: number; couleurs: string[]; n?: number; portee?: number }> = ({ depuis, x, y, couleurs, n = 30, portee = 520 }) => {
  const { t } = useSeconds();
  const age = t - depuis;
  if (age < 0 || age > 2.2) return null;
  return (
    <>
      {Array.from({ length: n }, (_, i) => {
        const ang = random(`e${i}`) * 6.28;
        const d = (0.35 + random(`ed${i}`) * 0.65) * portee * out(clamp01(age / 1.1));
        const grav = 220 * age * age;
        const o = 1 - clamp01((age - 0.8) / 1.2);
        const s = 12 + random(`es${i}`) * 22;
        return <div key={i} style={{ position: "absolute", left: x + Math.cos(ang) * d, top: y + Math.sin(ang) * d + grav, width: s, height: i % 2 ? s : s * 0.4, background: couleurs[i % couleurs.length], borderRadius: i % 3 ? 4 : 99, opacity: o, transform: `rotate(${ang * 90 + age * 300}deg)` }} />;
      })}
    </>
  );
};

/** Texte qui apparaît lettre par lettre (machine douce). */
export const Lettres: React.FC<{ texte: string; debut: number; t: number; cadence?: number; style?: React.CSSProperties }> = ({ texte, debut, t, cadence = 28, style }) => {
  const n = Math.floor(Math.max(0, t - debut) * cadence);
  return <span style={style}>{texte.slice(0, n)}<span style={{ opacity: 0 }}>{texte.slice(n)}</span></span>;
};

export const interp = interpolate;
