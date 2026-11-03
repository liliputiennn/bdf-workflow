import { ICONES, type Icone } from "../infographie/icons";
import type { Episode } from "../infographie/types";

/**
 * Données d'une miniature + repli automatique.
 * L'épisode peut porter un champ `miniature` ; tout ce qui manque est déduit de `faits.json` et du titre.
 * Pur et sans dépendance Remotion : testé par `tests/miniature.test.ts`.
 */
export const STYLES = ["chiffre", "question", "contraste", "telephone", "pile", "createur"] as const;
export type MiniStyle = (typeof STYLES)[number];

export type Cote = { valeur: string; label: string };

/** Champ `miniature` de `episode.json` (tout est facultatif). */
export type MiniatureSpec = {
  style?: string;
  /** 3 à 5 mots, affichés très gros */
  texte_haut?: string;
  /** le nombre choc (« 14 % »), ou « ? » */
  gros?: string;
  icone?: string;
  /** style « contraste » : deux valeurs face à face */
  contraste?: [Cote, Cote];
};

export type Fait = { claim?: string; valeur?: string | number };
export type Publication = { titre?: string };

export type Resolved = {
  style: MiniStyle;
  texteHaut: string;
  gros: string;
  icone: Icone;
  contraste: [Cote, Cote] | null;
  theme: string;
  chaine: string;
  id: string;
};

export const MAX_MOTS = 5;

const STOP = new Set((
  "le la les l un une des du de d et ou où a à au aux en dans sur sous par pour avec sans ce cet cette ces son sa ses leur leurs " +
  "qui que quoi dont est sont été être avoir fait fais comment pourquoi quand combien quel quelle quels quelles pas plus très " +
  "il elle ils elles on nous vous je tu y se s qu n m t c ne mais donc car si"
).split(" "));

const NUM = /\d[\d  .,]*(?:[–-]\s?\d[\d  .,]*)?\s?(?:%|\$|€|£|ans?|x|k|M|Md|milliards?|millions?)?/;

const norm = (s: string) => s.replace(/[  ]/g, " ").replace(/\s+/g, " ").trim();
const words = (s: string) => norm(s).split(" ").filter(Boolean);

/** « 14% » → « 14 % », « 1.50$ » → « 1.50 $ » : espace avant le symbole, jamais de coupure. */
export const formatGros = (raw: string | number): string => {
  const s = norm(String(raw)).replace(/\s?(%|\$|€|£)$/, " $1");
  return s.replace(/ /g, " ");
};

/** Le premier nombre « parlant » d'une valeur ou d'une phrase, ou null. */
export const premierNombre = (v: string | number | undefined): string | null => {
  if (v === undefined || v === null) return null;
  const s = norm(String(v));
  if (!/\d/.test(s)) return null;
  if (s.length <= 9) return formatGros(s);
  const m = s.match(NUM);
  return m ? formatGros(m[0]) : null;
};

