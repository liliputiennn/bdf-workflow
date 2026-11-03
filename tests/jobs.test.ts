import { describe, expect, it } from "vitest";
import { createQueue, parseProgress } from "../server/jobs";
import type { JobView } from "../server/types";

const node = process.execPath;
const cwd = process.cwd();

describe("parseProgress", () => {
  it("lit la dernière fraction n/total", () => {
    expect(parseProgress("Rendered 10/200\rRendered 50/200")).toBeCloseTo(0.25);
    expect(parseProgress("Encoded 2841/2841")).toBe(1);
    expect(parseProgress("rien")).toBeNull();
  });
});

describe("createQueue", () => {
  it("exécute les tâches une à une, dans l'ordre", async () => {
    const order: string[] = [];
    const q = createQueue(() => {});
    q.enqueue({ episodeId: "a", kind: "align", steps: [{ label: "a", cmd: node, args: ["-e", "setTimeout(()=>{},150)"], cwd }], onSuccess: () => { order.push("a"); } });
    q.enqueue({ episodeId: "b", kind: "align", steps: [{ label: "b", cmd: node, args: ["-e", "0"], cwd }], onSuccess: () => { order.push("b"); } });
    await q.idle();
    expect(order).toEqual(["a", "b"]);
    expect(q.list().map((j) => j.status)).toEqual(["done", "done"]);
  });

  it("passe en erreur et garde la fin du journal", async () => {
    let failed = "";
    const q = createQueue(() => {});
    q.enqueue({ episodeId: "a", kind: "render", steps: [{ label: "x", cmd: node, args: ["-e", "console.error('boom'); process.exit(2)"], cwd }], onError: (log) => { failed = log; } });
    await q.idle();
    expect(q.list()[0].status).toBe("error");
    expect(failed).toContain("boom");
  });

  it("n'exécute pas les étapes suivantes après un échec", async () => {
    const q = createQueue(() => {});
    q.enqueue({ episodeId: "a", kind: "render", steps: [
      { label: "1", cmd: node, args: ["-e", "process.exit(1)"], cwd },
      { label: "2", cmd: node, args: ["-e", "console.log('ne doit pas tourner')"], cwd },
    ] });
    await q.idle();
    expect(q.list()[0].log.join("\n")).not.toContain("ne doit pas tourner");
  });

  it("émet la progression", async () => {
    const seen: JobView[] = [];
    const q = createQueue((j) => seen.push({ ...j }));
    q.enqueue({ episodeId: "a", kind: "render", steps: [{ label: "r", cmd: node, args: ["-e", "console.log('Rendered 1/2'); console.log('Rendered 2/2')"], cwd }] });
    await q.idle();
    expect(seen.some((j) => j.progress !== null && j.progress > 0)).toBe(true);
    expect(seen.at(-1)?.status).toBe("done");
  });
});
