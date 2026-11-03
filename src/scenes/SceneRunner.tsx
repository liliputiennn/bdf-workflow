import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, staticFile, useCurrentFrame } from "remotion";
import { CrtOverlay, Hud } from "../lib/components";
import type { PxScene } from "../px/Stage";
import { PixelStage } from "../px/Stage";
import { makeKit, type Imp, type ScriptLine, type SfxCue, type Timings } from "../episodes/kit";
import { makeChunkCaptions } from "./captions";
import { CUSTOM } from "./custom";
import { LIBRARY, SceneStamp, type Env, type SceneImpl } from "./library";
import { planScenes, seedOf, styleOf, type Planned } from "./plan";
import type { ScenesFile } from "./schema";
import type { Gfx } from "../px/gfx";
import { hash } from "../px/gfx";

/** Un épisode décrit par des données : script + timings + scenes.json. */
export type DataEpisode = { id: string; number: number; script: ScriptLine[]; timings: Timings; scenes: ScenesFile };
/** Une ligne de src/episodes/data-index.ts (fichier généré). */
export type DataEntry = { meta: { id: string; number: number; compositionId: string; coverId: string }; script: ScriptLine[]; timings: Timings; scenes: ScenesFile };

const implOf = (p: Planned): SceneImpl => {
  if (p.scene.type !== "sur-mesure") return LIBRARY[p.scene.type];
  const name = (p.scene.params as { composant: string }).composant;
  const impl = CUSTOM[name];
  if (!impl) throw new Error(`scène sur mesure « ${name} » introuvable dans src/scenes/custom/index.ts`);
  return impl;
};

/**
 * Fabrique tout un épisode à partir de ses données : scènes pixel, textes, impulsions, sons.
 * Renvoie les mêmes informations qu'un épisode codé à la main (voir registry.ts).
 */
