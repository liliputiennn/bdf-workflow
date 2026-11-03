import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, Sequence, staticFile, useCurrentFrame } from "remotion";
import { BigCounter, CrtOverlay, DataLabel, Hud, Stamp } from "../lib/components";
import { C, TITLE, tw } from "../lib/theme";
import { buildMcoScenes, mcoKeys } from "../px/mcoScenes";
import { Fx, PixelStage } from "../px/Stage";
import script from "./mco.script.json";
import timings from "./mco.timings.json";

const FPS = 30;
/** Voix off : le MP3 ElevenLabs s'il existe (timings alignés par tools/align.py), sinon la maquette. */
export const VOICE = "mco/voix1.mp3";

type Word = { w: string; start: number; end: number };
type Line = { start: number; end: number; words?: Word[] };
const T = timings as { total: number; lines: Line[] };

export const MCO_FRAMES = Math.ceil(T.total * FPS);
const L = T.lines.map((l) => Math.round(l.start * FPS));
const at = (i: number, frac = 0) => {
  const st = L[i];
  const en = L[i + 1] ?? st + 60;
  return Math.round(st + (en - st) * frac);
};
const K = mcoKeys(L, at);
const SCENES = buildMcoScenes(L, MCO_FRAMES);

/** Mots horodatés de chaque phrase (estimés au prorata des lettres si absents). */
const WORDS: Word[][] = T.lines.map((l, i) => {
  if (l.words?.length) return l.words;
  const toks = script[i].text.replace("…", " ").split(/\s+/).filter(Boolean);
  const tot = toks.reduce((s, w) => s + w.length + 2, 0);
  let acc = l.start;
  return toks.map((w) => {
    const d = ((l.end - l.start) * (w.length + 2)) / tot;
    const o = { w, start: acc, end: acc + d };
    acc += d;
    return o;
  });
});

/* ───────── Effets globaux : impulsions qui décroissent ───────── */
type Imp = { at: number; dur: number; shake?: number; aberr?: number; glitch?: number; flash?: number; flashColor?: string; zoom?: number };
const IMPULSES: Imp[] = [
  { at: K.boom, dur: 16, shake: 6, aberr: 4, glitch: 0.7, flash: 0.9, flashColor: "#fff2b0", zoom: 0.12 },
  { at: K.genius, dur: 10, glitch: 0.8, aberr: 3 },
  { at: K.ignition, dur: 60, shake: 2.5 },
  { at: K.imperial, dur: 12, shake: 3, aberr: 3, glitch: 0.5 },
  { at: K.lightning, dur: 10, flash: 0.5, aberr: 2, shake: 2 },
  { at: K.hit, dur: 10, shake: 3, aberr: 2 },
  { at: K.never, dur: 12, shake: 4, glitch: 0.4, zoom: 0.06 },
  { at: K.low, dur: 24, shake: 4, aberr: 3, glitch: 0.3, zoom: 0.08 },
  { at: K.lost, dur: 30, glitch: 0.9, aberr: 4 },
  { at: L[28], dur: 8, zoom: 0.1, aberr: 2 },
  { at: K.lander, dur: 14, glitch: 0.8, aberr: 3, shake: 3 },
  { at: K.classified, dur: 12, shake: 4, flash: 0.35, flashColor: "#3dff8f", zoom: 0.06 },
];
// punch-in sur le mot-clé de chaque phrase
WORDS.forEach((ws, i) => {
  const hi = script[i].hi.split(/\s+/)[0].toLowerCase();
  const w = ws.find((x) => x.w.toLowerCase().startsWith(hi.slice(0, Math.max(2, hi.length - 1))));
  if (w) IMPULSES.push({ at: Math.round(w.start * FPS), dur: 9, zoom: 0.045, aberr: 1.2 });
});
// chaque transition de scène donne un petit coup d'aberration
SCENES.slice(1).forEach((s) => IMPULSES.push({ at: s.from, dur: 6, aberr: 2 }));

