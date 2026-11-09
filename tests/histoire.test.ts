import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { getTheme } from "../src/infographie/themes";
import * as court from "../src/infographie/scenes";
import * as large from "../src/long/scenes";

const th = getTheme("parchemin");
const base = { l: 200, th, words: [], t: 0 } as never;
const cas = {
  Frise: { reperes: [{ date: "1628", label: "Le départ" }, { date: "1628", label: "Le naufrage", accent: true }] },
  Carte: { lieux: [{ nom: "Stockholm", x: 20, y: 30 }, { nom: "Baltique", x: 70, y: 60 }], trajet: true },
  Citation: { texte: "Ceci est une citation assez longue.", auteur: "Un témoin", date: "1628" },
} as const;

describe("scènes Histoire", () => {
  it("le thème parchemin existe", () => {
    expect(th.id).toBe("parchemin");
  });
  it("le fond parchemin n'affiche aucun symbole monétaire", () => {
    expect(th.glyphs).toBeDefined();
    expect((th.glyphs ?? []).join("")).not.toMatch(/[€$%]/);
    expect(getTheme("papier-vert").glyphs).toBeUndefined();
  });
  for (const [nom, p] of Object.entries(cas)) {
    for (const [fmt, mod] of [["9:16", court], ["16:9", large]] as const) {
      it(`${nom} se rend en ${fmt} avec le texte`, () => {
        const C = (mod as unknown as Record<string, React.FC<never>>)[nom];
        expect(C).toBeTypeOf("function");
        const html = renderToStaticMarkup(React.createElement(C as unknown as React.FC<Record<string, unknown>>, { ...(base as object), p } as Record<string, unknown>));
        const texte = (p as { reperes?: { label: string }[]; lieux?: { nom: string }[]; texte?: string });
        const attendu = texte.reperes?.[0].label ?? texte.lieux?.[0].nom ?? texte.texte!;
        expect(html).toContain(attendu);
        if (nom === "Carte") expect(html).toContain("Schéma");
      });
    }
  }
});
