import { useCallback, useEffect, useRef, useState } from "react";
import type { Snapshot } from "../server/autopilot";
import { API_BASE } from "./config";

/** Même source que l'écran Autopilote : l'API du PC en local, un fichier JSON statique (instantané) ou le dépôt GitHub public en ligne. */
const SNAPSHOT_URL: string = import.meta.env.VITE_SNAPSHOT_URL ?? "";
const CLOUD_REPO: string = import.meta.env.VITE_CLOUD_REPO ?? "";
export const STATIQUE = SNAPSHOT_URL !== "" || CLOUD_REPO !== "";
const url = () => (CLOUD_REPO ? `https://raw.githubusercontent.com/${CLOUD_REPO}/main/live/snapshot.json?t=${Math.floor(Date.now() / 60000)}` : STATIQUE ? SNAPSHOT_URL : `${API_BASE}/api/autopilot/snapshot`);

/** Lit l'état du workflow toutes les 4 s (en direct) ou toutes les minutes (instantané en ligne). */
export const useSnapshot = () => {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  const run = useCallback(() => {
    fetch(url(), { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error ?? r.statusText);
        return r.json() as Promise<Snapshot>;
      })
      .then(
        (d) => {
          if (!alive.current) return;
          setData(d);
          setError(null);
        },
        (e: Error) => alive.current && setError(e.message),
      );
  }, []);
  useEffect(() => {
    alive.current = true;
    run();
    const id = setInterval(run, STATIQUE ? 60000 : 4000);
    return () => {
      alive.current = false;
      clearInterval(id);
    };
  }, [run]);
  return { data, error, reload: run };
};

/** Date courte en français : « 8 nov., 18:00 » (heure locale du navigateur), ou « jamais ». */
export const dateCourte = (iso: string | null | undefined) => {
  if (!iso) return "jamais";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return "jamais";
  return d.toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};
