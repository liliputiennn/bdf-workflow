import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

export type Tools = { node: string; remotion: string; vite: string; firebase: string | null; bash: string; uv: string; ffmpeg: string; rushSorter: string };

const firstExisting = (cands: string[], fallback: string) => cands.find((c) => fs.existsSync(c)) ?? fallback;

export const findTools = (root: string): Tools => ({
  node: process.execPath,
  remotion: path.join(root, "node_modules", "@remotion", "cli", "remotion-cli.js"),
  vite: path.join(root, "node_modules", "vite", "bin", "vite.js"),
  firebase: [path.join(process.env.APPDATA ?? "", "npm", "node_modules", "firebase-tools", "lib", "bin", "firebase.js")].find((p) => fs.existsSync(p)) ?? null,
  bash: firstExisting(["C:\\Program Files\\Git\\bin\\bash.exe", "C:\\Program Files\\Git\\usr\\bin\\bash.exe"], "bash"),
  uv: "uv",
  ffmpeg: "ffmpeg",
  rushSorter: path.resolve(root, "..", "..", "rush-sorter"),
});

const runs = (cmd: string, args: string[]) => spawnSync(cmd, args, { windowsHide: true }).status === 0;

export const health = (t: Tools) => ({
  ffmpeg: runs(t.ffmpeg, ["-version"]),
  bash: runs(t.bash, ["--version"]),
  uv: runs(t.uv, ["--version"]),
  remotion: fs.existsSync(t.remotion),
  whisperVenv: fs.existsSync(path.join(t.rushSorter, ".venv")),
});
