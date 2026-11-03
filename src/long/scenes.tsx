import React from "react";
import { Icon } from "../infographie/icons";
import { ease, FPS, SceneClock } from "../infographie/scenes";
import { GIANT, UI, type Theme } from "../infographie/themes";
import type { SceneParams, Word } from "../infographie/types";

/**
 * Les dix scènes de `src/infographie/scenes.tsx`, redessinées pour le 16:9 (1920×1080).
 * Mêmes paramètres, mêmes animations (`ease`), mêmes thèmes ; seule la mise en page change.
 */
export const LW = 1920;
export const LH = 1080;

type Ctx<T extends keyof SceneParams> = { p: SceneParams[T]; l: number; th: Theme; words: Word[]; t: number };

const Card: React.FC<{ th: Theme; children: React.ReactNode; style?: React.CSSProperties }> = ({ th, children, style }) => {
  const l = React.useContext(SceneClock);
  const shine = ease(l, 8, 42);
  return (
    <div style={{ position: "relative", overflow: "hidden", background: th.card, border: `2px solid ${th.line}`, borderRadius: 40, padding: 48, boxShadow: th.dark ? `0 30px 80px rgba(0,0,0,.45), 0 0 80px ${th.accent}26` : `0 24px 60px rgba(20,40,30,.14), 0 0 60px ${th.accent}22`, ...style }}>
      {children}
      {/* reflet qui traverse la carte à son arrivée */}
      <div style={{ position: "absolute", top: -40, bottom: -40, width: 260, left: `${-35 + shine * 150}%`, transform: "skewX(-18deg)", background: `linear-gradient(90deg, transparent, ${th.dark ? "rgba(255,255,255,.12)" : "rgba(255,255,255,.7)"}, transparent)`, opacity: shine < 1 ? 1 : 0, pointerEvents: "none" }} />
    </div>
  );
};
const Kicker: React.FC<{ th: Theme; children: React.ReactNode; color?: string }> = ({ th, children, color }) => (
  <div style={{ fontFamily: UI, fontSize: 34, fontWeight: 700, letterSpacing: 6, textTransform: "uppercase", color: color ?? th.accent }}>{children}</div>
);
/** Zone des scènes : au-dessus du bandeau de sous-titres. */
const Stage: React.FC<{ children: React.ReactNode; row?: boolean }> = ({ children, row }) => (
  <div style={{ position: "absolute", left: 90, right: 90, top: 125, height: 665, display: "flex", flexDirection: row ? "row" : "column", justifyContent: "center", alignItems: "center", gap: row ? 110 : 28 }}>{children}</div>
);
const fmt = (n: number, d = 0) => {
  const [i, f] = n.toFixed(d).split(".");
  const g = i.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return f ? `${g},${f}` : g;
};
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");

/* ─────────── Gros sous-titres ─────────── */
export const TitreGeant: React.FC<Ctx<"titre-geant">> = ({ p, th, words, t }) => {
  const n = words.length;
  const size = n <= 3 ? 270 : n <= 5 ? 225 : n <= 8 ? 175 : n <= 11 ? 142 : 120;
  const accents = (p.accents ?? []).map(norm);
  return (
    <div style={{ position: "absolute", left: 100, right: 100, top: 110, height: 860, display: "flex", flexWrap: "wrap", alignContent: "center", justifyContent: "center", gap: `0 ${size * 0.2}px`, textAlign: "center" }}>
      {words.map((w, k) => {
        const s0 = w.start * FPS;
        const f = t * FPS;
        const pop = ease(f, s0, s0 + 7);
        const hot = accents.includes(norm(w.w)) || /\d/.test(w.w);
        const act = t >= w.start && t < w.end;
        return (
          <span key={k} style={{
            display: "inline-block", fontFamily: GIANT, fontSize: size, lineHeight: 1.12, textTransform: "uppercase",
            color: hot ? th.accent : th.ink, opacity: f >= s0 - 1 ? 1 : 0,
            transform: `translateY(${(1 - pop) * 90 * (k % 2 ? 1 : -1)}px) scale(${0.55 + 0.45 * pop + (act ? 0.05 : 0)}) rotate(${(1 - pop) * 4 * (k % 2 ? 1 : -1)}deg)`,
          }}>{w.w.replace(/[.,:?!]/g, "")}</span>
        );
      })}
    </div>
  );
};

