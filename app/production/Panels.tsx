import { useEffect, useState } from "react";
import { api, fileUrl, type EpisodeDetail } from "../api";
import type { JobView, StepKey } from "../../server/types";

const mmss = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000));
  return s >= 60 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s` : `${s} s`;
};

/** Temps restant estimé d'après l'avancement réel : écoulé × (reste / fait). */
export const eta = (job: JobView, now: number) => {
  if (job.startedAt == null) return "en attente…";
  const elapsed = now - job.startedAt;
  const p = job.progress ?? 0;
  if (p < 0.03 || elapsed < 4000) return `calcul du temps restant… (${mmss(elapsed)} écoulées)`;
  return `≈ ${mmss((elapsed * (1 - p)) / p)} restantes · ${Math.round(p * 100)} %`;
};

const Progress = ({ job }: { job: JobView | undefined }) => {
  const [now, setNow] = useState(Date.now());
  const active = !!job && (job.status === "running" || job.status === "queued");
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  if (!job || !active) return null;
  return (
    <div className="card pad">
      <p style={{ margin: "0 0 8px" }}>{job.status === "queued" ? "En attente…" : job.label}</p>
      <div className="bar">
        <div style={{ width: `${Math.round((job.progress ?? 0.04) * 100)}%` }} />
      </div>
      <p className="muted small" style={{ margin: "8px 0 0" }}>{eta(job, now)}</p>
    </div>
  );
};

const ErrorBox = ({ ep, step, onRetry }: { ep: EpisodeDetail; step: StepKey; onRetry: () => void }) =>
  ep.error?.step === step ? (
    <div className="card pad err">
      <p style={{ margin: 0 }}>La tâche a échoué. Voici la fin du journal :</p>
      <pre>{ep.error.log}</pre>
      <button className="btn ghost" onClick={onRetry}>
        Relancer
      </button>
    </div>
  ) : null;

const copy = (text: string, done: (v: string) => void) =>
  navigator.clipboard.writeText(text).then(
    () => done("Copié dans le presse-papiers."),
    () => done("Copie impossible : sélectionne le texte à la main."),
  );

type Props = { step: StepKey; ep: EpisodeDetail; job: JobView | undefined; scenesReady: boolean; reload: () => void };

export const Panel = ({ step, ep, job, scenesReady, reload }: Props) => {
  const [msg, setMsg] = useState("");
  const [mix, setMix] = useState(ep.mix);
  const [over, setOver] = useState(false);
  const run = (kind: "compare" | "align" | "render") =>
    api
      .runJob(ep.id, kind)
      .then(reload)
      .catch((e) => setMsg(e.message));
  const busy = job?.status === "running" || job?.status === "queued";
  const upload = (files: File[]) => {
    setMsg("");
    api.uploadTakes(ep.id, files).then(reload, (er) => setMsg(er.message));
  };

  if (step === "facts")
    return (
      <div className="panel">
        <h3>Faits & sources</h3>
        <div className="card pad">Les faits, leurs sources et les points contestés sont dans l'onglet Idées. Seuls les faits vérifiés dans au moins 2 sources vont dans le script.</div>
      </div>
    );

  if (step === "script")
    return (
      <div className="panel">
        <h3>Script</h3>
        <div className="card pad">
          Le script ({ep.scriptFile}) s'écrit avec Claude : des phrases courtes, des mots simples qu'un enfant comprend, chaque chiffre relié à un fait sourcé.
        </div>
      </div>
    );

  if (step === "voiceText")
    return (
      <div className="panel">
        <h3>Texte voix</h3>
        <div className="card pad">
          Sur elevenlabs.io : voix <b>Nicolas – Narrator</b>, modèle <b>Multilingual v2</b>. Stabilité ~40 %, similarité ~80 %, style ~25 %. Pas de balises d'émotion,
          ou 2 au maximum.
        </div>
        <pre className="card pad text">{ep.texts.voiceText || "Le texte voix n'est pas encore écrit (il se prépare avec Claude, avec le script)."}</pre>
        <button className="btn" disabled={!ep.texts.voiceText} onClick={() => copy(ep.texts.voiceText, setMsg)}>
          Copier le texte
        </button>
        {msg && <p className="muted small">{msg}</p>}
      </div>
    );

  if (step === "voice")
    return (
      <div className="panel">
        <h3>Voix</h3>
        <label
          className={`drop ${over ? "over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            upload([...e.dataTransfer.files]);
          }}
        >
          Glisse tes prises MP3 ici
          <br />
          <span className="small">ou clique pour les choisir · je garde la meilleure</span>
          <input type="file" accept=".mp3,audio/mpeg" multiple hidden onChange={(e) => upload([...(e.target.files ?? [])])} />
        </label>
        <Progress job={job?.kind === "compare" ? job : undefined} />
        {ep.voice.takes.map((t) => {
          const s = ep.voice.scores[t];
          return (
            <button key={t} className={`card take ${ep.voice.chosen === t ? "on" : ""}`} onClick={() => api.chooseTake(ep.id, t).then(reload)}>
              <b>{t}</b>
              <span className="muted small">{s ? `compris à ${s.similarity} % · ${s.pauses} respirations` : "pas encore écoutée"}</span>
              {ep.voice.chosen === t && <span className="tag">retenue</span>}
            </button>
          );
        })}
        <ErrorBox ep={ep} step="voice" onRetry={() => run("compare")} />
        {msg && <p className="warn">{msg}</p>}
      </div>
    );

  if (step === "align")
    return (
      <div className="panel">
        <h3>Calage au mot</h3>
        <div className="card pad">Whisper écoute la prise retenue ({ep.voice.chosen ?? "aucune"}) et repère chaque mot pour caler les sous-titres, les scènes et les sons.</div>
        <Progress job={job?.kind === "align" ? job : undefined} />
        <button className="btn" disabled={!ep.voice.chosen || busy} onClick={() => run("align")}>
          {ep.steps.align === "done" ? "Recaler" : "Lancer le calage"}
        </button>
        <ErrorBox ep={ep} step="align" onRetry={() => run("align")} />
        {msg && <p className="warn">{msg}</p>}
      </div>
    );

  if (step === "scenes") {
    const brief = `Épisode ${ep.number} « ${ep.title} » (id ${ep.id}, compte ${ep.channel}). Code ses scènes pixel art dans section3-motion/pixel-faits sur le modèle de l'épisode 01 (src/px/mcoScenes.ts, src/episodes/Mco.tsx), avec le script ${ep.scriptFile} et les timings ${ep.timingsFile}, puis inscris-le dans src/episodes/registry.ts (composition ${ep.compositionId}, couverture ${ep.coverId}). Respecte le prompt maître section3-motion/PROMPT-MAITRE-PIXEL-FAITS.md.`;
    return (
      <div className="panel">
        <h3>Scènes</h3>
        {scenesReady ? (
          <div className="card pad">Les scènes sont codées et inscrites au registre ({ep.compositionId}).</div>
        ) : (
          <>
            <div className="card pad">Les scènes se codent avec Claude. Copie ce brief et colle-le dans une session.</div>
            <pre className="card pad text">{brief}</pre>
            <button className="btn" onClick={() => copy(brief, setMsg)}>
              Copier le brief pour Claude
            </button>
          </>
        )}
        {msg && <p className="muted small">{msg}</p>}
      </div>
    );
  }

  if (step === "preview")
    return (
      <div className="panel">
        <h3>Aperçu</h3>
        <div className="card pad">Au centre, c'est exactement la vidéo finale : mêmes scènes, même voix, mêmes sons. Regarde-la en entier avant le rendu.</div>
      </div>
    );

  if (step === "render") {
    const m = ep.metrics;
    const save = (next: typeof mix) => {
      setMix(next);
      api.setMix(ep.id, next).then(reload);
    };
    return (
      <div className="panel">
        <h3>Rendu & mixage</h3>
        {(["music", "sfx"] as const).map((k) => (
          <label key={k} className="vol">
            {k === "music" ? "Musique" : "SFX"}
            <input type="range" min={0} max={2} step={0.05} value={mix[k]} onChange={(e) => save({ ...mix, [k]: Number(e.target.value) })} />
            <span>{Math.round(mix[k] * 100)} %</span>
          </label>
        ))}
        <p className="muted small" style={{ margin: 0 }}>
          La voix reste toujours prioritaire : la musique et les SFX baissent tout seuls dès qu'elle parle.
        </p>
        {m && (
          <div className="card pad">
            Clarté de la voix : écart <b className={m.medianDb >= 25 ? "ok" : "ko"}>{m.medianDb} dB</b> au-dessus du fond · Whisper comprend{" "}
            <b className={m.whisper >= 90 ? "ok" : "ko"}>{m.whisper} %</b>
          </div>
        )}
        <Progress job={job?.kind === "render" ? job : undefined} />
        <button className="btn" disabled={!scenesReady || ep.steps.align !== "done" || busy} onClick={() => run("render")}>
          Lancer le rendu final
        </button>
        {!scenesReady && <p className="muted small">Disponible une fois les scènes codées.</p>}
        <ErrorBox ep={ep} step="render" onRetry={() => run("render")} />
        {msg && <p className="warn">{msg}</p>}
      </div>
    );
  }

  return (
    <div className="panel">
      <h3>Publication</h3>
      {ep.steps.render === "done" ? (
        <>
          <video className="final" src={fileUrl(`${ep.id}/${ep.id}.mp4?v=${ep.metrics?.whisper ?? 0}`)} poster={fileUrl(`${ep.id}/cover.png?v=${ep.metrics?.whisper ?? 0}`)} controls preload="metadata" />
          <a className="btn ghost" href={fileUrl(`${ep.id}/${ep.id}.mp4`)} download={`${ep.id}.mp4`}>
            Télécharger la vidéo
          </a>
          <img className="phone cover" src={fileUrl(`${ep.id}/cover.png?v=${ep.metrics?.whisper ?? 0}`)} alt="Couverture de l'épisode" />
          <pre className="card pad text">{ep.texts.post || "Le texte du post n'est pas encore écrit (POST.md)."}</pre>
          <button className="btn" disabled={!ep.texts.post} onClick={() => copy(ep.texts.post, setMsg)}>
            Copier le texte du post
          </button>
          <button className="btn ghost" onClick={() => api.openFolder(ep.id)}>
            Ouvrir le dossier de la vidéo
          </button>
        </>
      ) : (
        <p className="muted">Disponible après le rendu final.</p>
      )}
      {msg && <p className="muted small">{msg}</p>}
    </div>
  );
};