const fxAt = (f: number): Fx => {
  const out: Fx = { shake: 0, aberr: 0, glitch: 0, flash: 0, zoom: 1 };
  for (const im of IMPULSES) {
    const k = f - im.at;
    if (k < 0 || k >= im.dur) continue;
    const e = 1 - k / im.dur;
    out.shake = Math.max(out.shake, (im.shake ?? 0) * e);
    out.aberr = Math.max(out.aberr, (im.aberr ?? 0) * e);
    out.glitch = Math.max(out.glitch, (im.glitch ?? 0) * e);
    if ((im.flash ?? 0) * e * e > out.flash) {
      out.flash = (im.flash ?? 0) * e * e;
      out.flashColor = im.flashColor;
    }
    out.zoom = Math.max(out.zoom, 1 + (im.zoom ?? 0) * e * e);
  }
  // léger « souffle » de caméra permanent
  out.zoom *= 1 + 0.012 * Math.sin(f / 40);
  return out;
};

/* ───────── Sous-titres mot à mot ───────── */
const Captions: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  let i = T.lines.findIndex((l, k) => t >= l.start - 0.05 && t < (T.lines[k + 1]?.start ?? 1e9) - 0.05);
  if (i < 0) i = 0;
  const words = WORDS[i];
  const text = script[i].text;
  const hi = script[i].hi.toLowerCase();
  const hiStart = text.toLowerCase().indexOf(hi);
  let cursor = 0;
  const alert = [1, 13, 22, 25, 27].includes(i);
  return (
    <div
      style={{
        position: "absolute",
        top: 205,
        left: 60,
        width: 960,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        columnGap: 18,
        rowGap: 4,
        fontFamily: TITLE,
        fontSize: 68,
        lineHeight: 1.12,
      }}
    >
      {words.map((w, k) => {
        const pos = text.indexOf(w.w, cursor);
        cursor = pos >= 0 ? pos + w.w.length : cursor;
        const isHi = hiStart >= 0 && pos >= hiStart && pos < hiStart + hi.length;
        const age = f - Math.round(w.start * FPS);
        const visible = age >= 0;
        const pop = age < 0 ? 0 : age < 4 ? [1.2, 1.08, 1.02, 1][age] : 1;
        const color = isHi ? (alert ? C.alert : C.accent) : C.white;
        return (
          <span
            key={k}
            style={{
              display: "inline-block",
              opacity: visible ? 1 : 0,
              scale: String(pop),
              color,
              textShadow: `0 6px 0 ${C.ink}, 5px 0 0 ${C.ink}, -5px 0 0 ${C.ink}, 0 -5px 0 ${C.ink}, 4px 4px 0 ${C.ink}, -4px 4px 0 ${C.ink}${isHi ? `, 0 0 26px ${color}` : ""}`,
            }}
          >
            {w.w}
          </span>
        );
      })}
    </div>
  );
};

