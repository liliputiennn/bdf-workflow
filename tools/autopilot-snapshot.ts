/**
 * Écrit l'état du workflow dans un fichier JSON statique (version cloud : publié après chaque étape, lu par la web app).
 *
 * Usage : npm run snapshot                     (écrit dist-console/live/snapshot.json)
 *         npm run snapshot -- --out=chemin.json
 * Joint aussi la fin du journal le plus récent (`log-tail`), pour suivre le déroulé sans accès au PC.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createAutopilot } from "../server/autopilot";
import { ROOT } from "../server/paths";

const out = process.argv.find((a) => a.startsWith("--out="))?.slice(6) ?? path.join(ROOT, "dist-console", "live", "snapshot.json");
const ap = createAutopilot(ROOT);
const snap = ap.snapshot();
// Cloud (GH_REPO défini) : les vidéos et miniatures n'existent pas sur le disque, elles sont dans la release « stock » du dépôt.
if (process.env.GH_REPO) {
  try {
    const brut = execFileSync("gh", ["release", "view", "stock", "--repo", process.env.GH_REPO, "--json", "assets"], { encoding: "utf8" });
    const names = new Set((JSON.parse(brut).assets as { name: string }[]).map((a) => a.name));
    for (const e of snap.episodes) {
      e.video = e.video || names.has(`exports__${e.id}__${e.id}.mp4`);
      e.miniature = e.miniature || names.has(`exports__${e.id}__miniature.png`);
    }
  } catch (err) {
    console.warn("release « stock » illisible :", String((err as Error).message).slice(0, 120));
  }
}
const last = snap.logs[0];
const data = { ...snap, logTail: last ? { nom: last.nom, lignes: ap.tail(last.nom, 150) } : null };
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(data));
console.log(`snapshot écrit : ${out} (${snap.episodes.length} épisodes, ${snap.alertes.length} alertes)`);
