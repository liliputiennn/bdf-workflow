import { useCallback, useEffect, useRef, useState } from "react";
import type { AutoEp, Etat, Snapshot } from "../../server/autopilot";
import { API_BASE } from "../config";
import { lireDate, planifier, formatHeure, formatReste, type FabEp } from "../chrono";
import { ChronoHero, SlotBadge, useNow } from "../FabChrono";

/** Version cloud : un fichier JSON statique (écrit par `npm run snapshot`) remplace l'API du PC. Lecture seule. */
const SNAPSHOT_URL: string = import.meta.env.VITE_SNAPSHOT_URL ?? "";
/** Dossier public des vidéos/miniatures en cloud (ex. stockage objet) ; vide = servies par l'API du PC. */
const MEDIA_BASE: string = import.meta.env.VITE_MEDIA_BASE ?? "";
/** Cloud : dépôt GitHub public (ex. liliputiennn/bdf-workflow). L'état vient de live/snapshot.json, les vidéos de la release « stock », l'avancement du workflow de l'API GitHub. */
const CLOUD_REPO: string = import.meta.env.VITE_CLOUD_REPO ?? "";
const CLOUD = CLOUD_REPO !== "";
const STATIC = SNAPSHOT_URL !== "" || CLOUD;
/** Moment fixé pour la session de rédaction avec ton Claude (texte affiché dans le message). */
const REDACTION_MOMENT: string = import.meta.env.VITE_REDACTION_MOMENT ?? "dimanche à 18 h";
const snapshotUrl = () => (CLOUD ? `https://raw.githubusercontent.com/${CLOUD_REPO}/main/live/snapshot.json?t=${Math.floor(Date.now() / 60000)}` : SNAPSHOT_URL);

type Live = Snapshot & { logTail?: { nom: string; lignes: string[] } | null };

const ETATS: [Etat, string][] = [
  ["ecrit", "Écrit"],
  ["voix", "Voix"],
  ["rendu", "Rendu"],
  ["controle", "Contrôle"],
  ["pret", "Prêt"],
  ["programme", "Programmé"],
  ["publie", "Publié"],
  ["quarantaine", "Quarantaine"],
];

const libelle = (e: Etat) => ETATS.find(([k]) => k === e)?.[1] ?? e;

const media = (id: string, kind: "miniature" | "video") =>
  CLOUD
    ? `https://github.com/${CLOUD_REPO}/releases/download/stock/exports__${id}__${kind === "video" ? `${id}.mp4` : "miniature.png"}`
    : MEDIA_BASE ? `${MEDIA_BASE}/${id}/${kind === "video" ? `${id}.mp4` : "miniature.png"}` : `${API_BASE}/api/autopilot/media/${id}/${kind}`;

const ago = (iso?: string | null) => {
  if (!iso) return "–";
  // dates sans fuseau = écrites par le cloud (UTC) ; sinon l'âge serait faussé d'une heure pour un visiteur à Paris
  const t = lireDate(iso, CLOUD);
  if (t == null) return "–";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  if (s < 172800) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} j`;
};
const dur = (s: number | null) => (s == null ? "" : s >= 90 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${Math.round(s)} s`);

const usePoll = <T,>(load: () => Promise<T>, every: number) => {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [at, setAt] = useState(0);
  const ref = useRef(load);
  ref.current = load;
  const run = useCallback(() => {
    ref.current().then(
      (d) => {
        setData(d);
        setError(null);
        setAt(Date.now());
      },
      (e: Error) => setError(e.message),
    );
  }, []);
  useEffect(() => {
    run();
    const id = setInterval(run, every);
    return () => clearInterval(id);
  }, [run, every]);
  return { data, error, at, reload: run };
};

const getJson = async <T,>(url: string): Promise<T> => {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error ?? r.statusText);
  return r.json() as Promise<T>;
};

