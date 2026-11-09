import React from "react";
import { Img, staticFile } from "remotion";
import { formatNombre, LangueCtx, Mot } from "../infographie/langue";
import { Video } from "@remotion/media";
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
const fmt = (n: number, d = 0, langue?: string) => formatNombre(n, d, langue);
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
  const lg = React.useContext(LangueCtx);
  const v = ease(l, 4, 36) * p.valeur;
  return (
    <Stage>
      <Card th={th} style={{ width: 1250, textAlign: "center", transform: `translateY(${ease(l, 0, 14, 60, 0)}px)`, opacity: ease(l, 0, 8) }}>
        <Kicker th={th}>{p.etiquette}</Kicker>
        <div style={{ fontFamily: GIANT, fontSize: 300, lineHeight: 1.05, color: th.ink, marginTop: 12 }}>
          {p.prefixe}{fmt(v, p.decimales ?? 0, lg)}<span style={{ color: th.accent }}>{p.suffixe}</span>
        </div>
        {p.sous && <div style={{ fontFamily: UI, fontSize: 42, color: th.muted, marginTop: 10 }}>{p.sous}</div>}
      </Card>
    </Stage>
  );
};

/* ─────────── Barres ─────────── */
export const Barres: React.FC<Ctx<"barres">> = ({ p, l, th }) => {
  const lg = React.useContext(LangueCtx);
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
                <div style={{ fontFamily: UI, fontSize: 70, fontWeight: 700, color: th.ink, opacity: g, height: 84 }}>{fmt(Math.round(b.valeur * g), 0, lg)}</div>
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

/* ─────────── Fiche business (panneau « business n°X ») ─────────── */
export const Fiche: React.FC<Ctx<"fiche">> = ({ p, l, th }) => (
  <Stage row>
    <div style={{ width: 640, flex: "none", opacity: ease(l, 0, 12), transform: `translateX(${ease(l, 0, 12, -50, 0)}px)` }}>
      <div style={{ fontFamily: GIANT, fontSize: 300, color: th.accent, lineHeight: 0.9 }}>{String(p.numero).padStart(2, "0")}</div>
      <Kicker th={th}>{p.badge ?? "Business"}</Kicker>
      <div style={{ fontFamily: GIANT, fontSize: 84, color: th.ink, textTransform: "uppercase", lineHeight: 1.05, marginTop: 14 }}>{p.titre}</div>
    </div>
    <div style={{ width: 1000, flex: "none" }}>
      {p.lignes.map((r, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "22px 30px", marginBottom: 14, borderRadius: 26, background: r.accent ? th.accent : th.card, border: r.accent ? "none" : `2px solid ${th.line}`, opacity: ease(l, 10 + i * 8, 22 + i * 8), transform: `translateX(${ease(l, 10 + i * 8, 22 + i * 8, 70, 0)}px)` }}>
          <div style={{ fontFamily: UI, fontSize: 40, fontWeight: 500, color: r.accent ? th.onAccent : th.muted }}>{r.label}</div>
          <div style={{ fontFamily: UI, fontSize: 54, fontWeight: 700, color: r.accent ? th.onAccent : th.ink }}>{r.valeur}</div>
        </div>
      ))}
    </div>
  </Stage>
);