/* ─────────── Gros chiffre ─────────── */
export const Chiffre: React.FC<Ctx<"chiffre">> = ({ p, l, th }) => {
  const v = ease(l, 4, 36) * p.valeur;
  return (
    <Stage>
      <Card th={th} style={{ width: 1250, textAlign: "center", transform: `translateY(${ease(l, 0, 14, 60, 0)}px)`, opacity: ease(l, 0, 8) }}>
        <Kicker th={th}>{p.etiquette}</Kicker>
        <div style={{ fontFamily: GIANT, fontSize: 300, lineHeight: 1.05, color: th.ink, marginTop: 12 }}>
          {p.prefixe}{fmt(v, p.decimales ?? 0)}<span style={{ color: th.accent }}>{p.suffixe}</span>
        </div>
        {p.sous && <div style={{ fontFamily: UI, fontSize: 42, color: th.muted, marginTop: 10 }}>{p.sous}</div>}
      </Card>
    </Stage>
  );
};

/* ─────────── Barres ─────────── */
export const Barres: React.FC<Ctx<"barres">> = ({ p, l, th }) => {
  const max = Math.max(...p.barres.map((b) => b.valeur));
  const H0 = 340;
  const n = p.barres.length;
  const bw = Math.min(260, 1250 / n - 70);
  return (
    <Stage>
      <Card th={th} style={{ width: 1500, opacity: ease(l, 0, 8), position: "relative" }}>
        {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
        {p.badge && (
          <div style={{ position: "absolute", right: 40, top: 26, background: th.hot, color: th.dark ? "#07100C" : "#2A1B00", fontFamily: UI, fontWeight: 700, fontSize: 46, padding: "6px 28px", borderRadius: 100, transform: `scale(${ease(l, 34, 44, 0.3, 1)})`, opacity: ease(l, 34, 40) }}>{p.badge}</div>
        )}
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "center", gap: 70, height: H0 + 130, marginTop: 12 }}>
          {p.barres.map((b, i) => {
            const g = ease(l, 6 + i * 8, 40 + i * 8);
            const h = (b.valeur / max) * H0 * g;
            return (
              <div key={i} style={{ width: bw, textAlign: "center" }}>
                <div style={{ fontFamily: UI, fontSize: 70, fontWeight: 700, color: th.ink, opacity: g, height: 84 }}>{fmt(Math.round(b.valeur * g))}</div>
                <div style={{ height: h, background: b.accent ? th.accent : th.line, borderRadius: 20, position: "relative", overflow: "hidden", marginTop: 6 }}>
                  {b.part != null && <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: (b.part / max) * H0 * g, background: th.hot }} />}
                </div>
                <div style={{ fontFamily: UI, fontSize: 36, color: th.muted, marginTop: 14 }}>{b.label}</div>
              </div>
            );
          })}
        </div>
      </Card>
    </Stage>
  );
};

/* ─────────── Courbe qui bute sur un plafond ─────────── */
export const Courbe: React.FC<Ctx<"courbe">> = ({ p, l, th }) => {
  const g = ease(l, 4, 46);
  const x0 = 70, x1 = 1230, yBase = 380, yTop = 50;
  const wish = (u: number) => yBase - u * (yBase - yTop) * 0.95;
  const capY = yBase - p.plafond * (yBase - yTop);
  const pts = Array.from({ length: 41 }, (_, k) => k / 40).filter((u) => u <= g);
  const X = (u: number) => x0 + u * (x1 - x0);
  const real = pts.map((u) => `${X(u)},${Math.max(capY, wish(u))}`).join(" ");
  const ghost = pts.map((u) => `${X(u)},${wish(u)}`).join(" ");
  return (
    <Stage>
      <Card th={th} style={{ width: 1500, opacity: ease(l, 0, 8) }}>
        {p.titre && <Kicker th={th} color={th.alert}>{p.titre}</Kicker>}
        <svg width="1404" height="430" viewBox="0 0 1300 430" style={{ marginTop: 12 }}>
          <line x1={x0} x2={x1 + 40} y1={capY} y2={capY} stroke={th.alert} strokeWidth="6" strokeDasharray="22 14" />
          <text x={x1 + 40} y={capY - 16} textAnchor="end" fontSize="40" fontWeight="700" fill={th.alert} fontFamily={UI}>{p.etiquettePlafond}</text>
          <polyline points={ghost} fill="none" stroke={th.muted} strokeWidth="6" strokeDasharray="3 15" strokeLinecap="round" opacity=".7" />
          <polyline points={real} fill="none" stroke={th.accent} strokeWidth="14" strokeLinecap="round" strokeLinejoin="round" />
          <text x={x0} y="420" fontSize="34" fill={th.muted} fontFamily={UI}>{p.etiquetteCourbe}</text>
        </svg>
      </Card>
    </Stage>
  );
};

