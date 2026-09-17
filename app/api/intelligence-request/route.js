import { createClient } from '@supabase/supabase-js';

const SCOUT_SYSTEM = `You are SCOUT, the evidence-retrieval layer of ALAGBARA. Your job is to observe current external reality, not to analyze or recommend.

Use the web search tool. Search the user's economic question and prioritize primary and authoritative sources: regulators, exchanges, issuers, official disclosures, government sources, and clearly attributable market sources. Prefer recent information when the question is time-sensitive.

Return ONLY raw JSON:
{"observed_at":"ISO-8601 timestamp","evidence":[{"source_url":"URL","source_title":"title","source_domain":"domain","source_type":"official|regulator|exchange|issuer|market|other","published_at":"ISO-8601 or null","claim":"one factual claim directly supported by the source","excerpt":"short supporting excerpt or faithful paraphrase","reliability":"high|medium|low","evidence_status":"observed"}],"unknowns":["material information not established by the searched sources"]}

Rules:
- Do not invent URLs, quotations, dates, figures, or source titles.
- Evidence URLs must be sources actually returned/used by web search.
- Keep claims factual and attributable.
- Do not provide investment advice, recommendations, forecasts, or opinions.
- Preserve contradictions between sources rather than resolving them.
- Return up to 12 high-value evidence items.`;

const ANALYSIS_SYSTEM = `You are ANA, the intelligence reasoning layer of ALAGBARA.

SCOUT has already retrieved external evidence. Reason ONLY from the supplied evidence ledger and clearly labeled request context. Do not pretend to have independently verified anything outside the ledger.

BILINGUAL OUTPUT IS MANDATORY. Every human-readable value must contain BOTH languages in this exact pattern:
English text\nFR: Texte français
For array items, apply the same pattern to every item. English comes first; French is the faithful translation second.

Keep these separate:
OBSERVED — directly supported by evidence.
DERIVED — reasoned from observed evidence.
UNVERIFIED — claims/signals not sufficiently established.
UNKNOWN — missing information that could materially change the conclusion.
CONTRADICTIONS — material conflicts between sources; preserve them.

Then produce:
PULSE — a timestamped normalized snapshot of the case state, grounded in the evidence.
ANALYSIS — concise reasoning from the Pulse/evidence.
RECOMMENDATION — a concrete next step for the requester. Do not present financial, legal, or regulatory certainty where evidence is incomplete.
RISKS — what could invalidate the reasoning or next step.
CONFIDENCE — low, medium, or high based on evidence quality.

Return ONLY raw JSON matching exactly:
{"pulse":"English text\\nFR: Texte français","facts":["English observed fact\\nFR: Fait observé français"],"unknowns":["English unknown\\nFR: Inconnue française"],"assumptions":["English derived/assumption\\nFR: Déduction/hypothèse française"],"analysis":"English analysis\\nFR: Analyse française","recommendation":"English next step\\nFR: Prochaine étape en français","risks":["English risk\\nFR: Risque français"],"confidence":"low|medium|high"}`;

export async function OPTIONS() { return new Response(null, { status: 204, headers: corsHeaders() }); }

