/**
 * Vue « Autopilote » : lit l'état réel du workflow (autopilot/state, episodes-b, exports-b, autopilot/logs).
 * Lecture seule, sauf deux actions (relancer / écarter) qui passent par autopilot/episode_action.py.
 * Le même constructeur sert l'API locale et `npm run snapshot` (fichier JSON statique pour la version cloud).
 */
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { Router } from "express";
import { safeJoin } from "./paths";

export const ETATS = ["ecrit", "voix", "rendu", "controle", "pret", "programme", "publie", "quarantaine"] as const;
export type Etat = (typeof ETATS)[number];

export type AutoEp = {
  id: string;
  parent: string | null;
  long: boolean;
  titre: string;
  etat: Etat;
  maj: string;
  raison: string | null;
  tentatives: number;
  duree_s: number | null;
  publiable: boolean | null;
  miniature: boolean;
  video: boolean;
  youtube: { video_id: string | null; url: string | null; visibilite: string | null; publie_a: string | null };
  tiktok: string | null;
  /** Légende prête à coller dans TikTok : titre + hashtags tirés de publication.json. */
  legende: string | null;
};

export type Snapshot = {
  genere: string;
  stock: Record<string, unknown> | null;
  episodes: AutoEp[];
  alertes: { t: string; msg: string }[];
  logs: { nom: string; maj: string; octets: number }[];
  redaction: { dernier_passage: string | null; cible: number | null; a_ecrire: number | null } | null;
  verrous: { gpu: boolean; fabrique: boolean };
};

