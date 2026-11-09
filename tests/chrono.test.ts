import { describe, expect, it } from "vitest";
import { formatReste, lireDate, MIN_LONG, MIN_SHORT, planifier, SHORTS_PAR_LONG, type FabEp } from "../app/chrono";

const H = 3_600_000;
const M = 60_000;
const NOW = Date.parse("2026-11-04T15:00:00Z");
const long = (id: string, etat = "ecrit", maj = "2026-11-04T09:00:00"): FabEp => ({ id, long: true, etat, maj });
const short = (id: string, etat = "ecrit", maj = "2026-11-04T09:00:00"): FabEp => ({ id, long: false, etat, maj });
const DUREE_LONG = (MIN_LONG + SHORTS_PAR_LONG * MIN_SHORT) * M;

describe("planifier", () => {
  it("ne compte que les vidéos en fabrication, longs d'abord", () => {
    const p = planifier([short("s1"), long("a"), long("b", "pret"), long("c")], { now: NOW, depart: NOW, travail: true, utc: true });
    expect(p.slots.map((s) => s.id)).toEqual(["a", "c", "s1"]);
    expect(p.slots[0].statut).toBe("en cours");
    expect(p.slots[1].statut).toBe("en file");
  });

  it("calcule le temps restant de la vidéo en cours et la fin de la file", () => {
    const p = planifier([long("a"), long("b")], { now: NOW + 10 * M, depart: NOW, travail: true, utc: true });
    expect(p.slots[0].reste).toBe(DUREE_LONG - 10 * M);
    expect(p.slots[0].depasse).toBe(0);
    expect(p.slots[1].reste).toBe(DUREE_LONG);
    expect(p.fin).toBe(NOW + 2 * DUREE_LONG);
    expect(p.reste).toBe(2 * DUREE_LONG - 10 * M);
    expect(p.avancement).toBeCloseTo((10 * M) / (2 * DUREE_LONG), 3);
  });

  it("signale un dépassement au lieu d'un temps négatif, et décale la suite", () => {
    const now = NOW + DUREE_LONG + 25 * M;
    const p = planifier([long("a"), long("b")], { now, depart: NOW, travail: true, utc: true });
    expect(p.slots[0].reste).toBe(0);
    expect(p.slots[0].depasse).toBe(25 * M);
    expect(p.slots[1].debut).toBe(now);
    expect(p.fin).toBe(now + DUREE_LONG);
    expect(p.reste).toBe(DUREE_LONG);
  });

  it("recale le départ sur la dernière vidéo terminée depuis le lancement", () => {
    const fait = long("fait", "controle", "2026-11-04T14:30:00");
    const p = planifier([fait, long("a")], { now: NOW, depart: NOW - 3 * H, travail: true, utc: true });
    expect(p.ancre).toBe(Date.parse("2026-11-04T14:30:00Z"));
    expect(p.slots[0].reste).toBe(DUREE_LONG - 30 * M);
  });

  it("sans heure de départ : durées prévues seulement, pas d'heure de fin", () => {
    const p = planifier([long("a"), short("s1")], { now: NOW, depart: null, travail: false, utc: true });
    expect(p.fin).toBeNull();
    expect(p.actif).toBe(false);
    expect(p.slots.every((s) => s.statut === "en file" && s.debut === null)).toBe(true);
    expect(p.reste).toBe(DUREE_LONG + MIN_SHORT * M);
  });

  it("une file vide n'est pas active", () => {
    const p = planifier([long("a", "pret")], { now: NOW, depart: NOW, travail: true, utc: true });
    expect(p.actif).toBe(false);
    expect(p.slots).toHaveLength(0);
    expect(p.avancement).toBe(0);
  });
});

describe("lireDate", () => {
  it("lit les dates sans fuseau en UTC quand elles viennent du cloud", () => {
    expect(lireDate("2026-11-04T10:00:00", true, NOW)).toBe(Date.parse("2026-11-04T10:00:00Z"));
    expect(lireDate("2026-11-04T10:00:00+01:00", true, NOW)).toBe(Date.parse("2026-11-04T09:00:00Z"));
  });
  it("ne renvoie jamais le futur et gère le vide", () => {
    expect(lireDate("2026-11-05T10:00:00Z", true, NOW)).toBe(NOW);
    expect(lireDate(null, true, NOW)).toBeNull();
    expect(lireDate("n'importe quoi", true, NOW)).toBeNull();
  });
});

describe("formatReste", () => {
  it("affiche heures, minutes ou minutes:secondes", () => {
    expect(formatReste(72 * M)).toBe("1 h 12");
    expect(formatReste(25 * M)).toBe("25 min");
    expect(formatReste(4 * M + 5000)).toBe("4:05");
    expect(formatReste(-5)).toBe("0:00");
    expect(formatReste(72 * M + 9000, true)).toBe("1 h 12 min 09 s");
  });
});
