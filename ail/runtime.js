const EPISTEMIC_STATES = Object.freeze([
  'observed', 'derived', 'unverified', 'unknown', 'contradiction'
]);

const ACTION_STATES = Object.freeze(['proposed', 'authorized', 'executed', 'rejected']);

function nonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function nextId(prefix, index) {
  return prefix + String(index + 1).padStart(3, '0');
}

export function buildAILEnvelope({ request, scout, intelligence }) {
  const sourceItems = Array.isArray(scout?.evidence) ? scout.evidence : [];
  const evidence = sourceItems.map((item, index) => ({
    id: item.evidence_id || nextId('EV-', index),
    source: {
      url: item.source_url || null,
      title: item.source_title || null,
      domain: item.source_domain || null,
      type: item.source_type || 'other',
      reliability: item.reliability || 'low',
      published_at: item.published_at || null
    },
    observed_at: scout?.observed_at || new Date().toISOString(),
    status: 'observed',
    claim: item.claim || null
  }));

  const evidenceIds = evidence.map(item => item.id);
  const claims = [];
  const addClaims = (items, state, predicate) => {
    for (const text of (Array.isArray(items) ? items : [])) {
      claims.push({
        id: nextId('CL-', claims.length),
        subject: 'request:' + (request?.id || 'unknown'),
        predicate,
        value: text,
        state,
        evidence_ids: state === 'unknown' ? [] : evidenceIds
      });
    }
  };

  addClaims(intelligence?.facts, 'observed', 'fact');
  addClaims(intelligence?.assumptions, 'derived', 'assumption');
  addClaims(intelligence?.unknowns, 'unknown', 'unknown');
  addClaims(intelligence?.risks, 'derived', 'risk');

  const action = nonEmptyString(intelligence?.recommendation)
    ? { id: 'ACT-001', state: 'proposed', intent: intelligence.recommendation, authorized: false, executed: false }
    : null;

  return {
    ail_version: '0.2.0',
    generated_at: new Date().toISOString(),
    request: {
      id: request?.id || null,
      question: request?.question || null,
      market: request?.market || null,
      decision: request?.decision || null
    },
    evidence,
    claims,
    pulse: nonEmptyString(intelligence?.pulse)
      ? { state: 'derived', value: intelligence.pulse, evidence_ids: evidenceIds }
      : null,
    reasoning: {
      analysis: intelligence?.analysis || null,
      confidence: intelligence?.confidence || null,
      confidence_is_epistemic: true,
      recommendation: intelligence?.recommendation || null
    },
    action,
    invariants: {
      confidence_is_not_intent: true,
      decay_is_not_deletion: true,
      decisions_are_not_authorization: true,
      proposals_are_not_execution: true
    }
  };
}

export function validateAIL(envelope) {
  const errors = [];
  const warnings = [];
  if (!envelope || typeof envelope !== 'object') return { ok: false, errors: ['AIL envelope must be an object'], warnings };
  if (envelope.ail_version !== '0.2.0') errors.push('Unsupported AIL version');

  const evidenceIds = new Set((Array.isArray(envelope.evidence) ? envelope.evidence : []).map(x => x?.id).filter(Boolean));
  for (const [i, item] of (Array.isArray(envelope.evidence) ? envelope.evidence : []).entries()) {
    if (!nonEmptyString(item?.id)) errors.push('Evidence #' + (i + 1) + ' has no id');
    if (!nonEmptyString(item?.source?.url)) errors.push('Evidence #' + (i + 1) + ' has no source URL');
    if (item?.status !== 'observed') errors.push('Evidence #' + (i + 1) + ' must be observed');
  }

  for (const [i, claim] of (Array.isArray(envelope.claims) ? envelope.claims : []).entries()) {
    if (!EPISTEMIC_STATES.includes(claim?.state)) errors.push('Claim #' + (i + 1) + ' has invalid epistemic state');
    const refs = Array.isArray(claim?.evidence_ids) ? claim.evidence_ids : [];
    if (claim?.state !== 'unknown' && refs.length === 0) errors.push('Claim #' + (i + 1) + ' violates NO CLAIM WITHOUT PROVENANCE');
    for (const ref of refs) if (!evidenceIds.has(ref)) errors.push('Claim #' + (i + 1) + ' references missing evidence ' + ref);
  }

  if (envelope.pulse && !['observed', 'derived'].includes(envelope.pulse.state)) errors.push('Pulse must be observed or derived');

  if (envelope.action) {
    if (!ACTION_STATES.includes(envelope.action.state)) errors.push('Invalid action state');
    if (envelope.action.state !== 'proposed' && envelope.action.authorized !== true) errors.push('Non-proposed action must carry explicit authorization');
    if (envelope.action.state !== 'executed' && envelope.action.executed === true) errors.push('Execution flag conflicts with action state');
  }

  if (envelope.reasoning?.confidence && !['low', 'medium', 'high'].includes(envelope.reasoning.confidence)) errors.push('Invalid confidence value');
  if (envelope.reasoning?.confidence_is_epistemic !== true) warnings.push('Confidence semantics are not explicitly marked epistemic');
  if (!Array.isArray(envelope.evidence) || envelope.evidence.length === 0) warnings.push('AIL envelope contains no evidence');

  return { ok: errors.length === 0, errors, warnings };
}

export { EPISTEMIC_STATES, ACTION_STATES };