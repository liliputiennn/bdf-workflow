import fs from "node:fs";
import path from "node:path";
import { DECORS, describePath, ICONS, PALETTES, POSES, repetitionIssues, RHYTHMS, SCENE_TYPES, validateScenes, VARIANTS, type ScenesFile } from "../src/scenes/schema";
import { writeDataIndex } from "./dataIndex";
import { JsonLineError, parseWithLines, type Path } from "./jsonLines";
import { safeJoin } from "./paths";
import { weakFacts, type Store } from "./store";
import type { Episode, Fact, Idea } from "./types";

/**
 * Semaine de production : 7 créneaux (un sujet par jour), un brief unique pour Claude,
 * puis l'import de sa réponse qui crée les 7 épisodes d'un coup.
 */

export type Slot = { idea?: string; subject?: string; episode?: string };
export type Week = { start: string; slots: Slot[] };

const ID = /^[a-z0-9][a-z0-9-]{0,80}$/;
const DAYS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];

export const dayDate = (start: string, i: number) => {
  const d = new Date(`${start}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + i);
  return d;
};
export const dayLabel = (start: string, i: number) => {
  const d = dayDate(start, i);
  return `${DAYS[d.getUTCDay()]} ${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
};

/* ───────── Stockage : weeks/<début>.json, la plus récente est la semaine courante ───────── */

export const createWeeks = (root: string) => {
  const dir = () => safeJoin(root, "weeks");
  const file = (start: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) throw new Error("date de début invalide (AAAA-MM-JJ)");
    return safeJoin(root, "weeks", `${start}.json`);
  };
  const latest = (): Week | null => {
    if (!fs.existsSync(dir())) return null;
    const f = fs.readdirSync(dir()).filter((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n)).sort().pop();
    return f ? (JSON.parse(fs.readFileSync(path.join(dir(), f), "utf-8")) as Week) : null;
  };
  const save = (w: Week, previousStart?: string) => {
    fs.mkdirSync(dir(), { recursive: true });
    if (w.slots.length !== 7) throw new Error("une semaine compte 7 créneaux");
    fs.writeFileSync(file(w.start), JSON.stringify(w, null, 2) + "\n", "utf-8");
    if (previousStart && previousStart !== w.start && fs.existsSync(file(previousStart))) fs.rmSync(file(previousStart));
    return w;
  };
  return { latest, save };
};

/* ───────── Le brief (règles une seule fois, format compact) ───────── */

/** Paramètres de chaque type, en une ligne (gardée alignée sur src/scenes/schema.ts ; un test le vérifie). */
const PARAMS_DOC: Record<string, string> = {
  accroche: 'titre ≤40, icone?',
  "chiffre-choc": 'valeur (nombre), prefixe? ≤4, suffixe? ≤10 (ex. " €"), decimales?, etiquette ≤30, icone?',
  liste: "titre? ≤30, items [2-5 ITEM] (podium = classement, 1er en premier)",
  comparaison: 'gauche CÔTÉ, droite CÔTÉ, gagnant? "gauche|droite|egalite"',
  "flux-argent": "depart {texte ≤20, icone?}, etapes [2-5 ITEM + part? en %] (où va l'argent)",
  frise: 'etapes [2-6 ITEM + date ≤10]',
  perso: `pose ${POSES.join("|")}, bulle? ≤60 (Max parle), texte? ≤22 (gros mot qui claque), icone? (objet), decor? (zoom = gros plan pour une réaction)`,
  "schema-fleches": 'personnage {nom ≤12, icone? "max|homme|femme" (Max par défaut)}, etapes [1-4 ITEM], resultat? {texte ≤26, ton? "bon|mauvais"}',
  tableau: 'titre? ≤30, colonnes ["A","B"], lignes [2-6 paires ["≤18","≤18"]], surligner? n° de ligne',
  coulisses: `decor ${DECORS.join("|")}, bulle ≤60, icone? (variante jour|nuit)`,
  "avant-apres": "avant CÔTÉ, apres CÔTÉ",
  "question-finale": 'question ≤60, choix? ["≤16","≤16"]',
  "sur-mesure": "composant (nom d'une scène du stock sur mesure)",
};

export const RULES = `RÈGLES (valables pour les 7 vidéos)
- Ton : un pote malin qui te montre un truc sur TON argent (droits oubliés, pièges du quotidien, petits business, salaire, arnaques, calculs chocs). On explique ce qui existe et ce que font certains ; jamais « fais ceci », jamais de conseil d'investissement.
- Héros : Max, la mascotte à casquette verte. Raconte en « tu », ou fais vivre la situation à Max.
- Durée 45-75 s : 18 à 28 phrases de 3 à 9 mots (~3 mots/s), une info par phrase. Zéro remplissage.
- Des mots qu'un enfant de 10 ans comprend ; un mot technique est expliqué tout de suite avec une image concrète.
- Structure : accroche personnelle choc (« Tu paies… », « Ton patron… ») qui sert de titre de couverture → « Sauf que… » → 2 ou 3 rebondissements avec des chiffres concrets du quotidien (€, jours, %) → « Le plus fou, c'est que… » → question aux commentaires.
- Chiffres : seulement ceux des faits fournis, ou que tu sources par 2 liens fiables (sites officiels, presse). Montants et règles français. Incertain → « environ » / « selon … ».
- Aucune marque dessinée ni logo : les visuels restent génériques (icônes).
- "voix" seulement si la lecture diffère du texte (chiffres en lettres, sigles). 1 à 2 balises d'émotion ElevenLabs AU TOTAL par vidéo (ex. [surprised]), jamais plus.
- Style : TOUJOURS vert (palettes vertes uniquement). Vidéo très dynamique : une scène PAR PHRASE ou presque, dont au moins 6 scènes « perso » avec Max, rythme « nerveux ».
- Originalité : palette différente de la veille, jamais la même suite de 3 types de scène qu'à la veille, des variantes différentes.`;

export const SCENES_DOC = () => `FORMAT "scenes"
{"version":1,"palette":P,"rythme":R,"dossier":"≤14","couverture":{"haut":"≤16","bas":"≤14","heros":ICONE,"etiquette":"≤24"},"scenes":[SCÈNE…]}
P : ${PALETTES.join("|")} · R : ${RHYTHMS.join("|")}
SCÈNE = {"type":T,"phrase":n° de la phrase où elle commence (1 = première, croissant),"variante"?:V,"params":{…},"tampon"?:{"texte":"≤16","mot"?:"mot dit","ton"?:"bon|mauvais"},"alerte"?:true}
15 à 24 scènes ; la 1re à la phrase 1 ; une scène par phrase ou presque ; jamais deux fois le même type de suite (sauf « perso ») ; 1 « sur-mesure » au plus.
ITEM = {"texte":"≤34","mot"?:"mot prononcé qui fait apparaître l'élément","icone"?:ICONE,"valeur"?:"≤14"} · CÔTÉ = {"titre":"≤18","valeur"?:"≤14","icone"?,"points"?:[1-3 × "≤28"]}
Types (variantes) → params :
${SCENE_TYPES.map((t) => `- ${t} (${VARIANTS[t].join("|")}) → ${PARAMS_DOC[t]}`).join("\n")}
ICONE : ${ICONS.join(" ")}`;

const OUTPUT_DOC = `RÉPONSE : UN SEUL bloc \`\`\`json, rien d'autre :
{"videos":[{"jour":1,"slug":"minuscules-avec-tirets","titre":"l'accroche en une phrase",
"faits":[{"claim":"…","sources":["https://…","https://…"]}],
"script":[{"texte":"phrase affichée","motCle":"mot ou groupe présent dans texte","voix"?:"…"}],
"publication":{"accroche":"1re ligne","description":"une phrase","question":"question pour les commentaires","hashtags":["#…" ×4-5]},
"scenes":{…}}, …]} — une entrée par jour, dans l'ordre. "faits" : obligatoire pour un SUJET LIBRE, sinon facultatif.`;

const factLine = (f: Fact) => `  · ${f.claim} [${[...new Set(f.sources)].join(" ; ")}]`;

export const buildBrief = (week: Week, ideas: Idea[]): string => {
  const subjects = week.slots.map((s, i) => {
    const head = `Jour ${i + 1} (${dayLabel(week.start, i)})`;
    const idea = s.idea ? ideas.find((x) => x.slug === s.idea) : undefined;
    if (idea) return `${head} — slug « ${idea.slug} » — accroche de départ : ${idea.hook}\n${idea.facts.map(factLine).join("\n")}`;
    if (s.subject) return `${head} — SUJET LIBRE : « ${s.subject} » (choisis le slug, donne les faits avec 2 sources chacun)`;
    return `${head} — SUJET LIBRE : choisis toi-même un business surprenant (slug + faits sourcés)`;
  });
  return [
    "Tu écris 7 vidéos courtes pour la chaîne « Le Bureau des Faits » (pixel art, voix off, sous-titres mot à mot). Écris tout d'un coup.",
    "",
    RULES,
    "",
    SCENES_DOC(),
    "",
    OUTPUT_DOC,
    "",
    "LES 7 SUJETS",
    ...subjects,
  ].join("\n");
};

/* ───────── L'import ───────── */

type ScriptRow = { texte: string; motCle: string; voix?: string };
type Video = {
  jour: number;
  slug: string;
  titre: string;
  faits?: Fact[];
  script: ScriptRow[];
  publication: { accroche: string; description: string; question: string; hashtags: string[] };
  scenes: ScenesFile;
};
export type ImportResult = { ok: boolean; errors: string[]; warnings: string[]; created: string[] };

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const EMOTION = /\[[a-zA-Z][a-zA-Z ]{1,30}\]/g;

/** Noms des scènes sur mesure du stock (lus dans src/scenes/custom/index.ts, sans charger React). */
export const customNames = (root: string) => {
  const f = safeJoin(root, "src", "scenes", "custom", "index.ts");
  if (!fs.existsSync(f)) return [];
  const body = /CUSTOM[^=]*=\s*\{([\s\S]*?)\n\};/.exec(fs.readFileSync(f, "utf-8"))?.[1] ?? "";
  return [...body.matchAll(/^\s{2}"?([\w-]+)"?\s*[:,]/gm)].map((m) => m[1]);
};

/** Vérifie la réponse de Claude ; ne modifie rien. */
export const checkWeek = (text: string, week: Week, opts: { customs?: string[]; existing?: (slug: string) => Episode | null } = {}) => {
  const errors: string[] = [];
  const warnings: string[] = [];
  let parsed;
  try {
    parsed = parseWithLines(text);
  } catch (e) {
    if (e instanceof JsonLineError) return { errors: [`ligne ${e.line} : le JSON est mal formé : ${e.message.replace(/^ligne \d+ : /, "")}`], warnings, videos: [] as Video[] };
    throw e;
  }
  const { value, lineOf } = parsed;
  const err = (p: Path, msg: string) => {
    const v = typeof p[1] === "number" ? p[1] : -1;
    const where = v >= 0 ? `vidéo ${v + 1}${p.length > 2 ? ` › ${describePath(p.slice(2))}` : ""}` : describePath(p) || "réponse";
    errors.push(`ligne ${lineOf(p) ?? "?"} · ${where} : ${msg}`);
  };
  if (!isObj(value) || !Array.isArray(value.videos)) {
    err([], "il faut un objet { \"videos\": [ … ] }");
    return { errors, warnings, videos: [] as Video[] };
  }
  const videos = value.videos as unknown[];
  if (videos.length !== week.slots.length) err(["videos"], `${videos.length} vidéos reçues, ${week.slots.length} attendues`);
  const seen = new Set<string>();
  videos.forEach((raw, i) => {
    const P = (...p: Path) => ["videos", i, ...p];
    if (!isObj(raw)) return err(P(), "chaque vidéo est un objet { … }");
    const slot = week.slots[i] ?? {};
    if (raw.jour !== i + 1) err(P("jour"), `« jour » vaut ${String(raw.jour)}, attendu ${i + 1} (les vidéos sont dans l'ordre des jours)`);
    const slug = raw.slug;
    if (typeof slug !== "string" || !ID.test(slug)) err(P("slug"), "« slug » : minuscules, chiffres et tirets seulement (ex. ikea-hot-dog)");
    else {
      if (slot.idea && slug !== slot.idea) err(P("slug"), `« slug » doit rester « ${slot.idea} » (sujet choisi dans la banque d'idées)`);
      if (seen.has(slug)) err(P("slug"), `slug « ${slug} » utilisé deux fois`);
      seen.add(slug);
      const ex = opts.existing?.(slug);
      if (ex && (ex.voice.chosen || ex.steps.render === "done")) err(P("slug"), `l'épisode « ${slug} » a déjà sa voix : il ne sera pas réécrit`);
    }
    if (typeof raw.titre !== "string" || !raw.titre.trim()) err(P("titre"), "« titre » manque");
    // faits
    if (raw.faits !== undefined || !slot.idea) {
      if (!Array.isArray(raw.faits) || raw.faits.length === 0) err(P("faits"), "« faits » manque : un sujet libre doit apporter ses faits, 2 sources chacun");
      else
        raw.faits.forEach((f, k) => {
          if (!isObj(f) || typeof f.claim !== "string" || !Array.isArray(f.sources)) return err(P("faits", k), 'chaque fait : {"claim": "…", "sources": ["https://…", "https://…"]}');
          const src = new Set(f.sources.filter((s): s is string => typeof s === "string" && /^https?:\/\//.test(s)));
          if (src.size < 2) err(P("faits", k), "il faut 2 sources différentes (liens https) par fait");
        });
    }
    // script
    const script = raw.script;
    if (!Array.isArray(script)) err(P("script"), "« script » : liste de phrases attendue");
    else {
      if (script.length < 12 || script.length > 40) err(P("script"), `${script.length} phrases ; il en faut de 12 à 40`);
      let emotions = 0;
      let words = 0;
      script.forEach((r, k) => {
        if (!isObj(r) || typeof r.texte !== "string" || !r.texte.trim()) return err(P("script", k), 'chaque phrase : {"texte": "…", "motCle": "…"}');
        words += r.texte.split(/\s+/).filter(Boolean).length;
        if (r.texte.length > 110) err(P("script", k, "texte"), `phrase trop longue (${r.texte.length} caractères) : coupe-la en deux`);
        if (EMOTION.test(r.texte)) err(P("script", k, "texte"), "les balises d'émotion vont dans « voix », pas dans le texte affiché");
        EMOTION.lastIndex = 0;
        if (typeof r.motCle !== "string" || !r.motCle.trim()) err(P("script", k, "motCle"), "« motCle » manque");
        else if (!r.texte.toLowerCase().includes(r.motCle.toLowerCase())) err(P("script", k, "motCle"), `« ${r.motCle} » n'apparaît pas dans la phrase`);
        if (r.voix !== undefined) {
          if (typeof r.voix !== "string") err(P("script", k, "voix"), "« voix » est un texte");
          else emotions += (r.voix.match(EMOTION) ?? []).length;
        }
      });
      if (emotions > 2) err(P("script"), `${emotions} balises d'émotion : 2 au maximum par vidéo`);
      const secs = Math.round(words / 3);
      if (secs < 40 || secs > 100) warnings.push(`vidéo ${i + 1} : environ ${secs} s de voix (visé : 45-75 s)`);
      if (isObj(raw.scenes)) {
        validateScenes(raw.scenes, script.length, opts.customs ?? []).forEach((is) => err(P("scenes", ...is.path), is.message));
        const n = Array.isArray(raw.scenes.scenes) ? raw.scenes.scenes.length : 0;
        if (n && script.length / n > 1.6) warnings.push(`vidéo ${i + 1} : ${n} scènes pour ${script.length} phrases, pas assez dynamique (visé : une scène par phrase ou presque)`);
        const persos = Array.isArray(raw.scenes.scenes) ? raw.scenes.scenes.filter((x) => isObj(x) && x.type === "perso").length : 0;
        if (n && persos < 4) warnings.push(`vidéo ${i + 1} : seulement ${persos} scène(s) avec Max (visé : au moins 6)`);
      }
      else err(P("scenes"), "« scenes » manque (objet du format scenes.json)");
    }
    // publication
    const pub = raw.publication;
    if (!isObj(pub)) err(P("publication"), "« publication » manque");
    else {
      for (const k of ["accroche", "description", "question"]) if (typeof pub[k] !== "string" || !(pub[k] as string).trim()) err(P("publication", k), `« ${k} » manque`);
      const tags = pub.hashtags;
      if (!Array.isArray(tags) || tags.length < 4 || tags.length > 5) err(P("publication", "hashtags"), "4 à 5 hashtags");
      else tags.forEach((t, k) => (typeof t !== "string" || !/^#[\p{L}\p{N}_]+$/u.test(t)) && err(P("publication", "hashtags", k), `hashtag « ${String(t)} » invalide (ex. #business)`));
    }
  });
  const ok = errors.length === 0;
  const list = ok ? (videos as Video[]) : [];
  list.slice(1).forEach((v, k) => repetitionIssues(list[k].scenes, v.scenes).forEach((m) => warnings.push(`vidéo ${k + 2} : ${m}`)));
  return { errors, warnings, videos: list };
};

const postMd = (number: number, v: Video) =>
  `# Post — Épisode ${String(number).padStart(2, "0")}\n\n**Description**\n${v.publication.accroche}\n${v.publication.description}\n${v.publication.question}\n\n**Hashtags** ${v.publication.hashtags.join(" ")}\n`;

const writeJson = (file: string, data: unknown) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n", "utf-8");
};

/** Vérifie puis crée (ou réécrit, tant que la voix n'est pas posée) les épisodes de la semaine. */
export const importWeek = (root: string, store: Store, week: Week, text: string): ImportResult & { week: Week } => {
  const existing = (slug: string) => (fs.existsSync(safeJoin(root, "episodes", slug, "episode.json")) ? store.getEpisode(slug) : null);
  const { errors, warnings, videos } = checkWeek(text, week, { customs: customNames(root), existing });
  if (errors.length) return { ok: false, errors, warnings, created: [], week };
  const created: string[] = [];
  const slots = week.slots.map((s) => ({ ...s }));
  videos.forEach((v, i) => {
    // 1. l'idée (sujet libre : créée à partir des faits apportés)
    const ideaFile = safeJoin(root, "ideas", `${v.slug}.json`);
    if (!fs.existsSync(ideaFile))
      store.saveIdea({ slug: v.slug, hook: v.titre, theme: "Business", year: new Date().getFullYear(), score: 0, scoreNote: "sujet de la semaine (brief)", facts: v.faits ?? [], disputed: [], status: "idea" });
    else if (v.faits?.length) store.saveIdea({ ...store.getIdea(v.slug), facts: v.faits });
    // 2. l'épisode
    const ep = existing(v.slug) ?? store.createEpisodeFromIdea(v.slug);
    const dir = safeJoin(root, "episodes", ep.id);
    writeJson(path.join(dir, "script.json"), v.script.map((r) => ({ text: r.texte, hi: r.motCle, ...(r.voix ? { eleven: r.voix } : {}) })));
    fs.writeFileSync(safeJoin(root, ep.voiceTextFile), v.script.map((r) => r.voix ?? r.texte).join("\n") + "\n", "utf-8");
    fs.writeFileSync(path.join(dir, "POST.md"), postMd(ep.number, v), "utf-8");
    writeJson(path.join(dir, "scenes.json"), v.scenes);
    const timings = safeJoin(root, ep.timingsFile);
    if (fs.existsSync(timings) && JSON.parse(fs.readFileSync(timings, "utf-8")).provisional) fs.rmSync(timings);
    const idea = store.getIdea(v.slug);
    store.saveEpisode({
      ...ep,
      title: v.titre,
      steps: { ...ep.steps, facts: weakFacts(idea).length === 0 ? "done" : "todo", script: "done", voiceText: "done", scenes: "done" },
      error: null,
    });
    slots[i] = { ...slots[i], idea: v.slug, episode: ep.id };
    created.push(ep.id);
  });
  writeDataIndex(root);
  return { ok: true, errors, warnings, created, week: { ...week, slots } };
};
