import fs from "node:fs";
import path from "node:path";
import { safeJoin } from "./paths";

/**
 * Verrou par épisode (renders/<id>/.verrou) : empêche le lot en ligne de commande et la Console
 * de calculer le même épisode en même temps. Un verrou laissé par un processus mort est ignoré.
 */

export type LockInfo = { pid: number; owner: string; since: string };

const alive = (pid: number) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return (e as NodeJS.ErrnoException).code === "EPERM";
  }
};

const lockFile = (root: string, id: string) => safeJoin(root, "renders", id, ".verrou");

export const lockHolder = (root: string, id: string): LockInfo | null => {
  const f = lockFile(root, id);
  if (!fs.existsSync(f)) return null;
  try {
    const info = JSON.parse(fs.readFileSync(f, "utf-8")) as LockInfo;
    return alive(info.pid) ? info : null;
  } catch {
    return null;
  }
};

/** Prend le verrou ou lève une erreur claire ; renvoie la fonction qui le libère. */
export const acquireLock = (root: string, id: string, owner: string): (() => void) => {
  const held = lockHolder(root, id);
  if (held && held.pid !== process.pid) throw new Error(`« ${id} » est déjà en cours dans ${held.owner} (depuis ${held.since.slice(11, 16)})`);
  const f = lockFile(root, id);
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, JSON.stringify({ pid: process.pid, owner, since: new Date().toISOString() }), "utf-8");
  return () => {
    const cur = lockHolder(root, id);
    if (!cur || cur.pid === process.pid) fs.rmSync(f, { force: true });
  };
};
