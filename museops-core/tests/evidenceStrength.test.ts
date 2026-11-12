import { describe, expect, it } from "vitest";
import {
  computeEvidenceStrength, createFindings, createObservationSets, createPulse, ingestSignal, extractCreatorObservations,
} from "../index.js";
import type { Contradiction } from "../index.js";
import { TIMEFRAME, testContext } from "./helpers.js";

describe("computeEvidenceStrength (ADR-003 MVP rules)", () => {
  it("single reliable source, no contradiction → medium", () => {
    expect(computeEvidenceStrength({ trusts: ["high"], independentSourceTypes: 1, hasContradiction: false })).toBe("medium");
    expect(computeEvidenceStrength({ trusts: ["medium"], independentSourceTypes: 1, hasContradiction: false })).toBe("medium");
  });
  it("two independent source types, none low-trust → high", () => {
    expect(computeEvidenceStrength({ trusts: ["high", "medium"], independentSourceTypes: 2, hasContradiction: false })).toBe("high");
  });
  it("contradiction or only low-trust sources → low", () => {
    expect(computeEvidenceStrength({ trusts: ["high", "high"], independentSourceTypes: 2, hasContradiction: true })).toBe("low");
    expect(computeEvidenceStrength({ trusts: ["low"], independentSourceTypes: 1, hasContradiction: false })).toBe("low");
  });
  it("repeated notifications from one channel do not inflate strength", () => {
    expect(computeEvidenceStrength({ trusts: ["high", "high", "high"], independentSourceTypes: 1, hasContradiction: false })).toBe("medium");
  });
  it("requires at least one source", () => {
    expect(() => computeEvidenceStrength({ trusts: [], independentSourceTypes: 0, hasContradiction: false })).toThrow();
  });
});

describe("evidence through the pipeline", () => {
  function build(sourceA: "android_notification" | "shared_image", sourceB?: "user_upload") {
    const ctx = testContext();
    const ing = [ingestSignal({ source: sourceA, content: "Stephanie is LIVE on TikTok" }, ctx)];
    if (sourceB) ing.push(ingestSignal({ source: sourceB, content: "Stephanie is LIVE on TikTok" }, ctx));
    const observations = ing.flatMap((i) => extractCreatorObservations(i.signal, ctx));
    const sets = createObservationSets(observations.map((observation) => ({ observation, subject_id: "sub_1" })), TIMEFRAME, ctx);
    const pulse = createPulse(sets, ctx);
    const store = { observationSets: sets, observations, signals: ing.map((i) => i.signal), sources: ing.map((i) => i.source) };
    return { ctx, pulse, store, observations };
  }

  it("two independent channels converge → one Finding with strength high and both source types", () => {
    const { ctx, pulse, store } = build("android_notification", "user_upload");
    const [f, ...rest] = createFindings(pulse, store, ctx);
    expect(rest).toEqual([]);
    expect(f!.evidence.evidence_strength).toBe("high");
    expect(f!.evidence.source_types).toEqual(["android_notification", "user_upload"]);
  });

  it("a low-trust channel alone → low", () => {
    const { ctx, pulse, store } = build("shared_image");
    expect(createFindings(pulse, store, ctx)[0]!.evidence.evidence_strength).toBe("low");
  });

  it("a preserved contradiction forces low and is kept on the Finding", () => {
    const { ctx, pulse, store, observations } = build("android_notification", "user_upload");
    const c: Contradiction = { id: "c1", observation_ids: observations.map((o) => o.id), description: "sources disagree" };
    const f = createFindings(pulse, store, ctx, [c])[0]!;
    expect(f.evidence.evidence_strength).toBe("low");
    expect(f.evidence.contradictions).toEqual([c]);
  });

  it("rejects a contradiction that references observations outside the Pulse", () => {
    const { ctx, pulse, store } = build("android_notification");
    expect(() => createFindings(pulse, store, ctx, [{ id: "c", observation_ids: ["a", "b"], description: "x" }])).toThrow();
  });
});
