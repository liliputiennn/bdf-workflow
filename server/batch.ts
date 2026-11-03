import fs from "node:fs";
import type { JobDef } from "./jobs";
import { safeJoin } from "./paths";
import { alignJob, renderJob, scenesReady, type Ctx } from "./pipelines";
import { summarize, toast, type BatchResult, type BatchSummary } from "./notify";
import type { Episode } from "./types";

/**
 * Lot : calage (si besoin) puis rendu de plusieurs épisodes. La seule source de vérité est l'état
 * des épisodes (episode.json) et la semaine (weeks/*.json) : plus de CSV à tenir à jour.
 */

/** Épisodes de la semaine la plus récente, dans l'ordre des jours. */
export const weekEpisodeIds = (root: string): string[] => {
  const dir = safeJoin(root, "weeks");
  if (!fs.existsSync(dir)) return [];
  const f = fs.readdirSync(dir).filter((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n)).sort().pop();
  if (!f) return [];
  const w = JSON.parse(fs.readFileSync(safeJoin(root, "weeks", f), "utf-8")) as { slots: { episode?: string }[] };
  return w.slots.map((s) => s.episode).filter((x): x is string => !!x);
};

export type Candidate = { ep: Episode; needsAlign: boolean; skip: string | null };

/** Ce que le lot fera pour chaque épisode (ou pourquoi il le saute). Les vidéos déjà rendues sont ignorées. */
export const batchCandidates = (ctx: Ctx, ids: string[]): Candidate[] =>
  ids
    .map((id) => {
      try {
        return ctx.store.getEpisode(id);
      } catch {
        return null;
      }
    })
    .filter((ep): ep is Episode => !!ep && ep.steps.render !== "done")
    .map((ep) => ({
      ep,
      needsAlign: ep.steps.align !== "done",
      skip: !ep.voice.chosen ? "aucune prise de voix retenue" : !scenesReady(ctx, ep.id) ? "scènes absentes (registre ou scenes.json)" : null,
    }));

/** Les tâches d'un épisode : calage éventuel, puis rendu annulé si le calage n'a pas abouti. */
export const batchJobs = (ctx: Ctx, c: Candidate): JobDef[] => {
  const render = renderJob(ctx, c.ep);
  const jobs = c.needsAlign ? [alignJob(ctx, c.ep)] : [];
  return [...jobs, { ...render, skipIf: () => (ctx.store.getEpisode(c.ep.id).steps.align === "done" ? null : "calage non terminé : rendu annulé") }];
};

/** Suivi d'un lot lancé depuis la Console (file de l'API). */
export const createBatchRunner = (ctx: Ctx) => {
  let current: { total: number; results: Map<string, BatchResult>; skipped: BatchResult[] } | null = null;
  let last: BatchSummary | null = null;

  const finish = () => {
    if (!current) return;
    const results = [...current.skipped, ...current.results.values()];
    last = summarize(results, ctx.store.listEpisodes());
    toast(last.errors.length ? "Lot terminé avec des erreurs" : "Lot terminé", last.text);
    current = null;
  };
  const record = (r: BatchResult) => {
    if (!current || current.results.has(r.id)) return;
    current.results.set(r.id, r);
    if (current.results.size >= current.total) finish();
  };

  const start = (ids: string[]) => {
    if (current) throw new Error("un lot est déjà en cours");
    if (!ctx.queue) throw new Error("file de tâches indisponible");
    const all = batchCandidates(ctx, ids);
    const ready = all.filter((c) => !c.skip);
    const skipped = all.filter((c) => c.skip).map((c) => ({ id: c.ep.id, ok: false, error: c.skip! }));
    current = { total: ready.length, results: new Map(), skipped };
    for (const c of ready) {
      const defs = batchJobs(ctx, c);
      defs.forEach((def, k) => {
        const lastJob = k === defs.length - 1;
        const wrapped: JobDef = {
          ...def,
          onSuccess: async () => {
            await def.onSuccess?.();
            if (lastJob) record({ id: c.ep.id, ok: true });
          },
          onError: async (log) => {
            await def.onError?.(log);
            record({ id: c.ep.id, ok: false, error: `${def.kind === "align" ? "calage" : "rendu"} : ${log.split("\n").filter(Boolean).at(-1) ?? "erreur"}` });
          },
        };
        const step = def.kind === "align" ? "align" : "render";
        const ep = ctx.store.getEpisode(c.ep.id);
        if (k === 0) ctx.store.saveEpisode({ ...ep, steps: { ...ep.steps, [step]: "running" }, error: null });
        ctx.queue!.enqueue(wrapped);
      });
    }
    if (ready.length === 0) finish();
    return { queued: ready.map((c) => c.ep.id), skipped };
  };

  const status = () => ({ running: !!current, total: current?.total ?? 0, done: current?.results.size ?? 0, summary: last });
  return { start, status };
};
