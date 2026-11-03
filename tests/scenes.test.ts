import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { renderDataIndex, writeDataIndex } from "../server/dataIndex";
import script from "../src/scenes/demo/script.json";
import demo from "../src/scenes/demo/scenes.json";
import { SPRITES } from "../src/scenes/icons";
import { chunkWords, planScenes, provisionalTimings, wordFrame } from "../src/scenes/plan";
import { describePath, repetitionIssues, validateScenes, type ScenesFile } from "../src/scenes/schema";

const file = demo as unknown as ScenesFile;
const clone = (): Record<string, unknown> & { scenes: Record<string, unknown>[] } => JSON.parse(JSON.stringify(demo));

describe("validateScenes", () => {
  it("accepte le catalogue de démo", () => {
    expect(validateScenes(demo, script.length)).toEqual([]);
  });

  it("explique les erreurs en français, avec le chemin", () => {
    const bad = clone();
    bad.palette = "rose";
    bad.scenes[2].type = "camembert";
    (bad.scenes[5].params as Record<string, unknown>).etapes = [];
    bad.scenes[4].phrase = 99;
    const msgs = validateScenes(bad, script.length).map((i) => `${describePath(i.path)} : ${i.message}`);
    expect(msgs).toContain("palette : « palette » vaut « rose » ; valeurs possibles : phosphore, emeraude, menthe, lime");
    expect(msgs.some((m) => m.startsWith("scène 3 › type : type « camembert » inconnu"))).toBe(true);
    expect(msgs).toContain("scène 6 › params › etapes : « etapes » contient 0 éléments ; il en faut de 2 à 5");
    expect(msgs).toContain(`scène 5 › phrase : « phrase » doit être un numéro de phrase du script, de 1 à ${script.length}`);
  });

  it("refuse deux scènes du même type de suite et les textes trop longs", () => {
    const bad = clone();
    bad.scenes[1] = { type: "accroche", phrase: 2, params: { titre: "x".repeat(50) } };
    const msgs = validateScenes(bad, script.length).map((i) => i.message);
    expect(msgs.some((m) => m.includes("deux scènes « accroche » de suite"))).toBe(true);
    expect(msgs.some((m) => m.includes("trop long (50 caractères, 40 au plus)"))).toBe(true);
  });

  it("vérifie que la scène sur mesure existe dans le stock", () => {
    const bad = clone();
    bad.scenes[1] = { type: "sur-mesure", phrase: 2, params: { composant: "Fusee" } };
    expect(validateScenes(bad, script.length, []).some((i) => i.message.includes("« Fusee » introuvable"))).toBe(true);
    expect(validateScenes(bad, script.length, ["Fusee"])).toEqual([]);
  });
});

describe("repetitionIssues", () => {
  it("signale la même suite de scènes deux jours de suite", () => {
    expect(repetitionIssues(file, file)).toEqual(["même suite de scènes que la veille", "même palette (phosphore) et même rythme (nerveux) que la veille"]);
  });
  it("signale un enchaînement de 3 types déjà vu la veille", () => {
    const cur = { ...file, palette: "emeraude" as const, scenes: [file.scenes[0], file.scenes[5], file.scenes[6], file.scenes[7], file.scenes[14]] };
    expect(repetitionIssues(file, cur)).toEqual(["même enchaînement que la veille : flux-argent → liste → comparaison"]);
  });
  it("laisse passer deux vidéos différentes", () => {
    const cur = { ...file, rythme: "pose" as const, scenes: [...file.scenes].reverse() };
    expect(repetitionIssues(file, cur)).toEqual([]);
  });
});