/* ─────────── Ligne du temps ─────────── */
export const LigneTemps: React.FC<Ctx<"ligne-temps">> = ({ p, l, th }) => {
  const g = ease(l, 8, 70);
  const TW = 1280;
  return (
    <Stage>
      <Card th={th} style={{ width: 1500, textAlign: "center", opacity: ease(l, 0, 8) }}>
        <Kicker th={th} color={th.hot}>{p.etiquette}</Kicker>
        <div style={{ fontFamily: GIANT, fontSize: 250, color: th.ink, lineHeight: 1.05, marginTop: 8, transform: `scale(${ease(l, 0, 12, 0.8, 1)})` }}>{p.valeur}</div>
        <div style={{ position: "relative", height: 140, margin: "30px 40px 0" }}>
          <div style={{ position: "absolute", left: 20, right: 20, top: 50, height: 12, borderRadius: 6, background: th.line }} />
          <div style={{ position: "absolute", left: 20, top: 50, height: 12, borderRadius: 6, background: th.accent, width: TW * g }} />
          <div style={{ position: "absolute", left: 0, top: 26, width: 60, height: 60, borderRadius: 30, background: th.accent, border: `8px solid ${th.card}` }} />
          <div style={{ position: "absolute", left: 20 + TW * g - 30, top: 26, width: 60, height: 60, borderRadius: 30, background: th.hot, border: `8px solid ${th.card}` }} />
          <div style={{ position: "absolute", left: 0, top: 96, fontFamily: UI, fontSize: 42, fontWeight: 700, color: th.muted }}>{p.de}</div>
          <div style={{ position: "absolute", right: 0, top: 96, fontFamily: UI, fontSize: 42, fontWeight: 700, color: th.muted }}>{p.a}</div>
        </div>
      </Card>
    </Stage>
  );
};

/* ─────────── Anneau ─────────── */
export const Anneau: React.FC<Ctx<"anneau">> = ({ p, l, th }) => {
  const R = 215, C = 2 * Math.PI * R;
  const g = ease(l, 4, 60) * p.valeur;
  const ang = ((p.repere ?? 0) / 100) * 360 - 90;
  return (
    <Stage row>
      <Card th={th} style={{ opacity: ease(l, 0, 8), padding: 40 }}>
        <svg width="540" height="540" viewBox="0 0 540 540">
          <circle cx="270" cy="270" r={R} fill="none" stroke={th.line} strokeWidth="62" />
          <circle cx="270" cy="270" r={R} fill="none" stroke={th.accent} strokeWidth="62" strokeDasharray={`${(C * g) / 100} ${C}`} transform="rotate(-90 270 270)" />
          {p.repere != null && (
            <line x1={270 + (R - 44) * Math.cos((ang * Math.PI) / 180)} y1={270 + (R - 44) * Math.sin((ang * Math.PI) / 180)} x2={270 + (R + 44) * Math.cos((ang * Math.PI) / 180)} y2={270 + (R + 44) * Math.sin((ang * Math.PI) / 180)} stroke={th.hot} strokeWidth="12" strokeLinecap="round" opacity={ease(l, 50, 60)} />
          )}
          <text x="270" y="296" textAnchor="middle" fontSize={p.centre.length > 5 ? 84 : 124} fontWeight="700" fill={th.ink} fontFamily={UI}>{p.centre}</text>
        </svg>
      </Card>
      <div style={{ width: 760, opacity: ease(l, 10, 24), transform: `translateX(${ease(l, 10, 24, 50, 0)}px)` }}>
        <div style={{ fontFamily: GIANT, fontSize: 120, lineHeight: 1.08, textTransform: "uppercase", color: th.ink }}>{p.etiquette}</div>
        <div style={{ height: 10, width: 160, borderRadius: 5, background: th.hot, marginTop: 24 }} />
      </div>
    </Stage>
  );
};

