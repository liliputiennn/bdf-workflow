import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { parseWithLines } from "../server/jsonLines";
import { createStore } from "../server/store";
import { buildBrief, checkWeek, customNames, importWeek, RULES, type Week } from "../server/week";
import script from "../src/scenes/demo/script.json";
import demo from "../src/scenes/demo/scenes.json";
import { SCENE_TYPES } from "../src/scenes/schema";

const PALS = ["phosphore", "emeraude", "menthe", "lime"];
const RYT = ["nerveux", "pose"];
const video = (i: number, slug: string, over: Record<string, unknown> = {}) => ({
  jour: i + 1,
  slug,
  titre: `Titre ${i + 1}`,
  faits: [{ claim: "Un fait", sources: ["https://a.fr/1", "https://b.fr/2"] }],
  script: script.map((l) => ({ texte: l.text, motCle: l.hi })),
  publication: { accroche: "Accroche", description: "Une phrase.", question: "Et toi ?", hashtags: ["#business", "#argent", "#entreprise", "#faits"] },
  // ordre des scènes décalé chaque jour pour ne pas répéter la veille
  scenes: { ...demo, palette: PALS[i % 4], rythme: RYT[i % 2], scenes: i % 2 ? [demo.scenes[0], ...demo.scenes.slice(1).reverse().map((s, k, a) => ({ ...s, phrase: demo.scenes[k + 1].phrase })) ].map((s) => s) : demo.scenes },
  ...over,
});
const week: Week = { start: "2026-10-26", slots: Array.from({ length: 7 }, () => ({})) };
const answer = (videos: unknown[]) => "Voici la semaine :\n```json\n" + JSON.stringify({ videos }, null, 2) + "\n```\n";
const seven = () => Array.from({ length: 7 }, (_, i) => video(i, `business-${i + 1}`));

let root: string;
beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-week-"));
  for (const d of ["ideas", "episodes", "src/episodes", "src/scenes/custom"]) fs.mkdirSync(path.join(root, d), { recursive: true });
});

describe("parseWithLines", () => {
  it("donne la ligne d'une valeur et des erreurs claires", () => {
    const p = parseWithLines('texte avant\n{\n  "a": [\n    1,\n    {"b": 2}\n  ]\n}');
    expect(p.lineOf(["a", 1, "b"])).toBe(5);
    expect(() => parseWithLines('{\n "a": 1,\n}')).toThrow("ligne 3 : virgule en trop avant « } »");
    expect(() => parseWithLines('{\n "a": «x»\n}')).toThrow("guillemets typographiques");
  });
});

describe("brief", () => {
  it("contient les règles une seule fois, tous les types et les 7 sujets", () => {
    const w: Week = { ...week, slots: [{ idea: "gimli" }, { subject: "Pourquoi IKEA vend des hot-dogs" }, {}, {}, {}, {}, {}] };
    const brief = buildBrief(w, [{ slug: "gimli", hook: "Panne sèche", theme: "x", year: 1, score: 1, scoreNote: "", facts: [{ claim: "69 occupants", sources: ["https://a", "https://b"] }], disputed: [], status: "idea" }]);
    expect(brief.split(RULES).length).toBe(2);
    for (const t of SCENE_TYPES) expect(brief).toContain(`- ${t} (`);
    expect(brief).toContain("Jour 1 (lun. 26/10) — slug « gimli »");
    expect(brief).toContain("69 occupants [https://a ; https://b]");
    expect(brief).toContain("SUJET LIBRE : « Pourquoi IKEA vend des hot-dogs »");
    expect(brief).toContain("Jour 7 (dim. 01/11)");
    expect(brief.length).toBeLessThan(6000);
  });
});

