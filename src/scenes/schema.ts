/**
 * Format `episodes/<id>/scenes.json` : un épisode décrit par des données, sans code.
 * Ce fichier ne dépend ni de React ni de Remotion (il sert aussi au serveur et aux tests).
 */

export const ICONS = [
  "banque", "billets", "piece", "tirelire", "maison", "immeuble", "usine", "boutique", "camion", "carton",
  "telephone", "cafe", "burger", "hotdog", "caddie", "graphique", "baisse", "feu", "cadenas", "cible",
  "etoile", "homme", "femme", "etat", "ampoule", "horloge", "avion", "voiture", "cadeau", "carte",
] as const;
export type Icon = (typeof ICONS)[number];

/** Toujours une palette verte (identité de la chaîne) : la variété vient des nuances, pas d'autres couleurs. */
export const PALETTES = ["phosphore", "emeraude", "menthe", "lime"] as const;
export type Palette = (typeof PALETTES)[number];
export const RHYTHMS = ["pose", "nerveux"] as const;
export type Rhythm = (typeof RHYTHMS)[number];

/** Types de scène et leurs variantes (la première est celle par défaut). */
export const VARIANTS = {
  perso: ["centre", "duo", "zoom"],
  accroche: ["cadre", "tampon", "zoom"],
  "chiffre-choc": ["compteur", "barre", "pile"],
  liste: ["encadres", "podium", "cartes"],
  comparaison: ["duel", "balance", "barres"],
  "flux-argent": ["tuyaux", "camembert", "ticket"],
  frise: ["route", "calendrier", "ascenseur"],
  "schema-fleches": ["ligne", "cercle"],
  tableau: ["lignes", "ecran"],
  coulisses: ["jour", "nuit"],
  "avant-apres": ["coupe", "volet"],
  "question-finale": ["simple", "vote"],
  "sur-mesure": ["unique"],
} as const;
export type SceneType = keyof typeof VARIANTS;
export const SCENE_TYPES = Object.keys(VARIANTS) as SceneType[];

export const DECORS = ["usine", "boutique", "entrepot", "bureau", "banque", "rue"] as const;
export type Decor = (typeof DECORS)[number];

/** Un élément révélé au moment où la voix dit `mot` (sinon réparti dans la scène). */
export type Item = { texte: string; mot?: string; icone?: Icon; valeur?: string };
export type Side = { titre: string; valeur?: string; icone?: Icon; points?: string[] };
export type Tone = "bon" | "mauvais";

/** Poses de Max, la mascotte (dessin dans mascot.ts). */
export const POSES = ["parle", "choc", "content", "telephone", "reflechit", "argent", "montre"] as const;
export type Pose = (typeof POSES)[number];

export type SceneParams = {
  perso: { pose: Pose; bulle?: string; texte?: string; icone?: Icon; decor?: Decor };
  accroche: { titre: string; icone?: Icon };
  "chiffre-choc": { valeur: number; prefixe?: string; suffixe?: string; decimales?: number; etiquette: string; icone?: Icon };
  liste: { titre?: string; items: Item[] };
  comparaison: { gauche: Side; droite: Side; gagnant?: "gauche" | "droite" | "egalite" };
  "flux-argent": { depart: { texte: string; icone?: Icon }; etapes: (Item & { part?: number })[] };
  frise: { etapes: (Item & { date: string })[] };
  "schema-fleches": { personnage: { nom: string; icone?: Icon | "max" }; etapes: Item[]; resultat?: { texte: string; ton?: Tone } };
  tableau: { titre?: string; colonnes: [string, string]; lignes: [string, string][]; surligner?: number };
  coulisses: { decor: Decor; bulle: string; icone?: Icon };
  "avant-apres": { avant: Side; apres: Side };
  "question-finale": { question: string; choix?: [string, string] };
  "sur-mesure": { composant: string; params?: Record<string, unknown> };
};

export type Scene<T extends SceneType = SceneType> = {
  type: T;
  /** Numéro de la phrase du script (1 = première) où la scène commence. */
  phrase: number;
  variante?: string;
  params: SceneParams[T];
  /** Tampon facultatif, posé quand la voix dit `mot`. */
  tampon?: { texte: string; mot?: string; ton?: Tone };
  /** Phrase d'alerte : mot-clé des sous-titres en rouge. */
  alerte?: boolean;
};

export type ScenesFile = {
  version: 1;
  palette: Palette;
  rythme: Rhythm;
  /** Étiquette du coin haut droit (ex. « IKEA »). */
  dossier: string;
  couverture: { haut: string; bas: string; heros: Icon; etiquette: string };
  scenes: Scene[];
};

