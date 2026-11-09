import { describe, expect, it } from "vitest";
import { affiche, decoupe } from "../src/infographie/nombres";
import type { Word } from "../src/infographie/types";

const mots = (phrase: string): Word[] => phrase.split(" ").map((w, i) => ({ w, start: i * 0.4, end: i * 0.4 + 0.35 }));
const texte = (phrase: string) => affiche(mots(phrase)).map((w) => w.w).join(" ");
const N = " ";

describe("sous-titres : nombres en chiffres", () => {
  it("années, entiers, composés", () => {
    expect(texte("Selon un rapport de deux mille quatorze, seuls")).toBe("Selon un rapport de 2014, seuls");
    expect(texte("soixante-six et soixante-treize")).toBe("66 et 73");
    expect(texte("quatre-vingt-dix-sept")).toBe("97");
    expect(texte("vingt et un jours")).toBe("21 jours");
    expect(texte("trois cent vingt-sept")).toBe("327");
    expect(texte("mille deux cents")).toBe("1200");
    expect(texte("Apollo treize")).toBe("Apollo 13");
  });
  it("virgules, pourcentages et monnaies", () => {
    expect(texte("un virgule cinq pour cent des joueurs")).toBe(`1,5${N}% des joueurs`);
    expect(texte("zéro virgule quinze pour cent")).toBe(`0,15${N}%`);
    expect(texte("zéro virgule zéro cinq")).toBe("0,05");
    expect(texte("cent pour cent sûr")).toBe(`100${N}% sûr`);
    expect(texte("trente euros par mois")).toBe(`30${N}€ par mois`);
    expect(texte("vingt mille euros")).toBe(`20${N}000${N}€`);
    expect(texte("trois cent vingt-sept millions de dollars")).toBe("327 millions de dollars");
    expect(texte("dix à quatorze fois")).toBe("10 à 14 fois");
  });
  it("garde la ponctuation et fusionne le calage", () => {
    const r = affiche(mots("de deux mille quatorze, seuls"));
    expect(r.map((w) => w.w)).toEqual(["de", "2014,", "seuls"]);
    expect(r[1].start).toBeCloseTo(0.4);
    expect(r[1].end).toBeCloseTo(1.2 + 0.35);
  });
  it("ne touche pas aux articles ni aux mots courants", () => {
    expect(texte("un rapport une fois ce neuf est neuf")).toBe("un rapport une fois ce neuf est neuf");
    expect(texte("neuf mois de voyage")).toBe("9 mois de voyage");
    expect(texte("deux équipes la pilotent")).toBe("2 équipes la pilotent");
  });
});

describe("sous-titres : morceaux courts", () => {
  it("coupe de préférence après une ponctuation, jamais plus de 6 mots", () => {
    const m = mots("Selon un rapport de 2014, seuls 1,5 % des joueurs achètent quelque chose dans le mois.");
    const morceaux = decoupe(m);
    expect(morceaux.length).toBeGreaterThanOrEqual(2);
    for (const c of morceaux) expect(c.length).toBeLessThanOrEqual(6);
    expect(morceaux.flat()).toHaveLength(m.length);
    expect(morceaux[0].at(-1)!.w).toMatch(/,$/);
  });
  it("garde une phrase courte d'un seul bloc", () => {
    expect(decoupe(mots("Alors, qui paie pour que"))).toHaveLength(1);
  });
});

describe("sous-titres anglais : nombres en chiffres", () => {
  const en = (phrase: string) => affiche(mots(phrase), "en").map((w) => w.w).join(" ");
  it("entiers, composés, années", () => {
    expect(en("Only twelve thousand five hundred people")).toBe("Only 12,500 people");
    expect(en("sixty-six and seventy-three")).toBe("66 and 73");
    expect(en("three hundred twenty-seven")).toBe("327");
    expect(en("one hundred percent sure")).toBe("100% sure");
    expect(en("in twenty twenty-four we saw")).toBe("in 2024 we saw");
    expect(en("since nineteen ninety-nine")).toBe("since 1999");
    expect(en("two thousand five hundred")).toBe("2500");
  });
  it("décimales, pourcentages et monnaies", () => {
    expect(en("one point five percent of players")).toBe("1.5% of players");
    expect(en("zero point zero five")).toBe("0.05");
    expect(en("thirty euros a month")).toBe("€30 a month");
    expect(en("twenty thousand dollars")).toBe("$20,000");
    expect(en("three million dollars")).toBe("$3 million");
    expect(en("ten to fourteen times")).toBe("10 to 14 times");
  });
  it("ne touche pas les mots courants et le français reste intact sans langue", () => {
    expect(en("one of them said that")).toBe("one of them said that");
    expect(en("a second look at the first one")).toBe("a second look at the first one");
    expect(texte("vingt mille euros")).toBe(`20${N}000${N}€`);
    expect(affiche(mots("deux équipes"), "fr").map((w) => w.w).join(" ")).toBe("2 équipes");
  });
  it("garde la ponctuation et fusionne le calage", () => {
    const r = affiche(mots("of two thousand fourteen, only"), "en");
    expect(r.map((w) => w.w)).toEqual(["of", "2014,", "only"]);
    expect(r[1].start).toBeCloseTo(0.4);
    expect(r[1].end).toBeCloseTo(1.2 + 0.35);
  });
});
