import fs from "node:fs";
import path from "node:path";
import { safeJoin } from "./paths";
import { provisionalTimings } from "../src/scenes/plan";
import type { Episode } from "./types";

/**
 * Index des épisodes « en données » (episodes/<id>/scenes.json) pour Remotion et la Console.
 * Remotion (webpack) et la Console (vite) ne partagent pas d'import dynamique : on génère donc
 * un fichier d'imports statiques, src/episodes/data-index.ts, réécrit seulement s'il change.
 */

type Line = { text: string };

export const DATA_INDEX = path.join("src", "episodes", "data-index.ts");

/** Épisodes qui ont un scenes.json (et un script). */
export const dataEpisodes = (root: string): Episode[] =>
  fs
    .readdirSync(safeJoin(root, "episodes"), { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .filter((id) => ["episode.json", "scenes.json", "script.json"].every((f) => fs.existsSync(safeJoin(root, "episodes", id, f))))
    .map((id) => JSON.parse(fs.readFileSync(safeJoin(root, "episodes", id, "episode.json"), "utf-8")) as Episode)
    .sort((a, b) => a.number - b.number);

const ident = (id: string) => id.replace(/[^a-zA-Z0-9]/g, "_");

export const renderDataIndex = (eps: Episode[]) => {
  const rel = (p: string) => `../../${p.replace(/\\/g, "/")}`;
  const imports = eps.flatMap((e) => {
    const v = ident(e.id);
    return [
      `import ${v}_ep from "${rel(`episodes/${e.id}/episode.json`)}";`,
      `import ${v}_script from "${rel(e.scriptFile)}";`,
      `import ${v}_timings from "${rel(e.timingsFile)}";`,
      `import ${v}_scenes from "${rel(`episodes/${e.id}/scenes.json`)}";`,
    ];
  });
  const rows = eps.map((e) => {
    const v = ident(e.id);
    return `  { meta: ${v}_ep, script: ${v}_script, timings: ${v}_timings as DataEntry["timings"], scenes: ${v}_scenes as unknown as DataEntry["scenes"] },`;
  });
  return [
    "// Fichier généré par la Console (server/dataIndex.ts) : ne pas modifier à la main.",
    'import type { DataEntry } from "../scenes/SceneRunner";',
    ...imports,
    "",
    "export const DATA_EPISODES: DataEntry[] = [",
    ...rows,
    "];",
    "",
  ].join("\n");
};

/** Régénère l'index ; crée des timings provisoires manquants. Renvoie true si le fichier a changé. */
export const writeDataIndex = (root: string): boolean => {
  const eps = dataEpisodes(root);
  for (const e of eps) {
    const tf = safeJoin(root, e.timingsFile);
    if (fs.existsSync(tf)) continue;
    const script = JSON.parse(fs.readFileSync(safeJoin(root, e.scriptFile), "utf-8")) as Line[];
    fs.mkdirSync(path.dirname(tf), { recursive: true });
    fs.writeFileSync(tf, JSON.stringify(provisionalTimings(script), null, 1) + "\n", "utf-8");
  }
  const file = safeJoin(root, DATA_INDEX);
  const next = renderDataIndex(eps);
  if (fs.existsSync(file) && fs.readFileSync(file, "utf-8") === next) return false;
  fs.writeFileSync(file, next, "utf-8");
  return true;
};