export type Issue = { path: (string | number)[]; message: string };

/* ───────── Validation, messages en français ───────── */

type Ctx = { issues: Issue[]; path: (string | number)[] };
const push = (c: Ctx, message: string, sub: (string | number)[] = []) => c.issues.push({ path: [...c.path, ...sub], message });
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const at = (c: Ctx, ...sub: (string | number)[]): Ctx => ({ issues: c.issues, path: [...c.path, ...sub] });

const str = (c: Ctx, o: Record<string, unknown>, k: string, opt: { max?: number; optional?: boolean } = {}) => {
  const v = o[k];
  if (v === undefined) {
    if (!opt.optional) push(c, `« ${k} » manque (texte attendu)`, [k]);
    return;
  }
  if (typeof v !== "string" || !v.trim()) return push(c, `« ${k} » doit être un texte non vide`, [k]);
  if (opt.max && v.length > opt.max) push(c, `« ${k} » est trop long (${v.length} caractères, ${opt.max} au plus)`, [k]);
};
const num = (c: Ctx, o: Record<string, unknown>, k: string, optional = false) => {
  const v = o[k];
  if (v === undefined) return optional ? undefined : push(c, `« ${k} » manque (nombre attendu)`, [k]);
  if (typeof v !== "number" || !Number.isFinite(v)) push(c, `« ${k} » doit être un nombre (sans guillemets ni espaces)`, [k]);
};
const oneOf = (c: Ctx, o: Record<string, unknown>, k: string, list: readonly string[], optional = true) => {
  const v = o[k];
  if (v === undefined) return optional ? undefined : push(c, `« ${k} » manque`, [k]);
  if (typeof v !== "string" || !list.includes(v)) push(c, `« ${k} » vaut « ${String(v)} » ; valeurs possibles : ${list.join(", ")}`, [k]);
};
const icon = (c: Ctx, o: Record<string, unknown>, k = "icone", optional = true) => oneOf(c, o, k, ICONS, optional);
const obj = (c: Ctx, o: Record<string, unknown>, k: string, optional = false): Record<string, unknown> | undefined => {
  const v = o[k];
  if (v === undefined) {
    if (!optional) push(c, `« ${k} » manque (objet { … } attendu)`, [k]);
    return;
  }
  if (!isObj(v)) return void push(c, `« ${k} » doit être un objet { … }`, [k]);
  return v;
};
const arr = (c: Ctx, o: Record<string, unknown>, k: string, min: number, max: number, optional = false): unknown[] | undefined => {
  const v = o[k];
  if (v === undefined) {
    if (!optional) push(c, `« ${k} » manque (liste [ … ] de ${min} à ${max} éléments attendue)`, [k]);
    return;
  }
  if (!Array.isArray(v)) return void push(c, `« ${k} » doit être une liste [ … ]`, [k]);
  if (v.length < min || v.length > max) push(c, `« ${k} » contient ${v.length} éléments ; il en faut de ${min} à ${max}`, [k]);
  return v;
};
const items = (c: Ctx, o: Record<string, unknown>, k: string, min: number, max: number, extra?: (c: Ctx, it: Record<string, unknown>) => void) =>
  arr(c, o, k, min, max)?.forEach((it, i) => {
    const ci = at(c, k, i);
    if (!isObj(it)) return push(ci, "chaque élément doit être un objet { « texte » : … }");
    str(ci, it, "texte", { max: 34 });
    str(ci, it, "mot", { optional: true });
    str(ci, it, "valeur", { optional: true, max: 14 });
    icon(ci, it);
    extra?.(ci, it);
  });
const side = (c: Ctx, o: Record<string, unknown>, k: string) => {
  const s = obj(c, o, k);
  if (!s) return;
  const cs = at(c, k);
  str(cs, s, "titre", { max: 18 });
  str(cs, s, "valeur", { optional: true, max: 14 });
  icon(cs, s);
  arr(cs, s, "points", 1, 3, true)?.forEach((p, i) => {
    if (typeof p !== "string" || !p.trim()) push(cs, "chaque point doit être un texte", ["points", i]);
    else if (p.length > 28) push(cs, `point trop long (${p.length} caractères, 28 au plus)`, ["points", i]);
  });
};

