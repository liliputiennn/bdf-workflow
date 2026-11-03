import React from "react";
import { AbsoluteFill, staticFile, type CalculateMetadataFunction } from "remotion";
import { ICONES, Icon, type Icone } from "../infographie/icons";
import { getTheme, GIANT, UI, type Theme } from "../infographie/themes";
import type { Episode } from "../infographie/types";
import { ajuste, resolveMiniature, type Fait, type MiniatureSpec, type Publication, type Resolved } from "./resolve";

export const W = 1280;
export const H = 720;
export const FPS = 30;

export type MiniatureProps = {
  id: string;
  /** force une mise en page (rendu de secours) */
  style?: string;
  /** force un thème */
  theme?: string;
  /** remplace des champs du `miniature` de l'épisode */
  miniature?: MiniatureSpec;
  /** rendu « masque » : le texte principal en rouge / vert / bleu pur sur noir, tout le reste invisible (contrôle automatique) */
  masque?: boolean;
  resolved?: Resolved;
  /** `episodes-b/<id>/visage.png` (portrait détouré, fond transparent) présent : le style « createur » le place à droite */
  visage?: boolean;
};

const getJson = async <T,>(file: string): Promise<T | null> => {
  try {
    const r = await fetch(staticFile(file));
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
};

export const calculateMetadata: CalculateMetadataFunction<MiniatureProps> = async ({ props }) => {
  const [episode, faits, pub] = await Promise.all([
    getJson<Episode & { miniature?: MiniatureSpec }>(`${props.id}/episode.json`),
    getJson<Fait[]>(`${props.id}/faits.json`),
    getJson<Publication>(`${props.id}/publication.json`),
  ]);
  if (!episode) throw new Error(`episodes-b/${props.id}/episode.json introuvable`);
  const resolved = resolveMiniature(episode, faits, pub, { style: props.style, theme: props.theme, miniature: props.miniature });
  const visage = await fetch(staticFile(`${props.id}/visage.png`)).then((r) => r.ok).catch(() => false);
  return { durationInFrames: 1, fps: FPS, width: W, height: H, props: { ...props, resolved, visage } };
};

/* ---------- briques communes ---------- */

/** Canal du masque : 1 = rouge (texte principal), 2 = vert (second texte important), 3 = bleu (légendes, non bloquant). */
const CANAL = { 1: "#ff0000", 2: "#00ff00", 3: "#0000ff" } as const;
type Groupe = keyof typeof CANAL;

const Texte: React.FC<{ g: Groupe; mask: boolean; style: React.CSSProperties; children: React.ReactNode }> = ({ g, mask, style, children }) => (
  <div
    style={{
      position: "absolute", fontFamily: GIANT, fontWeight: 400, textTransform: "uppercase", lineHeight: 0.98, whiteSpace: "nowrap",
      ...style,
      ...(mask ? { color: CANAL[g], background: "transparent", textShadow: "none", boxShadow: "none", border: "none", filter: "none" } : {}),
    }}
  >
    {children}
  </div>
);

/** Décor : disparaît dans le rendu masque, mais garde sa place. */
const Deco: React.FC<{ mask: boolean; style?: React.CSSProperties; children?: React.ReactNode }> = ({ mask, style, children }) => (
  <div style={{ position: "absolute", ...style, visibility: mask ? "hidden" : "visible" }}>{children}</div>
);

const pal = (th: Theme) => ({
  fond: `linear-gradient(160deg, ${th.bg[0]}, ${th.bg[1]})`,
  /** gros texte posé sur le fond */
  gros: th.dark ? th.accent : th.ink,
  /** ombre dure derrière le gros texte */
  ombre: th.dark ? th.deep : th.accent,
  /** grand aplat de couleur (panneau) */
  panneau: th.dark ? th.card : th.deep,
  panneauTexte: th.dark ? th.accent : "#FFFFFF",
  /** étiquette jaune */
  etiquette: th.hot,
  etiquetteTexte: th.dark ? th.onAccent : th.ink,
  /** texte sur aplat d'accent */
  surAccent: th.dark ? th.onAccent : "#FFFFFF",
  accentFort: th.dark ? th.accent : th.deep,
});

const Rayons: React.FC<{ th: Theme; cx: number; cy: number; size: number }> = ({ th, cx, cy, size }) => (
  <div
    style={{
      position: "absolute", left: cx - size / 2, top: cy - size / 2, width: size, height: size, borderRadius: "50%",
      background: `repeating-conic-gradient(from 0deg at 50% 50%, ${th.dark ? th.accent + "26" : "#ffffff22"} 0deg 8deg, transparent 8deg 22deg)`,
      WebkitMaskImage: "radial-gradient(circle, #000 35%, transparent 70%)", maskImage: "radial-gradient(circle, #000 35%, transparent 70%)",
    }}
  />
);

const Chaine: React.FC<{ r: Resolved; th: Theme; mask: boolean; left?: number }> = ({ r, th, mask, left = 44 }) => (
  <Deco mask={mask} style={{ left, bottom: 30, fontFamily: UI, fontWeight: 700, fontSize: 26, letterSpacing: 4, color: th.muted, textTransform: "uppercase" }}>
    {r.chaine}
  </Deco>
);

/** Étiquette (texte du haut) : bandeau jaune incliné. */
const Etiquette: React.FC<{ txt: string; th: Theme; mask: boolean; maxW: number; left: number; top: number; max?: number }> = ({ txt, th, mask, maxW, left, top, max = 104 }) => {
  const p = pal(th);
  const fs = ajuste(txt, maxW - 64, max);
  return (
    <Texte g={2} mask={mask} style={{ left, top, fontSize: fs, padding: `${Math.round(fs * 0.12)}px 32px ${Math.round(fs * 0.08)}px`, background: p.etiquette, color: p.etiquetteTexte, borderRadius: 14, transform: "rotate(-2deg)", transformOrigin: "left center", boxShadow: `0 8px 0 ${th.dark ? "#00000066" : th.deep}` }}>
      {txt}
    </Texte>
  );
};

/* ---------- (a) chiffre choc : gros nombre + mot court + icône ---------- */

const ChiffreChoc: React.FC<{ r: Resolved; th: Theme; mask: boolean }> = ({ r, th, mask }) => {
  const p = pal(th);
  const fs = ajuste(r.gros, 640, 430);
  return (
    <>
      <Deco mask={mask} style={{ inset: 0, background: p.panneau, clipPath: "polygon(870px 0, 1280px 0, 1280px 720px, 700px 720px)" }} />
      <Deco mask={mask} style={{ inset: 0, clipPath: "polygon(870px 0, 1280px 0, 1280px 720px, 700px 720px)" }}>
        <Rayons th={th} cx={1060} cy={370} size={760} />
      </Deco>
      <Deco mask={mask} style={{ left: 860, top: 170, filter: "drop-shadow(0 18px 0 #00000040)" }}>
        <Icon nom={r.icone} th={th.dark ? th : { ...th, accent: th.accent, deep: "#06402A" }} size={390} />
      </Deco>
      <Etiquette txt={r.texteHaut} th={th} mask={mask} maxW={760} left={50} top={56} />
      <Texte g={1} mask={mask} style={{ left: 46, top: 250 + (430 - fs) * 0.35, fontSize: fs, color: p.gros, textShadow: `${Math.round(fs * 0.035)}px ${Math.round(fs * 0.035)}px 0 ${p.ombre}` }}>
        {r.gros}
      </Texte>
      <Chaine r={r} th={th} mask={mask} />
    </>
  );
};

/* ---------- (b) question : gros ? + 3 mots ---------- */

/** Répartit les mots sur au plus 3 lignes, de longueurs voisines. */
const lignes = (txt: string): string[] => {
  const mots = txt.split(" ").filter(Boolean);
  // un texte court tient sur une ligne : coupé mot à mot il serait trop étroit pour le contrôle de lisibilité
  if (mots.length <= 3) return txt.length <= 14 ? [txt] : mots;
  const total = txt.length;
  const out: string[] = [];
  let cur = "";
  for (const m of mots) {
    if (cur && (cur + " " + m).length > total / 3 + 2 && out.length < 2) { out.push(cur); cur = m; }
    else cur = cur ? `${cur} ${m}` : m;
  }
  out.push(cur);
  return out;
};

const Question: React.FC<{ r: Resolved; th: Theme; mask: boolean }> = ({ r, th, mask }) => {
  const p = pal(th);
  const ls = lignes(r.texteHaut);
  const fs = Math.min(ajuste(ls.reduce((a, b) => (b.length > a.length ? b : a), ""), 660, 190), Math.floor(560 / ls.length));
  const hauteur = fs * 1.06 * ls.length;
  const top = (H - hauteur) / 2 - 10;
  return (
    <>
      <Deco mask={mask} style={{ inset: 0, background: `radial-gradient(620px 620px at 300px 340px, ${th.hot}${th.dark ? "55" : "88"}, transparent 70%)` }} />
      <Deco mask={mask} style={{ left: 0, top: 0, width: 24, height: H, background: p.accentFort }} />
      <Texte g={2} mask={mask} style={{ left: 100, top: -10, fontSize: 720, lineHeight: 1, color: th.hot, textShadow: `18px 18px 0 ${th.dark ? th.deep : th.deep}` }}>?</Texte>
      {ls.map((l, i) => {
        const dernier = i === ls.length - 1 && ls.length >= 3; // l'aplat n'existe qu'à partir de trois lignes : avec moins, il fausserait la mesure de contraste
        return (
          <Texte
            key={i} g={1} mask={mask}
            style={{
              left: 560, top: top + i * fs * 1.06, fontSize: fs, lineHeight: 1.0,
              color: dernier ? p.surAccent : p.gros,
              background: dernier ? p.accentFort : "transparent",
              padding: dernier ? `0 ${Math.round(fs * 0.14)}px` : 0, borderRadius: 10,
              textShadow: dernier ? "none" : `${Math.round(fs * 0.04)}px ${Math.round(fs * 0.04)}px 0 ${p.ombre}`,
            }}
          >
            {l}
          </Texte>
        );
      })}
      <Chaine r={r} th={th} mask={mask} left={564} />
    </>
  );
};

/* ---------- (c) contraste : deux valeurs face à face ---------- */

const Contraste: React.FC<{ r: Resolved; th: Theme; mask: boolean }> = ({ r, th, mask }) => {
  const p = pal(th);
  const [a, b] = r.contraste!;
  // même corps des deux côtés : la taille ne doit pas suggérer une échelle
  const fsA = Math.min(ajuste(a.valeur, 470, 360), ajuste(b.valeur, 470, 360));
  const fsB = fsA;
  const fsL = (t: string) => ajuste(t, 470, 62);
  return (
    <>
      {/* moitié gauche : le « petit » côté, neutre */}
      <Deco mask={mask} style={{ inset: 0, background: th.dark ? th.card : "#FFFFFF" }} />
      <Deco mask={mask} style={{ inset: 0, background: `repeating-linear-gradient(135deg, ${th.line}55 0 3px, transparent 3px 26px)` }} />
      {/* moitié droite : le côté qui compte, plein */}
      <Deco mask={mask} style={{ inset: 0, background: th.dark ? th.accent : th.deep, clipPath: "polygon(700px 0, 1280px 0, 1280px 720px, 580px 720px)" }} />
      <Deco mask={mask} style={{ inset: 0, clipPath: "polygon(700px 0, 1280px 0, 1280px 720px, 580px 720px)" }}>
        <Rayons th={th} cx={1000} cy={330} size={900} />
      </Deco>
      <Texte g={1} mask={mask} style={{ left: 44, top: 150 + (360 - fsA) * 0.4, fontSize: fsA, color: th.dark ? th.ink : th.ink, textShadow: `${Math.round(fsA * 0.035)}px ${Math.round(fsA * 0.035)}px 0 ${th.dark ? th.line : th.hot}` }}>{a.valeur}</Texte>
      <Texte g={2} mask={mask} style={{ left: 744, top: 150 + (360 - fsB) * 0.4, fontSize: fsB, color: p.surAccent, textShadow: `${Math.round(fsB * 0.035)}px ${Math.round(fsB * 0.035)}px 0 ${th.dark ? th.hot : "#06402A"}` }}>{b.valeur}</Texte>
      <Texte g={3} mask={mask} style={{ left: 50, top: 540, fontSize: fsL(a.label), color: th.dark ? th.ink : th.ink }}>{a.label}</Texte>
      <Texte g={3} mask={mask} style={{ left: 750, top: 540, fontSize: fsL(b.label), color: p.surAccent }}>{b.label}</Texte>
      <Texte g={3} mask={mask} style={{ left: 50, top: 46, fontSize: ajuste(r.texteHaut, 560, 72), color: th.dark ? th.hot : th.ink }}>{r.texteHaut}</Texte>
      {/* VS */}
      <Deco mask={mask} style={{ left: 590, top: 280, width: 150, height: 150, borderRadius: "50%", background: th.hot, boxShadow: `0 8px 0 ${th.dark ? "#000000aa" : th.deep}`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: GIANT, fontSize: 78, color: th.dark ? th.onAccent : th.ink }}>VS</Deco>
      <Chaine r={r} th={th} mask={mask} />
    </>
  );
};

/* ---------- (d) téléphone et (e) pile : le chiffre mis en scène, façon miniature de créateur ---------- */

/** Tuile d'icône « verre » : coins ronds, reflet, ombre dure + ombre douce. */
const Tuile: React.FC<{ th: Theme; nom: Icone; size: number; left: number; top: number; rot: number; mask: boolean; fond?: string }> = ({ th, nom, size, left, top, rot, mask, fond }) => (
  <Deco
    mask={mask}
    style={{
      left, top, width: size, height: size, borderRadius: size * 0.24, transform: `rotate(${rot}deg)`,
      background: fond ?? (th.dark ? `linear-gradient(160deg, ${th.line}, ${th.card})` : "linear-gradient(160deg, #FFFFFF, #E9E9EE)"),
      boxShadow: `inset 0 5px 0 rgba(255,255,255,${th.dark ? 0.25 : 0.9}), 0 12px 0 rgba(0,0,0,.28), 0 28px 44px rgba(0,0,0,.35)`,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}
  >
    <Icon nom={nom} th={th} size={size * 0.7} />
  </Deco>
);

/** Gros texte empilé à gauche : dernière ligne sur un aplat d'accent (le mot qui accroche). */
const GrosTitre: React.FC<{ r: Resolved; th: Theme; mask: boolean; maxW: number }> = ({ r, th, mask, maxW }) => {
  const p = pal(th);
  // un « ? » ou « ! » reste collé au mot qui le précède, jamais seul sur une ligne
  const propre = r.texteHaut.replace(/\s+([?!])/g, "$1");
  const mots = propre.split(" ").filter(Boolean);
  let ls: string[];
  if (mots.length === 3) {
    // trois mots : deux lignes équilibrées (le texte principal garde ainsi au moins un tiers de la largeur)
    const a = [mots[0], `${mots[1]} ${mots[2]}`], b = [`${mots[0]} ${mots[1]}`, mots[2]];
    const ecart = (x: string[]) => Math.abs(x[0].length - x[1].length);
    ls = ecart(a) < ecart(b) ? a : b;
  } else ls = lignes(propre);
  const fs = Math.min(ajuste(ls.reduce((a, b) => (b.length > a.length ? b : a), ""), maxW, 215), Math.floor(560 / ls.length));
  const top = (H - fs * 1.06 * ls.length) / 2 - 14;
  const o = Math.max(4, Math.round(fs * 0.035));
  return (
    <>
      {ls.map((l, i) => {
        const dernier = i === ls.length - 1 && ls.length > 1;
        return (
          <Texte
            // la ligne sur aplat est un « second texte » : mêlée au texte principal, elle faussait la mesure de contraste
            key={i} g={dernier ? 2 : 1} mask={mask}
            style={{
              left: 44, top: top + i * fs * 1.06, fontSize: fs, lineHeight: 1.0,
              color: dernier ? p.surAccent : p.gros,
              background: dernier ? p.accentFort : "transparent",
              padding: dernier ? `0 ${Math.round(fs * 0.14)}px` : 0, borderRadius: 12,
              // ombre franche d'une couleur très différente du texte (sinon le contrôle de contraste la compte comme du texte)
              textShadow: dernier ? "none" : `${o}px ${o}px 0 ${th.dark ? "#000000cc" : th.hot}`,
              boxShadow: dernier ? `0 ${o * 2}px 0 ${th.dark ? "#00000088" : th.deep}` : "none",
            }}
          >
            {l}
          </Texte>
        );
      })}
    </>
  );
};

const pivote = (dx: number, dy: number, deg: number) => {
  const a = (deg * Math.PI) / 180;
  return [dx * Math.cos(a) - dy * Math.sin(a), dx * Math.sin(a) + dy * Math.cos(a)];
};

const autres = (r: Resolved): Icone[] => ICONES.filter((i) => i !== r.icone);

/** Le téléphone : écran avec anneau exact (pour un %) ou icône, et le chiffre. `s` = échelle, `rot` = inclinaison en degrés. */
const Appareil: React.FC<{ r: Resolved; th: Theme; mask: boolean; cx: number; cy: number; s?: number; rot?: number }> = ({ r, th, mask, cx, cy, s = 1, rot = 6 }) => {
  const PW = 380, PH = 690;
  const pct = /^(\d+(?:[.,]\d+)?)\s?%$/.exec(r.gros);
  const v = pct ? Math.min(100, parseFloat(pct[1].replace(",", "."))) : null;
  const RAY = 118, CIRC = 2 * Math.PI * RAY;
  // centre du chiffre dans le téléphone (repère de l'écran, avant rotation)
  const [rx, ry] = pivote(0, v != null ? -40 * s : 70 * s, rot);
  const fs = Math.round(ajuste(r.gros, v != null ? 210 : 290, v != null ? 118 : 150) * s);
  return (
    <>
      <Deco mask={mask} style={{ left: cx - PW / 2, top: cy - PH / 2, width: PW, height: PH, transform: `rotate(${rot}deg) scale(${s})`, borderRadius: 62, background: "#0A0A0F", padding: 14, boxShadow: "0 22px 0 rgba(0,0,0,.30), 0 40px 80px rgba(0,0,0,.45)" }}>
        <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 50, overflow: "hidden", background: th.dark ? th.card : "#FFFFFF" }}>
          <div style={{ position: "absolute", top: 14, left: "50%", width: 112, height: 30, marginLeft: -56, borderRadius: 15, background: "#0A0A0F" }} />
          <div style={{ position: "absolute", top: 70, left: 0, right: 0, textAlign: "center", fontFamily: UI, fontWeight: 700, fontSize: 19, letterSpacing: 4, color: th.muted, textTransform: "uppercase" }}>{r.chaine}</div>
          {v != null ? (
            <svg width="352" height="352" viewBox="0 0 352 352" style={{ position: "absolute", left: 0, top: 108 }}>
              <circle cx="176" cy="176" r={RAY} fill="none" stroke={th.line} strokeWidth="38" />
              <circle cx="176" cy="176" r={RAY} fill="none" stroke={th.dark ? th.accent : th.deep} strokeWidth="38" strokeDasharray={`${(CIRC * v) / 100} ${CIRC}`} transform="rotate(-90 176 176)" />
            </svg>
          ) : (
            <div style={{ position: "absolute", left: 0, right: 0, top: 118, display: "flex", justifyContent: "center" }}><Icon nom={r.icone} th={th} size={210} /></div>
          )}
          <div style={{ position: "absolute", left: 40, right: 40, bottom: 44, height: 18, borderRadius: 9, background: th.line }} />
          <div style={{ position: "absolute", left: 40, bottom: 44, width: "58%", height: 18, borderRadius: 9, background: th.dark ? th.accent : th.deep }} />
          <div style={{ position: "absolute", left: 40, bottom: 84, width: "36%", height: 14, borderRadius: 7, background: th.line }} />
        </div>
      </Deco>
      <Texte g={2} mask={mask} style={{ left: cx + rx, top: cy + ry, fontSize: fs, transform: `translate(-50%, -50%) rotate(${rot}deg)`, color: th.ink, lineHeight: 1 }}>{r.gros}</Texte>
    </>
  );
};

