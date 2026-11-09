import React from "react";

/**
 * Langue du texte affiché (`Episode.langue`) : règle la mise en forme des nombres et les rares mots écrits par le moteur lui-même.
 * Sans langue (épisodes existants) : le français, comme avant. Fourni par `Short.tsx` et `Long.tsx`, lu par les scènes.
 */
export const LangueCtx = React.createContext<string | undefined>(undefined);

export const estAnglais = (langue?: string): boolean => !!langue && langue.toLowerCase().startsWith("en");

/** 12500.5 -> « 12 500,5 » (français) ou « 12,500.5 » (anglais). */
export const formatNombre = (n: number, d = 0, langue?: string): string => {
  const [i, f] = n.toFixed(d).split(".");
  if (estAnglais(langue)) {
    const g = i.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return f ? `${g}.${f}` : g;
  }
  const g = i.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return f ? `${g},${f}` : g;
};

const MOTS = {
  fr: { source: "Source :", vendu: "Vendu" },
  en: { source: "Source:", vendu: "Sold" },
} as const;

export const mot = (langue: string | undefined, cle: keyof (typeof MOTS)["fr"]): string => MOTS[estAnglais(langue) ? "en" : "fr"][cle];

/** Mot du moteur dans la langue de l'épisode (« Source : », « Vendu »). */
export const Mot: React.FC<{ k: keyof (typeof MOTS)["fr"] }> = ({ k }) => <>{mot(React.useContext(LangueCtx), k)}</>;
