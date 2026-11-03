import React from "react";
import { Easing, interpolate } from "remotion";
import { Icon } from "./icons";
import { GIANT, UI, type Theme } from "./themes";
import type { SceneParams, Word } from "./types";

export const OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const ease = (f: number, a: number, b: number, x = 0, y = 1) =>
  interpolate(f, [a, b], [x, y], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: OUT });

export const FPS = 30;
export const W = 1080;
export const H = 1920;

type Ctx<T extends keyof SceneParams> = { p: SceneParams[T]; l: number; th: Theme; words: Word[]; t: number };

/** Image locale de la scène courante (0 = début). Hors du lecteur de Short, la valeur par défaut montre l'état final. */
export const SceneClock = React.createContext(9999);

const Card: React.FC<{ th: Theme; children: React.ReactNode; style?: React.CSSProperties }> = ({ th, children, style }) => {
  const l = React.useContext(SceneClock);
  const shine = ease(l, 8, 42);
  return (
    <div style={{ position: "relative", overflow: "hidden", background: th.card, border: `2px solid ${th.line}`, borderRadius: 48, padding: 56, boxShadow: th.dark ? `0 40px 90px rgba(0,0,0,.45), 0 0 90px ${th.accent}26` : `0 30px 70px rgba(20,40,30,.14), 0 0 70px ${th.accent}22`, ...style }}>
      {children}
      {/* reflet qui traverse la carte à son arrivée */}
      <div style={{ position: "absolute", top: -40, bottom: -40, width: 280, left: `${-35 + shine * 150}%`, transform: "skewX(-18deg)", background: `linear-gradient(90deg, transparent, ${th.dark ? "rgba(255,255,255,.12)" : "rgba(255,255,255,.7)"}, transparent)`, opacity: shine < 1 ? 1 : 0, pointerEvents: "none" }} />
    </div>
  );
};
const Kicker: React.FC<{ th: Theme; children: React.ReactNode; color?: string }> = ({ th, children, color }) => (
  <div style={{ fontFamily: UI, fontSize: 40, fontWeight: 700, letterSpacing: 7, textTransform: "uppercase", color: color ?? th.accent }}>{children}</div>
);
const Stage: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ position: "absolute", left: 60, right: 60, top: 250, height: 1160, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", gap: 36 }}>{children}</div>
);
const fmt = (n: number, d = 0) => {
  const [i, f] = n.toFixed(d).split(".");
  const g = i.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return f ? `${g},${f}` : g;
};

/* ─────────── Gros sous-titres : les mots claquent au rythme de la voix ─────────── */
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");

