import { useEffect, useState } from "react";
import { api, fileUrl } from "../api";
import { STEP_KEYS, type Episode } from "../../server/types";
import { PixelCover } from "./Ideas";

const doneCount = (e: Episode) => STEP_KEYS.filter((k) => e.steps[k] === "done").length;

export const Published = ({ openEpisode, version }: { openEpisode: (id: string) => void; version: number }) => {
  const [eps, setEps] = useState<Episode[]>([]);
  useEffect(() => {
    api.episodes().then(setEps);
  }, [version]);
  return (
    <main className="published">
      {eps.length === 0 && <p className="muted">Aucun épisode pour l'instant : choisis une idée dans l'onglet Idées.</p>}
      {eps.map((e) => {
        const rerender = e.steps.render === "running" && e.metrics !== null;
        const ready = e.steps.render === "done" || rerender;
        return (
          <button key={e.id} className="pub card" onClick={() => openEpisode(e.id)}>
            {ready ? <img className="phone" src={fileUrl(`${e.id}/cover.png`)} alt={`Couverture de l'épisode ${e.number}`} /> : <PixelCover hook={e.title} />}
            <span className="pub-info">
              <b>
                N°{String(e.number).padStart(2, "0")} · {e.title}
              </b>
              <span className="muted">
                {rerender ? "nouveau rendu en cours…" : ready ? "prêt · vidéo, couverture et texte" : `en production · étape ${Math.min(9, doneCount(e) + 1)} sur 9`}
              </span>
            </span>
          </button>
        );
      })}
    </main>
  );
};
