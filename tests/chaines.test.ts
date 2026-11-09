import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAutopilot } from "../server/autopilot";
import { construireChaines, jourPacifique, lireFeuille, lireProfils, lireQuota, type EpisodeMin } from "../server/chaines";
import { ROOT } from "../server/paths";

let root: string;
const ecrire = (rel: string, contenu: unknown) => {
  const p = path.join(root, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, typeof contenu === "string" ? contenu : JSON.stringify(contenu));
};
const profil = (id: string, extra: object = {}) =>
  ecrire(`autopilot/chaines/${id}.json`, { id, nom: id.toUpperCase(), langue: "fr", format: "business", active: false, vague: 1, format_pret: false, ...extra });
const ep = (id: string, chaine: string, etat: EpisodeMin["etat"], extra: Partial<EpisodeMin> = {}): EpisodeMin => ({ id, chaine, etat, raison: null, youtube: { publie_a: null }, ...extra });

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-chaines-"));
  fs.mkdirSync(path.join(root, "autopilot", "state"), { recursive: true });
});
afterEach(() => vi.restoreAllMocks());

describe("profils", () => {
  it("sans dossier de profils : la chaîne historique seule, active (comportement d'avant)", () => {
    const p = lireProfils(root);
    expect(p.map((x) => [x.id, x.active])).toEqual([["fr", true]]);
  });

  it("trie par vague, ignore les fichiers commençant par _ et garde toujours la chaîne par défaut", () => {
    profil("quiz", { vague: 6 });
    profil("en", { vague: 2, langue: "en", source: { chaine: "fr", mode: "traduction" } });
    ecrire("autopilot/chaines/_feuille-de-route.json", { chantiers: [] });
    const p = lireProfils(root);
    expect(p.map((x) => x.id)).toEqual(["fr", "en", "quiz"]); // fr ajoutée d'office, en vague 1
    expect(p.find((x) => x.id === "en")?.source).toEqual({ chaine: "fr", mode: "traduction" });
    expect(p.find((x) => x.id === "quiz")?.active).toBe(false);
  });
});

describe("quota partagé", () => {
  const maintenant = new Date("2026-11-08T20:00:00Z");
  it("lit le registre du jour, avec le détail par chaîne", () => {
    ecrire("autopilot/state/youtube_quota.json", { jour_pt: jourPacifique(maintenant), envois: 12, unites: 340, plafond_envois: 100, plafond_unites: 10000, epuise: false, par_chaine: { fr: { envois: 9, unites: 300 }, en: { envois: 3, unites: 40 } } });
    const q = lireQuota(root, maintenant);
    expect(q).toMatchObject({ envois: 12, plafond_envois: 100, perime: false });
    expect(q.par_chaine.en.envois).toBe(3);
  });
  it("un registre d'un autre jour est perdu : compteurs à zéro, marqué périmé", () => {
    ecrire("autopilot/state/youtube_quota.json", { jour_pt: "2026-11-01", envois: 99, unites: 9000, epuise: true, par_chaine: { fr: { envois: 99, unites: 1 } } });
    expect(lireQuota(root, maintenant)).toMatchObject({ envois: 0, unites: 0, epuise: false, perime: true, par_chaine: {} });
  });
  it("sans registre : 100 envois par jour, rien de dépensé", () => {
    expect(lireQuota(root, maintenant)).toMatchObject({ envois: 0, plafond_envois: 100, perime: false });
  });
});

