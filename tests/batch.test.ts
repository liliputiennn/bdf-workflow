import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { batchCandidates, weekEpisodeIds } from "../server/batch";
import { createQueue } from "../server/jobs";
import { acquireLock, lockHolder } from "../server/lock";
import { summarize } from "../server/notify";
import type { Ctx } from "../server/pipelines";
import { createStore } from "../server/store";
import { findTools } from "../server/tools";

let root: string;
let ctx: Ctx;
const idea = (slug: string) => ({ slug, hook: slug, theme: "x", year: 2020, score: 1, scoreNote: "", facts: [], disputed: [], status: "idea" });

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-batch-"));
  for (const d of ["ideas", "episodes", "renders", "src/episodes", "weeks"]) fs.mkdirSync(path.join(root, d), { recursive: true });
  fs.writeFileSync(path.join(root, "src/episodes/registry.ts"), 'const CODED = {\n  "a": {},\n};\n');
  fs.writeFileSync(path.join(root, "src/episodes/data-index.ts"), 'import b_scenes from "../../episodes/b/scenes.json";\n');
  ctx = { root, store: createStore(root), tools: findTools(root) };
  for (const s of ["a", "b", "c", "d"]) {
    fs.writeFileSync(path.join(root, "ideas", `${s}.json`), JSON.stringify(idea(s)));
    ctx.store.createEpisodeFromIdea(s);
  }
  const set = (id: string, patch: object) => ctx.store.saveEpisode({ ...ctx.store.getEpisode(id), ...patch });
  set("a", { voice: { takes: ["v.mp3"], chosen: "v.mp3", scores: {} } });
  set("b", { voice: { takes: ["v.mp3"], chosen: "v.mp3", scores: {} }, steps: { ...ctx.store.getEpisode("b").steps, align: "done" } });
  set("d", { steps: { ...ctx.store.getEpisode("d").steps, render: "done" } });
});

describe("lot", () => {
  it("lit les épisodes de la semaine la plus récente", () => {
    fs.writeFileSync(path.join(root, "weeks", "2026-10-19.json"), JSON.stringify({ start: "2026-10-19", slots: [{ episode: "z" }] }));
    fs.writeFileSync(path.join(root, "weeks", "2026-10-26.json"), JSON.stringify({ start: "2026-10-26", slots: [{ episode: "b" }, {}, { episode: "a" }] }));
    expect(weekEpisodeIds(root)).toEqual(["b", "a"]);
  });

  it("dit pour chaque épisode ce qu'il fera, ou pourquoi il le saute (une seule source : les épisodes)", () => {
    const c = batchCandidates(ctx, ["a", "b", "c", "d", "inconnu"]);
    expect(c.map((x) => [x.ep.id, x.needsAlign, x.skip])).toEqual([
      ["a", true, null],
      ["b", false, null],
      ["c", true, "aucune prise de voix retenue"],
    ]);
  });

  it("résume le lot : rendus, erreurs, pire passage de clarté", () => {
    const s = summarize(
      [{ id: "a", ok: true }, { id: "b", ok: true }, { id: "c", ok: false, error: "aucune prise" }],
      [
        { id: "a", metrics: { medianDb: 31, worstDb: 9.5, whisper: 95 } },
        { id: "b", metrics: { medianDb: 28, worstDb: 4.2, whisper: 91 } },
      ],
    );
    expect(s.text).toBe("2 vidéos rendues · 1 erreur (c) · pire passage : b 4.2 dB (médiane 28 dB, Whisper 91 %)");
  });
});

describe("verrou", () => {
  it("bloque un 2e calcul du même épisode et ignore un verrou orphelin", () => {
    const release = acquireLock(root, "a", "le lot");
    expect(lockHolder(root, "a")?.owner).toBe("le lot");
    // un autre processus vivant (le parent de vitest) tient le verrou
    fs.writeFileSync(path.join(root, "renders", "a", ".verrou"), JSON.stringify({ pid: process.ppid, owner: "le lot (npm run batch)", since: "2026-10-20T21:05:00Z" }));
    expect(() => acquireLock(root, "a", "la Console")).toThrow("« a » est déjà en cours dans le lot (npm run batch) (depuis 21:05)");
    // processus mort : verrou ignoré
    fs.writeFileSync(path.join(root, "renders", "a", ".verrou"), JSON.stringify({ pid: 999999, owner: "le lot", since: "x" }));
    expect(lockHolder(root, "a")).toBeNull();
    expect(() => acquireLock(root, "a", "la Console")()).not.toThrow();
    release();
  });

  it("la file refuse une tâche dont l'épisode est verrouillé par un autre processus", async () => {
    fs.mkdirSync(path.join(root, "renders", "a"), { recursive: true });
    fs.writeFileSync(path.join(root, "renders", "a", ".verrou"), JSON.stringify({ pid: process.ppid, owner: "le lot", since: "2026-10-20T21:05:00Z" }));
    const errors: string[] = [];
    const q = createQueue(() => {});
    q.enqueue({ episodeId: "a", kind: "render", steps: [{ label: "x", cmd: process.execPath, args: ["-e", ""], cwd: root }], lock: { root, owner: "la Console" }, onError: (l) => void errors.push(l) });
    await q.idle();
    expect(q.list()[0].status).toBe("error");
    expect(errors[0]).toContain("déjà en cours dans le lot");
  });

  it("annule un rendu quand skipIf donne une raison", async () => {
    const q = createQueue(() => {});
    q.enqueue({ episodeId: "a", kind: "render", steps: [], skipIf: () => "calage non terminé : rendu annulé" });
    await q.idle();
    expect(q.list()[0]).toMatchObject({ status: "error", log: ["calage non terminé : rendu annulé"] });
  });
});
