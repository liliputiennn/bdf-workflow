import fs from "node:fs";
import path from "node:path";
import type { JobDef, JobStep, Queue } from "./jobs";
import { safeJoin } from "./paths";
import { buildPackage } from "./publish";
import type { Store } from "./store";
import type { Tools } from "./tools";
import type { Episode, Metrics, StepKey, StepState, TakeScore } from "./types";

export type Ctx = { root: string; store: Store; tools: Tools; queue?: Queue };

/** Les scènes d'un épisode sont prêtes quand il est inscrit au registre (codé) ou dans l'index des épisodes en données. */
export const scenesReady = (ctx: Ctx, id: string) => {
  const index = safeJoin(ctx.root, "src", "episodes", "data-index.ts");
  return (
    fs.readFileSync(safeJoin(ctx.root, "src", "episodes", "registry.ts"), "utf-8").includes(`"${id}": {`) ||
    (fs.existsSync(index) && fs.readFileSync(index, "utf-8").includes(`"../../episodes/${id}/scenes.json"`))
  );
};

/** Pilote automatique : enchaîne l'étape suivante si l'épisode l'autorise. */
const next = (ctx: Ctx, id: string, kind: "align" | "render") => {
  const ep = ctx.store.getEpisode(id);
  if (ep.autopilot === false || !ctx.queue) return;
  // déjà prévu (ex. lot de la semaine) : pas de doublon
  if (ctx.queue.list().some((j) => j.episodeId === id && j.kind === kind && j.status === "queued")) return;
  if (kind === "render" && !scenesReady(ctx, id)) return;
  const def = kind === "align" ? alignJob(ctx, ep) : renderJob(ctx, ep);
  ctx.store.saveEpisode({ ...ep, steps: { ...ep.steps, [kind]: "running" } });
  ctx.queue.enqueue(def);
};

/** Vérifie automatiquement les faits de la banque d'idées dans leurs sources. */
export const verifyJob = (ctx: Ctx): JobDef => ({
  episodeId: "ideas",
  kind: "verify",
  steps: [{ label: "Vérification des faits dans les sources", ...py(ctx, "tools/verify_facts.py", [safeJoin(ctx.root, "ideas")]) }],
});

const py = (ctx: Ctx, script: string, args: string[]) => ({
  cmd: ctx.tools.uv,
  args: ["run", "--no-sync", "--project", ctx.tools.rushSorter, "python", "-I", safeJoin(ctx.root, script), ...args],
  cwd: ctx.root,
});

const mark = (ctx: Ctx, id: string, patch: Partial<Record<StepKey, StepState>>, extra: Partial<Episode> = {}) => {
  const ep = ctx.store.getEpisode(id);
  ctx.store.saveEpisode({ ...ep, ...extra, steps: { ...ep.steps, ...patch } });
};
const fail = (ctx: Ctx, id: string, step: StepKey) => (log: string) => mark(ctx, id, { [step]: "error" }, { error: { step, log } });

/** Compare les prises : similarité au script (Whisper) puis nombre de pauses. */
export const compareJob = (ctx: Ctx, ep: Episode): JobDef => {
  const out = safeJoin(ctx.root, "renders", ep.id, "takes.json");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const files = ep.voice.takes.map((t) => safeJoin(ctx.root, "public", ep.publicDir, t));
  return {
    episodeId: ep.id,
    kind: "compare",
    steps: [{ label: "Écoute des prises (Whisper)", ...py(ctx, "tools/measure.py", ["takes", safeJoin(ctx.root, ep.scriptFile), out, ...files]) }],
    onSuccess: () => {
      const scores = JSON.parse(fs.readFileSync(out, "utf-8")) as Record<string, TakeScore>;
      const best = Object.entries(scores).sort((a, b) => b[1].similarity - a[1].similarity || b[1].pauses - a[1].pauses)[0]?.[0] ?? null;
      const cur = ctx.store.getEpisode(ep.id);
      mark(ctx, ep.id, { voice: "done" }, { voice: { ...cur.voice, scores, chosen: best }, error: null });
      if (best) next(ctx, ep.id, "align");
    },
    onError: fail(ctx, ep.id, "voice"),
  };
};

/**
 * Les timings sont compilés dans le site en ligne : après chaque calage, on le reconstruit et on le republie,
 * sinon l'aperçu en ligne resterait sur les anciens timings.
 */
