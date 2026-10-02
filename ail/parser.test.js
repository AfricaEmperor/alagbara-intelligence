import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAIL, validateAILProgram } from './parser.js';

test('parses the core AIL statements', () => {
  const program = parseAIL([
    'OBSERVE market:ipo.status = "open" @ EV-001',
    'UNKNOWN market:ipo.subscription_volume',
    'DERIVE CL-001 market:ipo.state = "active" FROM CL-001',
    'RELATE ED-001 issuer:Dangote -[issued]-> security:Dangote-IPO @ EV-001',
    'DECIDE ACT-001 Investigate subscription volume',
    'AUTHORIZE ACT-001 BY principal:operator',
    'EXECUTE ACT-001 RESULT queued'
  ].join('\n'));
  assert.equal(program.ok, true);
  const validation = validateAILProgram(program);
  assert.equal(validation.ok, true, JSON.stringify(validation.errors));
});

test('rejects an unproven relationship', () => {
  const program = parseAIL('RELATE ED-001 issuer:A -[works_with]-> issuer:B @ EV-999');
  const validation = validateAILProgram(program);
  assert.equal(validation.ok, false);
  assert.match(JSON.stringify(validation.errors), /NO EDGE WITHOUT PROVENANCE/);
});

test('blocks execution before authorization', () => {
  const program = parseAIL('EXECUTE ACT-001 RESULT queued');
  const validation = validateAILProgram(program);
  assert.equal(validation.ok, false);
  assert.match(JSON.stringify(validation.errors), /AUTHORIZE/);
});