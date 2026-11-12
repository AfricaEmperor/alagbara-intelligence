import { describe, expect, it } from "vitest";
import { FindingSchema, ProvenanceError, createFindings, traceProvenance } from "../index.js";
import { runCreatorPipeline } from "./helpers.js";

describe("provenance chain", () => {
  it("resolves Finding → Pulse → ObservationSet → Observation → Signal → Source", () => {
    const run = runCreatorPipeline("stephanie-live", { handle: "stephanie" });
    const findings = createFindings(run.pulse, run.store, run.ctx);
    expect(findings).toHaveLength(1);
    const finding = findings[0]!;

    expect(finding.pulse_id).toBe(run.pulse.id);
    expect(run.pulse.observation_set_ids).toEqual(run.sets.map((s) => s.id));
    expect(run.sets[0]!.observation_ids).toEqual(run.observations.map((o) => o.id));
    expect(run.observations[0]!.signal_id).toBe(run.signal.id);
    expect(run.signal.source_id).toBe(run.source.id);

    const chain = traceProvenance(finding, run.pulse, run.store);
    expect(chain).toEqual({
      finding_id: finding.id,
      pulse_id: run.pulse.id,
      observation_set_ids: [run.sets[0]!.id],
      observation_ids: [run.observations[0]!.id],
      signal_ids: [run.signal.id],
      source_ids: [run.source.id],
      source_types: ["android_notification"],
    });
  });

  it("uses evidence_strength 'medium' for a single reliable source with no contradiction", () => {
    const run = runCreatorPipeline("stephanie-live", { handle: "stephanie" });
    const finding = createFindings(run.pulse, run.store, run.ctx)[0]!;
    expect(finding.evidence).toEqual({
      source_types: ["android_notification"],
      evidence_strength: "medium",
      contradictions: [],
    });
    expect(finding).not.toHaveProperty("confidence");
  });

  it("makes a Finding impossible to construct without a valid Pulse reference", () => {
    const run = runCreatorPipeline("stephanie-live", { handle: "stephanie" });
    const good = createFindings(run.pulse, run.store, run.ctx)[0]!;

    // schema level: pulse_id is required and non-empty
    const withoutPulse: Record<string, unknown> = { ...good };
    delete withoutPulse.pulse_id;
    expect(FindingSchema.safeParse(withoutPulse).success).toBe(false);
    expect(FindingSchema.safeParse({ ...good, pulse_id: "" }).success).toBe(false);

    // runtime level: a Pulse whose chain does not resolve cannot yield a Finding
    const emptyStore = { ...run.store, observationSets: [] };
    expect(() => createFindings(run.pulse, emptyStore, run.ctx)).toThrow(ProvenanceError);
    const noSource = { ...run.store, sources: [] };
    expect(() => createFindings(run.pulse, noSource, run.ctx)).toThrow(ProvenanceError);

    // a Finding cannot be traced through a different Pulse
    const other = runCreatorPipeline("stephanie-live", { handle: "stephanie" });
    expect(() => traceProvenance(good, { ...other.pulse, id: "pulse_other" }, run.store)).toThrow(ProvenanceError);
  });
});
