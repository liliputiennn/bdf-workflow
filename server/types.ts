export const STEP_KEYS = ["facts", "script", "voiceText", "voice", "align", "scenes", "preview", "render", "publish"] as const;
export type StepKey = (typeof STEP_KEYS)[number];
export type StepState = "todo" | "running" | "done" | "error";
/** check : mots ou nombres qui doivent apparaître dans la source ; verified : sources où ils ont été trouvés. */
export type Fact = { claim: string; sources: string[]; check?: string[]; verified?: string[] };
export type Idea = {
  slug: string;
  hook: string;
  theme: string;
  year: number;
  score: number;
  scoreNote: string;
  facts: Fact[];
  disputed: string[];
  status: "idea" | "production" | "published";
};
export type TakeScore = { similarity: number; pauses: number };
export type Metrics = { medianDb: number; worstDb: number; whisper: number };
export type Episode = {
  id: string;
  number: number;
  title: string;
  idea: string;
  channel: string;
  publicDir: string;
  compositionId: string;
  coverId: string;
  scriptFile: string;
  voiceTextFile: string;
  timingsFile: string;
  steps: Record<StepKey, StepState>;
  voice: { takes: string[]; chosen: string | null; scores: Record<string, TakeScore> };
  mix: { music: number; sfx: number };
  metrics: Metrics | null;
  /** pilote automatique : voix déposée → meilleure prise → calage → rendu, sans clic */
  autopilot?: boolean;
  /** paquet de publication prêt (exports/<date>/<id>/) */
  package?: { dir: string; date: string } | null;
  /** date de publication cochée à la main (AAAA-MM-JJ) */
  publishedAt?: string | null;
  error: { step: StepKey; log: string } | null;
};
export type JobKind = "compare" | "align" | "render" | "verify";
export type JobStatus = "queued" | "running" | "done" | "error";
export type JobView = { id: string; episodeId: string; kind: JobKind; status: JobStatus; progress: number | null; label: string; log: string[]; startedAt: number | null };
