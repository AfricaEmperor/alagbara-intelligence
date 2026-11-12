import { describe, expect, it } from "vitest";
import {
  CapabilitySchema, ChannelSourceTypeSchema, ChannelTrustUnsetError, DEFAULT_CHANNEL_TRUST, FindingSchema,
  ObservationSchema, SourceSchema, defaultChannelTrust, ingestSignal, resolveChannelTrust, sourceTypeDefinition,
} from "../index.js";
import { NOW, testContext } from "./helpers.js";

const baseObservation = {
  id: "obs_1", signal_id: "sig_1", subject_candidate: "Stephanie",
  claim: { type: "creator_event", value: { event_type: "live_started" } },
  capability: "nlp", capability_confidence: 0.92, created_at: NOW,
};

describe("capability_confidence (numeric 0–1)", () => {
  it.each([0, 0.5, 0.92, 1])("accepts %s", (v) => {
    expect(ObservationSchema.safeParse({ ...baseObservation, capability_confidence: v }).success).toBe(true);
  });
  it.each(["high", "medium", "low", "0.5", 1.01, -0.01, Number.NaN, Number.POSITIVE_INFINITY, null])(
    "rejects %s",
    (v) => {
      expect(ObservationSchema.safeParse({ ...baseObservation, capability_confidence: v }).success).toBe(false);
    },
  );
  it("rejects evidence_strength or a generic confidence on an Observation", () => {
    expect(ObservationSchema.safeParse({ ...baseObservation, evidence_strength: "medium" }).success).toBe(false);
    expect(ObservationSchema.safeParse({ ...baseObservation, confidence: 0.9 }).success).toBe(false);
  });
});

describe("capability vocabulary", () => {
  it("retains nlp | ocr | vision", () => {
    expect(CapabilitySchema.options).toEqual(["nlp", "ocr", "vision"]);
  });
});

describe("Finding strictness", () => {
  const finding = {
    id: "f1", pulse_id: "p1", claim: { type: "t", value: 1 },
    evidence: { source_types: ["android_notification"], evidence_strength: "medium", contradictions: [] },
  };
  it("accepts evidence_strength and rejects a generic confidence", () => {
    expect(FindingSchema.safeParse(finding).success).toBe(true);
    expect(FindingSchema.safeParse({ ...finding, confidence: 0.9 }).success).toBe(false);
    expect(FindingSchema.safeParse({ ...finding, evidence: { ...finding.evidence, evidence_strength: 0.9 } }).success).toBe(false);
  });
});

describe("channel trust defaults (ADR-004)", () => {
  it.each([
    ["android_notification", "high"],
    ["user_upload", "medium"],
    ["screenshot", "medium"],
    ["shared_image", "low"],
  ] as const)("%s defaults to %s", (type, trust) => {
    expect(defaultChannelTrust(type)).toBe(trust);
    expect(resolveChannelTrust(type)).toBe(trust);
    expect(sourceTypeDefinition(type).default_channel_trust).toBe(trust);
  });

  it("covers every SourceType exactly once", () => {
    expect(Object.keys(DEFAULT_CHANNEL_TRUST).sort()).toEqual([...ChannelSourceTypeSchema.options].sort());
  });

  it("leaves api_response explicitly unset and invents no fallback", () => {
    expect(DEFAULT_CHANNEL_TRUST.api_response).toBeNull();
    expect(defaultChannelTrust("api_response")).toBeUndefined();
    expect(sourceTypeDefinition("api_response")).toEqual({ id: "api_response", type: "api_response" });
    expect(() => resolveChannelTrust("api_response")).toThrow(ChannelTrustUnsetError);
    expect(() => ingestSignal({ source: "api_response", content: "x" }, testContext())).toThrow(ChannelTrustUnsetError);
  });

  it("accepts an explicit trust for api_response and lets an explicit trust override a default", () => {
    const { source } = ingestSignal({ source: "api_response", content: "x", channel_trust: "low" }, testContext());
    expect(source.channel_trust).toBe("low");
    expect(resolveChannelTrust("screenshot", "low")).toBe("low");
  });

  it("rejects an unknown trust level and unknown source type", () => {
    expect(() => ingestSignal({ source: "screenshot", content: "x", channel_trust: "HIGH" }, testContext())).toThrow();
    expect(() => ingestSignal({ source: "tiktok_api_response", content: "x" }, testContext())).toThrow();
    expect(SourceSchema.safeParse({ id: "s", type_id: "screenshot", channel_trust: "medium", created_at: NOW, evidence_strength: "high" }).success).toBe(false);
  });
});

describe("Signal immutability", () => {
  it("freezes the ingested Source and Signal", () => {
    const { source, signal } = ingestSignal({ source: "android_notification", content: "hello" }, testContext());
    expect(Object.isFrozen(signal)).toBe(true);
    expect(Object.isFrozen(signal.payload)).toBe(true);
    expect(Object.isFrozen(source)).toBe(true);
    expect(() => { (signal as { source_id: string }).source_id = "x"; }).toThrow();
  });
});