type Run = { id: number; name?: string; status: string; conclusion: string | null; created_at: string; run_started_at?: string; html_url: string; event: string };
type Step = { name: string; status: string; conclusion: string | null; started_at: string | null; completed_at: string | null };

/** Dernière exécution du workflow « Fabrique » et ses étapes (API GitHub publique, sans compte : 60 requêtes/heure, donc un point toutes les 2 min). */
const useRuns = () =>
  usePoll<{ run: Run | null; steps: Step[] }>(async () => {
    if (!CLOUD) return { run: null, steps: [] };
    const r = await getJson<{ workflow_runs: (Run & { name: string })[] }>(`https://api.github.com/repos/${CLOUD_REPO}/actions/runs?per_page=8`);
    // une fabrication ou une publication en cours passe avant tout ; les essais de voix et instantanés sont ignorés
    const utiles = r.workflow_runs.filter((x) => x.name === "Fabrique" || x.name === "Publication");
    const run = utiles.find((x) => x.status !== "completed") ?? utiles[0] ?? r.workflow_runs[0] ?? null;
    if (!run || run.status === "completed") return { run, steps: [] };
    const j = await getJson<{ jobs: { steps: Step[] }[] }>(`https://api.github.com/repos/${CLOUD_REPO}/actions/runs/${run.id}/jobs`);
    return { run, steps: j.jobs[0]?.steps ?? [] };
  }, 120000);

const CONSIGNE_REDACTION =
  "Écris les prochains épisodes de la chaîne La Débrouille : ouvre le dossier section3-motion/pixel-faits, lis autopilot/writer/CONSIGNES.md, lance python autopilot/writer/stock.py besoin et écris tout ce qui manque. Quand tout est validé, envoie-le au cloud avec : powershell -File autopilot/cloud/envoyer_redaction.ps1";

