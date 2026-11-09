import React from "react";
import { AbsoluteFill, random } from "remotion";
import { GIANT, type Theme } from "./themes";

const GLYPHS = ["€", "%", "$", "+"];

/** Particules et symboles monétaires qui montent en parallaxe : de la profondeur derrière les cartes. */
export const Particles: React.FC<{ th: Theme; f: number; w: number; h: number }> = ({ th, f, w, h }) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    {Array.from({ length: Math.round(30 * (w * h) / (1080 * 1920) + 14) }, (_, i) => {
      const r = (k: string) => random(`bdf-${i}-${k}`);
      const size = 10 + r("s") * 34;
      const depth = 0.4 + r("d") * 0.9;
      const span = h + 300;
      const y = h + 150 - ((f * (0.9 + depth * 1.6) + r("o") * span) % span);
      const x = r("x") * w + Math.sin(f / (40 + r("w") * 40) + i) * 34 * depth;
      const col = r("c") > 0.5 ? th.accent : th.hot;
      if (r("g") > 0.6) {
        return <div key={i} style={{ position: "absolute", left: x, top: y, fontFamily: GIANT, fontSize: size * 2, color: col, opacity: 0.1 + depth * 0.12, filter: `blur(${(1.4 - depth) * 3}px)` }}>{(th.glyphs ?? GLYPHS)[Math.floor(r("t") * (th.glyphs ?? GLYPHS).length)]}</div>;
      }
      return <div key={i} style={{ position: "absolute", left: x, top: y, width: size, height: size, borderRadius: "50%", background: col, opacity: 0.14 + depth * 0.16, filter: `blur(${(1.5 - depth) * 4}px)`, boxShadow: `0 0 ${size * 2}px ${col}` }} />;
    })}
  </AbsoluteFill>
);

/** Fond animé : dégradé, lueurs qui dérivent, grille, particules, faisceau. */
export const Backdrop: React.FC<{ th: Theme; f: number; w: number; h: number; opacity?: number }> = ({ th, f, w, h, opacity = 1 }) => {
  const drift = f / 9;
  const k = w > h ? 0.75 : 1; // cadre paysage : lueurs un peu moins hautes
  return (
    <AbsoluteFill style={{ opacity }}>
      <AbsoluteFill style={{ background: `linear-gradient(${th.bg[0]}, ${th.bg[1]})` }} />
      <AbsoluteFill style={{ background: `radial-gradient(${900 * (w > h ? 1.3 : 1)}px ${800 * k}px at ${25 + Math.sin(drift / 14) * 18}% ${18 + Math.cos(drift / 12) * 10}%, ${th.accent}${th.dark ? "3a" : "30"}, transparent 70%), radial-gradient(${1000 * (w > h ? 1.3 : 1)}px ${900 * k}px at ${85 + Math.cos(drift / 17) * 10}% ${82 + Math.sin(drift / 13) * 6}%, ${th.hot}${th.dark ? "26" : "28"}, transparent 70%), radial-gradient(${700 * (w > h ? 1.3 : 1)}px ${700 * k}px at ${50 + Math.sin(drift / 20) * 30}% 50%, ${th.accent}${th.dark ? "18" : "14"}, transparent 70%)` }} />
      <AbsoluteFill style={{ backgroundImage: `linear-gradient(${th.line}66 1px, transparent 1px), linear-gradient(90deg, ${th.line}66 1px, transparent 1px)`, backgroundSize: "72px 72px", backgroundPosition: `${(f * 0.25) % 72}px ${(f * 0.6) % 72}px`, opacity: th.dark ? 0.4 : 0.45 }} />
      <Particles th={th} f={f} w={w} h={h} />
      {/* faisceau lumineux qui traverse l'écran toutes les 5 secondes */}
      <div style={{ position: "absolute", top: -200, bottom: -200, width: 360, left: `${((f % 150) / 150) * 170 - 40}%`, transform: "rotate(18deg)", background: `linear-gradient(90deg, transparent, ${th.dark ? "rgba(255,255,255,.06)" : "rgba(255,255,255,.35)"}, transparent)`, pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};
