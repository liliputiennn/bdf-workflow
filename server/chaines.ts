/**
 * Vue « Chaînes » et « Feuille de route » : lit les profils (`autopilot/chaines/*.json`) et l'état écrit par le pipeline
 * (`autopilot/state/` : jetons.json, youtube_quota.json, youtube_auth-<chaîne>.json, stock.json). Lecture seule.
 *
 * Aucun secret ici : on ne lit JAMAIS `autopilot/secrets/`. « Jeton connecté » vient de `state/jetons.json`, écrit par le publieur
 * (des booléens, jamais le contenu d'un jeton).
 */
import fs from "node:fs";
import path from "node:path";
import { safeJoin } from "./paths";

export const ETATS_VIDEO = ["ecrit", "voix", "rendu", "controle", "pret", "programme", "publie", "quarantaine"] as const;
export type EtatVideo = (typeof ETATS_VIDEO)[number];

export type Profil = {
  id: string;
  nom: string;
  langue: string;
  format: string;
  niche: string;
  active: boolean;
  /** chantier 2 : du stock se fabrique (voix, rendu, miniature) sans que rien soit publié tant que `active` est faux */
  preparation: boolean;
  vague: number;
  format_pret: boolean;
  /** chantier 3 : module de format déclaré et bilan écrit à la main dans le profil (`format_statut`) */
  format_module: string | null;
  format_statut: FormatStatut | null;
  source: { chaine: string; mode?: string; cible_jours_de_stock?: number; decalage_heures?: number } | null;
  notes: string;
  frequence: { shorts_par_jour?: number; longs_par_semaine?: number };
  voix: { dossier: string | null };
};

/** Multilingue (chantier 2) : où en est l'adaptation des épisodes de la chaîne source vers cette chaîne. */
export type TraductionVue = {
  source: string;
  mode: string;
  langue: string;
  langue_source: string;
  /** voix de la chaîne : clone = voix de référence de l'utilisateur, integree = voix intégrée du modèle, null = aucune encore */
  voix: { mode: "clone" | "integree" | "projet" | null; disponible: boolean; locuteur: string | null };
  cible_jours_de_stock: number | null;
  decalage_heures: number | null;
  adaptes: number;
  /** adaptés encore en fabrication (écrit, voix, rendu, contrôle) */
  en_attente: number;
  /** adaptés prêts à publier (prêt, programmé) */
  prets: number;
  publies: number;
  a_relire: number;
  file: { demandes: number; brouillons: number };
  sources_restantes: number;
  claude_bloque: boolean;
  /** moteur gratuit de repli (MarianMT) : installé ou non */
  repli: { disponible: boolean; detail: string } | null;
  /** la file de traduction a-t-elle déjà tourné (autopilot/state/traduction.json) ? */
  file_lue: boolean;
  maj: string | null;
};

/** Bilan honnête d'un format de contenu (chantier 3) : ce qui a été vérifié, ce qui manque, licences retenues, risques YouTube restants. */
export type FormatStatut = {
  verifie: string | null;
  /** épisode de test et chemin parcouru */
  test: string;
  manque: string[];
  licences: string[];
  risques: string[];
};

export type EtapeChaine = { cle: string; titre: string; fait: boolean };
export type AlerteChaine = { niveau: "bad" | "warn"; texte: string };

export type ChaineVue = {
  id: string;
  nom: string;
  langue: string;
  format: string;
  niche: string;
  active: boolean;
  preparation: boolean;
  vague: number;
  source: { chaine: string; mode?: string } | null;
  /** présent pour une chaîne qui reprend une autre (multilingue) */
  traduction: TraductionVue | null;
  notes: string;
  /** null = inconnu (le publieur n'a pas encore noté l'état des jetons) */
  jeton: boolean | null;
  /** titre de la chaîne YouTube reliée au profil (notée par l'outil de connexion), si connu */
  chaine_youtube: string | null;
  format_pret: boolean;
  /** module de format déclaré par le profil (null = pipeline standard) */
  format_module: string | null;
  format_statut: FormatStatut | null;
  stock: Record<EtatVideo, number>;
  prets: number;
  total: number;
  jours_de_stock: number | null;
  rythme: { shorts_par_jour: number | null; longs_par_semaine: number | null };
  derniere_publication: string | null;
  quarantaines: { id: string; raison: string | null }[];
  alertes: AlerteChaine[];
  etapes: EtapeChaine[];
  avancement: number;
  /** envois du jour dans le quota partagé */
  envois_du_jour: number;
};

