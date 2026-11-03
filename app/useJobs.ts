import { useEffect, useState } from "react";
import type { JobView } from "../server/types";
import { API_BASE, CLOUD_ONLY, ONLINE } from "./config";

/** Dernière tâche par épisode, mise à jour en direct ; `version` change quand une tâche se termine. */
export const useJobs = () => {
  const [byEpisode, setByEpisode] = useState<Record<string, JobView>>({});
  const [version, setVersion] = useState(0);
  const [toast, setToast] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    if (CLOUD_ONLY) return;
    const es = new EventSource(`${API_BASE}/api/jobs/stream`);
    es.onmessage = (e) => {
      const job = JSON.parse(e.data) as JobView;
      setByEpisode((m) => ({ ...m, [job.episodeId]: job }));
      if (job.status === "done" || job.status === "error") {
        setVersion((v) => v + 1);
        const what = { compare: "Écoute des prises", align: "Calage", render: "Rendu final", verify: "Vérification des faits" }[job.kind];
        setToast({ ok: job.status === "done", text: `${what} ${job.status === "done" ? "terminé" : "en échec"}${job.episodeId !== "ideas" ? ` · ${job.episodeId}` : ""}` });
        setTimeout(() => setToast(null), 7000);
      }
      // en ligne, un calage republie le site avec les nouveaux timings : on recharge pour les prendre
      if (ONLINE && job.kind === "align" && job.status === "done") setTimeout(() => window.location.reload(), 1500);
    };
    return () => es.close();
  }, []);
  const active = Object.values(byEpisode).filter((j) => j.status === "running" || j.status === "queued");
  return { byEpisode, version, active, toast };
};