const Telephone: React.FC<{ r: Resolved; th: Theme; mask: boolean }> = ({ r, th, mask }) => {
  const cx = 990, cy = 361;
  const ic = autres(r);
  return (
    <>
      <Deco mask={mask} style={{ inset: 0, background: `radial-gradient(560px 560px at ${cx}px ${cy}px, ${th.accent}${th.dark ? "70" : "66"}, transparent 70%)` }} />
      <Deco mask={mask} style={{ inset: 0 }}><Rayons th={th} cx={cx} cy={cy} size={980} /></Deco>
      <Tuile th={th} nom={ic[0]} size={176} left={668} top={462} rot={-12} mask={mask} />
      <Appareil r={r} th={th} mask={mask} cx={cx} cy={cy} />
      <Tuile th={th} nom={ic[1]} size={136} left={1136} top={150} rot={14} mask={mask} />
      <Tuile th={th} nom={ic[2]} size={142} left={1112} top={468} rot={10} mask={mask} />
      <GrosTitre r={r} th={th} mask={mask} maxW={620} />
      <Chaine r={r} th={th} mask={mask} />
    </>
  );
};

/* ---------- (f) créateur : titre pleine largeur en haut, scène en dessous (téléphone qui déborde, hub d'icônes, visage facultatif) ---------- */