export type QuotaVue = {
  jour_pt: string | null;
  envois: number;
  plafond_envois: number;
  unites: number;
  plafond_unites: number;
  epuise: boolean;
  par_chaine: Record<string, { envois: number; unites: number }>;
  /** le registre date d'un autre jour (heure du Pacifique) : les compteurs sont repartis de zéro */
  perime: boolean;
};

export type Chantier = {
  id: string;
  titre: string;
  statut: "fait" | "en_cours" | "a_faire";
  resume: string;
  etapes: { titre: string; fait: boolean; qui?: string }[];
  /** profils (chaînes) ou formats concernés : l'avancement de chacun est calculé à partir de l'état réel */
  chaines?: string[];
};

export type Feuille = { maj: string | null; chantiers: Chantier[] };

export type EpisodeMin = { chaine: string; etat: EtatVideo; id: string; raison: string | null; youtube: { publie_a: string | null } };

const readJson = <T,>(p: string): T | null => {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, "")) as T;
  } catch {
    return null;
  }
};

const FR: Profil = {
  id: "fr", nom: "La Débrouille", langue: "fr", format: "business", niche: "Faits et business", active: true, preparation: false, vague: 1, format_pret: true,
  format_module: null, format_statut: null, source: null, notes: "", frequence: {}, voix: { dossier: null },
};

const liste = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

const lireStatutFormat = (v: unknown): FormatStatut | null => {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  return { verifie: typeof o.verifie === "string" ? o.verifie : null, test: typeof o.test === "string" ? o.test : "", manque: liste(o.manque), licences: liste(o.licences), risques: liste(o.risques) };
};

/** Profils de chaînes, triés par vague puis identifiant. Sans dossier de profils : la chaîne historique seule (comportement d'avant). */
export const lireProfils = (root: string): Profil[] => {
  const dir = safeJoin(root, "autopilot", "chaines");
  let fichiers: string[] = [];
  try {
    fichiers = fs.readdirSync(dir).filter((n) => n.endsWith(".json") && !n.startsWith("_"));
  } catch {
    // pas de dossier : chaîne par défaut seule
  }
  const profils: Profil[] = [];
  for (const f of fichiers) {
    const b = readJson<Partial<Profil>>(path.join(dir, f));
    if (!b) continue;
    const id = String(b.id ?? f.replace(/\.json$/, ""));
    profils.push({
      id,
      nom: b.nom ?? id,
      langue: b.langue ?? "fr",
      format: b.format ?? "faits",
      niche: b.niche ?? "",
      active: !!b.active,
      preparation: !!b.preparation,
      vague: Number(b.vague ?? 1),
      format_pret: !!b.format_pret,
      format_module: b.format_module ?? null,
      format_statut: lireStatutFormat((b as { format_statut?: unknown }).format_statut),
      source: b.source ?? null,
      notes: b.notes ?? "",
      frequence: b.frequence ?? {},
      voix: { dossier: b.voix?.dossier ?? null },
    });
  }
  if (!profils.some((p) => p.id === "fr")) profils.push(FR);
  return profils.sort((a, b) => a.vague - b.vague || a.id.localeCompare(b.id));
};

/** Jour courant à Los Angeles (le quota YouTube repart de zéro à minuit heure du Pacifique). */
export const jourPacifique = (d = new Date()) => d.toLocaleDateString("en-CA", { timeZone: "America/Los_Angeles" });

export const lireQuota = (root: string, now = new Date()): QuotaVue => {
  const q = readJson<Partial<QuotaVue> & { jour_pt?: string }>(safeJoin(root, "autopilot", "state", "youtube_quota.json"));
  const base: QuotaVue = { jour_pt: q?.jour_pt ?? null, envois: 0, plafond_envois: q?.plafond_envois ?? 100, unites: 0, plafond_unites: q?.plafond_unites ?? 10000, epuise: false, par_chaine: {}, perime: false };
  if (!q) return base;
  if (q.jour_pt !== jourPacifique(now)) return { ...base, perime: true };
  return { ...base, envois: q.envois ?? 0, unites: q.unites ?? 0, epuise: !!q.epuise, par_chaine: q.par_chaine ?? {} };
};