describe("checkWeek", () => {
  it("accepte 7 vidéos valides", () => {
    const r = checkWeek(answer(seven()), week);
    expect(r.errors).toEqual([]);
    expect(r.videos).toHaveLength(7);
  });

  it("explique chaque erreur avec sa ligne, en français", () => {
    const v = seven();
    v[2] = video(2, "business-3", { faits: undefined });
    (v[4].script as { texte: string; motCle: string; voix?: string }[])[1].motCle = "absent";
    (v[5].script as { voix?: string }[]).forEach((r, k) => k < 3 && (r.voix = "[excited] oui"));
    const text = answer(v);
    const r = checkWeek(text, week);
    const line = (needle: string) => text.split("\n").findIndex((l) => l.includes(needle)) + 1;
    expect(r.errors).toContain("ligne " + (line('"slug": "business-3"') - 2) + " · vidéo 3 › faits : « faits » manque : un sujet libre doit apporter ses faits, 2 sources chacun");
    expect(r.errors).toContain(`ligne ${line('"motCle": "absent"')} · vidéo 5 › script › n°2 › motCle : « absent » n'apparaît pas dans la phrase`);
    expect(r.errors.some((e) => e.includes("vidéo 6 › script : 3 balises d'émotion : 2 au maximum par vidéo"))).toBe(true);
  });

  it("signale un JSON cassé avec sa ligne", () => {
    const r = checkWeek('```json\n{"videos": [\n  {"jour": 1,}\n]}\n```', week);
    expect(r.errors[0]).toMatch(/^ligne 3 : le JSON est mal formé : virgule en trop/);
  });

  it("avertit quand deux jours se suivent avec la même suite de scènes", () => {
    const v = seven();
    v[1] = { ...video(1, "business-2"), scenes: { ...v[0].scenes, palette: "emeraude" } };
    expect(checkWeek(answer(v), week).warnings).toContain("vidéo 2 : même suite de scènes que la veille");
  });
});

describe("importWeek", () => {
  it("crée les 7 épisodes, leurs textes, leurs scènes et l'index", () => {
    const store = createStore(root);
    const r = importWeek(root, store, week, answer(seven()));
    expect(r.errors).toEqual([]);
    expect(r.created).toEqual(["business-1", "business-2", "business-3", "business-4", "business-5", "business-6", "business-7"]);
    const ep = store.getEpisode("business-3");
    expect(ep.number).toBe(3);
    expect(ep.steps).toMatchObject({ facts: "done", script: "done", voiceText: "done", scenes: "done", voice: "todo" });
    const dir = path.join(root, "episodes", "business-3");
    expect(JSON.parse(fs.readFileSync(path.join(dir, "script.json"), "utf-8"))[0]).toEqual({ text: script[0].text, hi: script[0].hi });
    expect(fs.readFileSync(path.join(dir, "POST.md"), "utf-8")).toContain("**Hashtags** #business #argent #entreprise #faits");
    expect(fs.existsSync(path.join(dir, "scenes.json"))).toBe(true);
    expect(fs.readFileSync(path.join(root, "src/episodes/data-index.ts"), "utf-8")).toContain("business_7_scenes");
    expect(r.week.slots[6]).toEqual({ idea: "business-7", episode: "business-7" });
    // réimport (correction) : réécrit sans créer de doublon
    expect(importWeek(root, store, r.week, answer(seven())).created).toHaveLength(7);
    expect(store.listEpisodes()).toHaveLength(7);
  });

  it("ne crée rien si une seule vidéo est fausse", () => {
    const v = seven();
    v[6] = video(6, "Pas Bon");
    const r = importWeek(root, createStore(root), week, answer(v));
    expect(r.ok).toBe(false);
    expect(fs.readdirSync(path.join(root, "episodes"))).toEqual([]);
  });

  it("lit les noms du stock sur mesure", () => {
    fs.writeFileSync(path.join(root, "src/scenes/custom/index.ts"), 'export const CUSTOM: Record<string, SceneImpl> = {\n  Fusee: fusee,\n  "pluie-billets": pluie,\n};\n');
    expect(customNames(root)).toEqual(["Fusee", "pluie-billets"]);
  });
});
