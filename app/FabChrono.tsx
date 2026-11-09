import { useEffect, useState } from "react";
import { formatHeure, formatReste, type Plan, type Slot } from "./chrono";

/** Horloge partagée : bat chaque seconde seulement quand `on` (une fabrication est en cours ou en attente). */
export const useNow = (on: boolean, every = 1000) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), every);
    return () => clearInterval(id);
  }, [on, every]);
  return now;
};

const pct = (x: number) => `${Math.round(Math.max(0, Math.min(1, x)) * 100)}%`;

/** Gros chrono du haut de page : temps restant pour TOUTE la file, avec barre et heure d'arrivée prévue. */
export const ChronoHero = ({ plan, etape, label, nom }: { plan: Plan; etape?: string; label: string; nom?: (id: string) => string }) => {
  const n = plan.slots.length;
  if (n === 0) return null;
  const retard = plan.depasse > 0;
  const enCours = plan.slots.find((s) => s.statut === "en cours");
  return (
    <section className={`ap-chrono ${plan.actif ? "run" : "wait"} ${retard ? "late" : ""}`} aria-label="Chrono de fabrication">
      <div className="ap-chrono-main">
        <span className="ap-chrono-k">{plan.actif ? "Temps restant" : "Durée prévue"}</span>
        <span className="ap-chrono-v" role="timer" aria-live="off">
          {plan.fin != null || !plan.actif ? "≈ " : ""}
          {formatReste(plan.reste, plan.actif && plan.reste < 3_600_000)}
        </span>
        <span className="ap-chrono-sub">
          {n} vidéo{n > 1 ? "s" : ""} {plan.actif ? "en fabrication" : "en attente"}
          {plan.fin != null && plan.actif ? ` · fin vers ${formatHeure(plan.fin)}` : ""}
        </span>
      </div>
      <div className="ap-chrono-side">
        <div className="ap-bar" aria-hidden="true"><span style={{ width: pct(plan.avancement) }} /></div>
        <p className="small">
          {retard
            ? `Plus long que prévu : ${enCours ? (nom?.(enCours.id) ?? enCours.id) : "la vidéo en cours"} dépasse l'estimation de ${formatReste(plan.depasse)}. Vérifie l'étape en cours ci-dessous.`
            : plan.actif
              ? `${label}${etape ? ` · étape : ${etape}` : ""}`
              : "Aucune fabrication en route pour l'instant : la file démarrera au prochain lancement."}
        </p>
        <p className="small ap-chrono-note">Estimation d'après les durées habituelles (long ≈ {Math.round(plan.slots.find((s) => s.long)?.duree ? (plan.slots.find((s) => s.long)!.duree / 60000) : 62)} min avec ses Shorts, Short ≈ 2 min), recalée à chaque vidéo terminée.</p>
      </div>
    </section>
  );
};

/** Petit chrono sur la carte d'une vidéo en fabrication. */
export const SlotBadge = ({ slot }: { slot: Slot | undefined }) => {
  if (!slot) return null;
  const run = slot.statut === "en cours";
  return (
    <div className={`ap-slot ${run ? "run" : ""} ${slot.depasse > 0 ? "late" : ""}`}>
      <div className="ap-slot-top">
        <span className="ap-slot-t" role="timer" aria-live="off">
          {run ? (slot.depasse > 0 ? `+${formatReste(slot.depasse)} de retard` : `reste ≈ ${formatReste(slot.reste, slot.reste < 600_000)}`) : `durée ≈ ${formatReste(slot.duree)}`}
        </span>
        <span className="small">
          {run ? "en cours" : slot.debut != null ? `démarre vers ${formatHeure(slot.debut)}` : "en file"}
          {slot.fin != null ? ` · prête vers ${formatHeure(slot.fin)}` : ""}
        </span>
      </div>
      <div className="ap-bar" aria-hidden="true"><span style={{ width: pct(run ? slot.avancement : 0) }} /></div>
      {slot.long && slot.shorts > 0 && <span className="small">+ {slot.shorts} Shorts tirés de ce long</span>}
    </div>
  );
};
