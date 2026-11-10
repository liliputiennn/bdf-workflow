// Format « Apprendre une langue » : style calme et lisible (papier, encre, une couleur d'accent par leçon), légende mot à mot.
// Mouvements lents, sans rebond : apparition douce, souligné qui se trace sous le mot dit, fondu entre les leçons.
// Toutes les durées arrivent en secondes depuis Python (formats/rendu_remotion.py).
import React from "react";
import { AbsoluteFill, random } from "remotion";
import { Grain, SERIF, TEXT, clamp01, hexRgb, lerp, out, rgba, useSeconds } from "./kit";

export type MotT = { w: string; s: number; e: number };
export type Lecon = { fr: string; cible: string; phonetique?: string | null; t_f: number; t_c: number; t_l: number; fin_l: number; suite: number; mots_c: MotT[]; mots_l: MotT[] };
export type LangueProps = {
  w: number; h: number; fps: number; total: number;
  chaine: string; langue: string; situation: string; t_outro: number;
  lecons: Lecon[];
};

// Papier + encre + un accent : quatre ambiances douces qui se succèdent.
const TONS = [
  { fond: "#F4ECDD", encre: "#2A2622", doux: "#7A6F63", accent: "#C0603A", halo: ["#F0D3B4", "#F7E3C8"] },
  { fond: "#E9EEE3", encre: "#23302A", doux: "#6B7A70", accent: "#3E7A68", halo: ["#CFE0D0", "#E1EBD8"] },
  { fond: "#F3E6E1", encre: "#35262A", doux: "#86706F", accent: "#A5495B", halo: ["#EBCFCB", "#F4DAD2"] },
  { fond: "#E7E9F0", encre: "#262A38", doux: "#6E7488", accent: "#4F5FA3", halo: ["#CDD3E8", "#DDE0EE"] },
];

const mixHex = (a: string, b: string, k: number) => {
  const x = hexRgb(a), y = hexRgb(b);
  return `rgb(${[0, 1, 2].map((i) => Math.round(lerp(x[i], y[i], k))).join(",")})`;
};

const tailleCible = (txt: string) => {
  const n = txt.length;
  return n <= 14 ? 210 : n <= 24 ? 168 : n <= 38 ? 132 : 104;
};

/** Phrase mot à mot : les mots à venir sont pâles, le mot dit s'éclaire et un trait se dessine dessous, les mots passés restent à l'encre. */
const Phrase: React.FC<{ mots: MotT[]; t: number; debut: number; taille: number; ton: (typeof TONS)[number]; fin: number }> = ({ mots, t, debut, taille, ton, fin }) => (
  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: `${taille * 0.12}px ${taille * 0.28}px`, fontFamily: SERIF, fontWeight: 400, fontSize: taille, lineHeight: 1.08, letterSpacing: -taille * 0.015, textAlign: "center" }}>
    {mots.map((m, i) => {
      const entree = out(clamp01((t - (debut + i * 0.07)) / 0.7));
      const dit = t >= m.s - 0.03;
      const actif = dit && t < Math.max(m.e, m.s + 0.2) + 0.05;
      const trait = out(clamp01((t - m.s) / 0.35));
      const eclat = dit ? 1 : t < fin ? 0.28 : 1;
      return (
        <span key={i} style={{ position: "relative", display: "inline-block", opacity: entree * eclat, transform: `translateY(${(1 - entree) * 26}px)`, color: actif ? ton.accent : ton.encre, transition: "none" }}>
          {m.w}
          <span style={{ position: "absolute", left: 0, right: 0, bottom: -taille * 0.04, height: Math.max(5, taille * 0.045), borderRadius: 99, background: ton.accent, transformOrigin: "left center", transform: `scaleX(${dit && !(!actif && t >= m.e + 0.4) ? trait : 0})`, opacity: actif ? 0.9 : 0 }} />
        </span>
      );
    })}
  </div>
);

const Anneau: React.FC<{ p: number; taille: number; ton: (typeof TONS)[number]; t: number }> = ({ p, taille, ton, t }) => {
  const R = taille * 0.46, S = taille, C = 2 * Math.PI * R;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: taille * 0.3 }}>
      <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
        <circle cx={S / 2} cy={S / 2} r={R} stroke={rgba(ton.encre, 0.12)} strokeWidth={taille * 0.05} fill="none" />
        <circle cx={S / 2} cy={S / 2} r={R} stroke={ton.accent} strokeWidth={taille * 0.05} fill="none" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * p} transform={`rotate(-90 ${S / 2} ${S / 2})`} />
        <circle cx={S / 2} cy={S / 2} r={taille * (0.1 + 0.02 * Math.sin(t * 2.2))} fill={ton.accent} opacity={0.85} />
      </svg>
      <span style={{ fontFamily: SERIF, fontSize: taille * 0.6, color: ton.encre }}>À toi, répète.</span>
    </div>
  );
};