const Createur: React.FC<{ r: Resolved; th: Theme; mask: boolean; visage: boolean }> = ({ r, th, mask, visage }) => {
  const p = pal(th);
  const txt = r.texteHaut.replace(/\s+([?!])/g, "$1");
  const mots = txt.split(" ").filter(Boolean);
  const largeur = visage ? 800 : 1190;
  // une ligne si elle reste très grosse, sinon deux lignes équilibrées
  const f1 = ajuste(txt, largeur, 170);
  let ls: string[];
  if (f1 >= 118 || mots.length < 2) ls = [txt];
  else {
    let best = 1, sc = Infinity;
    for (let k = 1; k < mots.length; k++) {
      const a = mots.slice(0, k).join(" "), b = mots.slice(k).join(" ");
      const d = Math.abs(a.length - b.length);
      if (d < sc) { sc = d; best = k; }
    }
    ls = [mots.slice(0, best).join(" "), mots.slice(best).join(" ")];
  }
  const fs = Math.min(ajuste(ls.reduce((a, b) => (b.length > a.length ? b : a), ""), largeur, 175), ls.length === 1 ? 175 : 150);
  const o = Math.max(4, Math.round(fs * 0.035));
  const hb = 26 + fs * 1.04 * ls.length + 14; // bas du titre
  const ic = autres(r);
  const hubX = visage ? 620 : 930, hubY = Math.min(H - 130, hb + (H - hb) * 0.72);
  const petites: [number, number][] = visage ? [[470, 14], [620, -16], [770, 14]] : [[740, 14], [930, -16], [1120, 14]];
  const ty = hubY - 118 - 76 - 120;
  const phoneS = Math.min(1.0, (H - hb + 70) / 690);
  const phoneCx = visage ? 250 : 270, phoneCy = hb + (690 * phoneS) / 2 - 22;
  return (
    <>
      <Deco mask={mask} style={{ inset: 0, background: `radial-gradient(700px 520px at ${hubX}px ${hubY}px, ${th.accent}${th.dark ? "55" : "44"}, transparent 70%)` }} />
      <Deco mask={mask} style={{ inset: 0 }}><Rayons th={th} cx={hubX} cy={hubY} size={1100} /></Deco>
      {/* pointillés entre les petites tuiles et le hub */}
      <Deco mask={mask} style={{ inset: 0 }}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          {petites.map(([x, dy], i) => (
            <path key={i} d={`M ${x + 60} ${ty + dy + 128} C ${x + 60} ${ty + dy + 190}, ${hubX} ${hubY - 170}, ${hubX} ${hubY - 108}`} fill="none" stroke={th.dark ? th.accent : th.deep} strokeWidth="7" strokeDasharray="4 16" strokeLinecap="round" opacity=".9" />
          ))}
        </svg>
      </Deco>
      {petites.map(([x, dy], i) => (
        <Tuile key={i} th={th} nom={ic[i % ic.length]} size={120} left={x} top={ty + dy} rot={i === 1 ? 0 : i === 0 ? -8 : 8} mask={mask} />
      ))}
      <Tuile th={th} nom={r.icone} size={216} left={hubX - 108} top={hubY - 108} rot={-4} mask={mask} fond={th.dark ? th.accent : th.deep} />
      <Appareil r={r} th={th} mask={mask} cx={phoneCx} cy={phoneCy} s={phoneS} rot={-6} />
      {visage && (
        <Deco mask={mask} style={{ right: 0, bottom: 0, height: 690, filter: `drop-shadow(8px 0 0 ${th.hot}) drop-shadow(-8px 0 0 ${th.hot}) drop-shadow(0 -8px 0 ${th.hot}) drop-shadow(0 30px 40px rgba(0,0,0,.5))` }}>
          <img src={staticFile(`${r.id}/visage.png`)} style={{ height: 690, display: "block" }} />
        </Deco>
      )}
      {ls.map((l, i) => {
        const dernier = i === ls.length - 1 && ls.length > 1;
        return (
          <Texte
            key={i} g={dernier ? 2 : 1} mask={mask}
            style={{
              left: 44, top: 24 + i * fs * 1.04, fontSize: fs, lineHeight: 1.0,
              color: dernier ? p.surAccent : p.gros,
              background: dernier ? p.accentFort : "transparent",
              padding: dernier ? `0 ${Math.round(fs * 0.14)}px` : 0, borderRadius: 14,
              textShadow: dernier ? "none" : `${o}px ${o}px 0 ${th.dark ? "#000000cc" : th.hot}`,
              boxShadow: dernier ? `0 ${o * 2}px 0 ${th.dark ? "#00000088" : th.deep}` : "none",
            }}
          >
            {l}
          </Texte>
        );
      })}
      <Chaine r={r} th={th} mask={mask} left={visage ? 44 : 520} />
    </>
  );
};

