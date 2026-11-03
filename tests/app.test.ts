import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp } from "../server/app";
import { createQueue } from "../server/jobs";
import { findTools } from "../server/tools";

const H = { "x-console": "1" };
let root: string;
let base: string;
let close: () => void;

beforeEach(async () => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "bdf-api-"));
  for (const d of ["ideas", "episodes", "public", "renders"]) fs.mkdirSync(path.join(root, d));
  fs.writeFileSync(
    path.join(root, "ideas", "apollo-13.json"),
    JSON.stringify({
      slug: "apollo-13", hook: "Du scotch", theme: "Espace", year: 1970, score: 8.7, scoreNote: "estimation",
      facts: [{ claim: "Explosion à 330 000 km", sources: ["https://a", "https://b"] }], disputed: [], status: "idea",
    }),
  );
  const { app } = createApp({ root, tools: findTools(root), queue: createQueue(() => {}) });
  const server = app.listen(0, "127.0.0.1");
  await new Promise((r) => server.once("listening", r));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  close = () => server.close();
});
afterEach(() => close());

describe("API", () => {
  it("propose la banque de sujets business / finance", async () => {
    fs.mkdirSync(path.join(root, "subjects"));
    fs.writeFileSync(path.join(root, "subjects", "business.json"), JSON.stringify([{ titre: "Pourquoi IKEA vend des hot-dogs", theme: "Business", angle: "produit d'appel" }]));
    expect(await (await fetch(`${base}/api/week/suggestions`)).json()).toEqual([{ titre: "Pourquoi IKEA vend des hot-dogs", theme: "Business", angle: "produit d'appel" }]);
  });

  it("liste les idées avec leurs faits fragiles", async () => {
    const r = await (await fetch(`${base}/api/ideas`)).json();
    expect(r[0].slug).toBe("apollo-13");
    expect(r[0].weakFacts).toEqual([]);
  });

  it("produit une idée puis la liste en épisode", async () => {
    const p = await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST", headers: H });
    expect(p.status).toBe(201);
    const eps = await (await fetch(`${base}/api/episodes`)).json();
    expect(eps[0].id).toBe("apollo-13");
    expect((await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST", headers: H })).status).toBe(409);
  });

  it("accepte un MP3 et refuse le reste", async () => {
    await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST", headers: H });
    const ok = new FormData();
    ok.append("takes", new Blob([new Uint8Array([0xff, 0xfb, 0x90, 0x00])], { type: "audio/mpeg" }), "voix1.mp3");
    const r1 = await fetch(`${base}/api/episodes/apollo-13/voice?compare=0`, { method: "POST", headers: H, body: ok });
    expect(r1.status).toBe(200);
    expect(fs.existsSync(path.join(root, "public", "apollo-13", "voix1.mp3"))).toBe(true);
    const bad = new FormData();
    bad.append("takes", new Blob(["x"], { type: "text/plain" }), "evil.txt");
    expect((await fetch(`${base}/api/episodes/apollo-13/voice?compare=0`, { method: "POST", headers: H, body: bad })).status).toBe(400);
  });

  it("borne les volumes du mixage", async () => {
    await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST", headers: H });
    const r = await fetch(`${base}/api/episodes/apollo-13/mix`, {
      method: "PATCH",
      headers: { ...H, "content-type": "application/json" },
      body: JSON.stringify({ music: 9, sfx: -1 }),
    });
    expect((await r.json()).mix).toEqual({ music: 2, sfx: 0 });
  });

  it("refuse un identifiant qui sort du projet", async () => {
    expect((await fetch(`${base}/api/episodes/..%2F..%2Fetc`)).status).toBe(400);
  });

  it("refuse un site étranger et les actions sans en-tête", async () => {
    expect((await fetch(`${base}/api/ideas`, { headers: { origin: "https://evil.example" } })).status).toBe(403);
    expect((await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST" })).status).toBe(403);
  });

  it("autorise la Console en ligne, avec accès au réseau privé", async () => {
    const r = await fetch(`${base}/api/ideas`, {
      method: "OPTIONS",
      headers: { origin: "https://bureau-des-faits.web.app", "access-control-request-private-network": "true", "access-control-request-method": "POST" },
    });
    expect(r.status).toBe(204);
    expect(r.headers.get("access-control-allow-origin")).toBe("https://bureau-des-faits.web.app");
    expect(r.headers.get("access-control-allow-private-network")).toBe("true");
  });

  it("active ou coupe le pilote automatique", async () => {
    await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST", headers: H });
    expect((await (await fetch(`${base}/api/episodes/apollo-13`)).json()).autopilot).toBe(true);
    const r = await fetch(`${base}/api/episodes/apollo-13/autopilot`, { method: "PATCH", headers: { ...H, "content-type": "application/json" }, body: JSON.stringify({ on: false }) });
    expect((await r.json()).autopilot).toBe(false);
  });

  it("marque en erreur une tâche interrompue par un redémarrage", async () => {
    await fetch(`${base}/api/ideas/apollo-13/produce`, { method: "POST", headers: H });
    const f = path.join(root, "episodes", "apollo-13", "episode.json");
    const ep = JSON.parse(fs.readFileSync(f, "utf-8"));
    fs.writeFileSync(f, JSON.stringify({ ...ep, steps: { ...ep.steps, render: "running" } }));
    createApp({ root, tools: findTools(root), queue: createQueue(() => {}) });
    const after = JSON.parse(fs.readFileSync(f, "utf-8"));
    expect(after.steps.render).toBe("error");
    expect(after.error.log).toContain("interrompue");
  });

  it("répond 404 pour un épisode inconnu", async () => {
    expect((await fetch(`${base}/api/episodes/inconnu`)).status).toBe(404);
  });
});
