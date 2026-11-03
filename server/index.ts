import { createApp } from "./app";
import { ROOT } from "./paths";
import { findTools, health } from "./tools";

const tools = findTools(ROOT);
const { app, queue } = createApp({ root: ROOT, tools });
// au démarrage : vérifier les faits pas encore contrôlés (tout seul, sans clic)
import("./store").then(({ createStore }) => {
  const todo = createStore(ROOT).listIdeas().some((i) => i.facts.some((f) => f.check?.length && !f.verified));
  if (todo) import("./pipelines").then(({ verifyJob }) => queue.enqueue(verifyJob({ root: ROOT, store: createStore(ROOT), tools })));
});
app.listen(5181, "127.0.0.1", () => {
  console.log("API Console : http://127.0.0.1:5181");
  const missing = Object.entries(health(tools)).filter(([, ok]) => !ok).map(([k]) => k);
  if (missing.length) console.warn(`Outils manquants : ${missing.join(", ")}`);
});