const PILE: [number, number, number, number][] = [
  [730, 450, 190, -8], [900, 494, 186, 6], [1070, 450, 190, -6],
  [750, 234, 170, 10], [1104, 236, 166, 12], [830, 36, 164, -10], [1000, 24, 176, 8],
];

const Pile: React.FC<{ r: Resolved; th: Theme; mask: boolean }> = ({ r, th, mask }) => {
  const p = pal(th);
  const cx = 972, cy = 345, D = 372;
  const fs = ajuste(r.gros, 290, 190);
  const fonds = [undefined, th.hot, th.accent, undefined, th.hot, undefined, th.accent];
  return (
    <>
      <Deco mask={mask} style={{ inset: 0, background: `radial-gradient(620px 620px at ${cx}px ${cy}px, ${th.accent}${th.dark ? "66" : "55"}, transparent 70%)` }} />
      <Deco mask={mask} style={{ inset: 0 }}><Rayons th={th} cx={cx} cy={cy} size={1000} /></Deco>
      {PILE.map(([x, y, s, rot], i) => (
        <Tuile key={i} th={th} nom={ICONES[i % ICONES.length]} size={s} left={x} top={y} rot={rot} mask={mask} fond={fonds[i]} />
      ))}
      <Deco mask={mask} style={{ left: cx - D / 2, top: cy - D / 2, width: D, height: D, borderRadius: "50%", background: p.etiquette, border: `10px solid ${th.dark ? th.card : th.ink}`, boxShadow: `0 16px 0 rgba(0,0,0,.30), 0 34px 60px rgba(0,0,0,.4)`, transform: "rotate(-5deg)" }} />
      <Texte g={2} mask={mask} style={{ left: cx, top: cy, fontSize: fs, transform: "translate(-50%, -50%) rotate(-5deg)", color: p.etiquetteTexte, lineHeight: 1 }}>{r.gros}</Texte>
      <GrosTitre r={r} th={th} mask={mask} maxW={600} />
      <Chaine r={r} th={th} mask={mask} />
    </>
  );
};

