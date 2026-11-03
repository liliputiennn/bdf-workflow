import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, type BatchStatus, type ImportResult, type IdeaRow, type Week as WeekT } from "../api";
import type { Episode, StepState } from "../../server/types";

/**
 * Vue « Semaine » : 7 vidéos, une par jour. Pour chacune, l'état de chaque étape et qui doit agir :
 * moi (sujet, voix, publication), Claude (le script, via UN brief pour toute la semaine) ou automatique.
 * À droite, les étapes de la semaine dans l'ordre, la prochaine mise en avant.
 */

type Who = "moi" | "claude" | "auto";
type Stage = { label: string; who: Who; state: StepState };
type Slot = WeekT["slots"][number];
const WHO: Record<Who, string> = { moi: "à faire par moi", claude: "à faire par Claude", auto: "automatique" };
const STAGES = ["Sujet", "Script", "Voix", "Calage", "Rendu", "Paquet", "Publié"];

const DAYS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];
const dateOf = (start: string, i: number) => {
  const d = new Date(`${start}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + i);
  return d;
};
const iso = (d: Date) => d.toISOString().slice(0, 10);
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const stagesOf = (slot: Slot, ep: Episode | undefined): Stage[] => {
  const s = (b: boolean): StepState => (b ? "done" : "todo");
  return [
    { label: "Sujet", who: "moi", state: s(!!(slot.idea || slot.subject || ep)) },
    { label: "Script", who: "claude", state: s(ep?.steps.script === "done") },
    { label: "Voix", who: "moi", state: ep ? (ep.voice.chosen ? "done" : ep.steps.voice === "running" ? "running" : ep.steps.voice === "error" ? "error" : "todo") : "todo" },
    { label: "Calage", who: "auto", state: ep?.steps.align ?? "todo" },
    { label: "Rendu", who: "auto", state: ep?.steps.render ?? "todo" },
    { label: "Paquet", who: "auto", state: s(!!ep?.package) },
    { label: "Publié", who: "moi", state: s(!!ep?.publishedAt) },
  ];
};

const isMp3 = (f: File) => /\.mp3$/i.test(f.name);

export const Week = ({ openEpisode, version }: { openEpisode: (id: string) => void; version: number }) => {
  const [week, setWeek] = useState<WeekT | null>(null);
  const [eps, setEps] = useState<Episode[]>([]);
  const [ideas, setIdeas] = useState<IdeaRow[]>([]);
  const [brief, setBrief] = useState("");
  const [reply, setReply] = useState("");
  const [bulk, setBulk] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const [offline, setOffline] = useState(false);
  const [sugg, setSugg] = useState<{ titre: string; theme: string; angle: string }[]>([]);
  const [suggTheme, setSuggTheme] = useState("");

  const load = useCallback(() => {
    const off = () => setOffline(true);
    api.week().then((w) => (setWeek(w), setOffline(false)), off);
    api.episodes().then(setEps, off);
    api.ideas().then(setIdeas, off);
    api.batch().then(setBatch, off);
    api.suggestions().then(setSugg, () => {});
  }, []);
  useEffect(load, [load, version]);

  const flash = (text: string, ok = true) => {
    setMsg({ ok, text });
    setTimeout(() => setMsg(null), 3500);
  };
  const fail = (e: Error) => flash(e.message, false);
  const save = (w: WeekT, previousStart?: string) => {
    setWeek(w);
    setBrief("");
    api.saveWeek(w, previousStart).catch(fail);
  };
  if (!week)
    return (
      <main className="week">
        {offline ? (
          <section className="card pad week-offline">
            <h2>Le moteur de ton PC ne répond pas</h2>
            <p>
              Lance <code>npm run console</code> (ou <code>npm run api</code>) dans <code>section3-motion/pixel-faits</code> : la page se reconnecte toute seule.
            </p>
          </section>
        ) : (
          <p className="muted">Chargement…</p>
        )}
      </main>
    );

  const byId = new Map(eps.map((e) => [e.id, e]));
  const free = ideas.filter((i) => i.status === "idea");
  const bySlug = new Map(ideas.map((i) => [i.slug, i]));
  const now = today();
  const rows = week.slots.map((slot, i) => {
    const ep = slot.episode ? byId.get(slot.episode) : undefined;
    const stages = stagesOf(slot, ep);
    return { slot, i, ep, stages, next: stages.find((st) => st.state !== "done"), date: iso(dateOf(week.start, i)) };
  });
  const emptySlots = rows.filter((r) => r.stages[0].state !== "done").length;
  const forClaude = rows.filter((r) => r.stages[1].state !== "done").length;
  const needVoice = rows.filter((r) => r.ep && r.stages[1].state === "done" && r.stages[2].state !== "done").length;
  const toRender = rows.filter((r) => r.ep?.voice.chosen && r.ep.steps.render !== "done").length;
  const toPublish = rows.filter((r) => r.ep?.package && !r.ep.publishedAt).length;
  // la prochaine étape de la semaine, mise en avant à droite
  const focus = emptySlots ? "subjects" : forClaude ? (brief || reply ? "import" : "brief") : needVoice ? "voice" : toRender ? "render" : toPublish ? "publish" : "done";

  const setSlot = (i: number, patch: Slot) => save({ ...week, slots: week.slots.map((s, k) => (k === i ? patch : s)) });
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= week.slots.length) return;
    const slots = [...week.slots];
    [slots[i], slots[j]] = [slots[j], slots[i]];
    save({ ...week, slots });
  };
  /** Une seule case : un titre de la banque d'idées devient l'idée, sinon c'est un sujet libre. */
  const pickSubject = (i: number, text: string) => {
    const t = text.trim();
    const idea = free.find((f) => f.hook === t || f.slug === t);
    setSlot(i, idea ? { idea: idea.slug } : t ? { subject: t } : {});
  };
  const fillFromBulk = () => {
    const lines = bulk.split("\n").map((l) => l.trim()).filter(Boolean);
    let k = 0;
    const slots = week.slots.map((s) => (s.idea || s.subject || s.episode || k >= lines.length ? s : { subject: lines[k++] }));
    save({ ...week, slots });
    setBulk("");
    flash(`${k} jour${k > 1 ? "s" : ""} rempli${k > 1 ? "s" : ""}`);
  };
  const used = new Set(week.slots.map((s) => s.subject).filter(Boolean));
  const themes = [...new Set(sugg.map((s) => s.theme))];
  const theme = suggTheme || themes[0];
  const addSuggestion = (titre: string) => {
    const i = week.slots.findIndex((s) => !s.idea && !s.subject && !s.episode);
    if (i < 0) return flash("les 7 jours sont déjà remplis", false);
    setSlot(i, { subject: titre });
  };
  const copy = (text: string, what: string) => navigator.clipboard.writeText(text).then(() => flash(`${what} copié`), () => flash("copie refusée par le navigateur", false));
  const upload = (ep: Episode, files: File[]) => {
    const mp3 = files.filter(isMp3);
    if (!mp3.length) return flash("dépose des fichiers MP3", false);
    flash(`${mp3.length} prise${mp3.length > 1 ? "s" : ""} envoyée${mp3.length > 1 ? "s" : ""} : écoute en cours…`);
    api.uploadTakes(ep.id, mp3).then(load, fail);
  };
  const subjectText = (slot: Slot) => (slot.idea ? (bySlug.get(slot.idea)?.hook ?? slot.idea) : (slot.subject ?? ""));

  const Step = ({ id, n, title, children, hint }: { id: string; n: number; title: string; hint?: string; children?: ReactNode }) => (
    <section className={`card wstep ${focus === id ? "focus" : ""}`}>
      <h2>
        <i>{n}</i> {title}
        {focus === id && <span className="tag">maintenant</span>}
      </h2>
      {hint && <p className="muted small">{hint}</p>}
      {children}
    </section>
  );

  return (
    <main className="week">
      <header className="week-head">
        <h1>Semaine du</h1>
        <input type="date" value={week.start} onChange={(e) => e.target.value && save({ ...week, start: e.target.value }, week.start)} aria-label="Premier jour de la semaine" />
        <span className={`who-count ${forClaude ? "claude" : "done"}`}>{forClaude ? `Claude : ${forClaude} vidéo${forClaude > 1 ? "s" : ""} à écrire → 1 seul brief` : "Claude : rien à faire"}</span>
        <span className="who-count moi">
          Moi : {emptySlots ? `${emptySlots} sujet${emptySlots > 1 ? "s" : ""} · ` : ""}
          {needVoice} voix · {toPublish} à publier
        </span>
        <button
          className="btn ghost sm"
          onClick={() => {
            if (window.confirm("Vider les jours dont la voix n'est pas encore faite ? Les épisodes restent dans Production.")) save({ ...week, slots: week.slots.map((s) => (s.episode && byId.get(s.episode)?.voice.chosen ? s : {})) });
          }}
        >
          Recommencer la semaine
        </button>
        {msg && <span className={`flash ${msg.ok ? "ok" : "ko"}`}>{msg.text}</span>}
      </header>

      <div className="week-main">
        <section className="card week-table" aria-label="Planning de la semaine">
          <div className="wrow whead">
            <span>Jour</span>
            <span>Sujet</span>
            <span className="stages">
              {STAGES.map((s) => (
                <b key={s}>{s}</b>
              ))}
            </span>
            <span>Action</span>
          </div>
          {rows.map(({ slot, i, ep, stages, next, date }) => {
            const voiceTurn = !!ep && stages[1].state === "done" && stages[2].state !== "done";
            return (
              <div
                key={i}
                className={`wrow ${date === now ? "today" : ""} ${over === i ? "over" : ""}`}
                onDragOver={(e) => {
                  if (!ep) return;
                  e.preventDefault();
                  setOver(i);
                }}
                onDragLeave={() => setOver(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  setOver(null);
                  if (ep) upload(ep, [...e.dataTransfer.files]);
                }}
              >
                <span className="day">
                  <span className="move">
                    <button className="arrow" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Avancer d'un jour">
                      ▲
                    </button>
                    <button className="arrow" onClick={() => move(i, 1)} disabled={i === week.slots.length - 1} aria-label="Reculer d'un jour">
                      ▼
                    </button>
                  </span>
                  <span>
                    {DAYS[dateOf(week.start, i).getUTCDay()]}
                    <b>
                      {date.slice(8, 10)}/{date.slice(5, 7)}
                    </b>
                    {date === now && <small>aujourd'hui</small>}
                  </span>
                </span>
                <span className="subject">
                  {ep ? (
                    <button className="link" onClick={() => openEpisode(ep.id)} title="Ouvrir dans Production">
                      <small>N°{String(ep.number).padStart(2, "0")}</small> {ep.title}
                    </button>
                  ) : (
                    <input
                      key={`${week.start}-${i}-${subjectText(slot)}`}
                      list="week-ideas"
                      placeholder="Un sujet, ou choisis dans la banque d'idées"
                      defaultValue={subjectText(slot)}
                      onBlur={(e) => e.target.value.trim() !== subjectText(slot) && pickSubject(i, e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                      aria-label={`Sujet du ${DAYS[dateOf(week.start, i).getUTCDay()]} ${date.slice(8, 10)}`}
                    />
                  )}
                  {slot.idea && !ep && <small className="muted">banque d'idées · faits déjà sourcés</small>}
                </span>
                <span className="stages">
                  {stages.map((s) => (
                    <i key={s.label} className={`pill ${s.state} ${s.who}`} title={`${s.label} : ${s.state === "done" ? "fait" : WHO[s.who]}`}>
                      {s.state === "done" ? "✓" : s.state === "error" ? "!" : s.state === "running" ? "…" : ""}
                    </i>
                  ))}
                </span>
                <span className="acts">
                  {ep && !ep.voice.chosen && (
                    <button className="arrow" title="Retirer ce sujet de la semaine (l'épisode reste dans Production)" aria-label="Retirer ce sujet" onClick={() => setSlot(i, {})}>
                      ✕
                    </button>
                  )}
                  {voiceTurn && (
                    <>
                      <button className="btn ghost sm" onClick={() => api.episode(ep.id).then((d) => copy(d.texts.voiceText, "Texte voix"))} title="À coller dans ElevenLabs">
                        Texte voix
                      </button>
                      <label className="btn sm file">
                        Déposer MP3
                        <input type="file" accept=".mp3,audio/mpeg" multiple onChange={(e) => upload(ep, [...(e.target.files ?? [])])} hidden />
                      </label>
                    </>
                  )}
                  {ep?.package && (
                    <>
                      <button className="btn ghost sm" onClick={() => api.episode(ep.id).then((d) => copy(d.texts.publication, "Texte de publication"))}>
                        Copier le texte
                      </button>
                      <button className="btn ghost sm" onClick={() => api.openFolder(ep.id, "package").catch(fail)}>
                        Dossier
                      </button>
                      <label className={`pubcheck ${ep.publishedAt ? "on" : ""}`}>
                        <input type="checkbox" checked={!!ep.publishedAt} onChange={(e) => api.setPublished(ep.id, e.target.checked).then(load, fail)} />
                        {ep.publishedAt ? `publié ${ep.publishedAt.slice(8, 10)}/${ep.publishedAt.slice(5, 7)}` : "publié"}
                      </label>
                    </>
                  )}
                  {ep?.steps.render === "done" && !ep.package && (
                    <button className="btn ghost sm" onClick={() => api.buildPackage(ep.id).then(load, fail)}>
                      Préparer le paquet
                    </button>
                  )}
                  {!voiceTurn && !ep?.package && !(ep?.steps.render === "done") && next && (
                    <span className="wnext">
                      <em className={`who ${next.who}`}>{next.who === "moi" ? "Moi" : next.who === "claude" ? "Claude" : "Auto"}</em> {next.label.toLowerCase()}
                    </span>
                  )}
                </span>
              </div>
            );
          })}
          <p className="legend muted small">
            <em className="who moi">Moi</em> sujet, voix, publication · <em className="who claude">Claude</em> script, textes, scènes · <em className="who auto">Auto</em> calage, rendu, paquet ·
            Glisse les MP3 d'ElevenLabs directement sur la ligne du jour.
          </p>
          <datalist id="week-ideas">
            {free.map((f) => (
              <option key={f.slug} value={f.hook} />
            ))}
          </datalist>
        </section>

        <aside className="week-side">
          <Step id="subjects" n={1} title="Choisir les 7 sujets" hint="Une case par jour, ou colle une liste (un sujet par ligne) pour remplir les jours vides.">
            {sugg.length > 0 && (
              <div className="sugg">
                <div className="row">
                  {themes.map((t) => (
                    <button key={t} className={`chip ${t === theme ? "on" : ""}`} onClick={() => setSuggTheme(t)}>
                      {t}
                    </button>
                  ))}
                </div>
                <div className="sugg-list">
                  {sugg
                    .filter((s) => s.theme === theme && !used.has(s.titre))
                    .map((s) => (
                      <button key={s.titre} className="sugg-item" onClick={() => addSuggestion(s.titre)} title={`Angle : ${s.angle}`}>
                        + {s.titre}
                      </button>
                    ))}
                </div>
              </div>
            )}
            {emptySlots > 0 && (
              <>
                <textarea rows={3} placeholder={"Pourquoi IKEA vend des hot-dogs\nComment une laverie gagne de l'argent\n…"} value={bulk} onChange={(e) => setBulk(e.target.value)} />
                <button className="btn ghost sm" disabled={!bulk.trim()} onClick={fillFromBulk}>
                  Remplir les {emptySlots} jour{emptySlots > 1 ? "s" : ""} vide{emptySlots > 1 ? "s" : ""}
                </button>
              </>
            )}
          </Step>

          <Step id="brief" n={2} title="Brief pour Claude" hint="Un seul message pour les 7 vidéos : script, texte voix, publication et scènes.">
            <div className="row">
              <button
                className="btn"
                onClick={() =>
                  api.brief().then((b) => {
                    setBrief(b.text);
                    copy(b.text, "Brief");
                  }, fail)
                }
              >
                {brief ? "Recopier le brief" : "Générer et copier le brief"}
              </button>
              {brief && <span className="muted small">~{Math.round(brief.length / 3.5).toLocaleString("fr-FR")} jetons</span>}
            </div>
            {brief && (
              <details>
                <summary className="small muted">Voir le brief</summary>
                <textarea className="mono" readOnly value={brief} rows={8} />
              </details>
            )}
          </Step>

          <Step id="import" n={3} title="Importer la réponse" hint="Colle toute la réponse de Claude. Rien n'est créé tant qu'une erreur reste.">
            <textarea className="mono" placeholder="Colle ici la réponse de Claude (le bloc ```json)" value={reply} onChange={(e) => setReply(e.target.value)} rows={4} />
            <button
              className="btn"
              disabled={!reply.trim()}
              onClick={() =>
                api.importWeek(reply).then((r) => {
                  setResult(r);
                  if (r.ok) {
                    setReply("");
                    load();
                  }
                }, fail)
              }
            >
              Vérifier et créer les épisodes
            </button>
            {result && (
              <div className="import-result">
                {result.ok ? (
                  <p className="ok">✓ {result.created.length} épisodes prêts pour la voix</p>
                ) : (
                  <p className="ko">
                    {result.errors.length} point{result.errors.length > 1 ? "s" : ""} à corriger :
                  </p>
                )}
                {result.errors.length > 0 && (
                  <ul className="errs">
                    {result.errors.map((e, k) => (
                      <li key={k}>{e}</li>
                    ))}
                  </ul>
                )}
                {result.warnings.length > 0 && (
                  <ul className="warns">
                    {result.warnings.map((w, k) => (
                      <li key={k}>{w}</li>
                    ))}
                  </ul>
                )}
                {!result.ok && (
                  <button className="btn ghost sm" onClick={() => copy(`Corrige uniquement ces points et renvoie le JSON complet :\n${result.errors.join("\n")}`, "Message de correction")}>
                    Copier la correction pour Claude
                  </button>
                )}
              </div>
            )}
          </Step>

          <Step id="voice" n={4} title="Voix (ElevenLabs)" hint="Pour chaque jour : « Texte voix » → ElevenLabs (Nicolas – Narrator) → glisse les MP3 sur la ligne.">
            {needVoice > 0 ? <p className="small">{needVoice} voix à faire</p> : null}
          </Step>

          <Step id="render" n={5} title="Rendre la semaine" hint="Calage, rendu et paquet de chaque vidéo qui a sa voix. Notification à la fin.">
            <div className="row">
              <button className="btn" disabled={batch?.running || toRender === 0} onClick={() => api.startBatch().then((r) => (flash(`${r.queued.length} vidéo(s) en file`), load()), fail)}>
                {batch?.running ? `En cours : ${batch.done}/${batch.total}` : `Rendre ${toRender || ""} vidéo${toRender > 1 ? "s" : ""}`.replace("  ", " ")}
              </button>
            </div>
            {batch?.running && (
              <div className="bar">
                <div style={{ width: `${(batch.done / Math.max(1, batch.total)) * 100}%` }} />
              </div>
            )}
            {batch?.summary && !batch.running && <p className={`small ${batch.summary.errors.length ? "ko" : "ok"}`}>Dernier lot : {batch.summary.text}</p>}
          </Step>

          <Step id="publish" n={6} title="Publier (10 min/jour)" hint="Sur la ligne du jour : copier le texte, ouvrir le dossier, publier dans l'appli, cocher « publié ».">
            {focus === "done" && <p className="ok small">Semaine terminée.</p>}
          </Step>
        </aside>
      </div>
    </main>
  );
};
