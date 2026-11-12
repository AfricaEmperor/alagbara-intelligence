import { describe, expect, it } from "vitest";
import { extractCreatorObservations, extractHashtagObservations, ingestSignal, ObservationSchema } from "../index.js";
import { testContext } from "./helpers.js";

function signalFor(content: string, ctx = testContext()) {
  return { ctx, signal: ingestSignal({ source: "android_notification", content }, ctx).signal };
}

describe("NLP extractors (Sprint 1 capability = nlp)", () => {
  it("CreatorExtractor emits nlp observations with numeric capability_confidence", () => {
    const { ctx, signal } = signalFor("Stephanie is LIVE on TikTok");
    const [o, ...rest] = extractCreatorObservations(signal, ctx);
    expect(rest).toEqual([]);
    expect(ObservationSchema.safeParse(o).success).toBe(true);
    expect(o).toMatchObject({ capability: "nlp", subject_candidate: "Stephanie", signal_id: signal.id });
    expect(typeof o!.capability_confidence).toBe("number");
  });

  it("CreatorExtractor emits nothing for unmatched text (no guessing)", () => {
    const { ctx, signal } = signalFor("Something unrelated happened");
    expect(extractCreatorObservations(signal, ctx)).toEqual([]);
  });

  it("HashtagExtractor normalizes and de-duplicates", () => {
    const { ctx, signal } = signalFor("Look #Baddie and #baddie plus #Boss");
    const out = extractHashtagObservations(signal, ctx);
    expect(out.map((o) => o.claim.value)).toEqual(["baddie", "boss"]);
    expect(out.every((o) => o.capability === "nlp")).toBe(true);
  });
});
