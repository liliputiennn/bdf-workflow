import { describe, expect, it } from "vitest";
import { eta } from "../app/production/Panels";
import type { JobView } from "../server/types";

const job = (progress: number | null, startedAt: number | null): JobView => ({ id: "x", episodeId: "e", kind: "render", status: "running", progress, label: "", log: [], startedAt });

describe("eta", () => {
  it("estime le temps restant d'après l'avancement", () => {
    expect(eta(job(0.25, 0), 60_000)).toBe("≈ 3 min 00 s restantes · 25 %");
  });
  it("attend un peu d'avancement avant d'estimer", () => {
    expect(eta(job(0.01, 0), 10_000)).toContain("calcul du temps restant");
    expect(eta(job(null, null), 0)).toBe("en attente…");
  });
});
