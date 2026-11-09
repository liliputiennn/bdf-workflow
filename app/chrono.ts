/**
 * Chrono de fabrication : estime, pour chaque vidéo en cours de fabrication, le temps qu'il reste.
 *
 * Aucune brique du workflow n'écrit encore sa progression : ce sont donc des ESTIMATIONS, calées sur les durées mesurées
 * (cloud, 04/11/2026) et recalées à chaque vidéo terminée. L'interface le dit (« ≈ »), et signale un dépassement
 * plutôt que d'afficher un temps négatif.
 */

/** Durées moyennes mesurées en fabrication cloud (minutes). */
export const MIN_LONG = 48; // voix (Kaggle) + rendu 16:9 d'un long
export const MIN_SHORT = 2; // rendu d'un Short
export const SHORTS_PAR_LONG = 7; // un long « 7 business » donne 7 Shorts

export type FabEp = { id: string; long: boolean; etat: string; maj: string; parent?: string | null };

export type Slot = {
  id: string;
  long: boolean;
  /** « en cours » pour la vidéo que le moteur traite, « en file » pour les suivantes */
  statut: "en cours" | "en file";
  /** instant prévu de début et de fin (ms depuis 1970) ; null tant que la fabrication n'a pas d'heure de départ connue */
  debut: number | null;
  fin: number | null;
  /** durée prévue de cette vidéo (ms) */
  duree: number;
  /** temps restant (ms), jamais négatif */
  reste: number;
  /** dépassement de la prévision (ms), 0 si dans les temps */
  depasse: number;
  /** avancement estimé de 0 à 1 */
  avancement: number;
  /** nombre de Shorts encore à tirer de ce long (compris dans la durée) */
  shorts: number;
};

export type Plan = {
  actif: boolean;
  slots: Slot[];
  /** heure de départ retenue (ms) ou null */
  ancre: number | null;
  fin: number | null;
  reste: number;
  depasse: number;
  avancement: number;
  total: number;
};

const ETATS_FAB = new Set(["ecrit", "voix", "rendu"]);
const min = (n: number) => n * 60_000;

/** Lit une date du snapshot. Sans fuseau (écrite par le cloud, donc en UTC), on la lit en UTC ; jamais dans le futur. */
export const lireDate = (iso: string | null | undefined, utc: boolean, now = Date.now()): number | null => {
  if (!iso) return null;
  const t = Date.parse(utc && !/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? `${iso}Z` : iso);
  return Number.isNaN(t) ? null : Math.min(t, now);
};

/**
 * Plan de fabrication.
 * - `episodes` : tout le stock (seuls ecrit / voix / rendu comptent dans la file) ;
 * - `depart` : heure de lancement de la fabrication (cloud : début de l'étape « Fabrication » ; PC : verrou) ou null ;
 * - `travail` : le moteur travaille réellement en ce moment.
 * Les longs passent avant les Shorts. Le départ est recalé sur la dernière vidéo terminée depuis le lancement.
 */
export const planifier = (episodes: FabEp[], opts: { now: number; depart: number | null; travail: boolean; utc: boolean }): Plan => {
  const { now, depart, travail, utc } = opts;
  const file = episodes
    .filter((e) => ETATS_FAB.has(e.etat))
    .sort((a, b) => Number(b.long) - Number(a.long) || a.maj.localeCompare(b.maj) || a.id.localeCompare(b.id));

  // recalage : la dernière vidéo terminée (contrôle / prête) depuis le lancement donne le vrai point de départ de la suivante
  let ancre = depart;
  if (depart != null) {
    for (const e of episodes) {
      if (e.etat !== "controle" && e.etat !== "pret") continue;
      const t = lireDate(e.maj, utc, now);
      if (t != null && t >= depart && t > (ancre ?? 0)) ancre = t;
    }
  }

  let curseur = ancre;
  const slots: Slot[] = file.map((e, i) => {
    const shorts = e.long ? SHORTS_PAR_LONG : 0;
    const duree = min(e.long ? MIN_LONG + shorts * MIN_SHORT : MIN_SHORT);
    const debut = curseur;
    const fin = debut == null ? null : debut + duree;
    curseur = fin;
    const premier = i === 0;
    const ecoule = debut == null ? 0 : Math.max(0, now - debut);
    // la vidéo en cours ne peut pas finir « dans le passé » : si la prévision est dépassée, on garde un reste nul et on signale le retard
    const depasse = premier && travail && fin != null && now > fin ? now - fin : 0;
    const reste = debut == null ? duree : premier && travail ? Math.max(0, (fin ?? now) - now) : Math.max(0, duree - (premier ? ecoule : 0));
    const avancement = premier && travail && debut != null ? Math.min(0.97, ecoule / duree) : 0;
    return { id: e.id, long: e.long, statut: premier && travail ? "en cours" : "en file", debut, fin, duree, reste, depasse, avancement, shorts };
  });

  // les vidéos suivantes démarrent quand la première aura fini, même si elle est en retard
  if (travail && slots[0] && slots[0].depasse > 0) {
    let t = now;
    for (const [i, s] of slots.entries()) {
      if (i === 0) {
        s.fin = now;
        t = now;
        continue;
      }
      s.debut = t;
      s.fin = t + s.duree;
      s.reste = s.duree;
      t = s.fin;
    }
  }

  const total = slots.reduce((a, s) => a + s.duree, 0);
  const reste = slots.reduce((a, s) => a + s.reste, 0);
  const fin = slots.length && slots.every((s) => s.fin != null) ? Math.max(...slots.map((s) => s.fin as number)) : null;
  const depasse = slots[0]?.depasse ?? 0;
  const termine = Math.max(0, total - reste);
  return { actif: travail && slots.length > 0, slots, ancre, fin, reste, depasse, avancement: total ? Math.min(0.99, termine / total) : 0, total };
};

/** « 1 h 12 », « 12 min », « 4:05 » : compact, pour un affichage qui bouge chaque seconde. */
export const formatReste = (ms: number, precis = false): string => {
  const s = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return precis ? `${h} h ${String(m).padStart(2, "0")} min ${String(sec).padStart(2, "0")} s` : `${h} h ${String(m).padStart(2, "0")}`;
  if (precis || m < 10) return `${m}:${String(sec).padStart(2, "0")}`;
  return `${m} min`;
};

/** Heure d'arrivée prévue, à l'heure du visiteur : « 17:42 ». */
export const formatHeure = (t: number | null): string =>
  t == null ? "–" : new Date(t).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
