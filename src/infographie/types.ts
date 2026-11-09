import type { Icone } from "./icons";

/** Même format que `src/episodes/*.timings.json` (calage au mot près). */
export type Word = { w: string; start: number; end: number };
export type Line = { start: number; end: number; words: Word[] };
export type Timings = { total: number; lines: Line[] };

export type SceneParams = {
  "titre-geant": { accents?: string[] };
  chiffre: { valeur: number; prefixe?: string; suffixe?: string; decimales?: number; etiquette: string; sous?: string };
  /** `part` : portion de la barre mise en avant (même unité que `valeur`), dessinée à l'échelle exacte. */
  barres: { barres: { label: string; valeur: number; accent?: boolean; part?: number }[]; badge?: string; titre?: string };
  courbe: { titre?: string; plafond: number; etiquettePlafond: string; etiquetteCourbe: string };
  "ligne-temps": { de: string; a: string; valeur: string; etiquette: string };
  anneau: { valeur: number; repere?: number; centre: string; etiquette: string };
  duel: { haut: { titre: string; part: number }; bas: { titre: string; part: number }; titre?: string };
  objet: { icone: Icone; titre: string; sous?: string };
  question: { question: string; pistes?: string[] };
  liste: { titre?: string; items: { texte: string; valeur?: string }[] };
  /** Panneau « business n°X » : lignes label / valeur (coût de lancement, temps, gain par jour…), `accent` met une ligne en avant. */
  fiche: { numero: number | string; titre: string; badge?: string; lignes: { label: string; valeur: string; accent?: boolean }[] };
  /** Carte de prix de marketplace dessinée par nous avec les prix réellement constatés ; `fichier` = photo facultative (chemin sous episodes-b). */
  annonce: { titre: string; prix: string; ancien?: string; etat?: string; lieu?: string; source?: string; vendu?: boolean; fichier?: string; recherche?: string; credit?: string };
  /** Photo plein cadre (réelle ou générée) qui montre de quoi on parle ; `fichier` = chemin sous episodes-b, ex. « mon-episode/visuels/laser.jpg ». */
  photo: { fichier?: string; recherche?: string; legende?: string; credit?: string };
  /** Extrait vidéo libre de droits en boucle (sans son) ; `recherche` : mots-clés (anglais), la fabrication renseigne `fichier`. */
  clip: { fichier?: string; recherche?: string; legende?: string; credit?: string };
  /** Histoire : frise de dates (2 à 6 repères, `accent` met un repère en avant). */
  frise: { titre?: string; reperes: { date: string; label: string; accent?: boolean }[] };
  /** Histoire : schéma de lieux (x, y de 0 à 100), pas à l'échelle ; `trajet` relie les lieux dans l'ordre. */
  carte: { titre?: string; lieux: { nom: string; x: number; y: number }[]; trajet?: boolean };
  /** Histoire : citation d'époque, sourcée dans faits.json. */
  citation: { texte: string; auteur: string; date?: string };
};
export type SceneType = keyof SceneParams;

export type Scene<T extends SceneType = SceneType> = {
  type: T;
  /** Numéro de la phrase (1 = première) où la scène commence. */
  phrase: number;
  params: SceneParams[T];
  /** Thème de cette scène seulement (touche de couleur) ; sinon `theme_accent` pour les gros sous-titres, sinon le thème de l'épisode. */
  theme?: string;
};

/** `episodes-b/<id>/episode.json` : un épisode décrit par des données. */
export type Episode = {
  id: string;
  titre: string;
  theme: string;
  /** Thème de contraste (ex. chocolat-caramel) appliqué aux scènes de gros sous-titres, pour relancer le rythme. */
  theme_accent?: string;
  /** Étiquette du coin haut gauche (nom de la chaîne). */
  chaine: string;
  /** Langue du texte parlé et affiché (« en »…) ; sans valeur : le français. Règle les sous-titres (nombres en chiffres) et le format des nombres. */
  langue?: string;
  phrases: string[];
  scenes: Scene[];
  /** Miniature YouTube (facultatif, voir src/miniature/resolve.ts) : style, texte_haut, gros, icone, contraste. */
  miniature?: { style?: string; texte_haut?: string; gros?: string; icone?: string; contraste?: [{ valeur: string; label: string }, { valeur: string; label: string }] };
};

export type ShortProps = { id: string; episode?: Episode; timings?: Timings };
