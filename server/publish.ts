import fs from "node:fs";
import path from "node:path";
import { safeJoin } from "./paths";
import type { Episode, Metrics } from "./types";

/**
 * Paquet de publication : exports/<date>/<id>/ avec la vidéo, la couverture, le texte à coller
 * et une fiche de contrôle. Rien n'est envoyé : la publication reste manuelle.
 */

export const TARGETS = { medianDb: 25, whisper: 90 };

/** Texte à coller dans l'appli (description + question + hashtags), tiré de POST.md. */
export const publicationText = (postMd: string) => {
  const desc = /\*\*Description\*\*\s*\n([\s\S]*?)(\n\s*\n|\n\*\*|$)/.exec(postMd)?.[1].trim() ?? "";
  const tags = /\*\*Hashtags\*\*\s*(.+)/.exec(postMd)?.[1].trim() ?? "";
  return [desc, tags].filter(Boolean).join("\n\n") + "\n";
};

const fmtDuration = (s: number) => `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, "0")} s`;

export const controlSheet = (ep: Episode, durationS: number | null, m: Metrics | null) => {
  const ok = (b: boolean) => (b ? "OK " : "À REVOIR");
  return [
    `FICHE DE CONTRÔLE — ${ep.title}`,
    `Épisode ${ep.number} · ${ep.id} · compte ${ep.channel}`,
    "",
    `Durée : ${durationS ? fmtDuration(durationS) : "inconnue"}`,
    m
      ? [
          `Clarté voix/fond (écart médian) : ${m.medianDb} dB  [${ok(m.medianDb > TARGETS.medianDb)}] (visé > ${TARGETS.medianDb} dB)`,
          `Pire passage : ${m.worstDb} dB`,
          `Compréhension (Whisper) : ${m.whisper} %  [${ok(m.whisper >= TARGETS.whisper)}] (visé ≥ ${TARGETS.whisper} %)`,
        ].join("\n")
      : "Métriques de clarté : non mesurées (relancer le rendu)",
    "",
    "À cocher au moment de publier :",
    "[ ] Étiquette « contenu généré par IA » si la plateforme la demande (voix de synthèse)",
    "[ ] Couverture choisie (cover.png)",
    "[ ] Texte collé (texte.txt), question en commentaire épinglé si besoin",
    "[ ] Aucune marque ni logo réel à l'écran",
    "[ ] Case « publié » cochée dans la Console",
    "",
  ].join("\n");
};

/** Date du paquet : le jour prévu dans la semaine la plus récente qui contient l'épisode, sinon aujourd'hui. */
export const packageDate = (root: string, id: string, today = new Date()) => {
  const dir = safeJoin(root, "weeks");
  if (fs.existsSync(dir))
    for (const f of fs.readdirSync(dir).filter((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n)).sort().reverse()) {
      const w = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")) as { start: string; slots: { episode?: string }[] };
      const i = w.slots.findIndex((s) => s.episode === id);
      if (i >= 0) {
        const d = new Date(`${w.start}T12:00:00Z`);
        d.setUTCDate(d.getUTCDate() + i);
        return d.toISOString().slice(0, 10);
      }
    }
  return today.toISOString().slice(0, 10);
};

/** Copie ou lien dur (même disque : pas de place perdue pour une vidéo de 50 Mo). */
const place = (src: string, dst: string) => {
  fs.rmSync(dst, { force: true });
  try {
    fs.linkSync(src, dst);
  } catch {
    fs.copyFileSync(src, dst);
  }
};

export const buildPackage = (root: string, ep: Episode, date = packageDate(root, ep.id)) => {
  const renders = safeJoin(root, "renders", ep.id);
  const video = path.join(renders, `${ep.id}.mp4`);
  if (!fs.existsSync(video)) throw new Error("vidéo pas encore rendue");
  const dir = safeJoin(root, "exports", date, ep.id);
  fs.mkdirSync(dir, { recursive: true });
  place(video, path.join(dir, `${ep.id}.mp4`));
  const cover = path.join(renders, "cover.png");
  if (fs.existsSync(cover)) place(cover, path.join(dir, "cover.png"));
  const post = safeJoin(root, "episodes", ep.id, "POST.md");
  fs.writeFileSync(path.join(dir, "texte.txt"), fs.existsSync(post) ? publicationText(fs.readFileSync(post, "utf-8")) : `${ep.title}\n`, "utf-8");
  const timings = safeJoin(root, ep.timingsFile);
  const dur = fs.existsSync(timings) ? (JSON.parse(fs.readFileSync(timings, "utf-8")) as { total: number }).total : null;
  fs.writeFileSync(path.join(dir, "fiche-controle.txt"), controlSheet(ep, dur, ep.metrics), "utf-8");
  return { dir: path.relative(root, dir).replace(/\\/g, "/"), date };
};
