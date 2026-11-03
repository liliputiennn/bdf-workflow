import { useCallback, useEffect, useState } from "react";
import { api, type EpisodeDetail } from "../api";
import { STEP_KEYS, type StepKey } from "../../server/types";
import { EPISODES } from "../../src/episodes/registry";
import { Panel } from "../production/Panels";
import { Stage } from "../production/Stage";
import { StepList, stateOf } from "../production/StepList";
import { Timeline } from "../production/Timeline";
import type { useJobs } from "../useJobs";

export const Production = ({ episodeId, jobs }: { episodeId: string | null; jobs: ReturnType<typeof useJobs> }) => {
  const [ep, setEp] = useState<EpisodeDetail | null>(null);
  const [step, setStep] = useState<StepKey>("voice");
  const [frame, setFrame] = useState(0);
  const reload = useCallback(() => {
    if (episodeId) api.episode(episodeId).then(setEp);
  }, [episodeId]);
  useEffect(reload, [reload, jobs.version]);
  const epId = ep?.id;
  useEffect(() => {
    if (!ep) return;
    const first = STEP_KEYS.find((k) => stateOf(ep, k, !!EPISODES[ep.id]) !== "done");
    setStep(first ?? "publish");
    // seulement à l'ouverture d'un épisode
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epId]);
  if (!episodeId) return <main className="production empty muted">Choisis une idée à produire, ou un épisode dans Publiés.</main>;
  if (!ep) return <main className="production empty muted">Chargement…</main>;
  const entry = EPISODES[ep.id];
  return (
    <main className="production">
      <StepList ep={ep} scenesReady={!!entry} current={step} onSelect={setStep} onAutopilot={(on) => api.setAutopilot(ep.id, on).then(reload)} />
      <Stage entry={entry} ep={ep} onFrame={setFrame} />
      <Panel key={`${ep.id}-${step}`} step={step} ep={ep} job={jobs.byEpisode[ep.id]} scenesReady={!!entry} reload={reload} />
      <Timeline entry={entry} frame={frame} />
    </main>
  );
};
