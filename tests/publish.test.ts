import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { buildPackage, controlSheet, packageDate, publicationText } from "../server/publish";
import type { Episode } from "../server/types";

const POST = "# Post — Épisode 03\n\n**Description**\nIKEA perd de l'argent sur ses hot-dogs.\nEt pourtant, ça lui rapporte.\nTu en as déjà mangé un ?\n\n**Hashtags** #business #ikea #argent #faits\n";

const ep = (over: Partial<Episode> = {}): Episode =>
  ({
    id: "ikea-hotdog", number: 3, title: "Le hot-dog à 1 €", idea: "ikea-hotdog", channel: "bureau-des-faits", publicDir: "ikea-hotdog",
    compositionId: "Ep03-IkeaHotdog", coverId: "Ep03-IkeaHotdog-Cover", scriptFile: "episodes/ikea-hotdog/script.json",
    voiceTextFile: "episodes/ikea-hotdog/TEXTE-VOIX.txt", timingsFile: "src/episodes/ikea-hotdog.timings.json",
    steps: {} as Episode["steps"], voice: { takes: [], chosen: "a.mp3", scores: {} }, mix: { music: 1, sfx: 1 },
    metrics: { medianDb: 31.2, worstDb: 9.4, whisper: 93.1 }, error: null, ...over,
  }) as Episode;

let root: string;
beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-pub-"));
  fs.mkdirSync(path.join(root, "renders", "ikea-hotdog"), { recursive: true });
  fs.mkdirSync(path.join(root, "episodes", "ikea-hotdog"), { recursive: true });
  fs.mkdirSync(path.join(root, "src", "episodes"), { recursive: true });
  fs.writeFileSync(path.join(root, "renders", "ikea-hotdog", "ikea-hotdog.mp4"), "video");
  fs.writeFileSync(path.join(root, "renders", "ikea-hotdog", "cover.png"), "png");
  fs.writeFileSync(path.join(root, "episodes", "ikea-hotdog", "POST.md"), POST);
  fs.writeFileSync(path.join(root, "src", "episodes", "ikea-hotdog.timings.json"), JSON.stringify({ total: 74.6, lines: [] }));
});

describe("paquet de publication", () => {
  it("extrait le texte à coller de POST.md", () => {
    expect(publicationText(POST)).toBe("IKEA perd de l'argent sur ses hot-dogs.\nEt pourtant, ça lui rapporte.\nTu en as déjà mangé un ?\n\n#business #ikea #argent #faits\n");
  });

  it("crée exports/<date>/<id>/ avec vidéo, couverture, texte et fiche", () => {
    const r = buildPackage(root, ep(), "2026-10-27");
    expect(r).toEqual({ dir: "exports/2026-10-27/ikea-hotdog", date: "2026-10-27" });
    const dir = path.join(root, r.dir);
    expect(fs.readdirSync(dir).sort()).toEqual(["cover.png", "fiche-controle.txt", "ikea-hotdog.mp4", "texte.txt"]);
    expect(fs.readFileSync(path.join(dir, "ikea-hotdog.mp4"), "utf-8")).toBe("video");
    const fiche = fs.readFileSync(path.join(dir, "fiche-controle.txt"), "utf-8");
    expect(fiche).toContain("Durée : 1 min 15 s");
    expect(fiche).toContain("31.2 dB  [OK ]");
    expect(fiche).toContain("contenu généré par IA");
    // reconstruire le paquet ne casse rien
    expect(() => buildPackage(root, ep(), "2026-10-27")).not.toThrow();
  });

  it("signale une clarté insuffisante", () => {
    expect(controlSheet(ep(), 60, { medianDb: 21, worstDb: 3, whisper: 84 })).toMatch(/21 dB {2}\[À REVOIR\][\s\S]*84 % {2}\[À REVOIR\]/);
  });

  it("refuse sans vidéo rendue", () => {
    fs.rmSync(path.join(root, "renders", "ikea-hotdog", "ikea-hotdog.mp4"));
    expect(() => buildPackage(root, ep())).toThrow("vidéo pas encore rendue");
  });

  it("date le paquet au jour prévu dans la semaine", () => {
    fs.mkdirSync(path.join(root, "weeks"));
    fs.writeFileSync(path.join(root, "weeks", "2026-10-26.json"), JSON.stringify({ start: "2026-10-26", slots: [{}, {}, { episode: "ikea-hotdog" }, {}, {}, {}, {}] }));
    expect(packageDate(root, "ikea-hotdog")).toBe("2026-10-28");
    expect(packageDate(root, "autre", new Date("2026-11-02T10:00:00Z"))).toBe("2026-11-02");
  });
});