/** Message clair : faut-il lancer la rédaction avec ton Claude ? */
const redactionMessage = (jours: number | undefined, rupture: string | undefined) => {
  if (jours == null) return null;
  if (jours <= 3) return { niveau: "bad", titre: "À faire maintenant : lance la rédaction avec ton Claude", texte: `Il ne reste que ${jours} jour(s) de vidéos${rupture ? ` (rupture le ${rupture})` : ""}. Sans nouveaux épisodes, la chaîne s'arrête.` };
  if (jours <= 7) return { niveau: "warn", titre: `À prévoir ${REDACTION_MOMENT} : session de rédaction avec ton Claude`, texte: `Stock : ${jours} jours${rupture ? `, rupture le ${rupture}` : ""}. Ne laisse pas passer la prochaine session.` };
  return { niveau: "ok", titre: "Rien à faire pour la rédaction", texte: `Stock suffisant${rupture ? ` jusqu'au ${rupture}` : ""}. Prochaine session conseillée : ${REDACTION_MOMENT}.` };
};

export const Autopilote = () => {
  const snap = usePoll<Live>(() => getJson(STATIC ? snapshotUrl() : `${API_BASE}/api/autopilot/snapshot`), STATIC ? 60000 : 4000);
  const runs = useRuns();
  const [filter, setFilter] = useState<Etat | null>(null);
  const [tout, setTout] = useState(false);
  const [logName, setLogName] = useState<string>("");
  const [player, setPlayer] = useState<AutoEp | null>(null);
  const [msg, setMsg] = useState<string>("");
  const s = snap.data;
  // l'horloge ne bat que s'il y a des vidéos en fabrication (écrit / voix / rendu)
  const enFab = (s?.episodes ?? []).filter((e) => e.etat === "ecrit" || e.etat === "voix" || e.etat === "rendu").length;
  const now = useNow(enFab > 0);
  const logs = s?.logs ?? [];
  useEffect(() => {
    if (!logName && logs[0]) setLogName(logs[0].nom);
  }, [logs, logName]);

  const log = usePoll<string[]>(async () => {
    if (STATIC) return s?.logTail?.lignes ?? [];
    if (!logName) return [];
    return (await getJson<{ lignes: string[] }>(`${API_BASE}/api/autopilot/log/${logName}?n=150`)).lignes;
  }, 3000);
  const logRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log.data]);
  useEffect(log.reload, [logName, s?.logTail, log.reload]);

  const act = async (id: string, action: "relancer" | "ecarter") => {
    if (action === "ecarter" && !confirm(`Écarter « ${id} » ? Il part en quarantaine et ne sera pas publié.`)) return;
    const r = await fetch(`${API_BASE}/api/autopilot/episodes/${id}/${action}`, { method: "POST", headers: { "x-console": "1" } });
    const b = (await r.json().catch(() => ({ message: r.statusText }))) as { message?: string; error?: string };
    setMsg(b.message ?? b.error ?? "");
    snap.reload();
  };

  if (!s) return <div className="ap"><p className="small">{snap.error ? `Impossible de lire l'état : ${snap.error}` : "Chargement…"}</p></div>;

  const enCours = runs.data?.run && runs.data.run.status !== "completed";
  const working = s.verrous.fabrique || s.verrous.gpu || !!enCours;
  // chrono : seule une exécution « Fabrique » compte (une publication en cours ne fabrique rien)
  const run = runs.data?.run;
  const fabEnCours = CLOUD ? !!enCours && (run?.name ? run.name === "Fabrique" : true) : s.verrous.fabrique || s.verrous.gpu;
  const departStep = runs.data?.steps.find((st) => st.name.startsWith("Fabrication") && st.started_at)?.started_at;
  const depart = CLOUD ? lireDate(departStep ?? run?.run_started_at ?? run?.created_at, false, now) : lireDate(s.verrous.depuis, false, now);
  const plan = planifier(s.episodes as FabEp[], { now, depart: fabEnCours ? depart : null, travail: fabEnCours, utc: CLOUD });
  const slotDe = new Map(plan.slots.map((x) => [x.id, x]));
  const counts = Object.fromEntries(ETATS.map(([k]) => [k, s.episodes.filter((e) => e.etat === k).length])) as Record<Etat, number>;
  // ordre d'affichage : prêts et programmés d'abord (ceux avec aperçu en tête), puis contrôle, écrits, publiés, quarantaine en dernier
  const RANG: Record<Etat, number> = { pret: 0, programme: 1, controle: 2, rendu: 3, voix: 4, ecrit: 5, publie: 6, quarantaine: 7 };
  const rang = (e: AutoEp) => (slotDe.has(e.id) ? -1 : RANG[e.etat]);
  const shown = s.episodes
    .filter((e) => !filter || e.etat === filter)
    .sort((a, b) => rang(a) - rang(b) || (slotDe.get(a.id)?.debut ?? 0) - (slotDe.get(b.id)?.debut ?? 0) || Number(b.video) - Number(a.video) || Number(b.long) - Number(a.long) || b.maj.localeCompare(a.maj));
  const stock = s.stock as { jours_de_stock?: number; date_rupture?: string; disque_libre_go?: number; disque_bas?: boolean; stock_bas?: boolean; youtube_auth_a_renouveler?: boolean; claude_bloque?: boolean; redaction_en_retard?: boolean } | null;
  const ytQueue = s.episodes.filter((e) => e.etat === "pret" || e.etat === "programme").sort((a, b) => (a.youtube.publie_a ?? "~").localeCompare(b.youtube.publie_a ?? "~"));
  const ttQueue = s.episodes.filter((e) => !e.long && ["pret", "programme", "publie"].includes(e.etat));
  const flags = [
    stock?.stock_bas && "stock bas",
    stock?.disque_bas && "disque presque plein",
    stock?.youtube_auth_a_renouveler && "connexion YouTube à renouveler",
    stock?.claude_bloque && "rédaction bloquée",
    stock?.redaction_en_retard && "rédaction en retard",
  ].filter(Boolean) as string[];
  const redac = redactionMessage(stock?.jours_de_stock, stock?.date_rupture);
  const etapeEnCours = runs.data?.steps.find((st) => st.status === "in_progress")?.name;
  const nQuarantaine = counts.quarantaine;
  const hero =
    enCours || working
      ? { niveau: "run", titre: "Fabrication en cours", texte: etapeEnCours ? `Étape : ${etapeEnCours}` : (CLOUD ? "Le cloud travaille, ton PC peut être éteint." : "Fabrication en cours sur ce PC.") }
      : nQuarantaine > 0 || flags.length > 0
        ? { niveau: "warn", titre: "Une chose demande ton attention", texte: [nQuarantaine > 0 && `${nQuarantaine} épisode(s) en quarantaine`, ...flags].filter(Boolean).join(" · ") }
        : { niveau: "ok", titre: "Tout est en ordre", texte: "Rien à faire pour l'instant." };
  const prochaine = ytQueue.find((e) => e.video) ?? ytQueue[0];
  const liste = tout ? shown : shown.slice(0, 8);

  return (
    <div className="ap">
      <section className={`ap-hero ${hero.niveau}`} aria-live="polite">
        <span className={`ap-dot ${hero.niveau === "run" ? "run" : ""}`} />
        <div>
          <h2>{hero.titre}</h2>
          <p>{hero.texte}</p>
          <p className="small">
            {CLOUD ? "Cloud" : STATIC ? "Instantané" : "Direct depuis le PC"} · état il y a {ago(s.genere)}
          </p>
        </div>
      </section>

      <ChronoHero plan={plan} nom={(id) => s.episodes.find((e) => e.id === id)?.titre ?? id} etape={etapeEnCours} label={CLOUD ? "Le cloud travaille, ton PC peut être éteint" : "Fabrication sur ce PC"} />

      {redac && redac.niveau !== "ok" && (
        <section className={`ap-redac ${redac.niveau}`} aria-live="polite">
          <div>
            <b>{redac.titre}</b>
            <p className="small">{redac.texte}</p>
          </div>
          <button
            className="btn sm"
            onClick={() => navigator.clipboard?.writeText(CONSIGNE_REDACTION).then(() => setMsg("Consigne copiée : colle-la dans ton Claude."), () => setMsg(CONSIGNE_REDACTION))}
          >
            Copier la consigne
          </button>
        </section>
      )}
      {msg && <div className="banner good">{msg}<button className="close" onClick={() => setMsg("")} aria-label="Fermer">×</button></div>}

      <section className="ap-kpis" aria-label="Indicateurs">
        <div className={`ap-kpi ${stock?.stock_bas ? "bad" : ""}`}><span className="k">Stock</span><span className="v">{stock?.jours_de_stock ?? "?"} j</span></div>
        <div className="ap-kpi"><span className="k">Prêtes</span><span className="v">{counts.pret + counts.programme}</span></div>
        <div className="ap-kpi"><span className="k">Rupture</span><span className="v">{stock?.date_rupture?.slice(5).replace("-", "/") ?? "?"}</span></div>
      </section>
      {redac && redac.niveau === "ok" && <p className="small ap-ok">{redac.texte}</p>}

      {prochaine && (
        <section className="ap-next">
          <h3>Prochaine vidéo</h3>
          <button className="ap-nextcard" onClick={() => prochaine.video && setPlayer(prochaine)} disabled={!prochaine.video}>
            {prochaine.miniature && <img src={media(prochaine.id, "miniature")} alt="" />}
            <span className="ap-nexttxt">
              <b>{prochaine.titre}</b>
              <span className="small">{prochaine.youtube.publie_a ? `prévue le ${prochaine.youtube.publie_a.slice(0, 10)} à ${prochaine.youtube.publie_a.slice(11, 16)}` : "date à fixer"}{prochaine.video ? " · toucher pour voir" : ""}</span>
            </span>
          </button>
        </section>
      )}

      <section className="ap-chips" aria-label="Stock par état">
        {ETATS.map(([k, label]) => (
          <button key={k} className={`ap-pill ${k} ${filter === k ? "on" : ""}`} onClick={() => setFilter(filter === k ? null : k)} aria-pressed={filter === k}>
            <b>{counts[k]}</b> {label}
          </button>
        ))}
      </section>

      <section className="ap-eps">
        {shown.length === 0 && <p className="small">Aucun épisode dans cet état.</p>}
        {liste.map((e) => (
          <article key={e.id} className={`ap-ep ${e.etat}`}>
            <button className="ap-thumb" onClick={() => e.video && setPlayer(e)} disabled={!e.video} aria-label={`Aperçu de ${e.titre}`}>
              {e.miniature ? <img src={media(e.id, "miniature")} alt="" loading="lazy" /> : <span className="small">–</span>}
            </button>
            <div className="ap-body">
              <div className="ap-title">{e.titre}</div>
              <div className="ap-meta">
                <span className={`ap-chip ${e.etat}`}>{libelle(e.etat)}</span>
                {e.long && <span className="ap-chip long">long</span>}
                {e.duree_s != null && <span className="small">{dur(e.duree_s)}</span>}
                <span className="small">il y a {ago(e.maj)}</span>
              </div>
              <SlotBadge slot={slotDe.get(e.id)} />
              {e.raison && <div className="ap-why">{e.raison.length > 150 ? `${e.raison.slice(0, 150)}…` : e.raison}</div>}
              {!STATIC && (
                <div className="ap-acts">
                  {e.etat === "quarantaine" && <button className="btn sm" onClick={() => act(e.id, "relancer")}>Relancer</button>}
                  {e.etat !== "quarantaine" && e.etat !== "publie" && e.etat !== "programme" && (
                    <button className="btn sm ghost" onClick={() => act(e.id, "ecarter")}>Écarter</button>
                  )}
                </div>
              )}
            </div>
          </article>
        ))}
        {shown.length > 8 && (
          <button className="btn ghost ap-more" onClick={() => setTout(!tout)}>
            {tout ? "Voir moins" : `Voir tout (${shown.length})`}
          </button>
        )}
      </section>

      {plan.slots.length > 0 && (
        <details className="ap-sec" open>
          <summary>File de fabrication ({plan.slots.length})</summary>
          {plan.slots.map((x) => (
            <div key={x.id} className="ap-row ap-fabrow">
              <span className={`ap-chip ${x.statut === "en cours" ? "programme" : ""}`}>{x.statut === "en cours" ? "en cours" : "en file"}</span>
              <span>{(s.episodes.find((e) => e.id === x.id)?.titre ?? x.id).slice(0, 90)}</span>
              <span className="small">{x.statut === "en cours" ? (x.depasse > 0 ? `+${formatReste(x.depasse)}` : `≈ ${formatReste(x.reste)}`) : x.fin != null ? `prête vers ${formatHeure(x.fin)}` : `≈ ${formatReste(x.duree)}`}</span>
            </div>
          ))}
          <p className="small">Estimations : elles se recalent à chaque vidéo terminée.</p>
        </details>
      )}

      <details className="ap-sec" open={!!enCours}>
        <summary>Avancement de la fabrication</summary>
        {CLOUD && (
          <div className="ap-run">
            {runs.error && <p className="small">GitHub : {runs.error} (limite de 60 requêtes/heure ?)</p>}
            {runs.data?.run ? (
              <>
                <p>
                  <span className={`ap-chip ${runs.data.run.status === "completed" ? (runs.data.run.conclusion === "success" ? "pret" : "quarantaine") : "programme"}`}>
                    {runs.data.run.status === "completed" ? (runs.data.run.conclusion === "success" ? "terminé" : "échec") : "en cours"}
                  </span>{" "}
                  <span className="small">il y a {ago(runs.data.run.created_at)} · <a href={runs.data.run.html_url} target="_blank" rel="noreferrer">détails</a></span>
                </p>
                {runs.data.steps.filter((st) => !st.name.startsWith("Post ") && st.name !== "Set up job" && st.name !== "Complete job").map((st) => (
                  <div key={st.name} className="ap-row">
                    <span className={`ap-chip ${st.conclusion === "success" ? "pret" : st.conclusion === "failure" ? "quarantaine" : ""}`}>{st.conclusion === "success" ? "ok" : st.conclusion === "failure" ? "échec" : st.status === "in_progress" ? "en cours" : "attente"}</span>
                    <span>{st.name}</span>
                    <span className="small">{st.started_at && st.completed_at ? `${Math.round((+new Date(st.completed_at) - +new Date(st.started_at)) / 1000)} s` : ""}</span>
                  </div>
                ))}
              </>
            ) : (
              !runs.error && <p className="small">Aucune fabrication encore lancée.</p>
            )}
            <button className="btn sm ghost" onClick={runs.reload}>Actualiser</button>
          </div>
        )}
        {!STATIC && (
          <>
            <select value={logName} onChange={(ev) => setLogName(ev.target.value)} aria-label="Journal">
              {logs.map((l) => (
                <option key={l.nom} value={l.nom}>{l.nom.replace(/^run_daily-/, "").replace(".log", "")} · il y a {ago(l.maj)}</option>
              ))}
            </select>
            <pre className="ap-log" ref={logRef}>{(log.data ?? []).map((l) => l.slice(0, 220)).join("\n") || "Journal vide."}</pre>
          </>
        )}
      </details>

      <details className="ap-sec">
        <summary>File YouTube ({ytQueue.length})</summary>
        {ytQueue.length === 0 && <p className="small">Rien en attente.</p>}
        {ytQueue.map((e) => (
          <div key={e.id} className="ap-row"><span className={`ap-chip ${e.etat}`}>{libelle(e.etat)}</span><span>{e.titre}</span><span className="small">{e.youtube.publie_a ? e.youtube.publie_a.slice(5, 16).replace("T", " ") : "–"}</span></div>
        ))}
      </details>

      <details className="ap-sec">
        <summary>File TikTok ({ttQueue.length})</summary>
        {ttQueue.length === 0 && <p className="small">Rien à envoyer.</p>}
        {ttQueue.length > 0 && <p className="small">Sans connexion TikTok : touche « Vidéo » pour la télécharger, « Légende » pour copier le texte, puis publie dans l'application.</p>}
        {ttQueue.slice(0, 12).map((e) => (
          <div key={e.id} className="ap-row">
            <span className="ap-chip">{e.tiktok ?? "à envoyer"}</span>
            <span>{e.titre}</span>
            <span className="ap-acts">
              {e.video && <a className="btn sm ghost" href={media(e.id, "video")} target="_blank" rel="noreferrer">Vidéo</a>}
              {e.legende && <button className="btn sm ghost" onClick={() => navigator.clipboard?.writeText(e.legende ?? "").then(() => setMsg("Légende copiée."), () => setMsg(e.legende ?? ""))}>Légende</button>}
            </span>
          </div>
        ))}
      </details>

      <details className="ap-sec">
        <summary>Alertes ({s.alertes.length})</summary>
        {s.alertes.length === 0 && <p className="small">Aucune.</p>}
        {s.alertes.slice(0, 10).map((a, i) => (
          <div key={i} className="ap-alert"><span className="small">{a.t.slice(5, 16).replace("T", " ")}</span> {a.msg.slice(0, 180)}</div>
        ))}
      </details>

      {player && (
        <div className="ap-modal" role="dialog" aria-label={player.titre} onClick={() => setPlayer(null)}>
          <div onClick={(ev) => ev.stopPropagation()}>
            <video src={media(player.id, "video")} controls autoPlay playsInline />
            <button className="btn ghost" onClick={() => setPlayer(null)}>Fermer</button>
          </div>
        </div>
      )}
    </div>
  );
};
