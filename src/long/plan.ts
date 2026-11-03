import type { Scene, Timings } from "../infographie/types";
import type { EpisodeLong } from "./types";

export type ChapitrePlan = {
  n: number;
  titre: string;
  /** numéros globaux (1 = première phrase du long) */
  first: number;
  last: number;
  carte: boolean;
};
export type LongPlan = { phrases: string[]; scenes: Scene[]; chapitres: ChapitrePlan[] };

/** Aplatit les chapitres : phrases bout à bout, scènes en numérotation globale (même ordre que `autopilot/long/longlib.py`). */
export const flatten = (ep: EpisodeLong): LongPlan => {
  const phrases: string[] = [];
  const scenes: Scene[] = [];
  const chapitres: ChapitrePlan[] = [];
  ep.chapitres.forEach((c, k) => {
    const first = phrases.length + 1;
    phrases.push(...c.phrases);
    c.scenes.forEach((s) => scenes.push({ ...s, phrase: first + s.phrase - 1 }));
    chapitres.push({ n: k + 1, titre: c.titre, first, last: phrases.length, carte: c.carte ?? k > 0 });
  });
  return { phrases, scenes, chapitres };
};

export type ChapitreTemps = ChapitrePlan & {
  /** début de la parole du chapitre */
  start: number;
  /** début de la carte de titre (= fin de la phrase précédente) ; null sans carte */
  carteDe: number | null;
  /** frontière de segment dans la barre de progression */
  borne: number;
  fin: number;
};

export const chapitresTemps = (plan: LongPlan, t: Timings): ChapitreTemps[] =>
  plan.chapitres.map((c, k, all) => {
    const line = (p: number) => t.lines[Math.min(p - 1, t.lines.length - 1)];
    const start = line(c.first).start;
    const carteDe = c.carte && c.first > 1 ? line(c.first - 1).end + 0.1 : null;
    const borne = k === 0 ? 0 : carteDe ?? start;
    const suivant = all[k + 1];
    const fin = suivant ? (suivant.carte && suivant.first > 1 ? line(suivant.first - 1).end + 0.1 : line(suivant.first).start) : t.total;
    return { ...c, start, carteDe, borne, fin };
  });