export const TitreGeant: React.FC<Ctx<"titre-geant">> = ({ p, th, words, t }) => {
  const n = words.length;
  const size = n <= 4 ? 250 : n <= 6 ? 215 : n <= 8 ? 185 : 160;
  const accents = (p.accents ?? []).map(norm);
  return (
    <div style={{ position: "absolute", left: 70, right: 70, top: 220, height: 1240, display: "flex", flexWrap: "wrap", alignContent: "center", justifyContent: "center", gap: `0 ${size * 0.2}px`, textAlign: "center" }}>
      {words.map((w, k) => {
        const s0 = w.start * FPS;
        const f = t * FPS;
        const pop = ease(f, s0, s0 + 7);
        const hot = accents.includes(norm(w.w)) || /\d/.test(w.w);
        const act = t >= w.start && t < w.end;
        return (
          <span key={k} style={{
            display: "inline-block", fontFamily: GIANT, fontSize: size, lineHeight: 1.02, textTransform: "uppercase",
            color: hot ? th.accent : th.ink, opacity: f >= s0 - 1 ? 1 : 0,
            transform: `translateY(${(1 - pop) * 110 * (k % 2 ? 1 : -1)}px) scale(${0.55 + 0.45 * pop + (act ? 0.05 : 0)}) rotate(${(1 - pop) * 5 * (k % 2 ? 1 : -1)}deg)`,
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
      <Card th={th} style={{ width: 900, textAlign: "center", transform: `translateY(${ease(l, 0, 14, 70, 0)}px)`, opacity: ease(l, 0, 8) }}>
        <Kicker th={th}>{p.etiquette}</Kicker>
        <div style={{ fontFamily: GIANT, fontSize: `${p.prefixe ?? ""}${fmt(p.valeur, p.decimales ?? 0)}${p.suffixe ?? ""}`.length > 5 ? 230 : 340, lineHeight: 1.05, color: th.ink, marginTop: 20, whiteSpace: "nowrap", textShadow: `0 0 80px ${th.accent}66`, transform: `scale(${1 + 0.05 * Math.max(0, 1 - Math.abs(l - 36) / 8)})` }}>
          {p.prefixe}{fmt(v, p.decimales ?? 0)}<span style={{ color: th.accent }}>{p.suffixe}</span>
        </div>
        {p.sous && <div style={{ fontFamily: UI, fontSize: 46, color: th.muted, marginTop: 16 }}>{p.sous}</div>}
      </Card>
    </Stage>
  );
};

/* ─────────── Barres ─────────── */
export const Barres: React.FC<Ctx<"barres">> = ({ p, l, th }) => {
  const max = Math.max(...p.barres.map((b) => b.valeur));
  const H0 = p.badge ? 480 : 540;
  return (
    <Stage>
      <Card th={th} style={{ width: 940, opacity: ease(l, 0, 8), position: "relative" }}>
        {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
        {p.badge && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
            <div style={{ background: th.hot, color: th.dark ? "#07100C" : "#2A1B00", fontFamily: UI, fontWeight: 700, fontSize: 50, padding: "8px 30px", borderRadius: 100, transform: `scale(${ease(l, 34, 44, 0.3, 1)})`, opacity: ease(l, 34, 40) }}>{p.badge}</div>
          </div>
        )}
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "center", gap: 90, height: H0 + 150, marginTop: 20 }}>
          {p.barres.map((b, i) => {
            const g = ease(l, 6 + i * 8, 40 + i * 8);
            const h = (b.valeur / max) * H0 * g;
            return (
              <div key={i} style={{ width: 260, textAlign: "center" }}>
                <div style={{ fontFamily: UI, fontSize: 84, fontWeight: 700, color: th.ink, opacity: g, height: 100 }}>{fmt(Math.round(b.valeur * g))}</div>
                <div style={{ height: h, background: b.accent ? th.accent : th.line, borderRadius: 22, position: "relative", overflow: "hidden", marginTop: 8, boxShadow: b.accent ? `0 0 50px ${th.accent}88` : "none" }}>
                  {b.part != null && <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: (b.part / max) * H0 * g, background: th.hot }} />}
                </div>
                <div style={{ fontFamily: UI, fontSize: 40, color: th.muted, marginTop: 18 }}>{b.label}</div>
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
  const x0 = 70, x1 = 840, yBase = 540, yTop = 60;
  const wish = (u: number) => yBase - u * (yBase - yTop) * 0.95;
  const capY = yBase - p.plafond * (yBase - yTop);
  const pts = Array.from({ length: 41 }, (_, k) => k / 40).filter((u) => u <= g);
  const X = (u: number) => x0 + u * (x1 - x0);
  const real = pts.map((u) => `${X(u)},${Math.max(capY, wish(u))}`).join(" ");
  const ghost = pts.map((u) => `${X(u)},${wish(u)}`).join(" ");
  return (
    <Stage>
      <Card th={th} style={{ width: 940, opacity: ease(l, 0, 8) }}>
        {p.titre && <Kicker th={th} color={th.alert}>{p.titre}</Kicker>}
        <svg width="860" height="640" viewBox="0 0 900 640" style={{ marginTop: 20 }}>
          <line x1={x0} x2={x1 + 40} y1={capY} y2={capY} stroke={th.alert} strokeWidth="7" strokeDasharray="22 14" />
          <text x={x1 + 40} y={capY - 20} textAnchor="end" fontSize="44" fontWeight="700" fill={th.alert} fontFamily={UI}>{p.etiquettePlafond}</text>
          <polyline points={ghost} fill="none" stroke={th.muted} strokeWidth="7" strokeDasharray="3 16" strokeLinecap="round" opacity=".7" />
          <polyline points={real} fill="none" stroke={th.accent} strokeWidth="16" strokeLinecap="round" strokeLinejoin="round" />
          <text x={x0} y="610" fontSize="38" fill={th.muted} fontFamily={UI}>{p.etiquetteCourbe}</text>
        </svg>
      </Card>
    </Stage>
  );
};

/* ─────────── Ligne du temps : une valeur qui ne bouge pas ─────────── */
export const LigneTemps: React.FC<Ctx<"ligne-temps">> = ({ p, l, th }) => {
  const g = ease(l, 8, 70);
  return (
    <Stage>
      <Card th={th} style={{ width: 940, textAlign: "center", opacity: ease(l, 0, 8) }}>
        <Kicker th={th} color={th.hot}>{p.etiquette}</Kicker>
        <div style={{ fontFamily: GIANT, fontSize: 300, color: th.ink, lineHeight: 1.05, marginTop: 14, transform: `scale(${ease(l, 0, 12, 0.8, 1)})` }}>{p.valeur}</div>
        <div style={{ position: "relative", height: 150, marginTop: 40 }}>
          <div style={{ position: "absolute", left: 20, right: 20, top: 60, height: 12, borderRadius: 6, background: th.line }} />
          <div style={{ position: "absolute", left: 20, top: 60, height: 12, borderRadius: 6, background: th.accent, width: 840 * g }} />
          <div style={{ position: "absolute", left: 0, top: 36, width: 60, height: 60, borderRadius: 30, background: th.accent, border: `8px solid ${th.card}` }} />
          <div style={{ position: "absolute", left: 20 + 840 * g - 30, top: 36, width: 60, height: 60, borderRadius: 30, background: th.hot, border: `8px solid ${th.card}` }} />
          <div style={{ position: "absolute", left: 0, top: 110, fontFamily: UI, fontSize: 46, fontWeight: 700, color: th.muted }}>{p.de}</div>
          <div style={{ position: "absolute", right: 0, top: 110, fontFamily: UI, fontSize: 46, fontWeight: 700, color: th.muted }}>{p.a}</div>
        </div>
      </Card>
    </Stage>
  );
};

/* ─────────── Anneau ─────────── */
export const Anneau: React.FC<Ctx<"anneau">> = ({ p, l, th }) => {
  const R = 270, C = 2 * Math.PI * R;
  const g = ease(l, 4, 60) * p.valeur;
  const ang = ((p.repere ?? 0) / 100) * 360 - 90;
  return (
    <Stage>
      <Card th={th} style={{ width: 940, textAlign: "center", opacity: ease(l, 0, 8) }}>
        <svg width="660" height="660" viewBox="0 0 660 660">
          <circle cx="330" cy="330" r={R} fill="none" stroke={th.line} strokeWidth="76" />
          <circle cx="330" cy="330" r={R} fill="none" stroke={th.accent} strokeWidth="76" strokeDasharray={`${(C * g) / 100} ${C}`} transform="rotate(-90 330 330)" style={{ filter: `drop-shadow(0 0 22px ${th.accent}cc)` }} />
          {p.repere != null && (
            <line x1={330 + (R - 52) * Math.cos((ang * Math.PI) / 180)} y1={330 + (R - 52) * Math.sin((ang * Math.PI) / 180)} x2={330 + (R + 52) * Math.cos((ang * Math.PI) / 180)} y2={330 + (R + 52) * Math.sin((ang * Math.PI) / 180)} stroke={th.hot} strokeWidth="14" strokeLinecap="round" opacity={ease(l, 50, 60)} />
          )}
          <text x="330" y="360" textAnchor="middle" fontSize={p.centre.length > 5 ? 100 : 150} fontWeight="700" fill={th.ink} fontFamily={UI}>{p.centre}</text>
        </svg>
        <Kicker th={th} color={th.hot}>{p.etiquette}</Kicker>
      </Card>
    </Stage>
  );
};

/* ─────────── Duel : deux blocs de tailles très différentes ─────────── */
export const Duel: React.FC<Ctx<"duel">> = ({ p, l, th }) => {
  const g = (i: number) => ease(l, 4 + i * 10, 34 + i * 10);
  return (
    <Stage>
      {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
      <Card th={th} style={{ width: 940 }}>
        {[p.haut, p.bas].map((s, i) => (
          <div key={i} style={{ marginBottom: i === 0 ? 70 : 0 }}>
            <div style={{ fontFamily: UI, fontSize: 56, fontWeight: 700, color: i === 0 ? th.ink : th.muted, marginBottom: 18 }}>{s.titre}</div>
            <div style={{ height: 130, borderRadius: 30, background: th.line, overflow: "hidden" }}>
              <div style={{ width: `${s.part * g(i)}%`, height: "100%", background: i === 0 ? th.accent : th.muted, borderRadius: 30 }} />
            </div>
          </div>
        ))}
      </Card>
    </Stage>
  );
};

/* ─────────── Objet : une icône qui rebondit ─────────── */
export const Objet: React.FC<Ctx<"objet">> = ({ p, l, th }) => (
  <Stage>
    <div style={{ position: "relative", width: 640, height: 640, display: "flex", alignItems: "center", justifyContent: "center" }}>
      {[0, 1, 2].map((k) => (
        <div key={k} style={{ position: "absolute", inset: -k * 70, borderRadius: "50%", border: `4px solid ${th.accent}`, opacity: Math.max(0, 0.35 - k * 0.1) * ease(l, 0, 20), transform: `scale(${1 + 0.03 * Math.sin(l / 8 + k)})` }} />
      ))}
      <div style={{ transform: `scale(${ease(l, 0, 14, 0.4, 1)}) rotate(${Math.sin(l / 9) * 3}deg) translateY(${Math.sin(l / 7) * 12}px)` }}>
        <Icon nom={p.icone} th={th} size={520} />
      </div>
    </div>
    <div style={{ textAlign: "center", opacity: ease(l, 8, 20) }}>
      <div style={{ fontFamily: GIANT, fontSize: 130, color: th.ink, textTransform: "uppercase", lineHeight: 1.05 }}>{p.titre}</div>
      {p.sous && <div style={{ fontFamily: UI, fontSize: 48, color: th.muted, marginTop: 14 }}>{p.sous}</div>}
    </div>
  </Stage>
);

/* ─────────── Question ─────────── */
export const Question: React.FC<Ctx<"question">> = ({ p, l, th }) => (
  <Stage>
    <div style={{ fontFamily: GIANT, fontSize: 560, lineHeight: 0.9, color: th.accent, transform: `scale(${ease(l, 0, 14, 0.4, 1)}) rotate(${Math.sin(l / 10) * 4}deg)` }}>?</div>
    <div style={{ fontFamily: UI, fontSize: 64, fontWeight: 700, color: th.ink, textAlign: "center", maxWidth: 900, opacity: ease(l, 6, 18) }}>{p.question}</div>
    <div style={{ display: "flex", gap: 18, marginTop: 20 }}>
      {(p.pistes ?? []).map((t, i) => (
        <Card key={i} th={th} style={{ padding: "26px 28px", opacity: ease(l, 14 + i * 7, 26 + i * 7), transform: `translateY(${ease(l, 14 + i * 7, 26 + i * 7, 40, 0)}px)` }}>
          <div style={{ fontFamily: UI, fontSize: 40, fontWeight: 700, color: th.muted, whiteSpace: "nowrap" }}>{t}</div>
        </Card>
      ))}
    </div>
  </Stage>
);

/* ─────────── Liste ─────────── */
export const Liste: React.FC<Ctx<"liste">> = ({ p, l, th }) => (
  <Stage>
    <Card th={th} style={{ width: 940 }}>
      {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
      {p.items.map((it, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "30px 0", borderBottom: i < p.items.length - 1 ? `2px solid ${th.line}` : "none", opacity: ease(l, 6 + i * 9, 18 + i * 9), transform: `translateX(${ease(l, 6 + i * 9, 18 + i * 9, 50, 0)}px)` }}>
          <div style={{ fontFamily: UI, fontSize: 54, fontWeight: 700, color: th.ink }}>{it.texte}</div>
          {it.valeur && <div style={{ fontFamily: UI, fontSize: 54, fontWeight: 700, color: th.accent }}>{it.valeur}</div>}
        </div>
      ))}
    </Card>
  </Stage>
);
