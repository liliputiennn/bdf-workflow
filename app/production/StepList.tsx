import { STEP_KEYS, type Episode, type StepKey, type StepState } from "../../server/types";

export const STEP_LABELS: Record<StepKey, [string, string]> = {
  facts: ["Faits & sources", "2 sources par chiffre"],
  script: ["Script", "brief de la semaine (Claude)"],
  voiceText: ["Texte voix", "à coller dans ElevenLabs"],
  voice: ["Voix", "dépose tes prises MP3"],
  align: ["Calage au mot", "Whisper"],
  scenes: ["Scènes", "scenes.json ou épisode codé"],
  preview: ["Aperçu", "le rendu exact"],
  render: ["Rendu & mixage", "voix prioritaire"],
  publish: ["Publication", "couverture + texte"],
};

/** L'étape Scènes se déduit du registre (composition codée ou non). */
export const stateOf = (ep: Episode, k: StepKey, scenesReady: boolean): StepState => (k === "scenes" ? (scenesReady ? "done" : "todo") : ep.steps[k]);

const NEXT: Record<StepKey, string> = {
  facts: "Compléter les sources dans l'onglet Idées",
  script: "Préparer la semaine : un seul brief pour Claude (onglet Semaine)",
  voiceText: "Préparer le texte voix avec Claude",
  voice: "Générer la voix sur ElevenLabs puis la déposer ici",
  align: "Lancer le calage (automatique avec le pilote)",
  scenes: "Importer la semaine (onglet Semaine) ou coder un épisode signature",
  preview: "Regarder l'aperçu",
  render: "Lancer le rendu final (automatique avec le pilote)",
  publish: "Copier le texte et publier sur TikTok",
};

export const StepList = ({
  ep,
  scenesReady,
  current,
  onSelect,
  onAutopilot,
}: {
  ep: Episode;
  scenesReady: boolean;
  current: StepKey;
  onSelect: (k: StepKey) => void;
  onAutopilot: (on: boolean) => void;
}) => {
  const next = STEP_KEYS.find((k) => stateOf(ep, k, scenesReady) !== "done");
  return (
  <nav className="steps" aria-label="Étapes de production">
    <button className={`card next ${next ? "" : "done"}`} onClick={() => next && onSelect(next)}>
      <small>Prochaine étape</small>
      <b>{next ? NEXT[next] : "Épisode terminé : prêt à publier"}</b>
    </button>
    <label className="autopilot">
      <input type="checkbox" checked={ep.autopilot !== false} onChange={(e) => onAutopilot(e.target.checked)} />
      <span>
        Pilote automatique
        <small>voix déposée → meilleure prise → calage → rendu, sans clic</small>
      </span>
    </label>
    {STEP_KEYS.map((k, i) => {
      const st = stateOf(ep, k, scenesReady);
      return (
        <button key={k} className={`step ${st} ${current === k ? "now" : ""}`} onClick={() => onSelect(k)}>
          <i>{st === "done" ? "✓" : st === "error" ? "!" : i + 1}</i>
          <span>
            {STEP_LABELS[k][0]}
            <small>{st === "running" ? "en cours…" : st === "error" ? "erreur : voir le panneau" : STEP_LABELS[k][1]}</small>
          </span>
        </button>
      );
    })}
  </nav>
  );
};