/* ─────────── Annonce (carte de prix dessinée par nous) ─────────── */
export const Annonce: React.FC<Ctx<"annonce">> = ({ p, l, th }) => (
  <Stage row>
    <div style={{ width: 760, height: 640, flex: "none", borderRadius: 36, overflow: "hidden", background: `linear-gradient(135deg, ${th.accent}33, ${th.deep}55)`, display: "flex", alignItems: "center", justifyContent: "center", border: `2px solid ${th.line}` }}>
      {p.fichier ? (
        <Img src={staticFile(p.fichier)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1 + 0.1 * ease(l, 0, 150)})` }} />
      ) : (
        <div style={{ fontFamily: GIANT, fontSize: 260, color: th.accent, opacity: 0.55 }}>€</div>
      )}
    </div>
    <div style={{ width: 900, position: "relative", flex: "none" }}>
      <div style={{ fontFamily: UI, fontSize: 56, fontWeight: 700, color: th.ink, lineHeight: 1.12, opacity: ease(l, 6, 18) }}>{p.titre}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 26, marginTop: 18, opacity: ease(l, 12, 26), transform: `scale(${ease(l, 12, 26, 0.85, 1)})`, transformOrigin: "left center" }}>
        <div style={{ fontFamily: GIANT, fontSize: 190, color: th.accent, lineHeight: 1 }}>{p.prix}</div>
        {p.ancien && <div style={{ fontFamily: UI, fontSize: 60, color: th.muted, textDecoration: "line-through" }}>{p.ancien}</div>}
      </div>
      <div style={{ fontFamily: UI, fontSize: 40, color: th.muted, marginTop: 12, opacity: ease(l, 18, 30) }}>{[p.etat, p.lieu].filter(Boolean).join("  ·  ")}</div>
      {p.source && <div style={{ fontFamily: UI, fontSize: 32, color: th.muted, marginTop: 8, opacity: ease(l, 22, 34) }}><Mot k="source" /> {p.source}</div>}
      {p.vendu && (
        <div style={{ position: "absolute", right: 10, top: 0, fontFamily: GIANT, fontSize: 90, color: th.alert, border: `8px solid ${th.alert}`, borderRadius: 18, padding: "4px 28px", textTransform: "uppercase", transform: `rotate(-9deg) scale(${ease(l, 34, 44, 1.8, 1)})`, opacity: ease(l, 34, 42) }}><Mot k="vendu" /></div>
      )}
    </div>
  </Stage>
);

/* ─────────── Photo (image réelle ou générée qui montre de quoi on parle) ─────────── */
export const Photo: React.FC<Ctx<"photo">> = ({ p, l, th }) => (
  <Stage>
    <div style={{ position: "relative", width: 1740, height: 665, borderRadius: 40, overflow: "hidden", border: `2px solid ${th.line}`, opacity: ease(l, 0, 10) }}>
      {p.fichier && <Img src={staticFile(p.fichier)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.02 + 0.1 * ease(l, 0, 160)})` }} />}
      {p.legende && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "80px 50px 34px", background: "linear-gradient(transparent, rgba(0,0,0,0.78))", opacity: ease(l, 10, 22) }}>
          <div style={{ fontFamily: GIANT, fontSize: 88, color: "#FFFFFF", textTransform: "uppercase", lineHeight: 1.05 }}>{p.legende}</div>
        </div>
      )}
      {p.credit && <div style={{ position: "absolute", right: 18, bottom: 8, fontFamily: UI, fontSize: 22, color: "rgba(255,255,255,0.7)" }}>{p.credit}</div>}
    </div>
  </Stage>
);

/* ─────────── Clip (extrait vidéo libre de droits en boucle, sans son) ─────────── */
export const Clip: React.FC<Ctx<"clip">> = ({ p, l, th }) => (
  <Stage>
    <div style={{ position: "relative", width: 1740, height: 665, borderRadius: 40, overflow: "hidden", border: `2px solid ${th.line}`, background: th.card, opacity: ease(l, 0, 10) }}>
      {p.fichier && <Video src={staticFile(p.fichier)} muted loop objectFit="cover" style={{ width: "100%", height: "100%" }} />}
      {p.legende && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "80px 50px 34px", background: "linear-gradient(transparent, rgba(0,0,0,0.78))", opacity: ease(l, 10, 22) }}>
          <div style={{ fontFamily: GIANT, fontSize: 88, color: "#FFFFFF", textTransform: "uppercase", lineHeight: 1.05 }}>{p.legende}</div>
        </div>
      )}
      {p.credit && <div style={{ position: "absolute", right: 18, bottom: 8, fontFamily: UI, fontSize: 22, color: "rgba(255,255,255,0.7)" }}>{p.credit}</div>}
    </div>
  </Stage>
);