export const publishSteps = (ctx: Ctx): JobStep[] =>
  ctx.tools.firebase
    ? [
        { label: "Mise à jour du site en ligne", cmd: ctx.tools.node, args: [ctx.tools.vite, "build", "--config", "app/vite.config.ts"], cwd: ctx.root, weight: 1 },
        { label: "Publication du site en ligne", cmd: ctx.tools.node, args: [ctx.tools.firebase, "deploy", "--only", "hosting", "--project", "bureau-des-faits"], cwd: ctx.root, weight: 1 },
      ]
    : [];

/** Calage au mot de la prise retenue sur le script. */
export const alignJob = (ctx: Ctx, ep: Episode): JobDef => {
  if (!ep.voice.chosen) throw new Error("aucune prise retenue");
  return {
    episodeId: ep.id,
    kind: "align",
    lock: { root: ctx.root, owner: "la Console" },
    steps: [
      {
        label: "Calage au mot (Whisper)",
        ...py(ctx, "tools/align.py", [safeJoin(ctx.root, "public", ep.publicDir, ep.voice.chosen), safeJoin(ctx.root, ep.scriptFile), safeJoin(ctx.root, ep.timingsFile)]),
        weight: 4,
      },
      ...publishSteps(ctx),
    ],
    onSuccess: () => {
      mark(ctx, ep.id, { align: "done" }, { error: null });
      next(ctx, ep.id, "render");
    },
    onError: fail(ctx, ep.id, "align"),
  };
};

/** Rendu image + musique + SFX, mixage voix prioritaire, mesure de clarté, couverture. */
export const renderJob = (ctx: Ctx, ep: Episode): JobDef => {
  if (!ep.voice.chosen) throw new Error("aucune prise retenue");
  const dir = safeJoin(ctx.root, "renders", ep.id);
  fs.mkdirSync(dir, { recursive: true });
  const props = path.join(dir, "props.json");
  fs.writeFileSync(props, JSON.stringify({ voice: "", mix: ep.mix }));
  const bed = path.join(dir, "bed.mp4");
  const tmp = path.join(dir, "final.tmp.mp4");
  const final = path.join(dir, `${ep.id}.mp4`);
  const voice = safeJoin(ctx.root, "public", ep.publicDir, ep.voice.chosen);
  const metrics = path.join(dir, "metrics.json");
  const t = ctx.tools;
  return {
    episodeId: ep.id,
    kind: "render",
    lock: { root: ctx.root, owner: "la Console" },
    steps: [
      { label: "Rendu image + musique + SFX", cmd: t.node, args: [t.remotion, "render", "src/index.ts", ep.compositionId, bed, `--props=${props}`, "--crf=17", "--timeout=120000"], cwd: ctx.root, weight: 8 },
      { label: "Mixage voix prioritaire", cmd: t.bash, args: [safeJoin(ctx.root, "tools", "mix.sh"), bed, voice, tmp], cwd: ctx.root, weight: 1 },
      {
        label: "Mesure de la clarté",
        ...py(ctx, "tools/measure.py", [
          "clarity",
          path.join(dir, "final.tmp-voix-traitee.wav"),
          path.join(dir, "final.tmp-fond-duck.wav"),
          safeJoin(ctx.root, ep.timingsFile),
          safeJoin(ctx.root, ep.scriptFile),
          tmp,
          metrics,
        ]),
        weight: 2,
      },
      { label: "Couverture", cmd: t.node, args: [t.remotion, "still", "src/index.ts", ep.coverId, path.join(dir, "cover.png"), "--timeout=120000"], cwd: ctx.root, weight: 1 },
    ],
    onSuccess: () => {
      fs.renameSync(tmp, final);
      const m = JSON.parse(fs.readFileSync(metrics, "utf-8")) as Metrics;
      mark(ctx, ep.id, { render: "done", preview: "done", scenes: "done" }, { metrics: m, error: null });
      try {
        const fresh = ctx.store.getEpisode(ep.id);
        ctx.store.saveEpisode({ ...fresh, package: buildPackage(ctx.root, fresh) });
      } catch {
        // le paquet se refait depuis la Console (bouton « Préparer le paquet »)
      }
    },
    onError: fail(ctx, ep.id, "render"),
  };
};