describe("formats de contenu (chantier 3)", () => {
  it("lit le bilan du format dans le profil et alerte si une chaîne est préparée sans format prêt", () => {
    profil("quiz", { format: "quiz", preparation: true, format_pret: false, format_module: "autopilot.formats.quiz",
      format_statut: { verifie: "2026-11-09", test: "quiz-essai : pret", manque: ["voix à confirmer"], licences: ["Qwen3-TTS, Apache-2.0"], risques: ["contenu répétitif"] } });
    profil("sommeil", { format: "sommeil" });
    const p = lireProfils(root).find((x) => x.id === "quiz")!;
    expect(p.format_module).toBe("autopilot.formats.quiz");
    expect(p.format_statut).toEqual({ verifie: "2026-11-09", test: "quiz-essai : pret", manque: ["voix à confirmer"], licences: ["Qwen3-TTS, Apache-2.0"], risques: ["contenu répétitif"] });
    const { chaines } = construireChaines(root, []);
    expect(chaines.find((c) => c.id === "quiz")!.format_statut?.manque).toEqual(["voix à confirmer"]);
    expect(chaines.find((c) => c.id === "quiz")!.alertes.some((a) => a.texte.includes("n'est pas déclaré prêt"))).toBe(true);
    expect(chaines.find((c) => c.id === "sommeil")!.format_statut).toBeNull();
  });
});

