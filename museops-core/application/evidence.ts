import type { EvidenceStrength, TrustLevel } from "../domain/common.js";

export interface EvidenceInputs {
  /** channel_trust of every supporting Source instance. */
  trusts: readonly TrustLevel[];
  /** Number of distinct *independent* source types supporting the claim. */
  independentSourceTypes: number;
  /** True when a recorded Contradiction touches a supporting observation. */
  hasContradiction: boolean;
}

/**
 * ADR-003 evidence rules (MVP, deterministic, no scoring):
 *  - low:    any contradiction, or only low-trust sources;
 *  - high:   two or more independent source types, none low-trust, no contradiction;
 *  - medium: otherwise (one reliable, direct source with no contradiction).
 * Independence is counted per source TYPE, not per capability or per Source row,
 * so repeated notifications from one channel do not inflate strength.
 */
export function computeEvidenceStrength(i: EvidenceInputs): EvidenceStrength {
  if (i.trusts.length === 0) throw new Error("Evidence requires at least one source");
  if (i.hasContradiction) return "low";
  if (i.trusts.every((t) => t === "low")) return "low";
  if (i.independentSourceTypes >= 2 && i.trusts.every((t) => t !== "low")) return "high";
  return "medium";
}