/** Mots-clés d'un texte : sans mots vides ni chiffres, dans l'ordre, au plus `n`. */
export const motsCles = (txt: string, n: number): string[] =>
  words(txt.replace(/[’']/g, " "))
    .filter((w) => !/\d/.test(w) && !STOP.has(w.toLowerCase()))
    .slice(0, n);

export const clampMots = (txt: string, n = MAX_MOTS): string => words(txt).slice(0, n).join(" ");

const ICON_HINTS: [RegExp, Icone][] = [
  [/hot-?dog|saucisse|restaurant/i, "hotdog"],
  [/carte|abonnement|membre|badge|cotisation/i, "carte"],
  [/magasin|boutique|supermarch|enseigne|grande surface/i, "magasin"],
  [/prix|marge|argent|gagne|b[ée]n[ée]fice|profit|dollar|euro|pi[èe]ce/i, "pieces"],
  [/panier|courses|achat|vente/i, "panier"],
];

const pickIcone = (ep: Episode, spec: MiniatureSpec, claim?: string): Icone => {
  if (spec.icone && (ICONES as readonly string[]).includes(spec.icone)) return spec.icone as Icone;
  // l'icône doit illustrer le chiffre mis en avant, pas seulement le sujet de la vidéo
  if (claim) for (const [re, ic] of ICON_HINTS) if (re.test(claim)) return ic;
  const hit = ep.scenes.find((s) => s.type === "objet") as { params?: { icone?: Icone } } | undefined;
  if (hit?.params?.icone && ICONES.includes(hit.params.icone)) return hit.params.icone;
  const txt = `${ep.titre} ${(ep.phrases ?? []).join(" ")}`;
  for (const [re, ic] of ICON_HINTS) if (re.test(txt)) return ic;
  return "pieces";
};

const faitsChiffres = (faits: Fait[]): { n: string; f: Fait }[] =>
  faits.flatMap((f) => {
    const n = premierNombre(f.valeur);
    return n ? [{ n, f }] : [];
  });

const labelDe = (f: Fait | undefined, fallback: string, n = 2) => {
  const k = motsCles(f?.claim ?? "", n).join(" ");
  return (k || fallback).toUpperCase();
};

/** Déduit tout ce qui manque. `forceStyle` (rendu de secours) l'emporte sur le champ de l'épisode. */
export function resolveMiniature(
  ep: Episode & { miniature?: MiniatureSpec },
  faits: Fait[] | null,
  pub: Publication | null,
  over: { style?: string; theme?: string; miniature?: MiniatureSpec } = {},
): Resolved {
  const spec: MiniatureSpec = { ...(ep.miniature ?? {}), ...(over.miniature ?? {}) };
  const titre = pub?.titre || ep.titre || "";
  const chiffres = faitsChiffres(faits ?? []);
  const gros0 = spec.gros && spec.gros.trim() !== "?" ? formatGros(spec.gros) : chiffres[0]?.n ?? premierNombre(titre);

  // contraste : deux valeurs, données ou tirées des deux premiers faits chiffrés
  let contraste: [Cote, Cote] | null = null;
  if (spec.contraste?.length === 2) {
    contraste = spec.contraste.map((c) => ({ valeur: formatGros(c.valeur), label: clampMots(c.label.toUpperCase(), 3) })) as [Cote, Cote];
  } else if (chiffres.length >= 2) {
    contraste = [
      { valeur: chiffres[0].n, label: labelDe(chiffres[0].f, "AVANT") },
      { valeur: chiffres[1].n, label: labelDe(chiffres[1].f, "APRÈS") },
    ];
  }

  // style : demandé > champ de l'épisode > déduit
  const demande = over.style ?? spec.style;
  let style: MiniStyle;
  if (demande && (STYLES as readonly string[]).includes(demande)) style = demande as MiniStyle;
  else if (!gros0) style = "question";
  else if (/\b(vs|contre|ou)\b/i.test(titre) && contraste) style = "contraste";
  else style = "chiffre";
  // un style impossible faute de données se replie sur celui qui reste possible
  if (style === "contraste" && !contraste) style = gros0 ? "chiffre" : "question";

  let gros: string;
  if (style === "question") gros = "?";
  else gros = gros0 ?? "?";
  const metEnScene = style === "chiffre" || style === "telephone" || style === "pile" || style === "createur";
  if (metEnScene && gros === "?") style = "question";

  // texte du haut : 3 à 5 mots
  let texteHaut = spec.texte_haut?.trim() ?? "";
  if (!texteHaut) {
    const source = metEnScene && style !== "question" ? chiffres[0]?.f.claim ?? titre : titre;
    const n = style === "question" ? 3 : 3;
    texteHaut = motsCles(source, n).join(" ");
    if (!texteHaut) texteHaut = motsCles(titre, n).join(" ") || titre;
  }
  texteHaut = clampMots(texteHaut.toUpperCase(), MAX_MOTS);

  return {
    style,
    texteHaut,
    gros,
    icone: pickIcone(ep, spec, metEnScene && style !== "question" ? chiffres[0]?.f.claim : undefined),
    contraste: style === "contraste" ? contraste : null,
    theme: over.theme ?? ep.theme,
    chaine: ep.chaine,
    id: ep.id,
  };
}

/** Largeur approximative d'un texte en capitales Anton, en « em » (pour dimensionner sans mesurer). */
export const largeurEm = (txt: string): number =>
  [...txt].reduce((w, c) => {
    if (c === " " || c === " ") return w + 0.24;
    if (c === " ") return w + 0.16;
    if (c === "%") return w + 0.86;
    if ("'’.,:;!".includes(c)) return w + 0.22;
    if (c === "?") return w + 0.44;
    if (/\d/.test(c)) return w + 0.5;
    return w + 0.47;
  }, 0);

/** Corps de police maximal tel que le texte tienne dans `maxW`, plafonné à `maxH`. */
export const ajuste = (txt: string, maxW: number, maxH: number): number => Math.floor(Math.min(maxH, maxW / Math.max(largeurEm(txt), 0.1)));
