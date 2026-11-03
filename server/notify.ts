import { spawn } from "node:child_process";
import type { Episode } from "./types";

/** Résumé d'un lot + notification Windows (toast) ; rien ne sort du PC. */

export type BatchResult = { id: string; ok: boolean; error?: string };
export type BatchSummary = {
  finishedAt: string;
  rendered: string[];
  errors: { id: string; error: string }[];
  /** passage le moins clair parmi les vidéos rendues */
  worst: { id: string; worstDb: number; medianDb: number; whisper: number } | null;
  text: string;
};

export const summarize = (results: BatchResult[], episodes: Pick<Episode, "id" | "metrics">[]): BatchSummary => {
  const rendered = results.filter((r) => r.ok).map((r) => r.id);
  const errors = results.filter((r) => !r.ok).map((r) => ({ id: r.id, error: r.error ?? "erreur" }));
  const measured = episodes.filter((e) => rendered.includes(e.id) && e.metrics).map((e) => ({ id: e.id, ...e.metrics! }));
  const worst = measured.sort((a, b) => a.worstDb - b.worstDb)[0] ?? null;
  const parts = [
    `${rendered.length} vidéo${rendered.length > 1 ? "s" : ""} rendue${rendered.length > 1 ? "s" : ""}`,
    errors.length ? `${errors.length} erreur${errors.length > 1 ? "s" : ""} (${errors.map((e) => e.id).join(", ")})` : "aucune erreur",
    worst ? `pire passage : ${worst.id} ${worst.worstDb} dB (médiane ${worst.medianDb} dB, Whisper ${worst.whisper} %)` : "",
  ].filter(Boolean);
  return { finishedAt: new Date().toISOString(), rendered, errors, worst, text: parts.join(" · ") };
};

/** Script PowerShell du toast : titre et texte passent par l'environnement (jamais interprétés). */
const TOAST = `
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t = $x.GetElementsByTagName('text')
$t.Item(0).AppendChild($x.CreateTextNode($env:BDF_TITLE)) > $null
$t.Item(1).AppendChild($x.CreateTextNode($env:BDF_BODY)) > $null
$n = [Windows.UI.Notifications.ToastNotification]::new($x)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($n)
`;

export const toast = (title: string, body: string) => {
  if (process.platform !== "win32" || process.env.BDF_NO_TOAST) return;
  const child = spawn("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", TOAST], {
    env: { ...process.env, BDF_TITLE: title.slice(0, 120), BDF_BODY: body.slice(0, 250) },
    windowsHide: true,
    stdio: "ignore",
  });
  child.on("error", () => {});
  child.unref();
};