describe("planScenes (SceneRunner)", () => {
  const T = provisionalTimings(script);
  const L = T.lines.map((l) => Math.round(l.start * 30));
  const frames = Math.ceil(T.total * 30);
  const plan = planScenes(file, L, frames, []);

  it("enchaîne les scènes sans trou, de 0 à la fin", () => {
    expect(plan[0].from).toBe(0);
    expect(plan[plan.length - 1].to).toBe(frames);
    plan.slice(1).forEach((p, i) => expect(p.from).toBe(plan[i].to));
    expect(plan[5].from).toBe(L[5]);
  });

  it("révèle les éléments dans l'ordre, à l'intérieur de la scène", () => {
    for (const p of plan) {
      p.reveals.forEach((r, k) => {
        expect(r).toBeGreaterThanOrEqual(p.from);
        expect(r).toBeLessThan(p.to);
        if (k) expect(r).toBeGreaterThan(p.reveals[k - 1]);
      });
    }
    expect(plan[5].reveals).toHaveLength(4);
  });

  it("cale un élément sur le mot prononcé", () => {
    const words = T.lines.map(() => [] as { w: string; start: number; end: number }[]);
    words[5] = [{ w: "La", start: 20, end: 20.2 }, { w: "farine,", start: 20.2, end: 20.6 }];
    expect(wordFrame(words, 4, 5, "Farine")).toBe(606);
    const p = planScenes(file, L, frames, words)[5];
    expect(p.reveals[0]).toBe(606);
  });

  it("choisit une variante par défaut stable mais propre à chaque épisode", () => {
    const bare = { ...file, scenes: file.scenes.map(({ variante: _v, ...s }) => s) } as ScenesFile;
    const a = planScenes(bare, L, frames, [], "ep-a").map((p) => p.variant);
    expect(planScenes(bare, L, frames, [], "ep-a").map((p) => p.variant)).toEqual(a);
    expect(planScenes(bare, L, frames, [], "ep-b").map((p) => p.variant)).not.toEqual(a);
  });
});

describe("stock d'icônes", () => {
  it("chaque sprite est un rectangle", () => {
    for (const [name, rows] of Object.entries(SPRITES)) for (const r of rows!) expect(r.length, name).toBe(rows![0].length);
  });
});

describe("data-index", () => {
  it("génère les imports et des timings provisoires", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-"));
    fs.mkdirSync(path.join(root, "episodes", "ikea"), { recursive: true });
    const ep = { id: "ikea", number: 3, scriptFile: "episodes/ikea/script.json", timingsFile: "src/episodes/ikea.timings.json", compositionId: "Ep03-Ikea", coverId: "Ep03-Ikea-Cover" };
    fs.writeFileSync(path.join(root, "episodes", "ikea", "episode.json"), JSON.stringify(ep));
    fs.writeFileSync(path.join(root, "episodes", "ikea", "script.json"), JSON.stringify(script));
    fs.writeFileSync(path.join(root, "episodes", "ikea", "scenes.json"), JSON.stringify(demo));
    fs.mkdirSync(path.join(root, "episodes", "codé"));
    expect(writeDataIndex(root)).toBe(true);
    expect(writeDataIndex(root)).toBe(false);
    const out = fs.readFileSync(path.join(root, "src", "episodes", "data-index.ts"), "utf-8");
    expect(out).toContain('import ikea_scenes from "../../episodes/ikea/scenes.json";');
    const t = JSON.parse(fs.readFileSync(path.join(root, ep.timingsFile), "utf-8"));
    expect(t.provisional).toBe(true);
    expect(t.lines).toHaveLength(script.length);
  });
  it("rend un index vide valide", () => {
    expect(renderDataIndex([])).toContain("export const DATA_EPISODES: DataEntry[] = [\n];");
  });
});

describe("Max et les sous-titres TikTok", () => {
  it("découpe les phrases en groupes de 3 mots, en coupant après la ponctuation", () => {
    const w = (s: string, i: number) => ({ w: s, start: i, end: i + 0.5 });
    const words = [["Tu", "paies", "trop,", "sauf", "que", "non", "vraiment."].map(w)];
    const c = chunkWords(words, [{ end: 7 }]);
    expect(c.map((x) => x.words.map((y) => y.w).join(" "))).toEqual(["Tu paies trop,", "sauf que non", "vraiment."]);
    expect(c[0].end).toBe(3);
    expect(c[2].end).toBe(7.25);
  });

  it("valide une scène « perso » et refuse une pose inconnue", () => {
    const ok = clone();
    ok.scenes[1] = { type: "perso", phrase: 2, variante: "zoom", params: { pose: "choc", texte: "x4 !" } };
    expect(validateScenes(ok, script.length)).toEqual([]);
    const bad = clone();
    bad.scenes[1] = { type: "perso", phrase: 2, params: { pose: "danse" } };
    expect(validateScenes(bad, script.length).map((i) => i.message)).toContain(
      "« pose » vaut « danse » ; valeurs possibles : parle, choc, content, telephone, reflechit, argent, montre",
    );
  });
});
