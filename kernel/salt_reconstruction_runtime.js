import crypto from 'node:crypto';

const UNKNOWN_ENDPOINTS = new Set(['UNKNOWN', 'UNKNOWN_EXPORTER', 'UNKNOWN_IMPORTER']);

function stableId(prefix, value) {
  const digest = crypto.createHash('sha256')
    .update(JSON.stringify(value))
    .digest('hex').slice(0, 16).toUpperCase();
  return prefix + '_' + digest;
}

function makeEvidence(record) {
  return {
    evidence_id: stableId('EVP', { source: record.source, raw_record: record.raw_record }),
    source: record.source,
    source_type: record.source_type,
    retrieved_at: record.retrieved_at,
    raw_record: record.raw_record,
    observations: record.observations,
    provenance: record.provenance || {},
    epistemic_status: 'OBSERVED',
    confidence: record.confidence || 'HIGH'
  };
}

function makeEvent(ev) {
  const o = ev.observations;
  return {
    event_id: stableId('TE', ev.evidence_id),
    event_type: 'TRADE_EVENT',
    reporter: o.reporter ?? null, partner: o.partner ?? null,
    exporter: o.exporter ?? null, importer: o.importer ?? null,
    origin: o.origin ?? null, destination: o.destination ?? null,
    entry_point: o.entry_point ?? null, period: o.period ?? null, flow: o.flow ?? null,
    product: o.product || {}, quantity: o.quantity || {},
    trade_value: o.trade_value || {}, attributes: o.attributes || {},
    evidence_ids: [ev.evidence_id], epistemic_status: 'OBSERVED'
  };
}

function makeProposal(event) {
  const a = event.attributes;
  return {
    proposal_id: stableId('GP', {
      subject: a.graph_subject, predicate: a.graph_predicate, object: a.graph_object, event_id: event.event_id
    }),
    subject: a.graph_subject, predicate: a.graph_predicate, object: a.graph_object,
    status: 'PROPOSED', evidence_ids: event.evidence_ids,
    attributes: { quantity: event.quantity, trade_value: event.trade_value, product: event.product },
    event_id: event.event_id
  };
}

function validate(proposals, evidenceById) {
  const accepted = [], unknown = [], contradictions = [];
  for (const p of proposals) {
    const missing = p.evidence_ids.filter(id => !evidenceById.has(id));
    const unresolved = UNKNOWN_ENDPOINTS.has(p.subject) || UNKNOWN_ENDPOINTS.has(p.object);
    if (unresolved || !p.evidence_ids.length || missing.length) {
      p.status = 'UNKNOWN';
      unknown.push({
        proposal: p,
        reason: unresolved ? 'UNRESOLVED_ENDPOINT' : (missing.length ? 'MISSING_EVIDENCE' : 'NO_EVIDENCE'),
        missing_evidence_ids: missing
      });
    } else {
      p.status = 'ACCEPTED';
      accepted.push(p);
    }
  }
  const groups = new Map();
  for (const p of accepted) {
    const key = [p.subject, p.predicate, p.object].join('|');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(p);
  }
  for (const group of groups.values()) {
    const attrs = new Set(group.flatMap(p => Object.keys(p.attributes || {})));
    for (const attribute of attrs) {
      const values = group.filter(p => attribute in p.attributes)
        .map(p => ({ proposal_id: p.proposal_id, value: p.attributes[attribute] }));
      if (new Set(values.map(v => JSON.stringify(v.value))).size > 1) {
        contradictions.push({
          subject: group[0].subject, predicate: group[0].predicate, object: group[0].object,
          attribute, status: 'CONTRADICTED', values,
          evidence_ids: [...new Set(group.flatMap(p => p.evidence_ids))].sort(),
          possible_explanations: [],
          next_evidence: ['Reconstruct bilateral transaction records and test timing, duplication and classification.']
        });
      }
    }
  }
  return { accepted, unknown, contradictions };
}

export function runSaltReconstruction(records, asOf = new Date().toISOString()) {
  const evidence = records.map(makeEvidence);
  const evidenceById = new Map(evidence.map(e => [e.evidence_id, e]));
  const tradeEvents = evidence.map(makeEvent);
  const graphProposals = tradeEvents.map(makeProposal);
  const validation = validate(graphProposals, evidenceById);
  const unknowns = validation.unknown.map((x, i) => ({
    unknown_id: 'UNK-' + String(i + 1).padStart(4, '0'),
    subject: x.proposal.subject, field: 'actor', status: 'OPEN',
    reason: x.reason, importance: 'HIGH',
    next_evidence: ['Resolve the unresolved actor or missing evidence at transaction level.'],
    context: { proposal_id: x.proposal.proposal_id, event_id: x.proposal.event_id }
  }));
  const contradictions = validation.contradictions.map((x, i) => ({
    contradiction_id: 'CON-' + String(i + 1).padStart(4, '0'), ...x
  }));
  const canonicalGraph = {
    nodes: [...new Set(validation.accepted.flatMap(p => [p.subject, p.object]))]
      .map(id => ({ id, kind: 'ACTOR' })),
    edges: validation.accepted
  };
  const pulse = {
    pulse_id: 'SALT-PULSE-' + asOf.replace(/[:.-]/g, ''),
    version: '0.1', subject: 'WEST_AFRICA_SALT_TRADE', as_of: asOf,
    facts: {
      canonical_nodes: canonicalGraph.nodes.length,
      canonical_edges: canonicalGraph.edges.length,
      observed_events: tradeEvents.length,
      evidence_passports: evidence.length
    },
    observed: tradeEvents, derived: [], routes: [], prices: [], demand: [],
    contradictions, unknowns,
    next_evidence: unknowns.map(x => x.next_evidence),
    confidence: { canonical_graph: 'SOURCE_BOUNDED', commercial_interpretation: 'NOT_ASSESSED' }
  };
  return {
    title: 'SALT INTELLIGENCE', version: 'RECONSTRUCTION KERNEL v0.1',
    status: 'KERNEL_GENERATED', dataPeriod: '2024', asOf,
    evidencePassports: evidence, tradeEvents, graphProposals,
    validation: {
      accepted: validation.accepted.map(p => p.proposal_id),
      unknown: validation.unknown.map(x => x.proposal.proposal_id),
      contradicted: contradictions.map(x => x.contradiction_id)
    },
    canonicalGraph, unknowns, contradictions, pulse
  };
}
