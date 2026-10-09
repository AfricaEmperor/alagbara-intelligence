import { createClient } from '@supabase/supabase-js';
import { createLoop, createPulse, mapEffect, resumeLoop, recordDecision, authorizeAction, recordOutcome, emitNextSignal, verifyAuditTrail } from '../../../empireOpsLoop.js';

function env() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !anonKey || !serviceRoleKey) throw new Error('Server authentication configuration is incomplete');
  return { url, anonKey, serviceRoleKey };
}
function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
}
export async function OPTIONS() {
  return new Response(null, { status: 204, headers: { Allow: 'POST, OPTIONS' } });
}
async function authorizeOperator(request, cfg) {
  const authorization = request.headers.get('authorization') || '';
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (!match) return { ok: false, status: 401, error: 'Authentication required' };
  const authClient = createClient(cfg.url, cfg.anonKey, { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } });
  const { data, error } = await authClient.auth.getUser(match[1]);
  if (error || !data?.user?.id || !data.user.email || !data.user.email_confirmed_at) return { ok: false, status: 401, error: 'Invalid or unconfirmed session' };
  const allowlist = (process.env.ALAGBARA_OPERATOR_EMAILS || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
  if (!allowlist.length || !allowlist.includes(data.user.email.toLowerCase())) return { ok: false, status: 403, error: 'Operator access denied' };
  return { ok: true, user: data.user };
}
export async function POST(request) {
  let cfg;
  try { cfg = env(); } catch (error) { return json({ error: error.message }, 503); }
  let operator;
  try { operator = await authorizeOperator(request, cfg); }
  catch (_) { return json({ error: 'Authentication service unavailable' }, 503); }
  if (!operator.ok) return json({ error: operator.error }, operator.status);
  try {
    const rawBody = await request.text();
    if (rawBody.length > 16_384) return json({ error: 'Request body too large' }, 413);
    const body = JSON.parse(rawBody);
    const id = body?.request_id;
    const transition = body?.transition;
    if (typeof id !== 'string' || !id || id.length > 64) return json({ error: 'Valid request_id is required' }, 400);
    const allowedTransitions = new Set(['human_decision', 'execution', 'result', 'next_signal']);
    if (!allowedTransitions.has(transition)) return json({ error: 'Invalid transition' }, 400);

    const db = createClient(cfg.url, cfg.serviceRoleKey, { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } });
    const { data: tokenRow, error: tokenError } = await db.from('big_intelligence_requests').select('empire_ops_token').eq('id', id).maybeSingle();
    if (tokenError || !tokenRow?.empire_ops_token) return json({ error: 'Case not found or not initialized' }, 404);
    const token = tokenRow.empire_ops_token;
    const { data: row, error } = await db.rpc('read_big_intelligence_empire_ops', { p_id: id, p_token: token });
    if (error || !row) return json({ error: 'Case not found or unavailable' }, 404);
    let loop;
    if (row.empire_ops_events?.length) loop = resumeLoop({ loop_id: row.empire_ops_loop_id, version: '0.1.0', state: row.empire_ops_state || {}, events: row.empire_ops_events });
    else return json({ error: 'Case has no EmpireOps loop' }, 409);
    if (transition === 'human_decision') recordDecision(loop, body.payload || {});
    else if (transition === 'execution') authorizeAction(loop, body.payload || {});
    else if (transition === 'result') recordOutcome(loop, body.payload || {});
    else if (transition === 'next_signal') emitNextSignal(loop, body.payload || {});
    loop.state.lifecycle = loop.status;
    const audit = verifyAuditTrail(loop);
    if (!audit.ok) return json({ error: 'Audit verification failed' }, 500);
    const { data: updated, error: updateError } = await db.rpc('write_big_intelligence_empire_ops', { p_id: id, p_token: token, p_loop_id: loop.loop_id, p_status: loop.status, p_state: loop.state, p_events: loop.events });
    if (updateError || updated !== true) return json({ error: 'Could not persist EmpireOps transition' }, 502);
    return json({ request_id: id, transition, status: loop.status, loop_id: loop.loop_id, audit, actor_id: operator.user.id });
  } catch (error) {
    console.error('[empire-ops]', error);
    return json({ error: 'EmpireOps transition failed' }, 409);
  }
}
