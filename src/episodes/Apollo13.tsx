import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, staticFile, useCurrentFrame } from "remotion";
import { BigCounter, CrtOverlay, DataLabel, Hud, Stamp } from "../lib/components";
import { C } from "../lib/theme";
import { apolloKeys, buildApolloScenes } from "../px/apolloScenes";
import { PixelStage } from "../px/Stage";
import script from "../../episodes/apollo-13/script.json";
import timings from "./apollo-13.timings.json";
import { makeKit, type Imp, type SfxCue, type Timings } from "./kit";

/** Voix off : déposée dans la Console (public/apollo-13/), vide tant qu'elle n'existe pas. */
export const APOLLO_VOICE = "";

const kit = makeKit(script, timings as Timings, [0, 6, 7, 13, 17]);
const { L, at, FRAMES } = kit;
export const APOLLO_FRAMES = FRAMES;
const K = apolloKeys(L, at);
const SCENES = buildApolloScenes(L, FRAMES);

const IMPULSES: Imp[] = [
  { at: K.tape, dur: 12, shake: 3, flash: 0.35, zoom: 0.08 },
  { at: K.ignition, dur: 70, shake: 2.5 },
  { at: K.boom, dur: 18, shake: 7, aberr: 5, glitch: 0.8, flash: 0.9, flashColor: "#fff2b0", zoom: 0.14 },
  { at: K.houston, dur: 12, glitch: 0.4, aberr: 2 },
  { at: K.lightsOff, dur: 14, glitch: 0.5, aberr: 2 },
  { at: K.squeeze, dur: 10, shake: 3, zoom: 0.06 },
  { at: K.mortal, dur: 16, aberr: 3, glitch: 0.4, zoom: 0.06 },
  { at: K.reject, dur: 10, shake: 4, aberr: 2 },
  { at: K.idea, dur: 10, flash: 0.3, flashColor: "#ffc23d" },
  { at: K.tapeRoll, dur: 10, shake: 2, zoom: 0.05 },
  { at: K.works, dur: 14, flash: 0.35, flashColor: "#3dff8f", zoom: 0.08 },
  { at: K.splash, dur: 14, shake: 3, flash: 0.3 },
  { at: K.question, dur: 8, zoom: 0.1, aberr: 2 },
  { at: K.classified, dur: 12, shake: 4, flash: 0.35, flashColor: "#3dff8f", zoom: 0.06 },
];
const fxAt = kit.makeFx(IMPULSES, SCENES);

