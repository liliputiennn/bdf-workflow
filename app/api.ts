import type { Episode, Fact, Idea, JobKind, JobView } from "../server/types";
import { API_BASE } from "./config";

export type IdeaRow = Idea & { weakFacts: Fact[] };

export type EpisodeDetail = Episode & { texts: { voiceText: string; post: string; publication: string } };
export type Week = { start: string; slots: { idea?: string; subject?: string; episode?: string }[] };
export type ImportResult = { ok: boolean; errors: string[]; warnings: string[]; created: string[]; week: Week };
export type BatchStatus = {
  running: boolean;
  total: number;
  done: number;
  summary: { finishedAt: string; rendered: string[]; errors: { id: string; error: string }[]; text: string } | null;
};

const j = async <T,>(r: Response): Promise<T> => {
  if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error);
  return r.json() as Promise<T>;
};

/** L'en-tête x-console prouve que l'action vient de la Console (exigé par l'API locale). */
const ACT = { "x-console": "1" };

const u = (path: string) => `${API_BASE}${path}`;
const post = (url: string, body?: unknown) =>
  fetch(u(url), { method: "POST", headers: body ? { ...ACT, "content-type": "application/json" } : ACT, body: body ? JSON.stringify(body) : undefined });

export const api = {
  health: () => fetch(u("/api/health")).then((r) => j<Record<string, boolean>>(r)),
  ideas: () => fetch(u("/api/ideas")).then((r) => j<IdeaRow[]>(r)),
  produce: (slug: string) => post(`/api/ideas/${slug}/produce`).then((r) => j<Episode>(r)),
  episodes: () => fetch(u("/api/episodes")).then((r) => j<Episode[]>(r)),
  episode: (id: string) => fetch(u(`/api/episodes/${id}`)).then((r) => j<EpisodeDetail>(r)),
  uploadTakes: (id: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("takes", f, f.name));
    return fetch(u(`/api/episodes/${id}/voice`), { method: "POST", headers: ACT, body: fd }).then((r) => j<Episode>(r));
  },
  chooseTake: (id: string, take: string) => post(`/api/episodes/${id}/voice/choose`, { take }).then((r) => j<Episode>(r)),
  setMix: (id: string, mix: { music: number; sfx: number }) =>
    fetch(u(`/api/episodes/${id}/mix`), { method: "PATCH", headers: { ...ACT, "content-type": "application/json" }, body: JSON.stringify(mix) }).then((r) =>
      j<Episode>(r),
    ),
  runJob: (id: string, kind: JobKind) => post(`/api/episodes/${id}/jobs/${kind}`).then((r) => j<JobView>(r)),
  verifyIdeas: () => post("/api/ideas/verify").then((r) => j<JobView>(r)),
  setAutopilot: (id: string, on: boolean) =>
    fetch(u(`/api/episodes/${id}/autopilot`), { method: "PATCH", headers: { ...ACT, "content-type": "application/json" }, body: JSON.stringify({ on }) }).then((r) =>
      j<Episode>(r),
    ),
  openFolder: (id: string, what?: "package") => post(`/api/episodes/${id}/open-folder${what ? `?what=${what}` : ""}`).then(() => undefined),
  week: () => fetch(u("/api/week")).then((r) => j<Week>(r)),
  saveWeek: (w: Week, previousStart?: string) =>
    fetch(u("/api/week"), { method: "PATCH", headers: { ...ACT, "content-type": "application/json" }, body: JSON.stringify({ ...w, previousStart }) }).then((r) => j<Week>(r)),
  suggestions: () => fetch(u("/api/week/suggestions")).then((r) => j<{ titre: string; theme: string; angle: string }[]>(r)),
  brief: () => fetch(u("/api/week/brief")).then((r) => j<{ text: string }>(r)),
  importWeek: (text: string) =>
    post("/api/week/import", { text }).then(async (r) => {
      const body = (await r.json()) as ImportResult & { error?: string };
      if (!r.ok && !body.errors) throw new Error(body.error ?? r.statusText);
      return body;
    }),
  batch: () => fetch(u("/api/batch")).then((r) => j<BatchStatus>(r)),
  startBatch: () => post("/api/batch", {}).then((r) => j<{ queued: string[]; skipped: { id: string; error?: string }[] }>(r)),
  buildPackage: (id: string) => post(`/api/episodes/${id}/package`).then((r) => j<Episode>(r)),
  setPublished: (id: string, on: boolean) =>
    fetch(u(`/api/episodes/${id}/published`), { method: "PATCH", headers: { ...ACT, "content-type": "application/json" }, body: JSON.stringify({ on }) }).then((r) =>
      j<Episode>(r),
    ),
};

/** Adresse d'un rendu (vidéo, couverture) servi par l'API locale. */
export const fileUrl = (path: string) => `${API_BASE}/files/${path}`;
