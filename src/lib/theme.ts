import { Easing, interpolate } from "remotion";
import { loadFont as loadArchivo } from "@remotion/google-fonts/ArchivoBlack";
import { loadFont as loadSilk } from "@remotion/google-fonts/Silkscreen";

export const TITLE = loadArchivo("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] }).fontFamily;
export const PIXEL = loadSilk("normal", { weights: ["400", "700"], subsets: ["latin", "latin-ext"] }).fontFamily;

/** Identité « Le Bureau des Faits » : un seul accent, vert phosphore. */
export const C = {
  bg: "#07110c",
  bgHi: "#0f2219",
  accent: "#3dff8f",
  accentDim: "#1f8a4f",
  accentDeep: "#0d3a22",
  white: "#f2f0e6",
  grey: "#9a9a92",
  greyDark: "#4a4a46",
  ink: "#040a07",
  alert: "#e8433a",
  alertDeep: "#6e1a16",
  skin: "#d9c7a3",
};

export const CHANNEL = "BUREAU DES FAITS";

export const OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const INOUT = Easing.bezier(0.65, 0, 0.35, 1);

export const tw = (
  f: number,
  input: [number, number],
  output: [number, number],
  easing: (t: number) => number = OUT,
) =>
  interpolate(f, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing,
  });

/** Quantifie le temps pour un mouvement « en pas » façon pixel art (12 i/s à 30 i/s). */
export const stepped = (f: number, every = 2.5) => Math.floor(f / every) * every;

/** Pseudo-aléatoire déterministe. */
export const rand = (seed: number) => {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};