const SFX: SfxCue[] = [
  ...kit.transitionSfx(SCENES),
  { at: 0, name: "impact_hit", vol: 0.7 },
  { at: 6, name: "alarm", vol: 0.25 },
  { at: K.tape, name: "whoosh_pop", vol: 0.6 },
  { at: K.tape + 10, name: "thud", vol: 0.8 },
  { at: K.tape + 14, name: "stamp_a", vol: 0.9 },
  { at: K.ignition, name: "rocket", vol: 0.9 },
  { at: K.ignition, name: "impact_braam", vol: 0.45 },
  ...[0.25, 0.5, 0.75].map((fr) => ({ at: at(3, fr), name: "pop", vol: 0.4 })),
  ...Array.from({ length: 12 }, (_, k) => ({ at: L[5] + 4 + k * 4, name: "blip_a", vol: 0.35 })),
  { at: L[6], name: "riser_cine", vol: 0.6 },
  { at: K.boom, name: "impact_cine", vol: 1 },
  { at: K.boom, name: "glitch_hd", vol: 0.45 },
  { at: K.boom + 2, name: "stamp_b", vol: 0.9 },
  { at: K.houston, name: "static_fm", vol: 0.3 },
  { at: K.lightsOff, name: "glitch_1", vol: 0.4 },
  { at: K.lightsOff + 10, name: "alarm", vol: 0.25 },
  ...[0, 10, 20].map((d) => ({ at: L[10] + d, name: "whoosh_short", vol: 0.35 })),
  { at: K.squeeze, name: "stamp_trad", vol: 0.8 },
  { at: K.mortal, name: "alarm_severe", vol: 0.35 },
  { at: K.mortal + 2, name: "stamp_a", vol: 0.8 },
  { at: K.full, name: "blip_b", vol: 0.5 },
  ...[0, 24, 48].map((d) => ({ at: at(17, 0.2) + 12 + d, name: "thud", vol: 0.7 })),
  { at: K.reject, name: "stamp_b", vol: 0.8 },
  { at: K.idea, name: "pickup", vol: 0.6 },
  ...[0.05, 0.4, 0.7].map((fr) => ({ at: at(20, fr), name: "pop", vol: 0.45 })),
  { at: K.tapeRoll, name: "whoosh_pop", vol: 0.5 },
  { at: L[22], name: "typing", vol: 0.4 },
  ...Array.from({ length: 4 }, (_, k) => ({ at: L[22] + k * 14, name: "menu", vol: 0.5 })),
  ...Array.from({ length: 4 }, (_, k) => ({ at: L[23] + 12 * (k + 1), name: "thud", vol: 0.6 })),
  { at: K.plug, name: "pickup", vol: 0.6 },
  { at: K.works, name: "impact_hit", vol: 0.7 },
  { at: K.works + 2, name: "stamp_trad", vol: 0.8 },
  { at: L[26], name: "whoosh_sub", vol: 0.4 },
  { at: K.splash, name: "impact_boom", vol: 0.7 },
  { at: L[27] + 6, name: "stamp_a", vol: 0.8 },
  { at: K.question - 30, name: "riser_cine", vol: 0.5 },
  { at: K.question, name: "impact_braam", vol: 0.6 },
  { at: K.flag, name: "ui_pop", vol: 0.7 },
  { at: K.swap, name: "whoosh_pop", vol: 0.5 },
  { at: L[31], name: "pop", vol: 0.4 },
  { at: K.classified, name: "impact_cine", vol: 0.9 },
  { at: K.classified, name: "stamp_trad", vol: 0.9 },
];

