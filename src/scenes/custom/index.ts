import type { SceneImpl } from "../library";

/**
 * Stock des scènes sur mesure (niveau 2) : une scène codée une fois, réutilisable ensuite par son nom
 * dans n'importe quel scenes.json (`{ "type": "sur-mesure", "params": { "composant": "<nom>" } }`).
 * Chaque entrée suit le contrat de la bibliothèque : `draw` (pixel art) + `Overlay` (texte).
 */
export const CUSTOM: Record<string, SceneImpl> = {};