const PARAMS: { [T in SceneType]: (c: Ctx, p: Record<string, unknown>) => void } = {
  perso: (c, p) => {
    oneOf(c, p, "pose", POSES, false);
    str(c, p, "bulle", { optional: true, max: 60 });
    str(c, p, "texte", { optional: true, max: 22 });
    icon(c, p);
    oneOf(c, p, "decor", DECORS);
  },
  accroche: (c, p) => {
    str(c, p, "titre", { max: 40 });
    icon(c, p);
  },
  "chiffre-choc": (c, p) => {
    num(c, p, "valeur");
    num(c, p, "decimales", true);
    str(c, p, "prefixe", { optional: true, max: 4 });
    str(c, p, "suffixe", { optional: true, max: 10 });
    str(c, p, "etiquette", { max: 30 });
    icon(c, p);
  },
  liste: (c, p) => {
    str(c, p, "titre", { optional: true, max: 30 });
    items(c, p, "items", 2, 5);
  },
  comparaison: (c, p) => {
    side(c, p, "gauche");
    side(c, p, "droite");
    oneOf(c, p, "gagnant", ["gauche", "droite", "egalite"]);
  },
  "flux-argent": (c, p) => {
    const d = obj(c, p, "depart");
    if (d) {
      str(at(c, "depart"), d, "texte", { max: 20 });
      icon(at(c, "depart"), d);
    }
    items(c, p, "etapes", 2, 5, (ci, it) => {
      if (it.part !== undefined && (typeof it.part !== "number" || it.part < 0 || it.part > 100))
        push(ci, "« part » est un pourcentage entre 0 et 100", ["part"]);
    });
  },
  frise: (c, p) => items(c, p, "etapes", 2, 6, (ci, it) => str(ci, it, "date", { max: 10 })),
  "schema-fleches": (c, p) => {
    const pe = obj(c, p, "personnage");
    if (pe) {
      str(at(c, "personnage"), pe, "nom", { max: 12 });
      oneOf(at(c, "personnage"), pe, "icone", ["max", "homme", "femme"]);
    }
    items(c, p, "etapes", 1, 4);
    const r = obj(c, p, "resultat", true);
    if (r) {
      str(at(c, "resultat"), r, "texte", { max: 26 });
      oneOf(at(c, "resultat"), r, "ton", ["bon", "mauvais"]);
    }
  },
  tableau: (c, p) => {
    str(c, p, "titre", { optional: true, max: 30 });
    const cols = arr(c, p, "colonnes", 2, 2);
    cols?.forEach((v, i) => typeof v !== "string" && push(c, "chaque colonne est un texte", ["colonnes", i]));
    const rows = arr(c, p, "lignes", 2, 6);
    rows?.forEach((r, i) => {
      if (!Array.isArray(r) || r.length !== 2 || r.some((x) => typeof x !== "string"))
        return push(c, 'chaque ligne est une paire de textes, ex. ["20 ans", "500 €"]', ["lignes", i]);
      if (r.some((x: string) => x.length > 18)) push(c, "texte de cellule trop long (18 caractères au plus)", ["lignes", i]);
    });
    if (p.surligner !== undefined && (typeof p.surligner !== "number" || !rows || p.surligner < 1 || p.surligner > rows.length))
      push(c, `« surligner » est le numéro d'une ligne (1 à ${rows?.length ?? "?"})`, ["surligner"]);
  },
  coulisses: (c, p) => {
    oneOf(c, p, "decor", DECORS, false);
    str(c, p, "bulle", { max: 60 });
    icon(c, p);
  },
  "avant-apres": (c, p) => {
    side(c, p, "avant");
    side(c, p, "apres");
  },
  "question-finale": (c, p) => {
    str(c, p, "question", { max: 60 });
    const ch = arr(c, p, "choix", 2, 2, true);
    ch?.forEach((v, i) => (typeof v !== "string" || v.length > 16) && push(c, "chaque choix est un texte court (16 caractères au plus)", ["choix", i]));
  },
  "sur-mesure": (c, p) => str(c, p, "composant"),
};

/**
 * Vérifie un scenes.json. `lineCount` = nombre de phrases du script, `customs` = composants sur mesure disponibles.
 * Renvoie la liste des problèmes (vide si tout va bien).
 */
