/**
 * Écrit l'état du workflow dans un fichier JSON statique (version cloud : publié après chaque étape, lu par la web app).
 *
 * Usage : npm run snapshot                     (écrit dist-console/live/snapshot.json)
 *         npm run snapshot -- --out=chemin.json
 * Joint aussi la fin du journal le plus récent (`log-tail`), pour suivre le déroulé sans accès au PC.
 */
import fs from "node:fs";
import path from "node:path";
import { createAutopilot } from "../server/autopilot";
import { ROOT } from "../server/paths";

const out = process.argv.find((a) => a.startsWith("--out="))?.slice(6) ?? path.join(ROOT, "dist-console", "live", "snapshot.json");
const ap = createAutopilot(ROOT);
const snap = ap.snapshot();
const last = snap.logs[0];
const data = { ...snap, logTail: last ? { nom: last.nom, lignes: ap.tail(last.nom, 150) } : null };
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(data));
console.log(`snapshot écrit : ${out} (${snap.episodes.length} épisodes, ${snap.alertes.length} alertes)`);
