import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { acquireLock } from "./lock";
import type { JobKind, JobView } from "./types";

export type JobStep = { label: string; cmd: string; args: string[]; cwd: string; weight?: number };
export type JobDef = {
  episodeId: string;
  kind: JobKind;
  steps: JobStep[];
  onSuccess?: () => void | Promise<void>;
  onError?: (log: string) => void | Promise<void>;
  /** verrou de l'épisode pendant le calcul (partagé avec le lot en ligne de commande) */
  lock?: { root: string; owner: string };
  /** vérifiée au démarrage : une raison renvoyée annule la tâche (ex. calage échoué avant le rendu) */
  skipIf?: () => string | null;
};
type Job = JobView & { def: JobDef };

const LOG_LINES = 40;

/** Dernière fraction « n/total » trouvée (sortie Remotion : Rendered 120/2841, Encoded …). */
export const parseProgress = (chunk: string): number | null => {
  const last = [...chunk.matchAll(/(\d+)\s*\/\s*(\d+)/g)].at(-1);
  if (!last) return null;
  const total = Number(last[2]);
  return total > 0 ? Math.min(1, Number(last[1]) / total) : null;
};

export const runStep = (step: JobStep, onData: (text: string) => void) =>
  new Promise<number>((resolve) => {
    const child = spawn(step.cmd, step.args, { cwd: step.cwd, windowsHide: true });
    child.stdout.on("data", (d: Buffer) => onData(d.toString()));
    child.stderr.on("data", (d: Buffer) => onData(d.toString()));
    child.on("error", (e) => {
      onData(`${e.message}\n`);
      resolve(-1);
    });
    child.on("close", (code) => resolve(code ?? -1));
  });

export const createQueue = (emit: (job: JobView) => void) => {
  const jobs: Job[] = [];
  let chain: Promise<void> = Promise.resolve();

  const view = (j: Job): JobView => {
    const { def: _def, ...rest } = j;
    return { ...rest, log: [...rest.log] };
  };

  const run = async (job: Job) => {
    job.status = "running";
    job.startedAt = Date.now();
    emit(view(job));
    const abort = async (reason: string) => {
      job.log.push(reason);
      job.status = "error";
      emit(view(job));
      await job.def.onError?.(reason);
    };
    let release = () => {};
    try {
      const reason = job.def.skipIf?.();
      if (reason) return await abort(reason);
      if (job.def.lock) release = acquireLock(job.def.lock.root, job.episodeId, job.def.lock.owner);
    } catch (e) {
      return await abort((e as Error).message);
    }
    try {
      await steps(job);
    } finally {
      release();
    }
  };

  const steps = async (job: Job) => {
    const weights = job.def.steps.map((s) => s.weight ?? 1);
    const totalW = weights.reduce((a, b) => a + b, 0);
    let doneW = 0;
    for (const [i, step] of job.def.steps.entries()) {
      job.label = step.label;
      emit(view(job));
      const code = await runStep(step, (text) => {
        for (const line of text.split(/\r|\n/).filter(Boolean)) job.log.push(line);
        job.log.splice(0, Math.max(0, job.log.length - LOG_LINES));
        const p = parseProgress(text);
        if (p !== null) job.progress = (doneW + p * weights[i]) / totalW;
        emit(view(job));
      });
      if (code !== 0) {
        job.status = "error";
        emit(view(job));
        await job.def.onError?.(job.log.slice(-15).join("\n"));
        return;
      }
      doneW += weights[i];
      job.progress = doneW / totalW;
    }
    try {
      await job.def.onSuccess?.();
      job.status = "done";
    } catch (e) {
      job.log.push(String(e));
      job.status = "error";
      await job.def.onError?.(String(e));
    }
    emit(view(job));
  };

  const enqueue = (def: JobDef): JobView => {
    const job: Job = { id: randomUUID(), episodeId: def.episodeId, kind: def.kind, status: "queued", progress: null, label: "", log: [], startedAt: null, def };
    jobs.push(job);
    emit(view(job));
    chain = chain.then(() => run(job));
    return view(job);
  };

  return { enqueue, list: () => jobs.map(view), idle: () => chain };
};
export type Queue = ReturnType<typeof createQueue>;
