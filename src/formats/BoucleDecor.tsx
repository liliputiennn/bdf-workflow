// Décors vivants en boucle parfaite (30 s) pour les formats SOMMEIL et MÉDITATION : la vidéo est bouclée par ffmpeg sur toute la durée.
// Règle : tout mouvement est périodique sur `boucle` secondes (fréquences entières), la boucle se raccorde sans saut.
import React from "react";
import { AbsoluteFill, random } from "remotion";
import { DISPLAY, Grain, SERIF, TEXT, Vignette, clamp01, rgba, useSeconds } from "./kit";

export type BoucleProps = { w: number; h: number; fps: number; boucle: number; format: "sommeil" | "meditation"; decor: string; graine: number; titre?: string };

const TAU = Math.PI * 2;
const per = (t: number, boucle: number, cycles: number, dephasage = 0) => Math.sin((t / boucle) * TAU * cycles + dephasage);

/** Relief : somme de sinus à fréquences entières sur la largeur => profil quelconque, déterministe. */
const colline = (w: number, h: number, base: number, amp: number, graine: string, pas = 12) => {
  const ph = [0, 1, 2].map((i) => random(`${graine}p${i}`) * TAU);
  const pts: string[] = [];
  for (let x = 0; x <= w + pas; x += pas) {
    const u = x / w;
    const y = h * base - amp * (0.5 + 0.3 * Math.sin(u * TAU * 1 + ph[0]) + 0.2 * Math.sin(u * TAU * 2 + ph[1]) + 0.1 * Math.sin(u * TAU * 4 + ph[2]));
    pts.push(`${x},${y.toFixed(1)}`);
  }
  return `M0,${h} L${pts.join(" L")} L${w},${h} Z`;
};

const Etoiles: React.FC<{ w: number; h: number; boucle: number; graine: number; zoneH: number; n: number; couleur: string }> = ({ w, h, boucle, graine, zoneH, n, couleur }) => {
  const { t } = useSeconds();
  return (
    <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
      {Array.from({ length: n }, (_, i) => {
        const couche = i % 3; // 0 loin, 2 proche
        const x0 = random(`${graine}x${i}`) * w;
        const y = random(`${graine}y${i}`) * zoneH;
        const derive = (couche + 1) * (w * 0.5); // un nombre entier de largeurs par boucle ne raccorderait pas : on dérive d'une demi-largeur et on revient
        const x = (((x0 + (per(t, boucle, 1) * 0.5 + 0.5) * derive * 0.08) % w) + w) % w;
        const r = 0.8 + couche * 0.7 + random(`${graine}r${i}`) * 1.2;
        const cyc = 1 + Math.floor(random(`${graine}c${i}`) * 4);
        const a = 0.35 + 0.65 * (0.5 + 0.5 * per(t, boucle, cyc, random(`${graine}d${i}`) * TAU));
        return <circle key={i} cx={x} cy={y} r={r} fill={couleur} opacity={a} />;
      })}
    </svg>
  );
};

const Brume: React.FC<{ w: number; h: number; boucle: number; couleur: string; lignes: { y: number; a: number; cyc: number }[] }> = ({ w, h, boucle, couleur, lignes }) => {
  const { t } = useSeconds();
  return (
    <>
      {lignes.map((b, i) => {
        const x = (((t / boucle) * b.cyc) % 1) * (w + 900) - 450;
        return <div key={i} style={{ position: "absolute", left: x - 450, top: h * b.y - 70, width: 900, height: 140, borderRadius: "50%", background: `radial-gradient(ellipse at center, ${rgba(couleur, b.a)} 0%, ${rgba(couleur, 0)} 70%)` }} />;
      })}
    </>
  );
};