/* ─────────── Histoire : frise de dates ─────────── */
export const Frise: React.FC<Ctx<"frise">> = ({ p, l, th }) => (
  <Stage>
    {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
    <div style={{ position: "relative", width: 1600, height: 380 }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 190, height: 6, background: th.line, borderRadius: 3, transformOrigin: "left", transform: `scaleX(${ease(l, 0, 24)})` }} />
      {p.reperes.map((r, i) => {
        const a = ease(l, 6 + i * 10, 20 + i * 10);
        const x = (i / Math.max(1, p.reperes.length - 1)) * 100;
        const haut = i % 2 === 0;
        return (
          <div key={i} style={{ position: "absolute", left: 150 + (x / 100) * 1300 - 170, width: 340, textAlign: "center", opacity: a, top: haut ? 0 : 240 }}>
            <div style={{ fontFamily: GIANT, fontSize: 84, lineHeight: 1, color: r.accent ? th.accent : th.ink }}>{r.date}</div>
            <div style={{ fontFamily: UI, fontSize: 36, fontWeight: 700, color: th.muted }}>{r.label}</div>
            <div style={{ position: "absolute", left: 148, top: haut ? 171 : -69, width: 44, height: 44, borderRadius: 22, background: r.accent ? th.accent : th.card, border: `6px solid ${r.accent ? th.deep : th.line}` }} />
          </div>
        );
      })}
    </div>
  </Stage>
);

/* ─────────── Histoire : carte schématique ─────────── */
export const Carte: React.FC<Ctx<"carte">> = ({ p, l, th }) => {
  const pts = p.lieux.map((q) => `${q.x},${q.y}`).join(" ");
  return (
    <Stage>
      {p.titre && <Kicker th={th}>{p.titre}</Kicker>}
      <Card th={th} style={{ width: 640, height: 560, padding: 20 }}>
        <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ display: "block" }}>
          {[20, 40, 60, 80].map((g) => (
            <g key={g} stroke={th.line} strokeWidth={0.3}><line x1={g} y1={0} x2={g} y2={100} /><line x1={0} y1={g} x2={100} y2={g} /></g>
          ))}
          {p.trajet !== false && <polyline points={pts} fill="none" stroke={th.accent} strokeWidth={1} strokeDasharray="2 1.6" style={{ opacity: ease(l, 10, 30) }} />}
          {p.lieux.map((q, i) => {
            const a = ease(l, 6 + i * 9, 16 + i * 9);
            return (
              <g key={i} style={{ opacity: a }}>
                <circle cx={q.x} cy={q.y} r={2.4 + (1 - a) * 3} fill={th.accent} stroke={th.deep} strokeWidth={0.6} />
                <text x={q.x} y={q.y - 4.5} textAnchor="middle" fontSize={4.6} fontWeight={700} fill={th.ink} style={{ fontFamily: UI, paintOrder: "stroke", stroke: th.card, strokeWidth: 1.6, strokeLinejoin: "round" }}>{q.nom}</text>
              </g>
            );
          })}
        </svg>
      </Card>
      <div style={{ fontFamily: UI, fontSize: 28, color: th.muted }}>Schéma, pas à l’échelle</div>
    </Stage>
  );
};

/* ─────────── Histoire : citation d'époque ─────────── */
export const Citation: React.FC<Ctx<"citation">> = ({ p, l, th }) => (
  <Stage row>
    <div style={{ fontFamily: GIANT, fontSize: 480, lineHeight: 0.8, color: th.accent, flex: "none", opacity: ease(l, 0, 12), transform: `scale(${ease(l, 0, 14, 0.6, 1)})` }}>“</div>
    <div style={{ width: 1100 }}>
      <div style={{ fontFamily: UI, fontSize: 64, fontWeight: 700, color: th.ink, lineHeight: 1.2, opacity: ease(l, 6, 22) }}>{p.texte}</div>
      <div style={{ fontFamily: UI, fontSize: 40, color: th.muted, marginTop: 28, opacity: ease(l, 20, 34) }}>— {p.auteur}{p.date ? `, ${p.date}` : ""}</div>
    </div>
  </Stage>
);