/* ---------- composition ---------- */

export const MiniatureView: React.FC<MiniatureProps> = ({ resolved, masque, visage }) => {
  if (!resolved) return null;
  const th = getTheme(resolved.theme);
  const p = pal(th);
  const mask = !!masque;
  return (
    <AbsoluteFill style={{ background: mask ? "#000" : p.fond, overflow: "hidden", fontFamily: UI }}>
      {!mask && resolved.style !== "contraste" && (
        <AbsoluteFill style={{ backgroundImage: `linear-gradient(${th.line}55 2px, transparent 2px), linear-gradient(90deg, ${th.line}55 2px, transparent 2px)`, backgroundSize: "64px 64px", opacity: th.dark ? 0.45 : 0.6 }} />
      )}
      {resolved.style === "chiffre" && <ChiffreChoc r={resolved} th={th} mask={mask} />}
      {resolved.style === "question" && <Question r={resolved} th={th} mask={mask} />}
      {resolved.style === "contraste" && resolved.contraste && <Contraste r={resolved} th={th} mask={mask} />}
      {resolved.style === "telephone" && <Telephone r={resolved} th={th} mask={mask} />}
      {resolved.style === "pile" && <Pile r={resolved} th={th} mask={mask} />}
      {resolved.style === "createur" && <Createur r={resolved} th={th} mask={mask} visage={!!visage} />}
    </AbsoluteFill>
  );
};
