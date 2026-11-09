import type { ChaineVue, Chantier } from "../../server/chaines";
import { STATIQUE, useSnapshot } from "../useSnapshot";

const STATUTS: Record<Chantier["statut"], { cls: string; texte: string }> = {
  fait: { cls: "pret", texte: "Fait" },
  en_cours: { cls: "programme", texte: "En cours" },
  a_faire: { cls: "", texte: "À faire" },
};

/** Première étape non faite d'une chaîne : ce qui la fait avancer. */
const prochaine = (c: ChaineVue) => c.etapes.find((e) => !e.fait)?.titre ?? null;

const LigneChaine = ({ c }: { c: ChaineVue }) => {
  const pct = Math.round(c.avancement * 100);
  const suite = prochaine(c);
  return (
    <div className="rt-chaine">
      <div className="rt-chaine-top">
        <b>{c.nom}</b>
        <span className={`ap-chip ${c.active ? "pret" : ""}`}>{c.active ? "Active" : c.preparation ? "En préparation" : "Inactive"}</span>
        <span className="small rt-pct">{pct} %</span>
      </div>
      <div className="ap-bar" role="progressbar" aria-label={`Avancement de ${c.nom}`} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div>
      {c.traduction && (
        <p className="small">
          {c.traduction.source} → {c.id} : <b>{c.traduction.adaptes}</b> épisode(s) adapté(s), <b>{c.traduction.prets}</b> prêt(s), {c.traduction.en_attente} en fabrication
          · voix {c.traduction.voix.disponible ? "disponible" : "manquante"} · file : {c.traduction.file.demandes + c.traduction.file.brouillons} en attente.
        </p>
      )}
      {c.format_statut && (
        <p className="small">
          Format : <b>{c.format_pret ? "prêt de bout en bout" : "pas encore prêt"}</b>
          {c.format_statut.test ? ` · test : ${c.format_statut.test}` : ""}
          {c.format_statut.manque.length > 0 ? ` · il manque : ${c.format_statut.manque.join(" ; ")}.` : ""}
        </p>
      )}
      <p className="small">{suite ? `Prochaine étape : ${suite}.` : "Toutes les étapes sont faites."}</p>
    </div>
  );
};

export const Route = () => {
  const snap = useSnapshot();
  const s = snap.data;
  if (!s) return <div className="ap"><p className="small">{snap.error ? `Impossible de lire l'état : ${snap.error}` : "Chargement…"}</p></div>;
  const chaines = s.chaines ?? [];
  const chantiers = s.feuille?.chantiers ?? [];
  const parVague = [...chaines].sort((a, b) => a.vague - b.vague || a.id.localeCompare(b.id));
  const faits = chantiers.filter((c) => c.statut === "fait").length;

  return (
    <div className="ap">
      <section className="ap-hero ok">
        <span className="ap-dot" />
        <div>
          <h2>Feuille de route</h2>
          <p>{chantiers.length} chantiers : {faits} terminé{faits > 1 ? "s" : ""}. Le moteur fait tourner plusieurs chaînes ; le multilingue et les nouveaux formats se branchent dessus.</p>
          <p className="small">{STATIQUE ? "Instantané" : "Direct depuis le PC"}{s.feuille?.maj ? ` · feuille de route mise à jour le ${s.feuille.maj}` : ""}</p>
        </div>
      </section>

      <section className="ap-sec rt-vagues" aria-label="Ordre d'activation">
        <h3 className="rt-h">Ordre d'activation des chaînes</h3>
        <ol className="rt-ordre">
          {parVague.map((c) => (
            <li key={c.id} className={c.active ? "on" : ""}>
              <span className="rt-num">{c.vague}</span>
              <span className="rt-nom">{c.nom}</span>
              <span className={`ap-chip ${c.active ? "pret" : ""}`}>{c.active ? "Active" : c.preparation ? "En préparation" : "Inactive"}</span>
            </li>
          ))}
        </ol>
        <p className="small">Une chaîne ne doit être activée que lorsque son jeton est connecté et que son format est prêt. L'activation se fait dans son profil (autopilot/chaines).</p>
      </section>

      {chantiers.length === 0 && <p className="small">Aucune feuille de route trouvée (autopilot/chaines/_feuille-de-route.json).</p>}
      {chantiers.map((ch) => {
        const st = STATUTS[ch.statut];
        const faites = ch.etapes.filter((e) => e.fait).length;
        const pct = ch.etapes.length ? Math.round((faites / ch.etapes.length) * 100) : 0;
        const concernees = (ch.chaines ?? []).map((id) => chaines.find((c) => c.id === id)).filter((c): c is ChaineVue => !!c);
        return (
          <details key={ch.id} className="ap-sec rt-chantier" open={ch.statut !== "fait"}>
            <summary>
              <span className="rt-sum">
                <b>{ch.titre}</b>
                <span className={`ap-chip ${st.cls}`}>{st.texte}</span>
              </span>
            </summary>
            <p>{ch.resume}</p>
            <div className="rt-pct-ligne"><span className="small">{faites} étape(s) sur {ch.etapes.length}</span><span className="small">{pct} %</span></div>
            <div className="ap-bar" role="progressbar" aria-label={`Avancement de ${ch.titre}`} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div>
            <ul className="ch-steps">
              {ch.etapes.map((e, i) => (
                <li key={i} className={e.fait ? "ok" : ""}>
                  <span aria-hidden="true">{e.fait ? "✓" : "○"}</span>
                  <span className="ch-step-t">
                    {e.titre}
                    {e.qui && !e.fait && <span className="ap-chip rt-qui">à faire par {e.qui}</span>}
                    <span className="sr-only">{e.fait ? " : fait" : " : à faire"}</span>
                  </span>
                </li>
              ))}
            </ul>
            {concernees.length > 0 && (
              <>
                <h4 className="rt-h">{ch.id === "formats" ? "Avancement de chaque format" : "Avancement de la chaîne"}</h4>
                <div className="rt-chaines">{concernees.map((c) => <LigneChaine key={c.id} c={c} />)}</div>
              </>
            )}
          </details>
        );
      })}
    </div>
  );
};
