import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const intake = readFileSync(new URL('../app/api/intelligence-request/route.js', import.meta.url), 'utf8');
const empireOps = readFileSync(new URL('../app/api/empire-ops/route.js', import.meta.url), 'utf8');
const migration = readFileSync(new URL('../supabase/migrations/20261009000000_security_boundary_v1.sql', import.meta.url), 'utf8');

test('intelligence endpoint uses only server-side service-role credentials', () => {
  assert.match(intake, /SUPABASE_SERVICE_ROLE_KEY/);
  assert.doesNotMatch(intake, /sb_publishable_[A-Za-z0-9_-]+/);
  assert.doesNotMatch(intake, /hbcxiyyuqgjokvypqrqr\.supabase\.co/);
});

test('intelligence endpoint does not expose internal nonce or EmpireOps token', () => {
  assert.match(intake, /randomUUID\(\)/);
  assert.doesNotMatch(intake, /token:\s*intake\.internal_nonce/);
  assert.doesNotMatch(intake, /recent_intelligence_memory/);
});

test('privileged EmpireOps endpoint authenticates and allowlists operators', () => {
  assert.match(empireOps, /auth\.getUser\(match\[1\]\)/);
  assert.match(empireOps, /ALAGBARA_OPERATOR_EMAILS/);
  assert.match(empireOps, /SUPABASE_SERVICE_ROLE_KEY/);
  assert.doesNotMatch(empireOps, /Access-Control-Allow-Origin.*\*/);
});

test('migration revokes public access and disables unscoped memory', () => {
  assert.match(migration, /revoke all on function public\.get_recent_big_intelligence_memory\(integer\) from public, anon, authenticated, service_role/i);
  assert.match(migration, /from public, anon, authenticated/i);
  assert.match(migration, /to service_role/i);
  assert.match(migration, /set search_path to ''/i);
});

test('EmpireOps initialization is one-time and server-token gated', () => {
  assert.match(migration, /empire_ops_token = coalesce\(empire_ops_token, p_token\)/i);
  assert.match(migration, /empire_ops_token = p_token or empire_ops_token is null/i);
  assert.match(migration, /length\(trim\(p_token\)\) < 32/i);
});
