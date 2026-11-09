import type { Scene, Timings } from "../infographie/types";

/** Marque d'un Short à extraire d'un chapitre (numéros de phrase relatifs au chapitre). */
export type ShortMarque = { debut_phrase: number; fin_phrase: number; accroche: string };

export type Chapitre = {
  titre: string;
  /** carte de titre animée avant le chapitre (défaut : oui, sauf pour le chapitre 1) */
  carte?: boolean;
  phrases: string[];
  /** `phrase` relatif au chapitre (1 = première phrase du chapitre) */
  scenes: Scene[];
  short?: ShortMarque;
};

/** `episodes-b/<id>/episode-long.json` */
export type EpisodeLong = {
  id: string;
  titre: string;
  theme: string;
  /** Thème de contraste (ex. chocolat-caramel) appliqué aux scènes de gros sous-titres. */
  theme_accent?: string;
  chaine: string;
  /** Langue du texte parlé et affiché (« en »…) ; sans valeur : le français. */
  langue?: string;
  pause_chapitre_s?: number;
  chapitres: Chapitre[];
};

export type LongProps = { id: string; episode?: EpisodeLong; timings?: Timings };