/* ───────── Habillage HTML par scène ───────── */
const Overlays: React.FC = () => {
  const f = useCurrentFrame();
  const show = (a: number, b: number) => f >= a && f < b;
  return (
    <>
      {show(0, L[2]) && <BigCounter from={0} to={327000000} at={8} dur={45} x={540} y={560} suffix=" $" size={92} />}
      {show(K.boom, L[2]) && <Stamp text="DÉTRUITE" at={K.boom + 4} x={540} y={1330} size={120} />}
      {show(L[2], L[3]) && <DataLabel text="BUG DE GÉNIE ?" at={L[2] + 10} x={540} y={1420} size={36} />}
      {show(L[3], L[4]) && <DataLabel text="NIVEAU : COLLÈGE" at={L[3] + 18} x={540} y={1420} color={C.accent} size={36} />}
      {show(L[4], L[6]) && <DataLabel text="CAP CANAVERAL · 11.12.1998" at={L[4] + 8} x={540} y={540} size={32} />}
      {show(L[6], L[7]) && <DataLabel text="OBJECTIF : SON CLIMAT" at={L[6] + 6} x={540} y={1560} color={C.accent} size={36} />}
      {show(L[7], L[8]) && <DataLabel text="DÉC. 98 → SEPT. 99 · 9 MOIS" at={L[7] + 6} x={540} y={1560} color={C.accent} size={34} />}
      {show(L[8], L[9]) && <DataLabel text="DENVER  ·  CALIFORNIE" at={L[8] + 8} x={540} y={1560} size={34} />}
      {show(L[9], L[11]) && <DataLabel text="LOCKHEED MARTIN · CONSTRUCTEUR" at={L[9] + 8} x={540} y={505} size={30} />}
      {show(L[10], L[11]) && <DataLabel text="JPL · NASA · NAVIGATION" at={L[10] + 8} x={540} y={1130} color={C.accent} size={30} />}
      {show(L[11], L[12]) && <DataLabel text="CORRECTION D'ATTITUDE" at={L[11] + 16} x={540} y={1560} size={34} />}
      {show(L[14], L[15]) && <DataLabel text="IMPÉRIAL" at={L[14] + 4} x={270} y={560} color={C.alert} size={40} />}
      {show(at(14, 0.35), L[15]) && <DataLabel text="MÉTRIQUE" at={at(14, 0.35)} x={810} y={560} color={C.accent} size={40} />}
      {show(L[15], L[16]) && <BigCounter from={1} to={4.45} at={L[15] + 6} dur={36} dec={2} suffix=" N" x={540} y={560} size={110} />}
      {show(at(16, 0.55), L[17]) && <DataLabel text="×4,45 TROP FAIBLE" at={at(16, 0.55)} x={540} y={1560} color={C.alert} size={40} />}
      {show(L[17], L[18]) && <BigCounter from={1} to={14} at={L[17] + 4} dur={Math.max(10, L[18] - L[17] - 14)} prefix="×" x={540} y={560} size={110} />}
      {show(L[18], L[19]) && <DataLabel text="ERREUR CUMULÉE" at={L[18] + 10} x={540} y={1560} color={C.alert} size={34} />}
      {show(K.hit, L[21]) && <Stamp text="HORS PROCÉDURE" at={K.hit + 2} x={540} y={1300} size={78} />}
      {show(K.never, L[23]) && <Stamp text="JAMAIS LANCÉE" at={K.never + 2} x={540} y={1240} size={84} />}
      {show(L[23], L[26]) && <DataLabel text="23.09.1999 · 09:00:46 UTC" at={L[23] + 8} x={540} y={540} color={C.accent} size={32} />}
      {show(at(24, 0.5), L[27]) && <DataLabel text="MINIMUM : 80 KM" at={at(24, 0.5)} x={1000} y={1000} color={C.alert} size={30} anchor="right" />}
      {show(K.low, at(26, 0.9)) && <DataLabel text="57 KM" at={K.low} x={760} y={1300} color={C.alert} size={46} />}
      {show(L[26], L[28]) && <DataLabel text="09:04:52 UTC · −49 S" at={L[26] + 4} x={540} y={540} color={C.alert} size={32} />}
      {show(K.lost, L[28]) && (f - K.lost) % 10 < 7 && <DataLabel text="SIGNAL PERDU" at={K.lost} x={540} y={1240} color={C.alert} size={52} />}
      {show(L[30], L[31]) && <DataLabel text="MARS POLAR LANDER · 03.12.1999" at={L[30] + 10} x={540} y={540} size={30} />}
      {show(K.lander, L[31]) && <Stamp text="PERDUE" at={K.lander + 2} x={540} y={1150} size={120} />}
      {show(L[31], MCO_FRAMES) && <DataLabel text="1 UNITÉ = 327 000 000 $" at={L[31] + 4} x={540} y={540} color={C.accent} size={38} />}
      {show(K.classified, MCO_FRAMES) && <Stamp text="DOSSIER CLASSÉ" at={K.classified} x={540} y={1630} size={84} color={C.accent} rotate={-6} />}
    </>
  );
};