describe("vue des chaînes", () => {
  beforeEach(() => {
    profil("fr", { active: true, format_pret: true, vague: 1 });
    profil("en", { active: false, langue: "en", vague: 2 });
    profil("sommeil", { active: true, format: "sommeil", vague: 4, format_pret: false });
  });

  it("compte les vidéos de chaque chaîne par état et sépare les chaînes", () => {
    const eps = [ep("a", "fr", "pret"), ep("b", "fr", "programme"), ep("c", "fr", "publie", { youtube: { publie_a: "2026-11-05T17:00:00Z" } }),
      ep("d", "fr", "publie", { youtube: { publie_a: "2026-11-07T17:00:00Z" } }), ep("e", "en", "ecrit")];
    const { chaines } = construireChaines(root, eps);
    const fr = chaines.find((c) => c.id === "fr")!;
    expect(fr.stock).toMatchObject({ pret: 1, programme: 1, publie: 2, ecrit: 0 });
    expect(fr.prets).toBe(2);
    expect(fr.derniere_publication).toBe("2026-11-07T17:00:00Z");
    expect(chaines.find((c) => c.id === "en")!.stock.ecrit).toBe(1);
    expect(chaines.find((c) => c.id === "en")!.total).toBe(1);
  });

  it("jeton : booléen noté par le publieur, ou inconnu (null) tant qu'il n'a rien noté", () => {
    expect(construireChaines(root, []).chaines.every((c) => c.jeton === null)).toBe(true);
    ecrire("autopilot/state/jetons.json", { fr: { connecte: true }, en: { connecte: false }, sommeil: { connecte: false } });
    const { chaines } = construireChaines(root, []);
    expect(chaines.map((c) => [c.id, c.jeton])).toEqual([["fr", true], ["en", false], ["sommeil", false]]);
  });

  it("alerte une chaîne ACTIVE sans jeton, pas une chaîne inactive", () => {
    ecrire("autopilot/state/jetons.json", { fr: { connecte: true }, en: { connecte: false }, sommeil: { connecte: false } });
    const { chaines } = construireChaines(root, []);
    expect(chaines.find((c) => c.id === "en")!.alertes).toEqual([]);
    const som = chaines.find((c) => c.id === "sommeil")!;
    expect(som.alertes.map((a) => a.texte).join(" ")).toMatch(/aucun jeton/);
    expect(som.alertes.map((a) => a.texte).join(" ")).toMatch(/format de contenu n'est pas déclaré prêt/);
    expect(chaines.find((c) => c.id === "fr")!.alertes).toEqual([]);
  });

  it("connexion à refaire, stock bas et quarantaines remontent", () => {
    ecrire("autopilot/state/jetons.json", { fr: { connecte: true } });
    ecrire("autopilot/state/youtube_auth.json", { etat: "a_refaire" });
    ecrire("autopilot/state/stock.json", { par_chaine: { fr: { jours_de_stock: 1.5, stock_bas: true, shorts_par_jour: 8, longs_par_semaine: 3 } } });
    const { chaines } = construireChaines(root, [ep("q", "fr", "quarantaine", { raison: "voix trop faible" })]);
    const fr = chaines[0];
    const textes = fr.alertes.map((a) => a.texte).join(" | ");
    expect(textes).toMatch(/Connexion YouTube à refaire/);
    expect(textes).toMatch(/Stock bas : 1.5/);
    expect(textes).toMatch(/1 épisode\(s\) en quarantaine/);
    expect(fr.quarantaines).toEqual([{ id: "q", raison: "voix trop faible" }]);
    expect(fr.jours_de_stock).toBe(1.5);
    expect(fr.rythme).toEqual({ shorts_par_jour: 8, longs_par_semaine: 3 });
  });

  it("avancement : six étapes mesurées sur l'état réel", () => {
    ecrire("autopilot/state/jetons.json", { fr: { connecte: true } });
    const { chaines } = construireChaines(root, [ep("p", "fr", "publie")]);
    const fr = chaines.find((c) => c.id === "fr")!;
    expect(fr.etapes.every((e) => e.fait)).toBe(true);
    expect(fr.avancement).toBe(1);
    const en = chaines.find((c) => c.id === "en")!;
    expect(en.etapes.filter((e) => e.fait).map((e) => e.cle)).toEqual(["profil"]);
    expect(en.avancement).toBeCloseTo(1 / 6);
  });

  it("envois du jour de chaque chaîne = part du quota partagé", () => {
    ecrire("autopilot/state/youtube_quota.json", { jour_pt: jourPacifique(), envois: 5, par_chaine: { fr: { envois: 4, unites: 1 }, en: { envois: 1, unites: 1 } } });
    const { chaines, quota } = construireChaines(root, []);
    expect(quota.envois).toBe(5);
    expect(chaines.map((c) => c.envois_du_jour)).toEqual([4, 1, 0]);
  });
});

describe("feuille de route", () => {
  it("absente : liste vide, pas d'erreur", () => {
    expect(lireFeuille(root)).toEqual({ maj: null, chantiers: [] });
  });
});

describe("instantané de l'autopilote avec plusieurs chaînes", () => {
  const episode = (id: string, status: object) => {
    ecrire(`episodes-b/${id}/episode.json`, { id });
    ecrire(`episodes-b/${id}/status.json`, { maj: "2026-11-08T10:00:00", raison: null, tentatives: 0, ...status });
    ecrire(`episodes-b/${id}/publication.json`, { titre: id });
  };

  it("un épisode sans chaine_id appartient à la chaîne par défaut (migration non destructive) ; les autres gardent la leur", () => {
    profil("fr", { active: true });
    profil("en", { langue: "en" });
    episode("ancien", { etat: "pret" });
    episode("anglais", { etat: "ecrit", chaine_id: "en" });
    const snap = createAutopilot(root).snapshot();
    expect(snap.episodes.map((e) => [e.id, e.chaine]).sort()).toEqual([["ancien", "fr"], ["anglais", "en"]]);
    expect(snap.chaines.find((c) => c.id === "fr")!.stock.pret).toBe(1);
    expect(snap.chaines.find((c) => c.id === "en")!.stock.ecrit).toBe(1);
    expect(snap.quota.plafond_envois).toBe(100);
  });

  it("ne lit jamais autopilot/secrets et n'en laisse rien filtrer", () => {
    profil("fr", { active: true });
    ecrire("autopilot/secrets/token.json", { refresh_token: "SECRET-A-NE-JAMAIS-AFFICHER" });
    ecrire("autopilot/state/jetons.json", { fr: { connecte: true } });
    const lus: string[] = [];
    const vrai = fs.readFileSync;
    vi.spyOn(fs, "readFileSync").mockImplementation(((p: fs.PathOrFileDescriptor, ...a: unknown[]) => {
      lus.push(String(p));
      return (vrai as (...x: unknown[]) => unknown)(p, ...a);
    }) as typeof fs.readFileSync);
    const snap = createAutopilot(root).snapshot();
    expect(lus.some((p) => p.includes("secrets"))).toBe(false);
    expect(JSON.stringify(snap)).not.toContain("SECRET-A-NE-JAMAIS-AFFICHER");
    expect(snap.chaines[0].jeton).toBe(true);
  });
});

describe("profils réels du dépôt", () => {
  it("les chaînes déclarées : seule la chaîne française est active, les autres attendent leur jeton", () => {
    const p = lireProfils(ROOT);
    expect(p.map((x) => x.id)).toEqual(expect.arrayContaining(["en", "fr", "histoire", "langues", "meditation", "musique-enfants", "quiz", "sommeil"]));
    expect(p.filter((x) => x.active).map((x) => x.id)).toEqual(["fr"]);
    expect(p.find((x) => x.id === "en")?.source?.chaine).toBe("fr");
  });

  it("la feuille de route montre les trois chantiers", () => {
    const f = lireFeuille(ROOT);
    expect(f.chantiers.map((c) => c.id)).toEqual(expect.arrayContaining(["moteur", "multilingue", "formats"]));
    for (const ch of f.chantiers) for (const id of ch.chaines ?? []) expect(lireProfils(ROOT).some((p) => p.id === id)).toBe(true);
  });
});

describe("multilingue : chaîne qui reprend une autre", () => {
  beforeEach(() => {
    profil("fr", { active: true, format_pret: true });
    profil("en", { vague: 2, langue: "en", preparation: true, source: { chaine: "fr", mode: "traduction", cible_jours_de_stock: 4, decalage_heures: 48 }, voix: { dossier: "voix/en" } });
  });

  it("sans fichier de traduction : la vue existe, marquée « file jamais lancée », voix inconnue donc signalée", () => {
    const { chaines } = construireChaines(root, []);
    const en = chaines.find((c) => c.id === "en")!;
    expect(en.preparation).toBe(true);
    expect(en.traduction).toMatchObject({ source: "fr", langue: "en", file_lue: false, adaptes: 0, cible_jours_de_stock: 4, decalage_heures: 48 });
    expect(en.alertes.map((a) => a.texte).join(" ")).toMatch(/Voix en manquante/);
    expect(chaines.find((c) => c.id === "fr")?.traduction).toBeNull();
  });

  it("lit state/traduction.json : épisodes adaptés en attente / prêts, file, voix, repli, Claude bloqué", () => {
    ecrire("autopilot/state/traduction.json", {
      maj: "2026-11-09T01:00:00", claude_bloque: true, moteur_repli: { "fr-en": { disponible: false, detail: "modèle non installé" } },
      chaines: { en: { langue_source: "fr", voix: { mode: "integree", disponible: true, locuteur: "Ryan" }, adaptes: 5, adaptes_par_etat: { ecrit: 1, controle: 1, pret: 2, publie: 1 },
                       a_relire: 2, file: { demandes: 3, brouillons: 1 }, sources_restantes: 7, cible_jours_de_stock: 4, decalage_heures: 48 } },
    });
    const en = construireChaines(root, [ep("en-a", "en", "pret")]).chaines.find((c) => c.id === "en")!;
    expect(en.traduction).toMatchObject({
      file_lue: true, adaptes: 5, en_attente: 2, prets: 2, publies: 1, a_relire: 2, file: { demandes: 3, brouillons: 1 }, sources_restantes: 7,
      claude_bloque: true, voix: { mode: "integree", disponible: true, locuteur: "Ryan" }, repli: { disponible: false, detail: "modèle non installé" },
    });
    const textes = en.alertes.map((a) => a.texte).join(" | ");
    expect(textes).toMatch(/2 épisode\(s\) traduit\(s\) par le moteur de repli/);
    expect(textes).toMatch(/Claude est bloqué/);
    expect(textes).not.toMatch(/Voix en manquante/);
  });

  it("une chaîne en préparation n'est jamais « active » dans la vue", () => {
    const { chaines } = construireChaines(root, []);
    const en = chaines.find((c) => c.id === "en")!;
    expect([en.active, en.preparation]).toEqual([false, true]);
    expect(en.jours_de_stock).toBeNull();
  });
});
