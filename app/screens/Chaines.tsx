import { useState } from "react";
import type { ChaineVue, EtatVideo, FormatStatut, TraductionVue } from "../../server/chaines";
import { dateCourte, STATIQUE, useSnapshot } from "../useSnapshot";

const NIVEAUX: [EtatVideo, string][] = [
  ["ecrit", "Écrit"],
  ["voix", "Voix"],
  ["rendu", "Rendu"],
  ["controle", "Contrôle"],
  ["pret", "Prêt"],
  ["programme", "Programmé"],
  ["publie", "Publié"],
  ["quarantaine", "Quarantaine"],
];
const LANGUES: Record<string, string> = { fr: "Français", en: "Anglais", es: "Espagnol", de: "Allemand", it: "Italien", pt: "Portugais" };
const FORMATS: Record<string, string> = {
  faits: "Faits", business: "Business", histoire: "Histoire", sommeil: "Sommeil", langues: "Apprentissage des langues", quiz: "Quiz", musique_enfants: "Musique pour enfants",
};
type Filtre = "toutes" | "actives" | "inactives" | "attention";

const jeton = (c: ChaineVue) =>
  c.jeton === true ? { cls: "pret", texte: "Jeton connecté" } : c.jeton === false ? { cls: c.active ? "quarantaine" : "", texte: "Jeton non connecté" } : { cls: "", texte: "Jeton : état inconnu" };

const VOIX: Record<string, string> = {
  clone: "voix clonée (référence de l'utilisateur)", integree: "voix intégrée du modèle", projet: "voix du projet",
};