const readJson = <T,>(p: string): T | null => {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, "")) as T;
  } catch {
    return null;
  }
};
const exists = (p: string) => fs.existsSync(p);
/** Retire les codes couleur du terminal des journaux. */
const stripAnsi = (s: string) => s.replace(/\x1b\[[0-9;]*m/g, "");

export const createAutopilot = (root: string) => {
  const ap = safeJoin(root, "autopilot");
  const eps = safeJoin(root, "episodes-b");
  const exp = safeJoin(root, "exports-b");
  const logsDir = safeJoin(ap, "logs");
  const stateDir = safeJoin(ap, "state");

  const readEpisode = (id: string, tiktok: Record<string, { statut?: string }>): AutoEp | null => {
    const d = path.join(eps, id);
    if (!exists(path.join(d, "episode.json"))) return null;
    const st = readJson<Partial<AutoEp>>(path.join(d, "status.json")) ?? {};
    // anciennes vidéos retirées de YouTube lors de la refonte (archivées) : on ne les montre plus dans l'interface
    if (String(st.raison ?? "").startsWith("retiré de YouTube")) return null;
    const pub = readJson<{ titre?: string; tags?: string[] }>(path.join(d, "publication.json"));
    const qa = readJson<{ duree_s?: number; publiable?: boolean }>(path.join(exp, id, "qa.json"));
    const long = exists(path.join(d, "episode-long.json"));
    const m = /^(.+)-s\d+$/.exec(id);
    const parent = m && exists(path.join(eps, m[1], "episode-long.json")) ? m[1] : null;
    return {
      id,
      parent,
      long,
      titre: pub?.titre ?? id,
      etat: (ETATS as readonly string[]).includes(st.etat ?? "") ? (st.etat as Etat) : "ecrit",
      maj: st.maj ?? "",
      raison: st.raison ?? null,
      tentatives: st.tentatives ?? 0,
      duree_s: qa?.duree_s ?? null,
      publiable: qa?.publiable ?? null,
      miniature: exists(path.join(d, "miniature.png")),
      video: exists(path.join(exp, id, `${id}.mp4`)),
      youtube: { video_id: null, url: null, visibilite: null, publie_a: null, ...(st.youtube ?? {}) },
      tiktok: tiktok[id]?.statut ?? null,
      legende: pub?.titre ? `${pub.titre} ${(pub.tags ?? []).slice(0, 4).map((t) => "#" + t.replace(/[^\p{L}\p{N}]+/gu, "")).filter((t) => t.length > 1).join(" ")}`.trim() : null,
    };
  };

  const alertes = (): Snapshot["alertes"] => {
    try {
      return fs
        .readFileSync(path.join(stateDir, "ALERTES.txt"), "utf8")
        .split(/\r?\n/)
        .filter(Boolean)
        .slice(-40)
        .reverse()
        .map((l) => ({ t: l.slice(0, 19), msg: l.slice(19).trim().replace(/^(Bureau des Faits|La Débrouille)\s*:\s*/, "") }));
    } catch {
      return [];
    }
  };

  const listLogs = (): Snapshot["logs"] => {
    try {
      return fs
        .readdirSync(logsDir)
        .filter((n) => n.endsWith(".log"))
        .map((nom) => {
          const s = fs.statSync(path.join(logsDir, nom));
          return { nom, maj: s.mtime.toISOString(), octets: s.size };
        })
        .sort((a, b) => b.maj.localeCompare(a.maj))
        .slice(0, 12);
    } catch {
      return [];
    }
  };

  const snapshot = (): Snapshot => {
    const tiktok = readJson<Record<string, { statut?: string }>>(path.join(stateDir, "tiktok.json")) ?? {};
    const ids = exists(eps) ? fs.readdirSync(eps).filter((n) => !n.startsWith("_") && !n.startsWith(".")) : [];
    const episodes = ids.map((id) => readEpisode(id, tiktok)).filter((e): e is AutoEp => e !== null);
    const red = readJson<{ dernier_passage?: string; cible?: number; a_ecrire?: number }>(path.join(stateDir, "redaction.json"));
    return {
      genere: new Date().toISOString(),
      stock: readJson(path.join(stateDir, "stock.json")),
      episodes,
      alertes: alertes(),
      logs: listLogs(),
      redaction: red ? { dernier_passage: red.dernier_passage ?? null, cible: red.cible ?? null, a_ecrire: red.a_ecrire ?? null } : null,
      verrous: { gpu: exists(path.join(stateDir, "gpu.lock")), fabrique: exists(path.join(stateDir, "run_fabriquer.lock")) },
    };
  };

  /** Fin d'un journal (les `n` dernières lignes), sans couleurs. */
  const tail = (nom: string, n: number): string[] => {
    if (!/^[\w.-]+\.log$/.test(nom)) throw new Error("nom de journal invalide");
    const lines = stripAnsi(fs.readFileSync(safeJoin(logsDir, nom), "utf8")).split(/\r?\n/).filter(Boolean);
    return lines.slice(-Math.max(1, Math.min(n, 500)));
  };

  const act = (id: string, action: "relancer" | "ecarter") =>
    new Promise<{ ok: boolean; message: string }>((resolve) => {
      const p = spawn("python", [path.join(ap, "episode_action.py"), id, action], { cwd: root, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
      let out = "";
      p.stdout.on("data", (b) => (out += b));
      p.stderr.on("data", (b) => (out += b));
      p.on("error", (e) => resolve({ ok: false, message: String(e) }));
      p.on("close", (code) => resolve({ ok: code === 0, message: out.trim().split(/\r?\n/).pop() ?? "" }));
    });

  const router = Router();
  const ID = /^[a-z0-9][a-z0-9-]{0,100}$/;
  router.param("id", (_req, res, next, id) => (ID.test(id) ? next() : res.status(400).json({ error: "identifiant invalide" })));
  router.get("/snapshot", (_req, res) => res.json(snapshot()));
  router.get("/log/:nom", (req, res) => {
    try {
      res.json({ nom: req.params.nom, lignes: tail(req.params.nom, Number(req.query.n) || 120) });
    } catch (e) {
      res.status(404).json({ error: (e as Error).message });
    }
  });
  router.get("/media/:id/miniature", (req, res) => {
    const f = safeJoin(eps, req.params.id, "miniature.png");
    exists(f) ? res.sendFile(f) : res.status(404).end();
  });
  router.get("/media/:id/video", (req, res) => {
    const f = safeJoin(exp, req.params.id, `${req.params.id}.mp4`);
    exists(f) ? res.sendFile(f) : res.status(404).end();
  });
  router.post("/episodes/:id/:action", async (req, res) => {
    const a = req.params.action;
    if (a !== "relancer" && a !== "ecarter") return res.status(400).json({ error: "action inconnue" });
    const r = await act(req.params.id, a);
    res.status(r.ok ? 200 : 409).json(r);
  });
  return { router, snapshot, tail };
};
