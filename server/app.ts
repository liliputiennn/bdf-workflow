import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import express, { type NextFunction, type Request, type Response } from "express";
import multer from "multer";
import { createQueue, type Queue } from "./jobs";
import { guard } from "./origins";
import { safeJoin } from "./paths";
import { alignJob, compareJob, renderJob, verifyJob, type Ctx } from "./pipelines";
import { createStore, weakFacts } from "./store";
import { health, type Tools } from "./tools";
import type { Episode, JobView } from "./types";
import { buildBrief, createWeeks, importWeek, type Week } from "./week";
import { buildPackage, publicationText } from "./publish";
import { createBatchRunner, weekEpisodeIds } from "./batch";
import { createAutopilot } from "./autopilot";

const ID = /^[a-z0-9][a-z0-9-]{0,80}$/;
const clamp = (v: unknown) => Math.max(0, Math.min(2, Number(v) || 0));

export const createApp = (opts: { root: string; tools: Tools; queue?: Queue }) => {
  const { root, tools } = opts;
  const store = createStore(root);
  const listeners = new Set<Response>();
  const queue =
    opts.queue ??
    createQueue((job: JobView) => {
      for (const res of listeners) res.write(`data: ${JSON.stringify(job)}\n\n`);
    });
  const ctx: Ctx = { root, store, tools, queue };
  // une tâche « en cours » au démarrage a forcément été interrompue (API redémarrée) : on le dit clairement
  for (const ep of store.listEpisodes()) {
    const stuck = (Object.keys(ep.steps) as (keyof Episode["steps"])[]).filter((k) => ep.steps[k] === "running");
    if (stuck.length) store.saveEpisode({ ...ep, steps: { ...ep.steps, ...Object.fromEntries(stuck.map((k) => [k, "error"])) }, error: { step: stuck[0], log: "Tâche interrompue (le moteur a redémarré). Clique sur Relancer." } });
  }
  const app = express();
  app.use(guard);
  app.use(express.json({ limit: "2mb" }));

  const withPublish = (ep: Episode): Episode => ({
    ...ep,
    steps: {
      ...ep.steps,
      publish: ep.steps.render === "done" && fs.existsSync(safeJoin(root, "episodes", ep.id, "POST.md")) ? "done" : ep.steps.publish,
    },
  });

  const checkId = (_req: Request, res: Response, next: NextFunction, id: string) => {
    if (ID.test(id)) next();
    else res.status(400).json({ error: "identifiant invalide" });
  };
  app.param("id", checkId);
  app.param("slug", checkId);

  app.get("/api/health", (_req, res) => {
    res.json(health(tools));
  });

  app.get("/api/ideas", (_req, res) => {
    res.json(store.listIdeas().map((i) => ({ ...i, weakFacts: weakFacts(i) })));
  });

  app.post("/api/ideas/:slug/produce", (req, res) => {
    try {
      res.status(201).json(store.createEpisodeFromIdea(req.params.slug as string));
    } catch (e) {
      res.status(409).json({ error: (e as Error).message });
    }
  });

  app.get("/api/episodes", (_req, res) => {
    res.json(store.listEpisodes().map(withPublish));
  });

  app.get("/api/episodes/:id", (req, res) => {
    const ep = withPublish(store.getEpisode(req.params.id as string));
    const read = (rel: string) => (fs.existsSync(safeJoin(root, rel)) ? fs.readFileSync(safeJoin(root, rel), "utf-8") : "");
    const post = read(`episodes/${ep.id}/POST.md`);
    res.json({ ...ep, texts: { voiceText: read(ep.voiceTextFile), post, publication: post ? publicationText(post) : ep.title } });
  });

  const upload = multer({
    storage: multer.diskStorage({
      destination: (req, _f, cb) => {
        try {
          const dir = safeJoin(root, "public", store.getEpisode(req.params.id as string).publicDir);
          fs.mkdirSync(dir, { recursive: true });
          cb(null, dir);
        } catch (e) {
          cb(e as Error, "");
        }
      },
      filename: (_req, f, cb) => cb(null, path.basename(f.originalname).replace(/[^\w.-]/g, "_")),
    }),
    limits: { fileSize: 30 * 1024 * 1024 },
    fileFilter: (_req, f, cb) => cb(null, /\.mp3$/i.test(f.originalname) && /audio\/(mpeg|mp3)/.test(f.mimetype)),
  });

  app.post("/api/episodes/:id/voice", upload.array("takes", 6), (req, res) => {
    const files = (req.files as Express.Multer.File[] | undefined) ?? [];
    if (files.length === 0) {
      res.status(400).json({ error: "dépose un ou plusieurs fichiers MP3" });
      return;
    }
    const ep = store.getEpisode(req.params.id as string);
    const takes = [...new Set([...ep.voice.takes, ...files.map((f) => f.filename)])];
    const compare = req.query.compare !== "0";
    const next: Episode = { ...ep, voice: { ...ep.voice, takes }, steps: { ...ep.steps, voice: compare ? "running" : ep.steps.voice }, error: null };
    store.saveEpisode(next);
    if (compare) queue.enqueue(compareJob(ctx, next));
    res.json(next);
  });

  app.post("/api/episodes/:id/voice/choose", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    const take = req.body?.take as string;
    if (!ep.voice.takes.includes(take)) {
      res.status(400).json({ error: "prise inconnue" });
      return;
    }
    const changed = ep.voice.chosen !== take;
    const next: Episode = {
      ...ep,
      voice: { ...ep.voice, chosen: take },
      steps: { ...ep.steps, voice: "done", align: changed ? "todo" : ep.steps.align },
    };
    store.saveEpisode(next);
    res.json(next);
  });

  app.patch("/api/episodes/:id/mix", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    const next = { ...ep, mix: { music: clamp(req.body?.music), sfx: clamp(req.body?.sfx) } };
    store.saveEpisode(next);
    res.json(next);
  });

  app.post("/api/episodes/:id/jobs/:kind", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    const kind = req.params.kind as "compare" | "align" | "render";
    const make = { compare: compareJob, align: alignJob, render: renderJob }[kind];
    if (!make) {
      res.status(404).json({ error: "tâche inconnue" });
      return;
    }
    try {
      const def = make(ctx, ep);
      const step = kind === "compare" ? "voice" : kind;
      store.saveEpisode({ ...ep, steps: { ...ep.steps, [step]: "running" }, error: null });
      res.status(202).json(queue.enqueue(def));
    } catch (e) {
      res.status(400).json({ error: (e as Error).message });
    }
  });

  app.post("/api/ideas/verify", (_req, res) => {
    res.status(202).json(queue.enqueue(verifyJob(ctx)));
  });

  app.patch("/api/episodes/:id/autopilot", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    const next = { ...ep, autopilot: req.body?.on !== false };
    store.saveEpisode(next);
    res.json(next);
  });

  /* ───────── Semaine : 7 sujets, un brief pour Claude, un import ───────── */
  const weeks = createWeeks(root);
  const blankWeek = (): Week => ({ start: new Date().toISOString().slice(0, 10), slots: Array.from({ length: 7 }, () => ({})) });
  const currentWeek = () => weeks.latest() ?? blankWeek();

  app.get("/api/week", (_req, res) => {
    res.json(currentWeek());
  });

  app.patch("/api/week", (req, res) => {
    const body = req.body as Week & { previousStart?: string };
    if (!Array.isArray(body?.slots) || typeof body.start !== "string") {
      res.status(400).json({ error: "semaine invalide" });
      return;
    }
    const slots = body.slots.map((s) => ({
      ...(typeof s.idea === "string" && s.idea ? { idea: s.idea } : {}),
      ...(typeof s.subject === "string" && s.subject.trim() ? { subject: s.subject.trim().slice(0, 200) } : {}),
      ...(typeof s.episode === "string" && s.episode ? { episode: s.episode } : {}),
    }));
    try {
      res.json(weeks.save({ start: body.start, slots }, body.previousStart));
    } catch (e) {
      res.status(400).json({ error: (e as Error).message });
    }
  });

  /** Banque de sujets business / finance expliquée (subjects/*.json) : des angles, sans chiffres ; Claude source les faits dans le brief. */
  app.get("/api/week/suggestions", (_req, res) => {
    const dir = safeJoin(root, "subjects");
    const all = fs.existsSync(dir)
      ? fs.readdirSync(dir).filter((f) => f.endsWith(".json")).flatMap((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")) as { titre: string; theme: string; angle: string }[])
      : [];
    res.json(all);
  });

  app.get("/api/week/brief", (_req, res) => {
    res.json({ text: buildBrief(currentWeek(), store.listIdeas()) });
  });

  app.post("/api/week/import", (req, res) => {
    const text = req.body?.text;
    if (typeof text !== "string" || !text.trim()) {
      res.status(400).json({ error: "colle la réponse de Claude" });
      return;
    }
    const r = importWeek(root, store, currentWeek(), text);
    if (r.ok) weeks.save(r.week);
    res.status(r.ok ? 200 : 422).json(r);
  });

  /* ───────── Lot : « Rendre la semaine » ───────── */
  const batch = createBatchRunner(ctx);
  app.get("/api/batch", (_req, res) => {
    res.json(batch.status());
  });
  app.post("/api/batch", (req, res) => {
    const ids = Array.isArray(req.body?.ids) ? (req.body.ids as unknown[]).filter((x): x is string => typeof x === "string" && ID.test(x)) : weekEpisodeIds(root);
    try {
      res.status(202).json(batch.start(ids));
    } catch (e) {
      res.status(409).json({ error: (e as Error).message });
    }
  });

  app.get("/api/jobs", (_req, res) => {
    res.json(queue.list());
  });

  app.get("/api/jobs/stream", (req, res) => {
    res.set({ "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
    res.flushHeaders();
    res.write(": ok\n\n");
    listeners.add(res);
    req.on("close", () => listeners.delete(res));
  });

  app.post("/api/episodes/:id/package", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    try {
      const next = { ...ep, package: buildPackage(root, ep) };
      store.saveEpisode(next);
      res.json(next);
    } catch (e) {
      res.status(400).json({ error: (e as Error).message });
    }
  });

  app.patch("/api/episodes/:id/published", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    const next = { ...ep, publishedAt: req.body?.on === false ? null : new Date().toISOString().slice(0, 10) };
    store.saveEpisode(next);
    res.json(next);
  });

  app.post("/api/episodes/:id/open-folder", (req, res) => {
    const ep = store.getEpisode(req.params.id as string);
    const pkg = req.query.what === "package" && ep.package ? safeJoin(root, ep.package.dir) : null;
    const r = safeJoin(root, "renders", req.params.id as string);
    const dir = pkg && fs.existsSync(pkg) ? pkg : fs.existsSync(r) ? r : safeJoin(root, "episodes", req.params.id as string);
    spawn("explorer.exe", [dir], { detached: true }).unref();
    res.json({ ok: true });
  });

  app.use("/files", express.static(safeJoin(root, "renders")));
  app.use("/api/autopilot", createAutopilot(root).router);
  // fichiers Remotion (voix, musique, SFX) servis depuis le PC : jamais publiés en ligne
  app.use("/static", express.static(safeJoin(root, "public")));

  app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    const status = /ENOENT/.test(err.message) ? 404 : /hors projet/.test(err.message) ? 400 : 500;
    res.status(status).json({ error: err.message });
  });

  return { app, queue };
};
