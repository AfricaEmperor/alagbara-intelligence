import { ContradictionSchema, FindingSchema } from "../domain/finding.js";
import type { Contradiction, Finding } from "../domain/finding.js";
import type { Claim } from "../domain/common.js";
import type { Observation } from "../domain/observation.js";
import type { ObservationSet } from "../domain/observationSet.js";
import { ProvenanceChainSchema } from "../domain/provenance.js";
import type { ProvenanceChain } from "../domain/provenance.js";
import type { Pulse } from "../domain/pulse.js";
import type { Signal } from "../domain/signal.js";
import type { Source } from "../domain/source.js";
import type { Context } from "./context.js";
import { computeEvidenceStrength } from "./evidence.js";
import { ProvenanceError } from "./errors.js";

/** Everything needed to resolve a Pulse back to its Sources. Read-only. */
export interface EvidenceStore {
  observationSets: readonly ObservationSet[];
  observations: readonly Observation[];
  signals: readonly Signal[];
  sources: readonly Source[];
}

const claimKey = (c: Claim): string => JSON.stringify([c.type, c.value]);

interface Resolved {
  sets: ObservationSet[];
  observations: Observation[];
}

function need<T>(found: T | undefined, what: string): T {
  if (found === undefined) throw new ProvenanceError(`Broken provenance chain: ${what}`);
  return found;
}

function resolvePulse(pulse: Pulse, store: EvidenceStore): Resolved {
  const sets = pulse.observation_set_ids.map((id) =>
    need(store.observationSets.find((s) => s.id === id), `ObservationSet ${id} (referenced by ${pulse.id}) not found`),
  );
  for (const s of sets) {
    if (s.subject_id !== pulse.subject_id) {
      throw new ProvenanceError(`ObservationSet ${s.id} subject ${s.subject_id} differs from Pulse subject ${pulse.subject_id}`);
    }
  }
  const observations = [...new Set(sets.flatMap((s) => s.observation_ids))].map((id) =>
    need(store.observations.find((o) => o.id === id), `Observation ${id} not found`),
  );
  return { sets, observations };
}

function sourcesFor(observations: readonly Observation[], store: EvidenceStore): { signals: Signal[]; sources: Source[] } {
  const signals = [...new Set(observations.map((o) => o.signal_id))].map((id) =>
    need(store.signals.find((s) => s.id === id), `Signal ${id} not found`),
  );
  const sources = [...new Set(signals.map((s) => s.source_id))].map((id) =>
    need(store.sources.find((s) => s.id === id), `Source ${id} not found`),
  );
  return { signals, sources };
}

/**
 * Produce one Finding per distinct claim in the Pulse. A Finding can only be
 * built from a Pulse whose full chain resolves to Sources in the store.
 * Claims are never combined across distinct claim keys.
 */
export function createFindings(
  pulse: Pulse,
  store: EvidenceStore,
  ctx: Context,
  contradictionsInput: readonly Contradiction[] = [],
): Finding[] {
  const contradictions = contradictionsInput.map((c) => ContradictionSchema.parse(c));
  const { observations } = resolvePulse(pulse, store);
  const known = new Set(observations.map((o) => o.id));
  for (const c of contradictions) {
    for (const id of c.observation_ids) {
      if (!known.has(id)) throw new ProvenanceError(`Contradiction ${c.id} references observation ${id} outside the Pulse`);
    }
  }

  const groups = new Map<string, Observation[]>();
  for (const o of observations) {
    const k = claimKey(o.claim);
    groups.set(k, [...(groups.get(k) ?? []), o]);
  }

  return [...groups.values()].map((group) => {
    const first = need(group[0], "empty claim group");
    const { sources } = sourcesFor(group, store);
    const ids = new Set(group.map((o) => o.id));
    const mine = contradictions.filter((c) => c.observation_ids.some((id) => ids.has(id)));
    const sourceTypes = [...new Set(sources.map((s) => s.type_id))].sort();
    return FindingSchema.parse({
      id: ctx.newId("fnd"),
      pulse_id: pulse.id,
      claim: first.claim,
      evidence: {
        source_types: sourceTypes,
        evidence_strength: computeEvidenceStrength({
          trusts: sources.map((s) => s.channel_trust),
          independentSourceTypes: sourceTypes.length,
          hasContradiction: mine.length > 0,
        }),
        contradictions: mine,
      },
    });
  });
}

/**
 * Resolve the full audit chain for a Finding:
 * Finding → Pulse → ObservationSet → Observation → Signal → Source → SourceType.
 * Throws ProvenanceError if any link is missing or inconsistent.
 */
export function traceProvenance(finding: Finding, pulse: Pulse, store: EvidenceStore): ProvenanceChain {
  if (finding.pulse_id !== pulse.id) {
    throw new ProvenanceError(`Finding ${finding.id} references Pulse ${finding.pulse_id}, not ${pulse.id}`);
  }
  const { sets, observations } = resolvePulse(pulse, store);
  const key = claimKey(finding.claim);
  const supporting = observations.filter((o) => claimKey(o.claim) === key);
  if (supporting.length === 0) throw new ProvenanceError(`No observation supports the claim of Finding ${finding.id}`);
  const { signals, sources } = sourcesFor(supporting, store);
  const sourceTypes = [...new Set(sources.map((s) => s.type_id))].sort();
  if (JSON.stringify(sourceTypes) !== JSON.stringify([...finding.evidence.source_types].sort())) {
    throw new ProvenanceError(`Finding ${finding.id} source_types do not match its resolved Sources`);
  }
  return ProvenanceChainSchema.parse({
    finding_id: finding.id,
    pulse_id: pulse.id,
    observation_set_ids: sets.map((s) => s.id),
    observation_ids: supporting.map((o) => o.id),
    signal_ids: signals.map((s) => s.id),
    source_ids: sources.map((s) => s.id),
    source_types: sourceTypes,
  });
}
