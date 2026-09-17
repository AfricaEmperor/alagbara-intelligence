import { createClient } from '@supabase/supabase-js';

const ANALYSIS_SYSTEM = `You are ALAGBARA, the commercial intelligence substrate behind BIG Consulting.

Turn a real economic-intent request into decision-grade intelligence without pretending uncertainty is certainty.

Keep these separate:
FACTS — explicitly stated or directly verifiable from the request/context.
UNKNOWNS — missing information that could materially change the conclusion.
ASSUMPTIONS — inferences used to reason despite missing information.

Then produce:
ANALYSIS — concise reasoning from the evidence.
RECOMMENDATION — a concrete next step for the requester. Do not present financial, legal, or regulatory certainty where evidence is incomplete.
RISKS — what could invalidate the recommendation.
CONFIDENCE — low, medium, or high based on evidence quality.
PULSE — one-sentence normalized restatement of the economic-intent request.

Return ONLY raw JSON matching exactly:
{"pulse":"...","facts":["..."],"unknowns":["..."],"assumptions":["..."],"analysis":"...","recommendation":"...","risks":["..."],"confidence":"low|medium|high"}`;

export async function OPTIONS() { return new Response(null, { status: 204, headers: corsHeaders() }); }

export async function POST(request) {
  const headers = corsHeaders();
  try {
    const body = await request.json();
    const question = typeof body.question === 'string' ? body.question.trim() : '';
    const market = typeof body.market === 'string' ? body.market.trim() : '';
    const decision = typeof body.decision === 'string' ? body.decision.trim() : '';
    const useful = typeof body.useful === 'string' ? body.useful.trim() : '';

    if (!question || question.length > 4000) return json({ error: 'question is required and must be 1–4000 characters' }, 400, headers);

    const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    if (!supabaseUrl || !supabaseKey) return json({ error: 'Supabase environment is incomplete' }, 500, headers);

    const supabase = createClient(supabaseUrl, supabaseKey);
    const { data: intake, error: intakeError } = await supabase.rpc('create_big_intelligence_request', {
      p_question: question,
      p_market: market || null,
      p_decision: decision || null,
      p_useful: useful || null,
      p_source: 'big-consulting-ui'
    });
    if (intakeError || !intake?.id || !intake?.internal_nonce) {
      return json({ error: 'Could not persist intelligence request', detail: intakeError?.message || 'No request id returned' }, 502, headers);
    }

    const requestId = intake.id;
    const openaiKey = process.env.OPENAI_API_KEY;
    if (!openaiKey) {
      return json({ request_id: requestId, status: 'received', next: 'intelligence_processing_pending' }, 202, headers);
    }

    const { data: recent, error: recentError } = await supabase.rpc('get_recent_big_intelligence_memory', { p_limit: 5 });
    if (recentError) throw new Error('Could not read intelligence memory: ' + recentError.message);

    const raw = await callOpenAI(openaiKey, JSON.stringify({
      request: { id: requestId, question, market: market || null, decision: decision || null, useful: useful || null },
      recent_intelligence_memory: recent || []
    }));
    const parsed = parseAnalysis(raw);
    if (!parsed.ok) throw new Error(parsed.reason);
    const a = parsed.value;

    const { data: completed, error: completionError } = await supabase.rpc('complete_big_intelligence_request', {
      p_id: requestId,
      p_nonce: intake.internal_nonce,
      p_status: 'response_ready',
      p_pulse: a.pulse,
      p_facts: a.facts,
      p_unknowns: a.unknowns,
      p_assumptions: a.assumptions,
      p_analysis: a.analysis,
      p_recommendation: a.recommendation,
      p_risks: a.risks,
      p_confidence: a.confidence,
      p_outcome: null
    });
    if (completionError || completed !== true) throw new Error('Reasoning succeeded but persistence completion failed: ' + (completionError?.message || 'request could not be updated'));

    return json({ request_id: requestId, status: 'response_ready', intelligence: a }, 200, headers);
  } catch (error) {
    console.error('[intelligence-request]', error);
    return json({ error: error.message || 'Intelligence processing failed after request persistence' }, 502, headers);
  }
}

async function callOpenAI(apiKey, userContent) {
  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: 'gpt-5.6-sol',
      input: [
        { role: 'system', content: [{ type: 'input_text', text: ANALYSIS_SYSTEM }] },
        { role: 'user', content: [{ type: 'input_text', text: userContent }] }
      ],
      max_output_tokens: 1400
    })
  });
  if (!response.ok) {
    let detail = 'status ' + response.status;
    try { const data = await response.json(); if (data?.error?.message) detail = data.error.message; } catch (_) {}
    throw new Error('OpenAI request failed — ' + detail);
  }
  const data = await response.json();
  if (typeof data.output_text === 'string') return data.output_text;
  return (data.output || []).flatMap((item) => item.content || []).filter((part) => part.type === 'output_text').map((part) => part.text).join('\n');
}

function parseAnalysis(text) {
  const clean = String(text || '').replace(/```json|```/g, '').trim();
  try {
    const value = JSON.parse(clean);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return { ok: false, reason: 'model response was not an object' };
    for (const field of ['facts', 'unknowns', 'assumptions', 'risks']) if (!Array.isArray(value[field])) return { ok: false, reason: field + ' must be an array' };
    for (const field of ['pulse', 'analysis', 'recommendation']) if (typeof value[field] !== 'string' || !value[field].trim()) return { ok: false, reason: field + ' must be a non-empty string' };
    if (!['low', 'medium', 'high'].includes(value.confidence)) return { ok: false, reason: 'confidence must be low, medium, or high' };
    return { ok: true, value };
  } catch (error) { return { ok: false, reason: 'model response was not valid JSON: ' + error.message }; }
}

function corsHeaders() {
  return { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Content-Type': 'application/json' };
}
function json(body, status, headers) { return new Response(JSON.stringify(body), { status, headers }); }
