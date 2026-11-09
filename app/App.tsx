import { useEffect, useState } from "react";
import { api, type BatchStatus } from "./api";
import { CLOUD_ONLY, ONLINE } from "./config";
import { JobTray } from "./JobTray";
import { Autopilote } from "./screens/Autopilote";
import { Chaines } from "./screens/Chaines";
import { Ideas } from "./screens/Ideas";
import { Production } from "./screens/Production";
import { Published } from "./screens/Published";
import { Route } from "./screens/Route";
import { Week } from "./screens/Week";
import { useJobs } from "./useJobs";

type Tab = "auto" | "chaines" | "route" | "week" | "ideas" | "production" | "published";
const TABS: [Tab, string][] = [
  ["auto", "Autopilote"],
  ["chaines", "Chaînes"],
  ["route", "Feuille de route"],
  ["week", "Semaine"],
  ["ideas", "Idées"],
  ["production", "Production"],
  ["published", "Publiés"],
];

export const App = () => {
  // en ligne (Console sur le cloud), seuls Autopilote, Chaînes et Feuille de route sont utiles : les autres pilotent le PC
  const tabs = import.meta.env.VITE_CLOUD_REPO ? TABS.filter(([k]) => k === "auto" || k === "chaines" || k === "route") : TABS;
  const [tab, setTab] = useState<Tab>("auto");
  const [episodeId, setEpisodeId] = useState<string | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const jobs = useJobs();
  // vérifie le moteur toutes les 5 s : le bandeau disparaît tout seul dès qu'il répond
  const [reconnects, setReconnects] = useState(0);
  useEffect(() => {
    if (CLOUD_ONLY) return;
    let wasDown = false;
    const check = () =>
      api
        .health()
        .then((h) => {
          setMissing(Object.entries(h).filter(([, ok]) => !ok).map(([k]) => k));
          if (wasDown) setReconnects((n) => n + 1);
          wasDown = false;
        })
        .catch(() => {
          wasDown = true;
          setMissing([ONLINE ? "le moteur sur ton PC : lance « npm run api » dans section3-motion/pixel-faits (reconnexion automatique)" : "API (lance npm run console)"]);
        });
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);
  // bandeau de fin de lot (résumé), jusqu'à ce qu'on le ferme
  const [batch, setBatch] = useState<BatchStatus["summary"]>(null);
  const [seenBatch, setSeenBatch] = useState(() => {
    try {
      return localStorage.getItem("bdf-batch-seen") ?? "";
    } catch {
      return "";
    }
  });
  useEffect(() => {
    if (CLOUD_ONLY) return;
    api.batch().then((b) => setBatch(b.summary), () => {});
  }, [jobs.version]);
  const closeBatch = () => {
    if (!batch) return;
    setSeenBatch(batch.finishedAt);
    try {
      localStorage.setItem("bdf-batch-seen", batch.finishedAt);
    } catch {
      // stockage indisponible : le bandeau reviendra au prochain chargement
    }
  };
  const openEpisode = (id: string) => {
    setEpisodeId(id);
    setTab("production");
  };
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">LA DÉBROUILLE</span>
        {tabs.map(([k, label]) => (
          <button key={k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
        <JobTray active={jobs.active} toast={jobs.toast} />
        {episodeId && <span className="ep">Épisode : {episodeId}</span>}
      </header>
      {missing.length > 0 && tab !== "auto" && tab !== "chaines" && tab !== "route" && <div className="banner">Outils introuvables : {missing.join(", ")}. Les tâches qui en ont besoin échoueront.</div>}
      {batch && batch.finishedAt !== seenBatch && (
        <div className={`banner ${batch.errors.length ? "" : "good"}`}>
          Lot terminé : {batch.text}
          {batch.errors.map((e) => (
            <span key={e.id} className="small"> · {e.id} : {e.error}</span>
          ))}
          <button className="close" onClick={closeBatch} aria-label="Fermer">
            ×
          </button>
        </div>
      )}
      {tab === "auto" && <Autopilote />}
      {tab === "chaines" && <Chaines />}
      {tab === "route" && <Route />}
      {tab === "week" && <Week key={reconnects} openEpisode={openEpisode} version={jobs.version} />}
      {tab === "ideas" && <Ideas key={reconnects} openEpisode={openEpisode} version={jobs.version} />}
      {tab === "production" && <Production key={reconnects} episodeId={episodeId} jobs={jobs} />}
      {tab === "published" && <Published key={reconnects} openEpisode={openEpisode} version={jobs.version} />}
    </div>
  );
};