const Aurore: React.FC<{ w: number; h: number; boucle: number; couleurs: string[] }> = ({ w, h, boucle, couleurs }) => {
  const { t } = useSeconds();
  return (
    <svg width={w} height={h} style={{ position: "absolute", inset: 0, mixBlendMode: "screen" }}>
      <defs>
        {couleurs.map((c, i) => (
          <linearGradient key={i} id={`au${i}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={c} stopOpacity="0" />
            <stop offset="0.5" stopColor={c} stopOpacity="0.38" />
            <stop offset="1" stopColor={c} stopOpacity="0" />
          </linearGradient>
        ))}
      </defs>
      {couleurs.map((c, i) => {
        const pts: string[] = [];
        for (let x = 0; x <= w; x += 20) {
          const u = x / w;
          const y = h * (0.22 + i * 0.07) + 46 * Math.sin(u * TAU * (1 + i) + (t / boucle) * TAU * (1 + (i % 2)) + i) + 20 * Math.sin(u * TAU * 3 - (t / boucle) * TAU);
          pts.push(`${x},${y.toFixed(1)}`);
        }
        return <path key={i} d={`M0,${h * 0.55} L${pts.join(" L")} L${w},${h * 0.55} Z`} fill={`url(#au${i})`} opacity={0.8} />;
      })}
    </svg>
  );
};

// ------------------------------------------------------------------ SOMMEIL
const Nuit: React.FC<BoucleProps> = ({ w, h, boucle, decor, graine }) => {
  const { t } = useSeconds();
  const g = String(graine);
  const lune = { x: w * (0.62 + random(g + "lx") * 0.24), y: h * (0.16 + random(g + "ly") * 0.12), r: 58 + random(g + "lr") * 20 };
  const respire = 1 + 0.025 * per(t, boucle, 3);
  const cam = 1.04 + 0.018 * per(t, boucle, 1);
  const tir = (t / boucle + 0.15) % 1; // une étoile filante par boucle
  const mer = decor === "lune-sur-mer";
  const foret = decor === "foret-brume";
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg, #03051A 0%, #0A1236 55%, #17224F 100%)", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${cam}) translate(${per(t, boucle, 1) * 10}px, ${per(t, boucle, 2) * 5}px)` }}>
        <Etoiles w={w} h={h} boucle={boucle} graine={graine} zoneH={h * 0.62} n={foret ? 90 : 190} couleur="#C9D3FF" />
        <Aurore w={w} h={h} boucle={boucle} couleurs={decor === "nuit-etoilee" ? ["#3B82F6", "#8B5CF6", "#22D3EE"] : ["#4F46E5", "#2563EB"]} />
        {/* lune : halo qui respire + croissant */}
        <div style={{ position: "absolute", left: lune.x - lune.r * 5, top: lune.y - lune.r * 5, width: lune.r * 10, height: lune.r * 10, borderRadius: "50%", background: `radial-gradient(circle, ${rgba("#E8E4D0", 0.34 * respire)} 0%, ${rgba("#9FB0E8", 0.12)} 35%, rgba(0,0,0,0) 68%)` }} />
        <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
          <defs>
            <mask id="croissant"><rect width={w} height={h} fill="black" /><circle cx={lune.x} cy={lune.y} r={lune.r} fill="white" /><circle cx={lune.x + lune.r * 0.5} cy={lune.y - 4} r={lune.r * 0.96} fill="black" /></mask>
            <radialGradient id="lg" cx="40%" cy="40%"><stop offset="0" stopColor="#FFFFFF" /><stop offset="1" stopColor="#D9D6BD" /></radialGradient>
          </defs>
          <rect width={w} height={h} fill="url(#lg)" mask="url(#croissant)" />
          {tir < 0.12 && (() => {
            const k = tir / 0.12;
            const x = w * 0.15 + k * w * 0.35, y = h * 0.08 + k * h * 0.22;
            return <line x1={x} y1={y} x2={x - 150 * (1 - k * 0.3)} y2={y - 60 * (1 - k * 0.3)} stroke="#fff" strokeWidth={3} strokeLinecap="round" opacity={Math.sin(k * Math.PI)} />;
          })()}
        </svg>
        <Brume w={w} h={h} boucle={boucle} couleur="#35478C" lignes={[{ y: 0.74, a: 0.4, cyc: 1 }, { y: 0.82, a: 0.5, cyc: 2 }, { y: 0.66, a: 0.28, cyc: 1 }]} />
        {mer ? (
          <>
            <div style={{ position: "absolute", left: 0, right: 0, top: h * 0.62, bottom: 0, background: "linear-gradient(180deg, #0B1840 0%, #050B24 100%)" }} />
            {Array.from({ length: 16 }, (_, i) => {
              const ww = lune.r * (2.4 - i * 0.1) + 14 * per(t, boucle, 2 + (i % 3), i);
              return <div key={i} style={{ position: "absolute", left: lune.x - ww / 2, top: h * 0.63 + i * 17 + 3 * per(t, boucle, 2, i), width: ww, height: 5, borderRadius: 3, background: rgba("#E8E4D0", Math.max(0.06, 0.55 - i * 0.03)) }} />;
            })}
          </>
        ) : (
          <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
            {foret ? (
              <>
                <path d={colline(w, h, 0.78, 120, g + "a")} fill="#0A1A26" />
                {Array.from({ length: 26 }, (_, i) => {
                  const x = (i / 25) * w + (random(g + "t" + i) - 0.5) * 40;
                  const hh = 120 + random(g + "th" + i) * 150;
                  const base = h * 0.9;
                  return <path key={i} d={`M${x},${base} L${x - 34},${base} L${x - 8},${base - hh * 0.5} L${x - 24},${base - hh * 0.5} L${x},${base - hh} L${x + 24},${base - hh * 0.5} L${x + 8},${base - hh * 0.5} L${x + 34},${base} Z`} fill={i % 2 ? "#06101A" : "#08141C"} />;
                })}
                <rect x={0} y={h * 0.9 - 2} width={w} height={h} fill="#050D13" />
              </>
            ) : (
              <>
                <path d={colline(w, h, 0.9, 110, g + "b")} fill="#0A1228" />
                <path d={colline(w, h, 0.97, 80, g + "c")} fill="#060B1C" />
              </>
            )}
          </svg>
        )}
      </AbsoluteFill>
      <Vignette force={0.6} />
      <Grain opacite={0.05} />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ MÉDITATION
const Souffle: React.FC<BoucleProps> = ({ w, h, boucle, decor, graine, titre }) => {
  const { t } = useSeconds();
  const g = String(graine);
  const cycle = 10; // une respiration = 10 s : 5 s d'inspiration, 5 s d'expiration
  const ph = (t % cycle) / cycle;
  const ampleur = 0.5 - 0.5 * Math.cos(ph * TAU); // 0 -> 1 -> 0
  const inspire = ph < 0.5;
  const cx = w * (0.4 + random(g + "cx") * 0.2);
  const cy = h * (decor === "souffle" ? 0.5 : 0.56);
  const R = 90 + ampleur * 60;
  const cam = 1.03 + 0.015 * per(t, boucle, 1);
  const lac = decor === "lac-doux";
  const collines = decor === "aube-collines";
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg, #2E2457 0%, #8E6FB8 52%, #F6B38E 100%)", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${cam})` }}>
        <div style={{ position: "absolute", left: cx - R * 5, top: cy - R * 5, width: R * 10, height: R * 10, borderRadius: "50%", background: `radial-gradient(circle, ${rgba("#FFD9A8", 0.55)} 0%, ${rgba("#FFB078", 0.2)} 35%, rgba(0,0,0,0) 68%)` }} />
        {/* anneaux de respiration */}
        {[0, 1, 2, 3].map((i) => {
          const k = (ampleur + i * 0.22) % 1;
          return <div key={i} style={{ position: "absolute", left: cx - (R + 40 + i * 70 * (0.6 + ampleur * 0.6)), top: cy - (R + 40 + i * 70 * (0.6 + ampleur * 0.6)), width: (R + 40 + i * 70 * (0.6 + ampleur * 0.6)) * 2, height: (R + 40 + i * 70 * (0.6 + ampleur * 0.6)) * 2, borderRadius: "50%", border: `2px solid ${rgba("#FFE9C9", 0.4 - i * 0.08)}`, opacity: 1 - k * 0.2 }} />;
        })}
        <div style={{ position: "absolute", left: cx - R, top: cy - R, width: R * 2, height: R * 2, borderRadius: "50%", background: "radial-gradient(circle at 40% 38%, #FFF3D9 0%, #FFD9A8 55%, #FFB27A 100%)", boxShadow: `0 0 ${60 + ampleur * 80}px ${rgba("#FFD9A8", 0.7)}` }} />
        {/* particules lentes */}
        {Array.from({ length: 40 }, (_, i) => {
          const x = random(g + "px" + i) * w + 14 * per(t, boucle, 1 + (i % 3), i);
          const y = (((random(g + "py" + i) - (t / boucle) * (1 + (i % 2))) % 1) + 1) % 1;
          return <div key={i} style={{ position: "absolute", left: x, top: y * h, width: 3 + (i % 4), height: 3 + (i % 4), borderRadius: "50%", background: "#FFE9C9", opacity: 0.25 + 0.5 * random(g + "po" + i) * (0.6 + 0.4 * per(t, boucle, 2, i)) }} />;
        })}
        <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
          {collines && [[0.8, 140, "#6A4C93"], [0.88, 120, "#4A3578"], [0.97, 100, "#33245E"]].map(([b, a, c], i) => <path key={i} d={colline(w, h, b as number, a as number, g + "m" + i)} fill={c as string} />)}
          {lac && (
            <>
              <path d={colline(w, h, 0.66, 60, g + "l")} fill="#6A4C93" />
              <rect x={0} y={h * 0.66} width={w} height={h} fill="#5B4488" />
              {Array.from({ length: 10 }, (_, i) => <rect key={i} x={cx - (130 - i * 8) + 8 * per(t, boucle, 2, i)} y={h * 0.68 + i * 18} width={(130 - i * 8) * 2} height={4} rx={2} fill="#FFE3B8" opacity={0.5 - i * 0.04} />)}
            </>
          )}
        </svg>
        {/* guide de respiration : la légende de la séance */}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: h * 0.1, textAlign: "center", fontFamily: SERIF, fontWeight: 300, fontSize: 74, color: "#FFF4E6", letterSpacing: 6 + ampleur * 10, textShadow: "0 4px 24px rgba(36,26,71,0.55)", opacity: 0.35 + 0.65 * Math.abs(Math.sin(ph * Math.PI)) }}>
          {inspire ? "Inspire" : "Souffle"}
        </div>
        {titre && <div style={{ position: "absolute", top: 42, left: 0, right: 0, textAlign: "center", fontFamily: TEXT, fontWeight: 600, fontSize: 26, letterSpacing: 8, color: rgba("#FFE9C9", 0.7) }}>{titre.toUpperCase()}</div>}
      </AbsoluteFill>
      <Vignette force={0.35} />
      <Grain opacite={0.05} />
    </AbsoluteFill>
  );
};

export const BoucleDecor: React.FC<BoucleProps> = (p) => (p.format === "sommeil" ? <Nuit {...p} /> : <Souffle {...p} />);
void clamp01;
void DISPLAY;
