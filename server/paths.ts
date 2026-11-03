import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Joint des segments sous `root` et refuse toute sortie du dossier. */
export const safeJoin = (root: string, ...parts: string[]) => {
  const base = path.resolve(root);
  const p = path.resolve(base, ...parts);
  if (p !== base && !p.startsWith(base + path.sep)) throw new Error("chemin hors projet");
  return p;
};
