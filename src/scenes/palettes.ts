import type { Palette, Rhythm } from "./schema";
import type { Transition } from "../px/Stage";

/** Une palette = un accent (l'identité garde un seul accent) + les tons du fond pixel. */
export type Pal = {
  accent: string;
  dim: string;
  deep: string;
  /** dégradé du fond, du haut vers le bas */
  sky: string[];
  /** lignes de la grille / du papier */
  grid: string;
  /** fond clair (papier) : textes de décor foncés */
  light: boolean;
};

export const PALS: Record<Palette, Pal> = {
  phosphore: { accent: "#3dff8f", dim: "#1f8a4f", deep: "#0d3a22", sky: ["#020604", "#04100a", "#071a10", "#0b2617"], grid: "#11472a", light: false },
  emeraude: { accent: "#2ee6a0", dim: "#17996a", deep: "#06362a", sky: ["#010806", "#03140f", "#062219", "#0a3024"], grid: "#0f4a36", light: false },
  menthe: { accent: "#7dffc4", dim: "#3fae84", deep: "#0e3a2b", sky: ["#030807", "#071510", "#0b2018", "#102c21"], grid: "#1a4d3a", light: false },
  lime: { accent: "#9dff4a", dim: "#5fa82a", deep: "#1f380b", sky: ["#040702", "#0a1305", "#111f08", "#192c0b"], grid: "#2c4a10", light: false },
};

/** Le rythme règle les transitions, la force des impulsions et l'écart entre deux apparitions. */
export type Pace = { transitions: Transition[]; tlen: number; punch: number; stagger: number };
export const PACES: Record<Rhythm, Pace> = {
  pose: { transitions: ["dissolve", "wipe", "slide"], tlen: 9, punch: 0.9, stagger: 0.8 },
  nerveux: { transitions: ["pixelate", "slide", "wipe", "iris"], tlen: 5, punch: 1.5, stagger: 0.55 },
};
