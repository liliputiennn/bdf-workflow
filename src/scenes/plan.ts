import { VARIANTS, type Item, type Scene, type ScenesFile } from "./schema";
import { PACES, PALS, type Pace, type Pal } from "./palettes";

/**
 * Calcul pur (sans React) : où commence chaque scène, quelle variante, quand chaque élément apparaît.
 * Testé à part ; le SceneRunner ne fait qu'afficher ce plan.
 */

export const FPS = 30;
type W = { w: string; start: number; end: number };

export type Planned = {
  scene: Scene;
  index: number;
  from: number;
  to: number;
  /** phrases couvertes (index 0) */
  firstLine: number;
  lastLine: number;
  variant: string;
  /** image d'apparition de chaque élément (items / étapes / lignes), absolue */
  reveals: number[];
  /** image du tampon, absolue (-1 sans tampon) */
  stampAt: number;
};

/** Hachage stable d'un texte (choix des variantes par défaut, différent d'un épisode à l'autre). */
export const seedOf = (s: string) => {
  let h = 2166136261;
  for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
};

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");

/** Image où la voix prononce `mot` dans les phrases [first, last] ; -1 si introuvable. */
export const wordFrame = (words: W[][], first: number, last: number, mot: string) => {
  const target = norm(mot.split(/\s+/)[0]);
  if (!target) return -1;
  for (let i = first; i <= last; i++) {
    const w = words[i]?.find((x) => {
      const n = norm(x.w);
      return n === target || (target.length >= 4 && n.startsWith(target.slice(0, Math.max(4, target.length - 2))));
    });
    if (w) return Math.round(w.start * FPS);
  }
  return -1;
};

/** Éléments à révéler un par un, selon le type de scène. */
export const revealItems = (s: Scene): Pick<Item, "mot">[] => {
  const p = s.params as Record<string, unknown>;
  switch (s.type) {
    case "liste":
      return p.items as Item[];
    case "flux-argent":
    case "frise":
    case "schema-fleches":
      return p.etapes as Item[];
    case "tableau":
      return (p.lignes as unknown[]).map(() => ({}));
    case "comparaison":
    case "avant-apres":
      return [{}, {}];
    case "question-finale":
      return (p.choix as unknown[] | undefined)?.map(() => ({})) ?? [];
    default:
      return [];
  }
};

export const planScenes = (file: ScenesFile, lineStarts: number[], frames: number, words: W[][], id = file.dossier): Planned[] => {
  const seed = seedOf(id);
  const pace = PACES[file.rythme];
  return file.scenes.map((scene, index) => {
    const next = file.scenes[index + 1];
    const firstLine = scene.phrase - 1;
    const lastLine = next ? next.phrase - 2 : lineStarts.length - 1;
    const from = index === 0 ? 0 : lineStarts[firstLine];
    const to = next ? lineStarts[next.phrase - 1] : frames;
    const vs = VARIANTS[scene.type] as readonly string[];
    const variant = scene.variante ?? vs[(seed + index * 7) % vs.length];
    const items = revealItems(scene);
    const start = from + Math.round(10 * pace.stagger);
    const span = Math.max(1, (to - start) * 0.72);
    const reveals = items.map((it, k) => {
      const w = it.mot ? wordFrame(words, firstLine, lastLine, it.mot) : -1;
      return w >= 0 ? w : Math.round(start + (span * k) / Math.max(1, items.length) * pace.stagger);
    });
    // jamais dans le désordre : un élément n'apparaît pas avant le précédent
    for (let k = 1; k < reveals.length; k++) reveals[k] = Math.max(reveals[k], reveals[k - 1] + 4);
    const stampAt = scene.tampon
      ? (() => {
          const w = scene.tampon.mot ? wordFrame(words, firstLine, lastLine, scene.tampon.mot) : -1;
          return w >= 0 ? w : Math.round(from + (to - from) * 0.6);
        })()
      : -1;
    return { scene, index, from, to, firstLine, lastLine, variant, reveals, stampAt };
  });
};

export const styleOf = (file: ScenesFile): { pal: Pal; pace: Pace } => ({ pal: PALS[file.palette], pace: PACES[file.rythme] });

/** Timings provisoires (≈ 14 caractères par seconde) tant que la voix n'est pas calée. */
export const provisionalTimings = (script: { text: string }[]) => {
  let t = 0.2;
  const lines = script.map((l) => {
    const d = Math.max(1.1, l.text.length / 14);
    const line = { start: +t.toFixed(2), end: +(t + d).toFixed(2) };
    t += d + 0.35;
    return line;
  });
  return { total: +(t + 1.2).toFixed(2), lines, provisional: true };
};

/* ───────── Sous-titres « TikTok » : groupes de mots ───────── */

export type Chunk = { line: number; words: W[]; start: number; end: number };

/** Découpe chaque phrase en groupes de 3 mots au plus, en coupant aussi après la ponctuation. */
export const chunkWords = (words: W[][], lines: { end: number }[], max = 3): Chunk[] =>
  words.flatMap((ws, line) => {
    const out: Chunk[] = [];
    let cur: W[] = [];
    ws.forEach((w, k) => {
      cur.push(w);
      if (cur.length >= max || /[,.!?:;…]$/.test(w.w) || k === ws.length - 1) {
        out.push({ line, words: cur, start: cur[0].start, end: 0 });
        cur = [];
      }
    });
    out.forEach((c, k) => (c.end = out[k + 1]?.start ?? lines[line].end + 0.25));
    return out;
  });