/* ─────────── Duel ─────────── */
export const Duel: React.FC<Ctx<"duel">> = ({ p, l, th }) => {
  const g = (i: number) => ease(l, 4 + i * 10, 34 + i * 10);
  return (
    <Stage>
      <Card th={th} style={{ width: 1500, opacity: ease(l, 0, 8) }}>
        {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
        {[p.haut, p.bas].map((s, i) => (
          <div key={i} style={{ marginTop: i === 0 ? 28 : 46 }}>
            <div style={{ fontFamily: UI, fontSize: 50, fontWeight: 700, color: i === 0 ? th.ink : th.muted, marginBottom: 14 }}>{s.titre}</div>
            <div style={{ height: 110, borderRadius: 28, background: th.line, overflow: "hidden" }}>
              <div style={{ width: `${s.part * g(i)}%`, height: "100%", background: i === 0 ? th.accent : th.muted, borderRadius: 28 }} />
            </div>
          </div>
        ))}
      </Card>
    </Stage>
  );
};

/* ─────────── Objet ─────────── */
export const Objet: React.FC<Ctx<"objet">> = ({ p, l, th }) => (
  <Stage row>
    <div style={{ position: "relative", width: 520, height: 520, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
      {[0, 1, 2].map((k) => (
        <div key={k} style={{ position: "absolute", inset: -k * 38, borderRadius: "50%", border: `4px solid ${th.accent}`, opacity: Math.max(0, 0.35 - k * 0.1) * ease(l, 0, 20), transform: `scale(${1 + 0.03 * Math.sin(l / 8 + k)})` }} />
      ))}
      <div style={{ transform: `scale(${ease(l, 0, 14, 0.4, 1)}) rotate(${Math.sin(l / 9) * 3}deg) translateY(${Math.sin(l / 7) * 10}px)` }}>
        <Icon nom={p.icone} th={th} size={420} />
      </div>
    </div>
    <div style={{ width: 880, opacity: ease(l, 8, 20), transform: `translateX(${ease(l, 8, 20, 60, 0)}px)` }}>
      <div style={{ fontFamily: GIANT, fontSize: 135, color: th.ink, textTransform: "uppercase", lineHeight: 1.05 }}>{p.titre}</div>
      {p.sous && <div style={{ fontFamily: UI, fontSize: 46, color: th.muted, marginTop: 16 }}>{p.sous}</div>}
    </div>
  </Stage>
);

/* ─────────── Question ─────────── */
export const Question: React.FC<Ctx<"question">> = ({ p, l, th }) => (
  <Stage row>
    <div style={{ fontFamily: GIANT, fontSize: 520, lineHeight: 0.9, color: th.accent, flex: "none", transform: `scale(${ease(l, 0, 14, 0.4, 1)}) rotate(${Math.sin(l / 10) * 4}deg)` }}>?</div>
    <div style={{ width: 1000 }}>
      <div style={{ fontFamily: UI, fontSize: 70, fontWeight: 700, color: th.ink, lineHeight: 1.15, opacity: ease(l, 6, 18) }}>{p.question}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 18, marginTop: 36 }}>
        {(p.pistes ?? []).map((t, i) => (
          <Card key={i} th={th} style={{ padding: "20px 28px", borderRadius: 30, opacity: ease(l, 14 + i * 7, 26 + i * 7), transform: `translateY(${ease(l, 14 + i * 7, 26 + i * 7, 40, 0)}px)` }}>
            <div style={{ fontFamily: UI, fontSize: 40, fontWeight: 700, color: th.muted, whiteSpace: "nowrap" }}>{t}</div>
          </Card>
        ))}
      </div>
    </div>
  </Stage>
);

/* ─────────── Liste ─────────── */
export const Liste: React.FC<Ctx<"liste">> = ({ p, l, th }) => {
  const fs = p.items.length > 6 ? 36 : 46;
  return (
    <Stage>
      <Card th={th} style={{ width: 1400 }}>
        {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
        {p.titre && <div style={{ height: 8 }} />}
        {p.items.map((it, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: `${fs * 0.4}px 0`, borderBottom: i < p.items.length - 1 ? `2px solid ${th.line}` : "none", opacity: ease(l, 6 + i * 9, 18 + i * 9), transform: `translateX(${ease(l, 6 + i * 9, 18 + i * 9, 50, 0)}px)` }}>
            <div style={{ fontFamily: UI, fontSize: fs, fontWeight: 700, color: th.ink }}>{it.texte}</div>
            {it.valeur && <div style={{ fontFamily: UI, fontSize: fs, fontWeight: 700, color: th.accent }}>{it.valeur}</div>}
          </div>
        ))}
      </Card>
    </Stage>
  );
};