/* ───────── Sound design ───────── */
/** La voix parle-t-elle à l'image f ? (marge pour couvrir attaques et fins de mots) */
const speakingAt = (fr: number) => {
  const t = fr / FPS;
  return T.lines.some((l) => t >= l.start - 0.08 && t <= l.end + 0.12);
};
/** Sons longs (nappes, parasites, alarmes) : très baissés sous la voix. Sons courts : baissés modérément. */
const LONG_SFX = new Set(["static", "static_fm", "riser_cine", "riser_7", "alarm", "alarm_severe", "rocket", "typing", "whoosh_sub", "impact_braam"]);
const Sfx: React.FC<{ at: number; name: string; volume?: number; gain?: number }> = ({ at: a, name, volume = 1, gain = 1 }) =>
  a < 0 ? null : (
    <Sequence from={a} durationInFrames={10 * FPS} layout="none">
      <Audio
        src={staticFile(`fx/${name}.wav`)}
        volume={(fr) => gain * volume * (speakingAt(a + fr) ? (LONG_SFX.has(name) ? 0.22 : 0.45) : 1)}
      />
    </Sequence>
  );

const WHOOSHES = ["whoosh_cine", "whoosh_short", "whoosh_clean", "whoosh_epic", "glitch_trans"];
const SFX: { at: number; name: string; vol?: number }[] = [
  // transitions
  ...SCENES.slice(1).map((s, i) => ({ at: s.from - 4, name: WHOOSHES[i % WHOOSHES.length], vol: 0.55 })),
  ...SCENES.slice(1).filter((s) => s.tin === "pixelate").map((s) => ({ at: s.from, name: "glitch_sfx", vol: 0.3 })),
  // accroche
  { at: 0, name: "impact_hit", vol: 0.7 },
  ...Array.from({ length: 11 }, (_, k) => ({ at: 8 + k * 4, name: "blip_a", vol: 0.35 })),
  { at: L[1], name: "riser_cine", vol: 0.6 },
  { at: K.boom, name: "impact_cine", vol: 1 },
  { at: K.boom, name: "glitch_hd", vol: 0.5 },
  { at: K.boom + 4, name: "stamp_a", vol: 0.9 },
  // génie / collège
  { at: L[2], name: "pickup", vol: 0.5 },
  { at: K.genius, name: "glitch_1", vol: 0.38 },
  { at: K.genius + 4, name: "typing", vol: 0.25 },
  // lancement
  { at: K.ignition, name: "rocket", vol: 0.9 },
  { at: K.ignition, name: "impact_braam", vol: 0.45 },
  // équipes, propulseurs, logiciel
  { at: L[8] + 8, name: "menu", vol: 0.6 },
  { at: L[9], name: "whoosh_pop", vol: 0.4 },
  { at: L[10], name: "whoosh_pop", vol: 0.4 },
  ...[0, 16, 30, 42, 52, 60, 68].map((p) => ({ at: L[11] + p, name: "whoosh_short", vol: 0.35 })),
  { at: L[12], name: "typing", vol: 0.45 },
  { at: K.imperial, name: "alarm", vol: 0.25 },
  { at: K.imperial, name: "impact_boom", vol: 0.45 },
  // duel, balance, barres, répétitions
  { at: L[14], name: "thud", vol: 0.8 },
  { at: K.lightning, name: "glitch_trans", vol: 0.7 },
  { at: K.lightning, name: "impact_hit", vol: 0.6 },
  ...Array.from({ length: 5 }, (_, k) => ({ at: L[15] + Math.round(k * Math.max(6, (L[16] - L[15] - 20) / 5)), name: "pickup", vol: 0.45 })),
  { at: L[16], name: "rocket", vol: 0.35 },
  ...Array.from({ length: 14 }, (_, k) => ({ at: L[17] + 4 + Math.round((k * Math.max(10, L[18] - L[17] - 14)) / 14), name: "blip_b", vol: 0.45 })),
  // dérive, radar, alerte, TCM-5
  { at: L[18], name: "whoosh_sub", vol: 0.4 },
  ...Array.from({ length: 4 }, (_, k) => ({ at: L[19] + k * 18, name: "menu", vol: 0.4 })),
  { at: K.hit, name: "impact_boom", vol: 0.6 },
  { at: K.hit + 2, name: "stamp_b", vol: 0.9 },
  { at: L[21], name: "alarm", vol: 0.25 },
  { at: K.never, name: "impact_cine", vol: 0.8 },
  { at: K.never + 2, name: "stamp_trad", vol: 0.8 },
  // arrivée
  { at: L[23], name: "riser_7", vol: 0.5 },
  { at: K.low, name: "alarm_severe", vol: 0.45 },
  { at: K.low, name: "impact_hit", vol: 0.7 },
  { at: K.lost, name: "static_fm", vol: 0.3 },
  { at: K.lost, name: "glitch_hd", vol: 0.28 },
  // révélation, sœur, fin
  { at: L[28] - 30, name: "riser_cine", vol: 0.5 },
  { at: L[28], name: "impact_braam", vol: 0.6 },
  { at: at(29, 0.45), name: "pickup", vol: 0.6 },
  { at: K.lander, name: "glitch_1", vol: 0.7 },
  { at: K.lander + 2, name: "stamp_a", vol: 0.9 },
  { at: L[31], name: "pop", vol: 0.4 },
  { at: K.classified, name: "impact_cine", vol: 0.9 },
  { at: K.classified, name: "stamp_trad", vol: 0.9 },
];