export const makeDataEpisode = (ep: DataEpisode) => {
  const { pal, pace } = styleOf(ep.scenes);
  const alertLines = ep.scenes.scenes.filter((s) => s.alerte).map((s) => s.phrase - 1);
  const kit = makeKit(ep.script, ep.timings, alertLines, pal.accent);
  const { L, FRAMES } = kit;
  const plan = planScenes(ep.scenes, L, FRAMES, kit.WORDS, ep.id);
  const seed = seedOf(ep.id);
  const envs: Env[] = plan.map((p) => ({ p, pal, pace, talking: kit.speakingAt }));
  const Captions = makeChunkCaptions(ep.script, kit.T, kit.WORDS, pal.accent, alertLines);

  const SCENES: PxScene[] = plan.map((p, i) => ({
    name: `${i + 1}-${p.scene.type}`,
    from: p.from,
    to: p.to,
    tin: i === 0 ? undefined : pace.transitions[(seed + i) % pace.transitions.length],
    tlen: pace.tlen,
    draw: (g, s) => {
      implOf(p).draw(g, s, envs[i]);
      sparkles(g, s.f, p.reveals, pal.accent);
    },
  }));

  const k = pace.punch;
  const IMPULSES: Imp[] = [
    { at: 2, dur: 12, shake: 3 * k, zoom: 0.07 * k, aberr: 2 },
    // chaque changement de scène : petit coup de zoom et de secousse, pour garder du rythme
    ...plan.slice(1).map((p) => ({ at: p.from, dur: 14, zoom: 0.06 * k, shake: 1.5 * k })),
    ...plan.flatMap((p) => p.reveals.map((at) => ({ at, dur: 8, zoom: 0.03 * k, aberr: 1.2 * k }))),
    ...plan.filter((p) => p.stampAt >= 0).map((p) => ({ at: p.stampAt, dur: 12, shake: 4 * k, flash: 0.3, flashColor: pal.accent, zoom: 0.06 })),
  ];
  const baseFx = kit.makeFx(IMPULSES, SCENES);
  /** Caméra jamais immobile : zoom lent dans chaque scène, une fois vers l'avant, une fois vers l'arrière. */
  const drift = (f: number) => {
    const i = Math.max(0, plan.findIndex((p) => f >= p.from && f < p.to));
    const p = plan[i];
    const k = Math.min(1, (f - p.from) / Math.max(1, p.to - p.from));
    return i % 2 ? 1.07 - 0.07 * k : 1 + 0.07 * k;
  };
  const fxAt = (f: number) => {
    const o = baseFx(f);
    return { ...o, zoom: o.zoom * drift(f) };
  };

  const SFX: SfxCue[] = [
    ...kit.transitionSfx(SCENES),
    { at: 0, name: "impact_hit", vol: 0.7 },
    ...plan.flatMap((p) => p.reveals.map((at, j) => ({ at, name: j % 2 ? "ui_pop" : "pop", vol: 0.4 }))),
    ...plan.filter((p) => p.stampAt >= 0).map((p) => ({ at: p.stampAt, name: "stamp_a", vol: 0.85 })),
    ...plan
      .filter((p) => p.scene.type === "chiffre-choc")
      .flatMap((p) => Array.from({ length: 10 }, (_, j) => ({ at: p.from + 8 + j * 4, name: "blip_a", vol: 0.3 }))),
    ...plan.filter((p) => p.scene.type === "coulisses").map((p) => ({ at: p.from + 14, name: "typing", vol: 0.3 })),
    // Max réagit : un son par pose
    ...plan
      .filter((p) => p.scene.type === "perso")
      .flatMap((p): SfxCue[] => {
        const pose = (p.scene.params as { pose: string }).pose;
        if (pose === "choc") return [{ at: p.from + 1, name: "impact_cine", vol: 0.6 }];
        if (pose === "content") return [{ at: p.from + 2, name: "pickup", vol: 0.6 }];
        if (pose === "argent") return [0, 4, 8, 12].map((d) => ({ at: p.from + d, name: "pop", vol: 0.35 }));
        if (pose === "telephone") return [{ at: p.from + 3, name: "blip_b", vol: 0.5 }];
        return [{ at: p.from + 6, name: "ui_pop", vol: 0.4 }];
      }),
  ];

  const Component: React.FC<{ voice?: string; mix?: { music: number; sfx: number } }> = ({ voice = "", mix = { music: 1, sfx: 1 } }) => {
    const f = useCurrentFrame();
    const cur = Math.max(0, plan.findIndex((p) => f >= p.from && f < p.to));
    const Overlay = implOf(plan[cur]).Overlay;
    return (
      <AbsoluteFill style={{ backgroundColor: "#020604" }}>
        <PixelStage scenes={SCENES} lineStarts={L} fx={fxAt} glow={pal.light ? 0.2 : 0.85} />
        <AbsoluteFill style={{ scale: String(1 + (drift(f) - 1) * 0.4) }}>
          <Overlay {...envs[cur]} />
          <SceneStamp {...envs[cur]} />
        </AbsoluteFill>
        <Captions />
        <Hud episode={ep.number} date={ep.scenes.dossier.toUpperCase()} dateKey={0} tint={pal} />
        <CrtOverlay />
        {voice ? <Audio src={staticFile(voice)} /> : null}
        <Audio src={staticFile("music/bed.wav")} volume={(fr) => mix.music * kit.musicVolume(fr)} />
        {SFX.map((s, i) => (
          <kit.Sfx key={i} at={s.at} name={s.name} volume={s.vol} gain={mix.sfx} />
        ))}
      </AbsoluteFill>
    );
  };

  return {
    component: Component,
    frames: FRAMES,
    timings: kit.T,
    sceneStarts: SCENES.map((s) => s.from),
    sfxFrames: SFX.map((s) => s.at).filter((a) => a >= 0),
    plan,
  };
};

/** Petite gerbe d'étincelles pixel à chaque apparition d'un élément. */
const sparkles = (g: Gfx, f: number, reveals: number[], accent: string) => {
  for (const r of reveals) {
    const k = f - r;
    if (k < 0 || k >= 14) continue;
    const cx = 40 + Math.floor(hash(r * 1.7) * 136);
    const cy = 120 + Math.floor(hash(r * 3.1) * 170);
    for (let j = 0; j < 10; j++) {
      const a = (j / 10) * Math.PI * 2 + hash(r + j);
      const d = 4 + k * 2.2;
      g.rect(Math.round(cx + Math.cos(a) * d), Math.round(cy + Math.sin(a) * d), 2, 2, j % 3 ? accent : "#ffffff");
    }
  }
};