const vide = (): Record<EtatVideo, number> => Object.fromEntries(ETATS_VIDEO.map((e) => [e, 0])) as Record<EtatVideo, number>;

type TraductionJson = {
  maj?: string;
  claude_bloque?: boolean;
  moteur_repli?: Record<string, { disponible?: boolean; detail?: string }>;
  chaines?: Record<string, {
    voix?: { mode?: string | null; disponible?: boolean; locuteur?: string | null };
    cible_jours_de_stock?: number; decalage_heures?: number; adaptes?: number; adaptes_par_etat?: Record<string, number>; a_relire?: number;
    file?: { demandes?: number; brouillons?: number }; sources_restantes?: number; claude_bloque?: boolean; langue_source?: string;
  }>;
};

/** Vue multilingue d'une chaîne qui reprend une autre : lue dans `state/traduction.json` (écrit par `traduction/traduire.py`), complétée par le profil. */
const construireTraduction = (p: Profil, tj: TraductionJson | null, profils: Profil[]): TraductionVue | null => {
  if (!p.source) return null;
  const t = tj?.chaines?.[p.id];
  const par = t?.adaptes_par_etat ?? {};
  const somme = (...cles: string[]) => cles.reduce((a, c) => a + (par[c] ?? 0), 0);
  const src = profils.find((x) => x.id === p.source?.chaine);
  const paire = `${src?.langue ?? "fr"}-${p.langue}`;
  const repli = tj?.moteur_repli?.[paire];
  const mode = (t?.voix?.mode ?? null) as TraductionVue["voix"]["mode"];
  return {
    source: p.source.chaine, mode: p.source.mode ?? "traduction", langue: p.langue, langue_source: t?.langue_source ?? src?.langue ?? "fr",
    voix: { mode, disponible: !!t?.voix?.disponible, locuteur: t?.voix?.locuteur ?? null },
    cible_jours_de_stock: t?.cible_jours_de_stock ?? p.source.cible_jours_de_stock ?? null,
    decalage_heures: t?.decalage_heures ?? p.source.decalage_heures ?? null,
    adaptes: t?.adaptes ?? 0, en_attente: somme("ecrit", "voix", "rendu", "controle"), prets: somme("pret", "programme"), publies: somme("publie"),
    a_relire: t?.a_relire ?? 0, file: { demandes: t?.file?.demandes ?? 0, brouillons: t?.file?.brouillons ?? 0 },
    sources_restantes: t?.sources_restantes ?? 0, claude_bloque: !!(t?.claude_bloque ?? tj?.claude_bloque),
    repli: repli ? { disponible: !!repli.disponible, detail: repli.detail ?? "" } : null, file_lue: !!t, maj: tj?.maj ?? null,
  };
};

type StockChaine = { jours_de_stock?: number; stock_bas?: boolean; shorts_par_jour?: number; longs_par_semaine?: number; erreurs?: string[]; auth_a_renouveler?: boolean };

