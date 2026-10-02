import test from 'node:test';
import assert from 'node:assert/strict';
import { buildAILEnvelope, validateAIL } from './runtime.js';

test('builds a valid AIL envelope from existing SCOUT and ANA payloads', () => {
  const ail = buildAILEnvelope({
    request: { id: 'REQ-1', question: 'What changed?', market: 'Nigeria' },
    scout: { observed_at: '2026-10-02T10:00:00Z', evidence: [{ source_url: 'https://example.org', source_title: 'Primary source', source_type: 'official', reliability: 'high', claim: 'The event is open' }] },
    intelligence: {
      pulse: 'The event is open.',
      facts: ['The event is open.'],
      unknowns: ['Subscription volume is not established.'],
      assumptions: ['Current status is derived from the latest source set.'],
      analysis: 'Evidence indicates an open event.',
      recommendation: 'Investigate the next verified update.',
      risks: ['The source may change after observation.'],
      confidence: 'high'
    }
  });
  const result = validateAIL(ail);
  assert.equal(result.ok, true, result.errors.join('; '));
  assert.equal(ail.claims[0].state, 'observed');
  assert.equal(ail.action.authorized, false);
  assert.equal(ail.action.executed, false);
});

test('rejects non-unknown claims without provenance', () => {
  const result = validateAIL({
    ail_version: '0.2.0',
    generated_at: '2026-10-02T10:00:00Z',
    request: { id: 'REQ-1' },
    evidence: [],
    claims: [{ id: 'CL-1', state: 'derived', evidence_ids: [] }],
    reasoning: { confidence: 'low', confidence_is_epistemic: true },
    action: null,
    invariants: {}
  });
  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /NO CLAIM WITHOUT PROVENANCE/);
});

test('keeps unknowns explicit instead of converting them to false', () => {
  const ail = buildAILEnvelope({
    request: { id: 'REQ-2' },
    scout: { observed_at: '2026-10-02T10:00:00Z', evidence: [] },
    intelligence: { unknowns: ['Missing data'] }
  });
  const unknown = ail.claims.find(x => x.state === 'unknown');
  assert.ok(unknown);
  assert.deepEqual(unknown.evidence_ids, []);
});