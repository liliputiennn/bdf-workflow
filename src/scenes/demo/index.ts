import { makeDataCover } from "../DataCover";
import { provisionalTimings } from "../plan";
import { makeDataEpisode } from "../SceneRunner";
import type { ScenesFile } from "../schema";
import script from "./script.json";
import scenes from "./scenes.json";

/** Catalogue du stock de scènes (boulangerie imaginaire, chiffres inventés) : à prévisualiser, jamais à publier. */
export const DEMO_SCENES = scenes as unknown as ScenesFile;
export const DEMO_SCRIPT = script;
export const DEMO = makeDataEpisode({ id: "demo-scenes", number: 0, script, timings: provisionalTimings(script), scenes: DEMO_SCENES });
export const DemoCover = makeDataCover(DEMO_SCENES);
