import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { safeJoin } from "../server/paths";
import { createStore, weakFacts } from "../server/store";
import type { Idea } from "../server/types";

const idea = (over: Partial<Idea> = {}): Idea => ({
  slug: "gimli-glider", hook: "Panne sèche à 12 000 m", theme: "Aviation", year: 1983, score: 9.4,
  scoreNote: "estimation", facts: [{ claim: "69 occupants", sources: ["https://a", "https://b"] }],
  disputed: [], status: "idea", ...over,
});

let root: string;
beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-"));
  fs.mkdirSync(path.join(root, "ideas"));
  fs.mkdirSync(path.join(root, "episodes"));
});

describe("safeJoin", () => {
  it("refuse les chemins hors projet", () => {
    expect(() => safeJoin(root, "..", "x")).toThrow("chemin hors projet");
    expect(safeJoin(root, "ideas", "a.json")).toBe(path.join(root, "ideas", "a.json"));
  });
});

describe("weakFacts", () => {
  it("signale les faits avec moins de 2 sources distinctes", () => {
    const i = idea({ facts: [{ claim: "x", sources: ["https://a", "https://a"] }, { claim: "y", sources: ["https://a", "https://b"] }] });
    expect(weakFacts(i).map((f) => f.claim)).toEqual(["x"]);
  });
});

describe("store", () => {
  it("lit et écrit les idées", () => {
    const s = createStore(root);
    s.saveIdea(idea());
    expect(s.listIdeas()).toHaveLength(1);
    expect(s.getIdea("gimli-glider").hook).toBe("Panne sèche à 12 000 m");
  });

  it("crée un épisode numéroté à partir d'une idée", () => {
    const s = createStore(root);
    s.saveIdea(idea());
    const ep = s.createEpisodeFromIdea("gimli-glider");
    expect(ep.id).toBe("gimli-glider");
    expect(ep.number).toBe(1);
    expect(ep.channel).toBe("bureau-des-faits");
    expect(ep.compositionId).toBe("Ep01-GimliGlider");
    expect(ep.coverId).toBe("Ep01-GimliGlider-Cover");
    expect(ep.steps.facts).toBe("done");
    expect(ep.steps.voice).toBe("todo");
    expect(ep.timingsFile).toBe("src/episodes/gimli-glider.timings.json");
    expect(s.getIdea("gimli-glider").status).toBe("production");
    expect(fs.existsSync(path.join(root, "episodes", "gimli-glider", "episode.json"))).toBe(true);
  });

  it("met l'étape faits à faire si une source manque", () => {
    const s = createStore(root);
    s.saveIdea(idea({ facts: [{ claim: "x", sources: ["https://a"] }] }));
    expect(s.createEpisodeFromIdea("gimli-glider").steps.facts).toBe("todo");
  });

  it("refuse de produire deux fois la même idée", () => {
    const s = createStore(root);
    s.saveIdea(idea());
    s.createEpisodeFromIdea("gimli-glider");
    expect(() => s.createEpisodeFromIdea("gimli-glider")).toThrow();
  });

  it("numérote après le plus grand numéro existant", () => {
    const s = createStore(root);
    s.saveIdea(idea());
    s.saveIdea(idea({ slug: "apollo-13" }));
    s.createEpisodeFromIdea("gimli-glider");
    expect(s.createEpisodeFromIdea("apollo-13").number).toBe(2);
  });
});
