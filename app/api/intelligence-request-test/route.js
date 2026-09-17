import { POST } from '../intelligence-request/route.js';

export async function GET(request) {
  const url = new URL(request.url);
  if (url.searchParams.get('run') !== '1') {
    return new Response('Smoke test requires run=1', { status: 400 });
  }

  const payload = {
    question: url.searchParams.get('question') || 'What should we understand about the current Dangote IPO opportunity before deciding whether to participate or advise a client?',
    market: url.searchParams.get('market') || 'Nigeria / Dangote IPO',
    decision: url.searchParams.get('decision') || 'Understand participation, access, timing and commercial intelligence needs',
    useful: url.searchParams.get('useful') || 'A concise market pulse, key facts, unknowns, risks and next intelligence action'
  };

  const syntheticPost = new Request(request.url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });

  return POST(syntheticPost);
}
