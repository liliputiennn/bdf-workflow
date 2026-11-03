import type React from "react";
import { MCO_FRAMES, MCO_SCENE_STARTS, MCO_SFX_FRAMES, MCO_TIMINGS, Mco, type MixProps } from "./Mco";
import { McoCover } from "./McoCover";
import { APOLLO_FRAMES, APOLLO_SCENE_STARTS, APOLLO_SFX_FRAMES, APOLLO_TIMINGS, Apollo13 } from "./Apollo13";
import { Apollo13Cover } from "./Apollo13Cover";
import { DATA_EPISODES } from "./data-index";
import { makeDataCover } from "../scenes/DataCover";
import { makeDataEpisode } from "../scenes/SceneRunner";

export type RegistryEntry = {
  id: string;
  compositionId: string;
  coverId: string;
  frames: number;
  fps: 30;
  component: React.FC<{ voice?: string; mix?: MixProps }>;
  cover: React.FC;
  timings: { total: number; lines: { start: number; end: number }[] };
  sceneStarts: number[];
  sfxFrames: number[];
};

/** Épisodes signature, codés à la main (niveau 3). */
const CODED: Record<string, RegistryEntry> = {
  "mars-climate-orbiter": {
    id: "mars-climate-orbiter",
    compositionId: "Ep01-MarsClimateOrbiter",
    coverId: "Ep01-Cover",
    frames: MCO_FRAMES,
    fps: 30,
    component: Mco,
    cover: McoCover,
    timings: MCO_TIMINGS,
    sceneStarts: MCO_SCENE_STARTS,
    sfxFrames: MCO_SFX_FRAMES,
  },
  "apollo-13": {
    id: "apollo-13",
    compositionId: "Ep02-Apollo13",
    coverId: "Ep02-Apollo13-Cover",
    frames: APOLLO_FRAMES,
    fps: 30,
    component: Apollo13,
    cover: Apollo13Cover,
    timings: APOLLO_TIMINGS,
    sceneStarts: APOLLO_SCENE_STARTS,
    sfxFrames: APOLLO_SFX_FRAMES,
  },
};

/** Épisodes en données (niveaux 1 et 2) : episodes/<id>/scenes.json, sans code. */
const DATA: Record<string, RegistryEntry> = Object.fromEntries(
  DATA_EPISODES.map(({ meta, script, timings, scenes }) => {
    const ep = makeDataEpisode({ id: meta.id, number: meta.number, script, timings, scenes });
    const entry: RegistryEntry = {
      id: meta.id,
      compositionId: meta.compositionId,
      coverId: meta.coverId,
      frames: ep.frames,
      fps: 30,
      component: ep.component,
      cover: makeDataCover(scenes),
      timings: ep.timings,
      sceneStarts: ep.sceneStarts,
      sfxFrames: ep.sfxFrames,
    };
    return [meta.id, entry];
  }),
);

/** Un épisode = une entrée. Un épisode codé garde la priorité sur des données du même nom. */
export const EPISODES: Record<string, RegistryEntry> = { ...DATA, ...CODED };