export const construireChaines = (root: string, episodes: EpisodeMin[], now = new Date()): { chaines: ChaineVue[]; quota: QuotaVue } => {
  const state = safeJoin(root, "autopilot", "state");
  const jetons = readJson<Record<string, { connecte?: boolean }>>(path.join(state, "jetons.json"));
  const liens = readJson<Record<string, { titre?: string }>>(path.join(state, "chaines_youtube.json")) ?? {};
  const stockJson = readJson<{ par_chaine?: Record<string, StockChaine> }>(path.join(state, "stock.json"));
  const traductionJson = readJson<TraductionJson>(path.join(state, "traduction.json"));
  const quota = lireQuota(root, now);
  const profils = lireProfils(root);
  const chaines = profils.map((p): ChaineVue => {
    const traduction = construireTraduction(p, traductionJson, profils);
    const eps = episodes.filter((e) => e.chaine === p.id);
    const stock = vide();
    for (const e of eps) stock[e.etat] += 1;
    const publies = eps.filter((e) => e.etat === "publie" && e.youtube.publie_a).map((e) => e.youtube.publie_a as string).sort();
    const st = stockJson?.par_chaine?.[p.id];
    const jeton = jetons && p.id in jetons ? !!jetons[p.id]?.connecte : null;
    const authFile = readJson<{ etat?: string }>(path.join(state, p.id === "fr" ? "youtube_auth.json" : `youtube_auth-${p.id}.json`));
    const quarantaines = eps.filter((e) => e.etat === "quarantaine").map((e) => ({ id: e.id, raison: e.raison }));
    const prets = stock.pret + stock.programme;
    const alertes: AlerteChaine[] = [];
    if (st?.erreurs?.length) alertes.push({ niveau: "bad", texte: `Profil invalide : ${st.erreurs.join(" ; ")}` });
    if (p.active && jeton === false) alertes.push({ niveau: "bad", texte: "Chaîne active mais aucun jeton : à connecter (guide CONNECTER-UNE-CHAINE)." });
    if (p.active && jeton !== false && authFile && authFile.etat && authFile.etat !== "ok") alertes.push({ niveau: "bad", texte: "Connexion YouTube à refaire." });
    if (p.preparation && !p.active && !p.format_pret) alertes.push({ niveau: "warn", texte: "En préparation alors que le format n'est pas déclaré prêt : du stock se fabrique sans avoir été vérifié de bout en bout." });
    if (p.active && !p.format_pret) alertes.push({ niveau: "warn", texte: "Active alors que le format de contenu n'est pas déclaré prêt." });
    if (p.active && st?.stock_bas) alertes.push({ niveau: "warn", texte: `Stock bas : ${st.jours_de_stock ?? "?"} jour(s) de vidéos prêtes.` });
    if (traduction && !traduction.voix.disponible && (p.active || p.preparation)) alertes.push({ niveau: "bad", texte: `Voix ${p.langue} manquante : déposer voix/${p.langue}/voix.json (voix intégrée) ou ref.wav + ref.txt (voix clonée).` });
    if (traduction && traduction.a_relire > 0) alertes.push({ niveau: "warn", texte: `${traduction.a_relire} épisode(s) traduit(s) par le moteur de repli : à relire avant d'activer la chaîne.` });
    if (traduction && traduction.claude_bloque) alertes.push({ niveau: "warn", texte: "Claude est bloqué : la traduction passe par le moteur gratuit de repli." });
    if (quarantaines.length) alertes.push({ niveau: "warn", texte: `${quarantaines.length} épisode(s) en quarantaine.` });
    const etapes: EtapeChaine[] = [
      { cle: "profil", titre: "Profil créé", fait: true },
      { cle: "jeton", titre: "Chaîne YouTube créée et jeton connecté", fait: jeton === true },
      { cle: "format", titre: p.source ? "Contenu repris de la chaîne source (adaptation, voix, rendu)" : "Format de contenu prêt", fait: p.format_pret },
      { cle: "episodes", titre: p.source ? "Premiers épisodes adaptés" : "Premiers épisodes écrits", fait: eps.length > 0 },
      { cle: "active", titre: "Chaîne activée", fait: p.active },
      { cle: "publie", titre: "Première vidéo publiée", fait: stock.publie > 0 },
    ];
    return {
      id: p.id, nom: p.nom, langue: p.langue, format: p.format, niche: p.niche, active: p.active, preparation: p.preparation, vague: p.vague, source: p.source, traduction, notes: p.notes,
      jeton, chaine_youtube: liens[p.id]?.titre ?? null, format_pret: p.format_pret, format_module: p.format_module, format_statut: p.format_statut, stock, prets, total: eps.length,
      jours_de_stock: p.active ? (st?.jours_de_stock ?? null) : null,
      rythme: { shorts_par_jour: st?.shorts_par_jour ?? p.frequence.shorts_par_jour ?? null, longs_par_semaine: st?.longs_par_semaine ?? p.frequence.longs_par_semaine ?? null },
      derniere_publication: publies.length ? publies[publies.length - 1] : null,
      quarantaines, alertes, etapes, avancement: etapes.filter((e) => e.fait).length / etapes.length,
      envois_du_jour: quota.par_chaine[p.id]?.envois ?? 0,
    };
  });
  return { chaines, quota };
};

/** Trois chantiers. Le fichier `autopilot/chaines/_feuille-de-route.json` est écrit à la main (chaque chantier met son statut à jour) ;
 * l'avancement de chaque chaîne ou format, lui, vient de l'état réel (`construireChaines`). */
export const lireFeuille = (root: string): Feuille => {
  const f = readJson<Feuille>(safeJoin(root, "autopilot", "chaines", "_feuille-de-route.json"));
  return f && Array.isArray(f.chantiers) ? f : { maj: null, chantiers: [] };
};