/** Chantier 3 : bilan honnête du format de contenu (prêt de bout en bout ou ce qui manque), licences et risques. */
const Format = ({ c, f }: { c: ChaineVue; f: FormatStatut }) => (
  <section className="ch-multi" aria-label="Format de contenu">
    <h4>Format : {FORMATS[c.format] ?? c.format} · {c.format_pret ? "prêt de bout en bout" : "pas encore prêt"}</h4>
    {f.test && <p className="small">Épisode de test : {f.test}{f.verifie ? ` (vérifié le ${f.verifie})` : ""}</p>}
    {f.manque.length > 0 && (<><p className="small"><b>Ce qu'il manque</b></p><ul className="ch-steps">{f.manque.map((m, i) => <li key={i}><span aria-hidden="true">○</span><span className="ch-step-t">{m}</span></li>)}</ul></>)}
    {f.licences.length > 0 && (<><p className="small"><b>Licences retenues</b></p><ul className="ch-steps">{f.licences.map((m, i) => <li key={i} className="ok"><span aria-hidden="true">✓</span><span className="ch-step-t">{m}</span></li>)}</ul></>)}
    {f.risques.length > 0 && (<><p className="small"><b>Risques YouTube restants</b></p><ul className="ch-steps">{f.risques.map((m, i) => <li key={i}><span aria-hidden="true">!</span><span className="ch-step-t">{m}</span></li>)}</ul></>)}
  </section>
);

/** Multilingue : source → cible, voix, file de traduction, épisodes adaptés en attente / prêts. */
const Multilingue = ({ c, t }: { c: ChaineVue; t: TraductionVue }) => (
  <section className="ch-multi" aria-label="Multilingue">
    <h4>Multilingue · {LANGUES[t.langue_source] ?? t.langue_source} → {LANGUES[t.langue] ?? t.langue}</h4>
    <p className="small">
      Adapte (sans copier) les épisodes de la chaîne « {t.source} » ({t.mode === "doublage" ? "doublage" : "traduction"}). {c.active ? "Chaîne active." : "Rien n'est publié tant que tu n'actives pas la chaîne."}
    </p>
    <div className="ch-states">
      <span className="ap-pill"><b>{t.adaptes}</b> adaptés</span>
      <span className="ap-pill controle"><b>{t.en_attente}</b> en fabrication</span>
      <span className="ap-pill pret"><b>{t.prets}</b> prêts</span>
      <span className="ap-pill publie"><b>{t.publies}</b> publiés</span>
      {t.a_relire > 0 && <span className="ap-pill quarantaine"><b>{t.a_relire}</b> à relire</span>}
    </div>
    <dl className="ch-facts">
      <div><dt>Voix</dt><dd className={t.voix.disponible ? "" : "ch-mq"}>{t.voix.disponible ? `${VOIX[t.voix.mode ?? ""] ?? "disponible"}${t.voix.locuteur ? ` · ${t.voix.locuteur}` : ""}` : "manquante : voix.json ou voix de référence à déposer"}</dd></div>
      <div><dt>File de traduction</dt><dd>{t.file.demandes} demande(s) pour Claude · {t.file.brouillons} brouillon(s) · {t.sources_restantes} épisode(s) source à venir</dd></div>
      <div><dt>Qui traduit</dt><dd>Claude d'abord{t.claude_bloque ? " (bloqué : le repli travaille)" : ""} · repli gratuit {t.repli ? (t.repli.disponible ? "installé" : "pas installé") : "inconnu"}</dd></div>
      <div><dt>Réglages</dt><dd>stock visé {t.cible_jours_de_stock ?? "?"} j · publication {t.decalage_heures ?? "?"} h après la version source</dd></div>
    </dl>
    {!t.file_lue && <p className="small">La file de traduction n'a pas encore tourné : <code>python autopilot/run_daily.py traduire</code>.</p>}
  </section>
);

const Carte = ({ c, ouverte, basculer }: { c: ChaineVue; ouverte: boolean; basculer: () => void }) => {
  const mauvais = c.alertes.some((a) => a.niveau === "bad");
  const j = jeton(c);
  return (
    <article className={`ch-card ${c.active ? "on" : "off"} ${mauvais ? "bad" : ""}`}>
      <button className="ch-head" onClick={basculer} aria-expanded={ouverte} aria-controls={`ch-${c.id}`}>
        <span className="ch-name">
          <b>{c.nom}</b>
          <span className="small">{LANGUES[c.langue] ?? c.langue} · {FORMATS[c.format] ?? c.format}</span>
        </span>
        <span className="ch-chips">
          <span className={`ap-chip ${c.active ? "pret" : ""}`}>{c.active ? "Active" : "Inactive"}</span>
          {c.preparation && !c.active && <span className="ap-chip programme">En préparation</span>}
          {c.format_statut && <span className={`ap-chip ${c.format_pret ? "pret" : ""}`}>{c.format_pret ? "Format prêt" : "Format à finir"}</span>}
          {c.traduction && <span className="ap-chip">{LANGUES[c.traduction.langue_source] ?? c.traduction.langue_source} → {LANGUES[c.langue] ?? c.langue}</span>}
          <span className={`ap-chip ${j.cls}`}>{j.texte}</span>
        </span>
        <span className="ch-nums">
          <span><b>{c.prets}</b> prêtes</span>
          <span><b>{c.stock.publie}</b> publiées</span>
          <span>{c.active && c.jours_de_stock != null ? <><b>{c.jours_de_stock}</b> j de stock</> : "–"}</span>
        </span>
        {c.alertes.length > 0 && <span className={`ch-flag ${mauvais ? "bad" : "warn"}`}>{c.alertes.length} alerte{c.alertes.length > 1 ? "s" : ""}</span>}
      </button>
      {ouverte && (
        <div className="ch-detail" id={`ch-${c.id}`}>
          {c.niche && <p className="small">{c.niche}</p>}
          {c.source && <p className="small">Reprend le contenu de la chaîne « {c.source.chaine} » ({c.source.mode ?? "reprise"}).</p>}
          {c.notes && <p className="small ch-note">{c.notes}</p>}
          {c.traduction && <Multilingue c={c} t={c.traduction} />}
          {c.format_statut && <Format c={c} f={c.format_statut} />}

          {c.alertes.length > 0 && (
            <div className="ch-alertes">
              {c.alertes.map((a, i) => (
                <div key={i} className={`ap-alert ch-al ${a.niveau}`}>{a.texte}</div>
              ))}
            </div>
          )}

          <h4>Vidéos par état</h4>
          <div className="ch-states">
            {NIVEAUX.map(([k, label]) => (
              <span key={k} className={`ap-pill ${k}`}><b>{c.stock[k]}</b> {label}</span>
            ))}
          </div>
          {c.quarantaines.length > 0 && (
            <div className="ch-quar">
              {c.quarantaines.slice(0, 5).map((q) => (
                <div key={q.id} className="ap-why"><b>{q.id}</b> : {q.raison ? (q.raison.length > 140 ? `${q.raison.slice(0, 140)}…` : q.raison) : "raison inconnue"}</div>
              ))}
            </div>
          )}

          <dl className="ch-facts">
            <div><dt>Dernière publication</dt><dd>{dateCourte(c.derniere_publication)}</dd></div>
            <div><dt>Cadence prévue</dt><dd>{c.rythme.shorts_par_jour ?? "?"} Short(s) par jour · {c.rythme.longs_par_semaine ?? "?"} long(s) par semaine</dd></div>
            <div><dt>Chaîne YouTube reliée</dt><dd>{c.chaine_youtube ?? "pas encore vérifiée"}</dd></div>
            <div><dt>Envois du jour</dt><dd>{c.envois_du_jour} (sur le quota partagé)</dd></div>
          </dl>

          <h4>Mise en route · {Math.round(c.avancement * 100)} %</h4>
          <div className="ap-bar" role="progressbar" aria-valuenow={Math.round(c.avancement * 100)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${c.avancement * 100}%` }} /></div>
          <ul className="ch-steps">
            {c.etapes.map((e) => (
              <li key={e.cle} className={e.fait ? "ok" : ""}><span aria-hidden="true">{e.fait ? "✓" : "○"}</span><span className="ch-step-t">{e.titre}<span className="sr-only">{e.fait ? " : fait" : " : à faire"}</span></span></li>
            ))}
          </ul>
          {c.jeton !== true && (
            <p className="small">Pour connecter cette chaîne : guide <b>autopilot/publish/CONNECTER-UNE-CHAINE.md</b>, puis <code>python autopilot/publish/connecter_chaine.py {c.id}</code>.</p>
          )}
        </div>
      )}
    </article>
  );
};

export const Chaines = () => {
  const snap = useSnapshot();
  const [filtre, setFiltre] = useState<Filtre>("toutes");
  const [ouverte, setOuverte] = useState<string | null>(null);
  const s = snap.data;
  if (!s) return <div className="ap"><p className="small">{snap.error ? `Impossible de lire l'état : ${snap.error}` : "Chargement…"}</p></div>;
  const chaines = s.chaines ?? [];
  const actives = chaines.filter((c) => c.active);
  const attention = chaines.filter((c) => c.alertes.length > 0);
  const q = s.quota;
  const pct = q ? Math.min(100, Math.round((q.envois / Math.max(1, q.plafond_envois)) * 100)) : 0;
  const montrees = chaines.filter((c) => (filtre === "actives" ? c.active : filtre === "inactives" ? !c.active : filtre === "attention" ? c.alertes.length > 0 : true));
  const hero =
    attention.some((c) => c.alertes.some((a) => a.niveau === "bad"))
      ? { cls: "warn", titre: "Une chaîne demande ton attention", texte: attention.filter((c) => c.alertes.some((a) => a.niveau === "bad")).map((c) => c.nom).join(" · ") }
      : { cls: "ok", titre: "Tout est en ordre", texte: "Aucune chaîne active n'a de problème bloquant." };
  const filtres: [Filtre, string, number][] = [
    ["toutes", "Toutes", chaines.length],
    ["actives", "Actives", actives.length],
    ["inactives", "Inactives", chaines.length - actives.length],
    ["attention", "À surveiller", attention.length],
  ];

  return (
    <div className="ap">
      <section className={`ap-hero ${hero.cls}`} aria-live="polite">
        <span className="ap-dot" />
        <div>
          <h2>{actives.length} chaîne{actives.length > 1 ? "s" : ""} active{actives.length > 1 ? "s" : ""} sur {chaines.length}</h2>
          <p><b>{hero.titre}.</b> {hero.texte}</p>
          <p className="small">{STATIQUE ? "Instantané" : "Direct depuis le PC"} · les chaînes se mettent en route par vagues (voir la feuille de route).</p>
        </div>
      </section>

      <section className="ch-quota" aria-label="Quota YouTube du jour">
        <div className="ch-quota-top">
          <b>Quota YouTube du jour</b>
          <span className="small">partagé par toutes les chaînes (un seul projet Google)</span>
        </div>
        <div className="ch-quota-num"><b>{q?.envois ?? 0}</b> / {q?.plafond_envois ?? 100} envois{q?.epuise ? " · épuisé pour aujourd'hui" : ""}</div>
        <div className="ap-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div>
        <p className="small">
          {q?.perime || !q?.jour_pt ? "Compteur reparti de zéro (le quota se renouvelle à minuit, heure du Pacifique)." : `Journée du ${q.jour_pt} (heure du Pacifique) · ${q.unites} unité(s) de lecture et d'écriture sur ${q.plafond_unites}.`}
        </p>
        {q && Object.keys(q.par_chaine).length > 0 && (
          <div className="ch-states">
            {Object.entries(q.par_chaine).map(([id, v]) => (
              <span key={id} className="ap-pill"><b>{v.envois}</b> {chaines.find((c) => c.id === id)?.nom ?? id}</span>
            ))}
          </div>
        )}
      </section>

      <section className="ap-chips" aria-label="Filtrer les chaînes">
        {filtres.map(([k, label, n]) => (
          <button key={k} className={`ap-pill ${filtre === k ? "on" : ""}`} onClick={() => setFiltre(k)} aria-pressed={filtre === k}>
            <b>{n}</b> {label}
          </button>
        ))}
      </section>

      <section className="ch-list">
        {montrees.length === 0 && <p className="small">Aucune chaîne dans cette catégorie.</p>}
        {montrees.map((c) => (
          <Carte key={c.id} c={c} ouverte={ouverte === c.id} basculer={() => setOuverte(ouverte === c.id ? null : c.id)} />
        ))}
      </section>
    </div>
  );
};
