import { describe, expect, it } from "vitest";
import type { Episode } from "../src/infographie/types";
import { ajuste, clampMots, formatGros, motsCles, premierNombre, resolveMiniature } from "../src/miniature/resolve";

const ep = {
  id: "t", titre: "Comment Costco gagne de l'argent", theme: "papier-vert", chaine: "Bureau des Faits",
  phrases: ["Costco gagne peu."], scenes: [{ type: "objet", phrase: 1, params: { icone: "hotdog", titre: "x" } }],
} as unknown as Episode;
const faits = [
  { claim: "Costco plafonne sa marge à 14 % au-dessus du coût.", valeur: "14 %" },
  { claim: "Les cotisations représentent la majorité du bénéfice.", valeur: "66 – 73 %" },
];

describe("premierNombre / formatGros", () => {
  it("normalise l'espace avant le symbole", () => {
    expect(formatGros("14%")).toBe("14\u202f%");
    expect(premierNombre("1,50 $")).toBe("1,50\u202f$");
  });
  it("tire le nombre d'une phrase et ignore le texte sans chiffre", () => {
    expect(premierNombre("une marge plafonnée à 14 % du coût")).toBe("14\u202f%");
    expect(premierNombre("aucun chiffre")).toBeNull();
    expect(premierNombre(undefined)).toBeNull();
  });
});

describe("motsCles / clampMots", () => {
  it("retire les mots vides et les nombres", () => {
    expect(motsCles("Comment Costco gagne de l'argent", 3)).toEqual(["Costco", "gagne", "argent"]);
  });
  it("limite à 5 mots", () => {
    expect(clampMots("un deux trois quatre cinq six sept").split(" ")).toHaveLength(5);
  });
});

describe("resolveMiniature", () => {
  it("sans champ miniature : chiffre choc tiré du premier fait", () => {
    const r = resolveMiniature(ep, faits, null);
    expect(r.style).toBe("chiffre");
    expect(r.gros).toBe("14\u202f%");
    expect(r.texteHaut.split(" ").length).toBeLessThanOrEqual(5);
    expect(r.icone).toBe("pieces");
  });
  it("sans aucun chiffre : question", () => {
    const r = resolveMiniature(ep, [], null);
    expect(r.style).toBe("question");
    expect(r.gros).toBe("?");
  });
  it("le champ de l'épisode l'emporte, le style forcé l'emporte sur le champ", () => {
    const e = { ...ep, miniature: { style: "question", texte_haut: "D'où vient l'argent", icone: "carte" } };
    expect(resolveMiniature(e, faits, null).style).toBe("question");
    expect(resolveMiniature(e, faits, null, { style: "chiffre" }).style).toBe("chiffre");
    expect(resolveMiniature(e, faits, null).icone).toBe("carte");
  });
  it("contraste : deux faits chiffrés suffisent ; sinon repli sur chiffre", () => {
    expect(resolveMiniature(ep, faits, null, { style: "contraste" }).contraste).toHaveLength(2);
    expect(resolveMiniature(ep, faits.slice(0, 1), null, { style: "contraste" }).style).toBe("chiffre");
  });
  it("texte du haut tronqué à 5 mots, thème forçable", () => {
    const e = { ...ep, miniature: { texte_haut: "un deux trois quatre cinq six sept" } };
    const r = resolveMiniature(e, faits, null, { theme: "nuit-vert" });
    expect(r.texteHaut.split(" ")).toHaveLength(5);
    expect(r.theme).toBe("nuit-vert");
  });
});

describe("ajuste", () => {
  it("un texte long donne un corps plus petit, plafonné par la hauteur", () => {
    expect(ajuste("OK", 1000, 200)).toBe(200);
    expect(ajuste("UN TEXTE BEAUCOUP PLUS LONG", 600, 200)).toBeLessThan(60);
  });
});
