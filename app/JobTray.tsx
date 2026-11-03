import { useEffect, useState } from "react";
import type { JobView } from "../server/types";
import { eta } from "./production/Panels";

/** Tâche en cours visible depuis n'importe quel onglet, avec son temps restant. */
export const JobTray = ({ active, toast }: { active: JobView[]; toast: { ok: boolean; text: string } | null }) => {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active.length) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active.length]);
  const job = active.find((j) => j.status === "running") ?? active[0];
  return (
    <>
      {job && (
        <div className="tray" title={job.label}>
          <span className="tray-label">{job.episodeId === "ideas" ? "Faits" : job.episodeId} · {job.label || "en attente"}</span>
          <span className="bar tray-bar"><span style={{ width: `${Math.round((job.progress ?? 0.03) * 100)}%` }} /></span>
          <span className="tray-eta">{eta(job, now)}{active.length > 1 ? ` · +${active.length - 1} en file` : ""}</span>
        </div>
      )}
      {toast && <div className={`toast ${toast.ok ? "ok" : "ko"}`} role="status">{toast.ok ? "✓ " : "⚠ "}{toast.text}</div>}
    </>
  );
};