export const MCO_SCENE_STARTS = SCENES.map((s) => s.from);
export const MCO_SFX_FRAMES = SFX.map((s) => s.at).filter((a) => a >= 0);
export const MCO_TIMINGS = T;

/** Volume de la musique : baissée sous la voix, remontée dans les silences. */
const musicVolume = (fr: number) => {
  const t = fr / FPS;
  // le ducking fin est fait au mixage (compression sidechain sur la voix) ; ici un léger pré-ducking
  const speaking = T.lines.some((l) => t >= l.start - 0.1 && t <= l.end + 0.15);
  const base = speaking ? 0.3 : 0.42;
  return base * tw(fr, [0, 15], [0, 1]) * tw(fr, [MCO_FRAMES - 45, MCO_FRAMES], [1, 0]);
};

const DATES: [number, string][] = [
  [0, "MCO"],
  [L[4], "12.1998"],
  [L[18], "1999"],
  [L[23], "23.09.1999"],
  [L[30], "03.12.1999"],
  [L[31], "CLASSÉ"],
];

export type MixProps = { music: number; sfx: number };
export const Mco: React.FC<{ voice?: string; mix?: MixProps }> = ({ voice = VOICE, mix = { music: 1, sfx: 1 } }) => {
  const f = useCurrentFrame();
  const [dateKey, date] = [...DATES].reverse().find(([a]) => f >= a)!;
  return (
    <AbsoluteFill style={{ backgroundColor: "#020604" }}>
      <PixelStage scenes={SCENES} lineStarts={L} fx={fxAt} />
      <Overlays />
      <Captions />
      <Hud episode={1} date={date} dateKey={dateKey} />
      <CrtOverlay />
      {voice ? <Audio src={staticFile(voice)} /> : null}
      <Audio src={staticFile("music/bed.wav")} volume={(fr) => mix.music * musicVolume(fr)} />
      {SFX.map((s, i) => (
        <Sfx key={i} at={s.at} name={s.name} volume={s.vol} gain={mix.sfx} />
      ))}
    </AbsoluteFill>
  );
};
