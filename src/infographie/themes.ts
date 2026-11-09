import { loadFont as loadGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";

export const UI = loadGrotesk("normal", { weights: ["500", "700"], subsets: ["latin", "latin-ext"] }).fontFamily;
export const GIANT = loadAnton("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] }).fontFamily;

/**
 * Un thème = des couleurs, rien d'autre. Un sujet business choisit le sien (champ « theme » de l'épisode).
 * Pour en ajouter un : une entrée ici, aucune scène à modifier.
 */
export type Theme = {
  id: string;
  /** dégradé du fond, haut puis bas */
  bg: [string, string];
  card: string;
  line: string;
  ink: string;
  muted: string;
  accent: string;
  /** texte posé sur l'accent */
  onAccent: string;
  deep: string;
  hot: string;
  alert: string;
  /** thème sombre (ombres, grille) */
  dark: boolean;
  /** symboles flottants du fond (défaut : € % $ +) */
  glyphs?: string[];
};

export const THEMES: Record<string, Theme> = {
  "papier-vert": {
    id: "papier-vert", bg: ["#F6F3EA", "#E9EFE3"], card: "#FFFFFF", line: "#D8D6C8", ink: "#12201A", muted: "#6B7A70",
    accent: "#0E9F5A", onAccent: "#FFFFFF", deep: "#0A6B3C", hot: "#F2A900", alert: "#E5484D", dark: false,
  },
  "menthe": {
    id: "menthe", bg: ["#E3F7EC", "#CDEEDC"], card: "#FFFFFF", line: "#B5DCC6", ink: "#0B2A1C", muted: "#4F7A64",
    accent: "#10B26C", onAccent: "#FFFFFF", deep: "#0B7A49", hot: "#FF9F1C", alert: "#E5484D", dark: false,
  },
  "nuit-vert": {
    id: "nuit-vert", bg: ["#06100B", "#0C1F16"], card: "#101C16", line: "#24382E", ink: "#EEF5F0", muted: "#8FA89A",
    accent: "#35F08A", onAccent: "#07100C", deep: "#12A35A", hot: "#FFD24A", alert: "#FF6A5A", dark: true,
  },
  "lime-vif": {
    id: "lime-vif", bg: ["#EEF9C9", "#D6F08F"], card: "#FFFFFF", line: "#BBD86A", ink: "#16260B", muted: "#55702F",
    accent: "#2FA84F", onAccent: "#FFFFFF", deep: "#1B7A32", hot: "#FF8A00", alert: "#E5484D", dark: false,
  },
  "foret": {
    id: "foret", bg: ["#0E4A32", "#176B48"], card: "#0B3524", line: "#2C8A60", ink: "#F0FAF4", muted: "#A6D6BC",
    accent: "#4BF59B", onAccent: "#062A1A", deep: "#12A35A", hot: "#FFD24A", alert: "#FF7A6A", dark: true,
  },
  "jade-clair": {
    id: "jade-clair", bg: ["#C9F0DC", "#8EDDB6"], card: "#FFFFFF", line: "#7CCFA4", ink: "#062A1A", muted: "#2F6E52",
    accent: "#0B9E5C", onAccent: "#FFFFFF", deep: "#07703F", hot: "#FF9F1C", alert: "#E5484D", dark: false,
  },
  "indigo-or": {
    id: "indigo-or", bg: ["#140B45", "#2A1580"], card: "#1C1166", line: "#4A38B5", ink: "#F5F3FF", muted: "#B5ABEF",
    accent: "#FFC83D", onAccent: "#1A0F4D", deep: "#E0A400", hot: "#FF6B9A", alert: "#FF6A5A", dark: true,
  },
  "aurore": {
    id: "aurore", bg: ["#4A1FB8", "#C026D3"], card: "#2E1070", line: "#8B5CF6", ink: "#FFFFFF", muted: "#E6C9FF",
    accent: "#FFE14D", onAccent: "#2E1070", deep: "#FFB800", hot: "#5CF2E6", alert: "#FF7A7A", dark: true,
  },
  "bleu-electrique": {
    id: "bleu-electrique", bg: ["#EDF3FF", "#D3E2FF"], card: "#FFFFFF", line: "#BCD0F7", ink: "#0B1B45", muted: "#5A6FA3",
    accent: "#2F6BFF", onAccent: "#FFFFFF", deep: "#1B47C2", hot: "#FF8A00", alert: "#E5484D", dark: false,
  },
  "soleil": {
    id: "soleil", bg: ["#FFC21F", "#FF8A1F"], card: "#FFFFFF", line: "#F0A030", ink: "#14123A", muted: "#7A4A12",
    accent: "#14123A", onAccent: "#FFFFFF", deep: "#2B2380", hot: "#E5304F", alert: "#E5304F", dark: false,
  },
  "corail-nuit": {
    id: "corail-nuit", bg: ["#0A0F2E", "#16205C"], card: "#111A4A", line: "#2E3E94", ink: "#F1F4FF", muted: "#9FB0F0",
    accent: "#FF5E7E", onAccent: "#FFFFFF", deep: "#E0335A", hot: "#3DE0FF", alert: "#FFB020", dark: true,
  },
  "noir-or": {
    id: "noir-or", bg: ["#0B0B0F", "#1A1620"], card: "#15131A", line: "#3A3340", ink: "#FAF6EC", muted: "#A89F8E",
    accent: "#F5C451", onAccent: "#14110A", deep: "#C99A2E", hot: "#FF6B6B", alert: "#FF6A5A", dark: true,
  },
  "chocolat-caramel": {
    id: "chocolat-caramel", bg: ["#1E0F0A", "#3D1E12"], card: "#2A140D", line: "#5A3326", ink: "#FBEFE3", muted: "#C8A48E",
    accent: "#E8A35B", onAccent: "#2A140D", deep: "#B86B2B", hot: "#FFD28A", alert: "#FF6A5A", dark: true,
  },
  "chocolat-lait": {
    id: "chocolat-lait", bg: ["#F6E6D4", "#E4C6A6"], card: "#FFF9F2", line: "#D3AE8C", ink: "#3B1C10", muted: "#8A5E45",
    accent: "#7B3F1D", onAccent: "#FFF9F2", deep: "#4E2410", hot: "#E8A317", alert: "#C2362B", dark: false,
  },
  // Vert pelouse (bannière « La débrouille ») : même moteur, mêmes cartes, seules les couleurs changent.
  "pelouse": {
    id: "pelouse", bg: ["#EAF6DF", "#C9E5B5"], card: "#FCFFF8", line: "#AFD39A", ink: "#10341A", muted: "#587A55",
    accent: "#2F8F3C", onAccent: "#FFFFFF", deep: "#1B5E26", hot: "#F6B73C", alert: "#D9483B", dark: false,
  },
  "pelouse-nuit": {
    id: "pelouse-nuit", bg: ["#0C2612", "#1B4A25"], card: "#12361B", line: "#2E6B3A", ink: "#F2FBEA", muted: "#A6CBA0",
    accent: "#7ED957", onAccent: "#0C2612", deep: "#3FA34D", hot: "#FFE08A", alert: "#FF7A6B", dark: true,
  },
  "chocolat-framboise": {
    id: "chocolat-framboise", bg: ["#3A1A12", "#6B2F20"], card: "#2C130D", line: "#8A4A38", ink: "#FFF1EA", muted: "#E0B3A3",
    accent: "#FF5C8A", onAccent: "#2C130D", deep: "#D23A6A", hot: "#FFC857", alert: "#FFB020", dark: true,
  },
  "parchemin": {
    id: "parchemin", bg: ["#F3E7CC", "#E6D3A8"], card: "#FBF4E1", line: "#CDB98A", ink: "#2B1D12", muted: "#7A6648",
    accent: "#9B2D20", onAccent: "#FFF8EA", deep: "#6E1F16", hot: "#C98A1B", alert: "#B3261E", dark: false, glyphs: ["+", "·"],
  },
};

export const getTheme = (id?: string): Theme => THEMES[id ?? ""] ?? THEMES["papier-vert"];