export const LangueVideo: React.FC<LangueProps> = (p) => {
  const { t } = useSeconds();
  const { w, h } = p;
  const portrait = h > w;
  const e = portrait ? w / 1080 : (w / 1280) * 0.85;
  const n = p.lecons.length;
  const cur = Math.max(-1, ...p.lecons.map((l, i) => (t >= l.t_f - 0.05 ? i : -1)));
  const outro = t >= p.t_outro - 0.05;
  const idx = cur < 0 ? 0 : outro ? n : cur;
  const l = cur >= 0 ? p.lecons[cur] : null;

  // couleurs : mélange doux autour de chaque frontière
  const bornes = [0, ...p.lecons.map((x) => x.t_f), p.t_outro];
  const tonDe = (i: number) => TONS[((i % TONS.length) + TONS.length) % TONS.length];
  let a = tonDe(idx), mix = 0, b = a;
  for (let i = 1; i < bornes.length; i++) {
    const k = clamp01((t - (bornes[i] - 0.5)) / 1.0);
    if (k > 0 && k < 1) { a = tonDe(i - 1); b = tonDe(i); mix = out(k); }
  }
  const ton = { fond: mixHex(a.fond, b.fond, mix), encre: mixHex(a.encre, b.encre, mix), doux: mixHex(a.doux, b.doux, mix), accent: mixHex(a.accent, b.accent, mix), halo: [mixHex(a.halo[0], b.halo[0], mix), mixHex(a.halo[1], b.halo[1], mix)] };

  // fondu de contenu : sort 0,4 s avant la frontière suivante, entre 0,5 s après la précédente
  let fondu = 1;
  for (let i = 1; i < bornes.length; i++) {
    const b0 = bornes[i] - 0.05;
    if (t > b0 - 0.5 && t < b0 + 0.6) fondu = t < b0 ? 1 - out(clamp01((t - (b0 - 0.5)) / 0.5)) : out(clamp01((t - b0) / 0.6));
  }

  // décor : deux grands disques doux qui dérivent lentement, grain papier
  const dérive = (i: number, s: number) => ({ x: Math.sin(t * 0.08 * s + i * 2.1) * w * 0.06, y: Math.cos(t * 0.06 * s + i * 1.3) * h * 0.04 });
  const lettrine = (txt: string) => txt.toUpperCase();

  return (
    <AbsoluteFill style={{ background: ton.fond, overflow: "hidden" }}>
      {[0, 1].map((i) => {
        const d = dérive(i, 1);
        const R = (i ? 0.62 : 0.8) * Math.min(w, h) * (portrait ? 1.1 : 1);
        return <div key={i} style={{ position: "absolute", left: (i ? w * 0.78 : w * 0.12) - R + d.x, top: (i ? h * 0.74 : h * 0.2) - R + d.y, width: R * 2, height: R * 2, borderRadius: "50%", background: ton.halo[i], opacity: 0.75 }} />;
      })}
      {/* fine bordure de page */}
      <div style={{ position: "absolute", inset: 34 * e, border: `${2 * e}px solid ${rgba(ton.encre, 0.12)}`, borderRadius: 26 * e }} />

      {/* en-tête : langue, situation, progression en petits traits */}
      <div style={{ position: "absolute", top: 92 * e, left: 0, right: 0, textAlign: "center", fontFamily: TEXT, fontWeight: 600, fontSize: 28 * e, letterSpacing: 7 * e, color: ton.doux }}>{lettrine(`${p.langue}  ·  ${p.situation}`)}</div>
      <div style={{ position: "absolute", top: 150 * e, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 14 * e }}>
        {p.lecons.map((x, i) => {
          const prog = i < cur ? 1 : i === cur ? clamp01((t - x.t_f) / Math.max(0.1, x.suite - x.t_f)) : 0;
          return <div key={i} style={{ width: 70 * e, height: 5 * e, borderRadius: 4, background: rgba(ton.encre, 0.14), overflow: "hidden" }}><div style={{ width: `${prog * 100}%`, height: "100%", background: ton.accent }} /></div>;
        })}
      </div>

      <AbsoluteFill style={{ opacity: fondu, alignItems: "center", justifyContent: "center", padding: `0 ${80 * e}px` }}>
        {cur < 0 && (
          <div style={{ textAlign: "center" }}>
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: `0 ${36 * e}px`, fontFamily: SERIF, fontWeight: 400, fontSize: 190 * e, lineHeight: 1.04, color: ton.encre, letterSpacing: -4 * e }}>
              {p.situation.split(" ").map((m, i) => {
                const k = out(clamp01((t - (0.2 + i * 0.25)) / 1.0));
                return <span key={i} style={{ display: "inline-block", opacity: k, transform: `translateY(${(1 - k) * 40}px)` }}>{m}</span>;
              })}
            </div>
            <div style={{ margin: `${50 * e}px auto 0`, width: 120 * e * out(clamp01((t - 0.9) / 0.8)), height: 5 * e, borderRadius: 4, background: ton.accent }} />
            <div style={{ marginTop: 44 * e, fontFamily: TEXT, fontWeight: 400, fontSize: 46 * e, color: ton.doux, opacity: out(clamp01((t - 1.2) / 0.8)) }}>{n} phrases à retenir</div>
          </div>
        )}

        {l && !outro && (() => {
          const lent = t >= l.t_l - 0.05;
          const mots = lent ? l.mots_l : l.mots_c;
          const debutMots = lent ? l.t_l : l.t_c;
          const fin = lent ? l.fin_l : l.t_l;
          const taille = tailleCible(l.cible) * e * (portrait ? 1 : 0.8);
          const repete = t >= l.fin_l + 0.1 && t < l.suite;
          const entF = out(clamp01((t - l.t_f) / 0.8));
          const entC = out(clamp01((t - l.t_c) / 0.8));
          return (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%", gap: 70 * e }}>
              <div style={{ textAlign: "center", opacity: entF, transform: `translateY(${(1 - entF) * 24}px)` }}>
                <div style={{ fontFamily: TEXT, fontWeight: 600, fontSize: 26 * e, letterSpacing: 6 * e, color: ton.accent, marginBottom: 20 * e }}>EN FRANÇAIS</div>
                <div style={{ fontFamily: TEXT, fontWeight: 400, fontSize: 56 * e, lineHeight: 1.25, color: ton.doux, maxWidth: w - 220 * e }}>{l.fr}</div>
              </div>
              <div style={{ width: 90 * e, height: 3 * e, background: rgba(ton.encre, 0.25), opacity: entF }} />
              {t >= l.t_c - 0.1 && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 46 * e, opacity: entC }}>
                  {lent && <div style={{ fontFamily: TEXT, fontWeight: 600, fontSize: 26 * e, letterSpacing: 6 * e, color: ton.accent }}>PLUS LENTEMENT</div>}
                  <Phrase mots={mots} t={t} debut={debutMots - 0.05} taille={taille} ton={ton} fin={fin} />
                  {l.phonetique && (
                    <div style={{ fontFamily: TEXT, fontWeight: 400, fontSize: 44 * e, color: ton.doux, opacity: out(clamp01((t - l.t_c - 0.4) / 0.8)) }}>« {l.phonetique} »</div>
                  )}
                </div>
              )}
              {repete && (
                <div style={{ position: "absolute", bottom: (portrait ? 270 : 80) * e, opacity: out(clamp01((t - l.fin_l - 0.1) / 0.6)) }}>
                  <Anneau p={clamp01((t - l.fin_l - 0.1) / Math.max(0.1, l.suite - l.fin_l - 0.15))} taille={110 * e} ton={ton} t={t} />
                </div>
              )}
            </div>
          );
        })()}

        {outro && (
          <div style={{ textAlign: "center", opacity: out(clamp01((t - p.t_outro) / 1.0)) }}>
            <div style={{ fontFamily: SERIF, fontWeight: 400, fontSize: 260 * e, color: ton.encre, letterSpacing: -6 * e }}>À toi.</div>
            <div style={{ margin: `${30 * e}px auto 0`, width: 120 * e, height: 5 * e, borderRadius: 4, background: ton.accent }} />
            <div style={{ fontFamily: TEXT, fontWeight: 400, fontSize: 54 * e, color: ton.doux, marginTop: 40 * e }}>Répète à voix haute.</div>
          </div>
        )}
      </AbsoluteFill>

      <div style={{ position: "absolute", bottom: 92 * e, left: 0, right: 0, textAlign: "center", fontFamily: TEXT, fontWeight: 600, fontSize: 24 * e, letterSpacing: 6 * e, color: rgba(ton.encre, 0.4) }}>{lettrine(p.chaine)}</div>
      <Grain opacite={0.1} />
    </AbsoluteFill>
  );
};
void random;