export async function POST(request) {
  const headers = corsHeaders(); let requestId = null; let intake = null;
  try {
    const body = await request.json();
    const question = typeof body.question === 'string' ? body.question.trim() : '';
    const market = typeof body.market === 'string' ? body.market.trim() : '';
    const decision = typeof body.decision === 'string' ? body.decision.trim() : '';
    const useful = typeof body.useful === 'string' ? body.useful.trim() : '';
    if (!question || question.length > 4000) return json({ error: 'question is required and must be 1–4000 characters / la question est obligatoire et doit contenir 1 à 4000 caractères' }, 400, headers);

    const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    if (!supabaseUrl || !supabaseKey) return json({ error: 'Supabase environment is incomplete / environnement Supabase incomplet' }, 500, headers);
    const openaiKey = process.env.OPENAI_API_KEY;
    if (!openaiKey) return json({ error: 'OpenAI environment is incomplete / environnement OpenAI incomplet' }, 500, headers);

    const supabase = createClient(supabaseUrl, supabaseKey);
    const intakeResult = await supabase.rpc('create_big_intelligence_request', { p_question: question, p_market: market || null, p_decision: decision || null, p_useful: useful || null, p_source: 'big-consulting-ui' });
    intake = intakeResult.data;
    if (intakeResult.error || !intake?.id || !intake?.internal_nonce) return json({ error: 'Could not persist intelligence request / impossible d’enregistrer la demande d’intelligence', detail: intakeResult.error?.message || 'No request id returned' }, 502, headers);
    requestId = intake.id;
    await setStatus(supabase, requestId, intake.internal_nonce, 'scouting');

    const model = process.env.OPENAI_MODEL || 'gpt-5.6-sol';
    const scout = await callScout(openaiKey, { request: { id: requestId, question, market: market || null, decision: decision || null, useful: useful || null } }, model);
    const scoutParsed = parseScout(scout.outputText);
    if (!scoutParsed.ok) throw new Error(scoutParsed.reason);

    const sourceUrls = new Set(scout.sourceUrls);
    const evidence = scoutParsed.value.evidence
      .filter(item => sourceUrls.has(item.source_url))
      .map(item => ({ ...item, request_id: requestId }));
    if (!evidence.length) throw new Error('Scout returned no validated evidence / SCOUT n’a retourné aucune preuve validée');

    const { error: evidenceError } = await supabase.rpc('record_big_intelligence_evidence', { p_id: requestId, p_nonce: intake.internal_nonce, p_evidence: evidence });
    if (evidenceError) throw new Error('Could not persist evidence ledger / impossible d’enregistrer le registre de preuves: ' + evidenceError.message);
    await setStatus(supabase, requestId, intake.internal_nonce, 'pulsed');

    const { data: recent, error: recentError } = await supabase.rpc('get_recent_big_intelligence_memory', { p_limit: 5 });
    if (recentError) throw new Error('Could not read intelligence memory / impossible de lire la mémoire d’intelligence: ' + recentError.message);

    await setStatus(supabase, requestId, intake.internal_nonce, 'analyzing');
    const raw = await callANA(openaiKey, JSON.stringify({ request: { id: requestId, question, market: market || null, decision: decision || null, useful: useful || null }, evidence_ledger: evidence, scout_unknowns: scoutParsed.value.unknowns || [], recent_intelligence_memory: recent || [] }), model);
    const parsed = parseAnalysis(raw); if (!parsed.ok) throw new Error(parsed.reason); const a = parsed.value;

    const { data: completed, error: completionError } = await supabase.rpc('complete_big_intelligence_request', { p_id: requestId, p_nonce: intake.internal_nonce, p_status: 'response_ready', p_pulse: a.pulse, p_facts: a.facts, p_unknowns: a.unknowns, p_assumptions: a.assumptions, p_analysis: a.analysis, p_recommendation: a.recommendation, p_risks: a.risks, p_confidence: a.confidence, p_outcome: null });
    if (completionError || completed !== true) throw new Error('Reasoning succeeded but persistence completion failed / le raisonnement a réussi mais la finalisation a échoué: ' + (completionError?.message || 'request could not be updated'));

    return json({ request_id: requestId, status: 'response_ready', scout: { observed_at: scoutParsed.value.observed_at, evidence_count: evidence.length, sources: evidence.map(({ request_id: _id, ...item }) => item) }, intelligence: a }, 200, headers);
  } catch (error) {
    console.error('[intelligence-request]', error);
    return json({ error: error.message || 'Intelligence processing failed after request persistence / échec du traitement après enregistrement', request_id: requestId }, 502, headers);
  }
}

