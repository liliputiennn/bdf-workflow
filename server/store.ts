import fs from "node:fs";
import path from "node:path";
import { safeJoin } from "./paths";
import { STEP_KEYS, type Episode, type Fact, type Idea, type StepKey, type StepState } from "./types";

export const weakFacts = (idea: Idea): Fact[] => idea.facts.filter((f) => new Set(f.sources).size < 2);

const readJson = <T>(file: string): T => JSON.parse(fs.readFileSync(file, "utf-8")) as T;
const writeJson = (file: string, data: unknown) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n", "utf-8");
  fs.renameSync(tmp, file);
};
const pascal = (slug: string) => slug.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join("");
const pad = (n: number) => String(n).padStart(2, "0");

export const createStore = (root: string) => {
  const ideaFile = (slug: string) => safeJoin(root, "ideas", `${slug}.json`);
  const episodeFile = (id: string) => safeJoin(root, "episodes", id, "episode.json");

  const listIdeas = (): Idea[] =>
    fs
      .readdirSync(safeJoin(root, "ideas"))
      .filter((f) => f.endsWith(".json"))
      .map((f) => readJson<Idea>(safeJoin(root, "ideas", f)))
      .sort((a, b) => b.score - a.score);
  const getIdea = (slug: string) => readJson<Idea>(ideaFile(slug));
  const saveIdea = (idea: Idea) => writeJson(ideaFile(idea.slug), idea);

  const listEpisodes = (): Episode[] =>
    fs
      .readdirSync(safeJoin(root, "episodes"), { withFileTypes: true })
      .filter((d) => d.isDirectory() && fs.existsSync(episodeFile(d.name)))
      .map((d) => readJson<Episode>(episodeFile(d.name)))
      .sort((a, b) => a.number - b.number);
  const getEpisode = (id: string) => readJson<Episode>(episodeFile(id));
  const saveEpisode = (ep: Episode) => writeJson(episodeFile(ep.id), ep);

  const createEpisodeFromIdea = (slug: string, channel = "bureau-des-faits"): Episode => {
    const idea = getIdea(slug);
    if (idea.status !== "idea" || fs.existsSync(episodeFile(slug))) throw new Error("idée déjà en production");
    const number = listEpisodes().reduce((m, e) => Math.max(m, e.number), 0) + 1;
    const steps = Object.fromEntries(STEP_KEYS.map((k) => [k, "todo"])) as Record<StepKey, StepState>;
    steps.facts = weakFacts(idea).length === 0 ? "done" : "todo";
    const ep: Episode = {
      id: slug,
      number,
      title: idea.hook,
      idea: slug,
      channel,
      publicDir: slug,
      compositionId: `Ep${pad(number)}-${pascal(slug)}`,
      coverId: `Ep${pad(number)}-${pascal(slug)}-Cover`,
      scriptFile: `episodes/${slug}/script.json`,
      voiceTextFile: `episodes/${slug}/TEXTE-VOIX.txt`,
      timingsFile: `src/episodes/${slug}.timings.json`,
      steps,
      voice: { takes: [], chosen: null, scores: {} },
      mix: { music: 1, sfx: 1 },
      metrics: null,
      autopilot: true,
      error: null,
    };
    saveEpisode(ep);
    saveIdea({ ...idea, status: "production" });
    return ep;
  };

  return { listIdeas, getIdea, saveIdea, listEpisodes, getEpisode, saveEpisode, createEpisodeFromIdea };
};
export type Store = ReturnType<typeof createStore>;
