/**
 * Rendu en lot, en ligne de commande : le même pipeline que la Console (calage si besoin, rendu,
 * mesure de clarté, couverture, paquet exports/<date>/<id>/). Seule source de vérité : l'état des épisodes.
 * Un verrou par épisode évite de calculer le même épisode que la Console au même moment.
 *
 * Usage : npm run batch                  (épisodes de la semaine en cours, pas encore rendus)
 *         npm run batch -- --id=apollo-13
 *         npm run batch -- --all         (tous les épisodes pas encore rendus)
 *         npm run batch -- --dry-run
 */
import { batchCandidates, batchJobs, weekEpisodeIds } from "../server/batch";
import { parseProgress, runStep, type JobDef } from "../server/jobs";
import { acquireLock } from "../server/lock";
import { summarize, toast, type BatchResult } from "../server/notify";
import { ROOT } from "../server/paths";
import type { Ctx } from "../server/pipelines";
import { createStore } from "../server/store";
import { findTools } from "../server/tools";

/** Exécute une tâche ici (sans la file de l'API) ; renvoie le message d'erreur ou null. */
const runInline = async (def: JobDef): Promise<string | null> => {
  const reason = def.skipIf?.();
  if (reason) {
    await def.onError?.(reason);
    return reason;
  }
  let log: string[] = [];
  for (const step of def.steps) {
    console.log(`  · ${step.label}`);
    let last = -1;
    const code = await runStep(step, (text) => {
      log = [...log, ...text.split(/\r|\n/).filter(Boolean)].slice(-40);
      const p = parseProgress(text);
      if (p !== null && Math.floor(p * 10) !== last) {
        last = Math.floor(p * 10);
        process.stdout.write(`\r    ${Math.round(p * 100)} %   `);
      }
    });
    process.stdout.write("\n");
    if (code !== 0) {
      await def.onError?.(log.slice(-15).join("\n"));
      return `${step.label} a échoué (code ${code}) : ${log.at(-1) ?? ""}`;
    }
  }
  await def.onSuccess?.();
  return null;
};

const main = async () => {
  const dryRun = process.argv.includes("--dry-run");
  const only = process.argv.find((a) => a.startsWith("--id="))?.slice("--id=".length);
  const ctx: Ctx = { root: ROOT, store: createStore(ROOT), tools: findTools(ROOT) };
  const ids = only ? [only] : process.argv.includes("--all") ? ctx.store.listEpisodes().map((e) => e.id) : weekEpisodeIds(ROOT);
  const candidates = batchCandidates(ctx, ids);
  if (candidates.length === 0) return console.log(only ? `« ${only} » : introuvable ou déjà rendu.` : "Rien à faire : tout est déjà rendu.");

  const results: BatchResult[] = [];
  for (const c of candidates) {
    const id = c.ep.id;
    if (c.skip) {
      console.error(`✗ ${id} : ${c.skip}`);
      results.push({ id, ok: false, error: c.skip });
      continue;
    }
    if (dryRun) {
      console.log(`○ ${id} : prêt (${c.needsAlign ? "calage + " : ""}rendu, voix ${c.ep.voice.chosen})`);
      continue;
    }
    let release: () => void;
    try {
      release = acquireLock(ROOT, id, "le lot (npm run batch)");
    } catch (e) {
      console.error(`✗ ${id} : ${(e as Error).message}`);
      results.push({ id, ok: false, error: (e as Error).message });
      continue;
    }
    const started = Date.now();
    try {
      let error: string | null = null;
      for (const def of batchJobs(ctx, c)) {
        console.log(`▶ ${id} : ${def.kind === "align" ? "calage" : "rendu"}`);
        error = await runInline(def);
        if (error) break;
      }
      if (error) {
        console.error(`✗ ${id} : ${error}`);
        results.push({ id, ok: false, error });
      } else {
        const pkg = ctx.store.getEpisode(id).package;
        console.log(`✓ ${id} → ${pkg?.dir ?? `renders/${id}`} (${Math.round((Date.now() - started) / 1000)} s)`);
        results.push({ id, ok: true });
      }
    } finally {
      release();
    }
  }
  if (dryRun) return;
  const s = summarize(results, ctx.store.listEpisodes());
  console.log(`\nRésumé : ${s.text}`);
  toast(s.errors.length ? "Lot terminé avec des erreurs" : "Lot terminé", s.text);
  if (s.errors.length) process.exitCode = 1;
};

main().catch((e) => {
  console.error(e);
  toast("Lot interrompu", String((e as Error).message ?? e));
  process.exitCode = 1;
});