async function callScout(apiKey, userContent, model) {
  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({ model, input: [{ role: 'system', content: [{ type: 'input_text', text: SCOUT_SYSTEM }] }, { role: 'user', content: [{ type: 'input_text', text: JSON.stringify(userContent) }] }], tools: [{ type: 'web_search', search_context_size: 'high' }], tool_choice: 'required', max_output_tokens: 2600 })
  });
  return parseOpenAIResponse(response, 'SCOUT');
}

async function callANA(apiKey, userContent, model) {
  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({ model, input: [{ role: 'system', content: [{ type: 'input_text', text: ANALYSIS_SYSTEM }] }, { role: 'user', content: [{ type: 'input_text', text: userContent }] }], max_output_tokens: 1800 })
  });
  const result = await parseOpenAIResponse(response, 'ANA');
  return result.outputText;
}

async function parseOpenAIResponse(response, stage) {
  if (!response.ok) {
    let detail = 'status ' + response.status;
    try { const data = await response.json(); if (data?.error?.message) detail = data.error.message; } catch (_) {}
    throw new Error(stage + ' OpenAI request failed / requête OpenAI échouée — ' + detail);
  }
  const data = await response.json();
  const outputText = typeof data.output_text === 'string' ? data.output_text : (data.output || []).flatMap(item => item.content || []).filter(part => part.type === 'output_text').map(part => part.text).join('\n');
  const sourceUrls = [];
  for (const item of data.output || []) {
    if (item.type !== 'web_search_call') continue;
    const sources = item.action?.sources || [];
    for (const source of sources) if (typeof source.url === 'string') sourceUrls.push(source.url);
  }
  return { outputText, sourceUrls: [...new Set(sourceUrls)] };
}

function parseScout(text) {
  const clean = String(text || '').replace(/```json|```/g, '').trim();
  try {
    const value = JSON.parse(clean);
    if (!value || typeof value !== 'object' || !Array.isArray(value.evidence)) return { ok: false, reason: 'Scout response was not a valid evidence object / réponse SCOUT invalide' };
    if (typeof value.observed_at !== 'string' || !value.observed_at.trim()) value.observed_at = new Date().toISOString();
    value.unknowns = Array.isArray(value.unknowns) ? value.unknowns : [];
    value.evidence = value.evidence.filter(item => item && typeof item === 'object' && typeof item.source_url === 'string' && typeof item.claim === 'string' && item.source_url.startsWith('http'));
    if (!value.evidence.length) return { ok: false, reason: 'Scout returned no usable evidence / SCOUT n’a retourné aucune preuve exploitable' };
    return { ok: true, value };
  } catch (error) { return { ok: false, reason: 'Scout response was not valid JSON / réponse SCOUT JSON invalide: ' + error.message }; }
}

function parseAnalysis(text) {
  const clean = String(text || '').replace(/```json|```/g, '').trim();
  try {
    const value = JSON.parse(clean);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return { ok: false, reason: 'model response was not an object / la réponse du modèle n’est pas un objet' };
    for (const field of ['facts','unknowns','assumptions','risks']) if (!Array.isArray(value[field])) return { ok:false, reason: field+' must be an array / doit être un tableau' };
    for (const field of ['pulse','analysis','recommendation']) if (typeof value[field] !== 'string' || !value[field].trim()) return { ok:false, reason: field+' must be a non-empty string / doit être une chaîne non vide' };
    if (!['low','medium','high'].includes(value.confidence)) return {ok:false,reason:'confidence must be low, medium, or high / doit être low, medium ou high'};
    return {ok:true,value};
  } catch (error) { return {ok:false,reason:'model response was not valid JSON / réponse JSON invalide: '+error.message}; }
}

function corsHeaders() { return {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type','Access-Control-Allow-Methods':'POST, OPTIONS','Content-Type':'application/json'}; }
function json(body,status,headers) { return new Response(JSON.stringify(body), {status,headers}); }