const Overlays: React.FC = () => {
  const f = useCurrentFrame();
  const show = (a: number, b: number) => f >= a && f < b;
  return (
    <>
      {show(0, L[2]) && <DataLabel text="APOLLO 13 · AVRIL 1970" at={8} x={540} y={540} color={C.alert} size={34} />}
      {show(K.tape, L[2]) && <Stamp text="SAUVÉS" at={K.tape + 14} x={540} y={1420} size={120} color={C.accent} rotate={-8} />}
      {show(L[2], L[3]) && <DataLabel text="11.04.1970 · FLORIDE" at={L[2] + 8} x={540} y={540} size={34} />}
      {show(L[3], L[4]) && (
        <>
          <DataLabel text="JIM LOVELL" at={at(3, 0.25)} x={210} y={1310} size={26} />
          <DataLabel text="JACK SWIGERT" at={at(3, 0.5)} x={540} y={1310} size={26} />
          <DataLabel text="FRED HAISE" at={at(3, 0.75)} x={870} y={1310} size={26} />
        </>
      )}
      {show(L[4], L[5]) && <DataLabel text="TOUT VA BIEN ✓" at={L[4] + 10} x={540} y={1500} color={C.accent} size={36} />}
      {show(L[5], L[6]) && <BigCounter from={0} to={300000} at={L[5] + 4} dur={48} suffix=" KM" x={540} y={560} size={96} />}
      {show(K.boom, L[8]) && <Stamp text="BANG" at={K.boom + 2} x={540} y={1450} size={150} />}
      {show(L[7], L[8]) && <DataLabel text="RÉSERVOIR D'OXYGÈNE" at={L[7] + 6} x={540} y={560} color={C.alert} size={36} />}
      {show(L[8], L[9]) && <DataLabel text="« HOUSTON, ON A EU UN PROBLÈME »" at={L[8] + 4} x={540} y={1420} color={C.accent} size={30} />}
      {show(L[11], L[12]) && <DataLabel text="PRÉVU POUR 2" at={L[11] + 4} x={540} y={540} size={40} />}
      {show(K.squeeze, L[12]) && <Stamp text="3 À BORD" at={K.squeeze} x={540} y={1500} size={96} />}
      {show(L[13], L[14]) && <DataLabel text="GAZ CARBONIQUE (CO2)" at={L[13] + 4} x={540} y={540} color={C.alert} size={34} />}
      {show(K.mortal, L[14]) && <Stamp text="MORTEL" at={K.mortal + 2} x={420} y={1480} size={110} />}
      {show(L[16], L[17]) && <DataLabel text="FILTRE DE RECHANGE" at={L[16] + 6} x={540} y={540} size={34} />}
      {show(K.reject, L[18]) && <Stamp text="ÇA NE RENTRE PAS" at={K.reject} x={540} y={1500} size={72} />}
      {show(L[18], L[19]) && <DataLabel text="HOUSTON · CENTRE DE CONTRÔLE" at={L[18] + 6} x={540} y={540} color={C.accent} size={32} />}
      {show(L[19], L[20]) && <DataLabel text="SEULEMENT CE QU'IL Y A À BORD" at={L[19] + 6} x={540} y={540} color={C.accent} size={32} />}
      {show(K.works, L[26]) && <Stamp text="ÇA MARCHE" at={K.works + 2} x={540} y={600} size={110} color={C.accent} rotate={-6} />}
      {show(L[26], L[28]) && <DataLabel text="17.04.1970 · OCÉAN PACIFIQUE" at={L[26] + 6} x={540} y={540} size={32} />}
      {show(L[27], L[28]) && <Stamp text="VIVANTS" at={L[27] + 6} x={540} y={900} size={120} color={C.accent} rotate={-6} />}
      {show(K.flag, L[30]) && <DataLabel text="« LA BOÎTE AUX LETTRES »" at={K.flag} x={540} y={1500} color={C.accent} size={36} />}
      {show(L[30], L[31]) && <DataLabel text="PRÉVU : KEN MATTINGLY" at={L[30] + 4} x={540} y={540} color={C.white} size={30} />}
      {show(K.swap, L[31]) && <DataLabel text="REMPLAÇANT : JACK SWIGERT" at={K.swap + 6} x={540} y={630} color={C.accent} size={30} />}
      {show(L[31], FRAMES) && <DataLabel text="SAUVÉE PAR DU SCOTCH" at={L[31] + 4} x={540} y={540} color={C.accent} size={38} />}
      {show(K.classified, FRAMES) && <Stamp text="DOSSIER CLASSÉ" at={K.classified} x={540} y={1630} size={84} color={C.accent} rotate={-6} />}
    </>
  );
};

const DATES: [number, string][] = [
  [0, "APOLLO 13"],
  [L[2], "04.1970"],
  [L[26], "17.04.1970"],
  [L[31], "CLASSÉ"],
];

export const Apollo13: React.FC<{ voice?: string; mix?: { music: number; sfx: number } }> = ({ voice = APOLLO_VOICE, mix = { music: 1, sfx: 1 } }) => {
  const f = useCurrentFrame();
  const [dateKey, date] = [...DATES].reverse().find(([a]) => f >= a)!;
  return (
    <AbsoluteFill style={{ backgroundColor: "#020604" }}>
      <PixelStage scenes={SCENES} lineStarts={L} fx={fxAt} />
      <Overlays />
      <kit.Captions />
      <Hud episode={2} date={date} dateKey={dateKey} />
      <CrtOverlay />
      {voice ? <Audio src={staticFile(voice)} /> : null}
      <Audio src={staticFile("music/bed.wav")} volume={(fr) => mix.music * kit.musicVolume(fr)} />
      {SFX.map((s, i) => (
        <kit.Sfx key={i} at={s.at} name={s.name} volume={s.vol} gain={mix.sfx} />
      ))}
    </AbsoluteFill>
  );
};

export const APOLLO_SCENE_STARTS = SCENES.map((s) => s.from);
export const APOLLO_SFX_FRAMES = SFX.map((s) => s.at).filter((a) => a >= 0);
export const APOLLO_TIMINGS = kit.T;
