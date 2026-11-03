import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { Timings } from "../src/infographie/types";
import { chapitresTemps, flatten } from "../src/long/plan";
import type { EpisodeLong } from "../src/long/types";

const scene = (type: string, phrase: number) => ({ type, phrase, params: {} }) as never;
const ep: EpisodeLong = {
  id: "t", titre: "t", theme: "papier-vert", chaine: "c",
  chapitres: [
    { titre: "A", phrases: ["a1", "a2"], scenes: [scene("titre-geant", 1), scene("question", 2)] },
    { titre: "B", phrases: ["b1", "b2", "b3"], scenes: [scene("chiffre", 1)] },
    { titre: "C", carte: false, phrases: ["c1"], scenes: [scene("liste", 1)] },
  ],
};

describe("moteur long : aplatissement", () => {
  it("numérote les phrases et les scènes globalement", () => {
    const p = flatten(ep);
    expect(p.phrases).toEqual(["a1", "a2", "b1", "b2", "b3", "c1"]);
    expect(p.scenes.map((s) => s.phrase)).toEqual([1, 2, 3, 6]);
    expect(p.chapitres.map((c) => [c.first, c.last, c.carte])).toEqual([[1, 2, false], [3, 5, true], [6, 6, false]]);
  });

  it("cale les chapitres sur les timings, carte avant la parole", () => {
    const lines = [1, 2, 3, 4, 5, 6].map((k) => ({ start: k * 3 + (k >= 3 ? 2 : 0), end: k * 3 + 1.5 + (k >= 3 ? 2 : 0), words: [] }));
    const t: Timings = { total: 25, lines };
    const c = chapitresTemps(flatten(ep), t);
    expect(c[0].borne).toBe(0);
    expect(c[1].carteDe).toBeCloseTo(lines[1].end + 0.1);
    expect(c[1].start).toBe(lines[2].start);
    expect(c[2].carteDe).toBeNull();
    expect(c[2].borne).toBe(lines[5].start);
    expect(c[2].fin).toBe(25);
    expect(c[0].fin).toBeCloseTo(c[1].borne);
  });

  it("donne les mêmes bornes que autopilot/long/longlib.py (démo, si elle existe)", () => {
    const dir = "episodes-b/_demo-long";
    if (!existsSync(`${dir}/chapitres.json`)) return;
    const demo = JSON.parse(readFileSync(`${dir}/episode-long.json`, "utf-8")) as EpisodeLong;
    const t = JSON.parse(readFileSync(`${dir}/timings.json`, "utf-8")) as Timings;
    const py = JSON.parse(readFileSync(`${dir}/chapitres.json`, "utf-8")) as { borne_s: number; borne_fin_s: number; debut_s: number }[];
    chapitresTemps(flatten(demo), t).forEach((c, k) => {
      expect(c.borne).toBeCloseTo(py[k].borne_s, 2);
      expect(c.fin).toBeCloseTo(py[k].borne_fin_s, 2);
      expect(c.start).toBeCloseTo(py[k].debut_s, 2);
    });
  });
});