export const validateScenes = (data: unknown, lineCount: number, customs: string[] = []): Issue[] => {
  const c: Ctx = { issues: [], path: [] };
  if (!isObj(data)) return [{ path: [], message: "le fichier doit être un objet JSON { … }" }];
  if (data.version !== 1) push(c, "« version » doit valoir 1", ["version"]);
  oneOf(c, data, "palette", PALETTES, false);
  oneOf(c, data, "rythme", RHYTHMS, false);
  str(c, data, "dossier", { max: 14 });
  const cov = obj(c, data, "couverture");
  if (cov) {
    const cc = at(c, "couverture");
    str(cc, cov, "haut", { max: 16 });
    str(cc, cov, "bas", { max: 14 });
    str(cc, cov, "etiquette", { max: 24 });
    icon(cc, cov, "heros", false);
  }
  const scenes = arr(c, data, "scenes", 3, 24);
  if (!scenes) return c.issues;
  let prevPhrase = 0;
  let prevType = "";
  scenes.forEach((s, i) => {
    const cs = at(c, "scenes", i);
    if (!isObj(s)) return push(cs, "chaque scène doit être un objet { « type », « phrase », « params » }");
    const type = s.type as SceneType;
    if (!SCENE_TYPES.includes(type)) return push(cs, `type « ${String(s.type)} » inconnu ; types possibles : ${SCENE_TYPES.join(", ")}`, ["type"]);
    if (typeof s.phrase !== "number" || !Number.isInteger(s.phrase) || s.phrase < 1 || s.phrase > lineCount)
      push(cs, `« phrase » doit être un numéro de phrase du script, de 1 à ${lineCount}`, ["phrase"]);
    else if (s.phrase <= prevPhrase) push(cs, `les scènes doivent avancer dans le script (phrase ${s.phrase} après la phrase ${prevPhrase})`, ["phrase"]);
    else prevPhrase = s.phrase;
    if (i === 0 && s.phrase !== 1) push(cs, "la première scène doit commencer à la phrase 1", ["phrase"]);
    if (type === prevType && type !== "sur-mesure" && type !== "perso") push(cs, `deux scènes « ${type} » de suite : alterne les types pour garder du rythme`, ["type"]);
    prevType = type;
    if (s.variante !== undefined && !(VARIANTS[type] as readonly string[]).includes(s.variante as string))
      push(cs, `variante « ${String(s.variante)} » inconnue pour « ${type} » ; possibles : ${VARIANTS[type].join(", ")}`, ["variante"]);
    const p = s.params;
    if (!isObj(p)) return push(cs, "« params » manque ou n'est pas un objet { … }", ["params"]);
    PARAMS[type](at(cs, "params"), p);
    if (type === "sur-mesure" && typeof p.composant === "string" && !customs.includes(p.composant))
      push(cs, `composant sur mesure « ${p.composant} » introuvable (src/scenes/custom/index.ts)`, ["params", "composant"]);
    const t = s.tampon;
    if (t !== undefined) {
      if (!isObj(t)) push(cs, "« tampon » doit être un objet { « texte » : … }", ["tampon"]);
      else {
        str(at(cs, "tampon"), t, "texte", { max: 16 });
        str(at(cs, "tampon"), t, "mot", { optional: true });
        oneOf(at(cs, "tampon"), t, "ton", ["bon", "mauvais"]);
      }
    }
  });
  const customCount = scenes.filter((s) => isObj(s) && s.type === "sur-mesure").length;
  if (customCount > 1) push(c, `${customCount} scènes sur mesure : une seule par épisode (sinon, c'est un épisode signature codé)`, ["scenes"]);
  return c.issues;
};

/** Chemin lisible : scenes[2].params.items[0].texte → « scène 3 › params › items 1 › texte ». */
export const describePath = (path: (string | number)[]) =>
  path
    .map((p, i) => (typeof p === "number" ? (path[i - 1] === "scenes" ? `scène ${p + 1}` : `n°${p + 1}`) : p === "scenes" ? "" : p))
    .filter(Boolean)
    .join(" › ");

/* ───────── Originalité : éviter la même suite deux jours de suite ───────── */

const core = (f: Pick<ScenesFile, "scenes">) => f.scenes.map((s) => s.type).filter((t) => t !== "accroche" && t !== "question-finale");

/**
 * Compare l'épisode du jour à celui de la veille. Renvoie des avertissements en français
 * (vide si les deux vidéos sont assez différentes).
 */
export const repetitionIssues = (prev: Pick<ScenesFile, "scenes" | "palette" | "rythme">, cur: Pick<ScenesFile, "scenes" | "palette" | "rythme">): string[] => {
  const out: string[] = [];
  const a = core(prev);
  const b = core(cur);
  if (a.join() === b.join()) out.push("même suite de scènes que la veille");
  else {
    const runs = new Set(a.slice(0, -2).map((_, i) => a.slice(i, i + 3).join(" → ")));
    const shared = b.slice(0, -2).map((_, i) => b.slice(i, i + 3).join(" → ")).find((r) => runs.has(r));
    if (shared) out.push(`même enchaînement que la veille : ${shared}`);
  }
  if (prev.palette === cur.palette && prev.rythme === cur.rythme) out.push(`même palette (${cur.palette}) et même rythme (${cur.rythme}) que la veille`);
  return out;
};
