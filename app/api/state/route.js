import { acquireComtrade, comtradeToKernelRecords } from '../../../../scout/comtrade_runtime';
import { runSaltReconstruction } from '../../../kernel/salt_reconstruction_runtime';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  let acquisition;

  try {
    acquisition = await acquireComtrade();
  } catch (error) {
    return Response.json({
      status: 'SOURCE_UNAVAILABLE',
      source: 'UN Comtrade',
      error: error.message,
      kernel: 'NOT_EXECUTED',
      fixture_fallback: false
    }, {
      status: 503,
      headers: { 'Cache-Control': 'no-store, max-age=0' }
    });
  }

  const records = comtradeToKernelRecords(acquisition);
  if (!records.length) {
    return Response.json({
      status: 'SOURCE_EMPTY',
      source: 'UN Comtrade',
      kernel: 'NOT_EXECUTED',
      fixture_fallback: false
    }, {
      status: 502,
      headers: { 'Cache-Control': 'no-store, max-age=0' }
    });
  }

  const state = runSaltReconstruction(records, new Date().toISOString());

  const flows = state.tradeEvents.map(e => ({
    id: e.event_id,
    type: 'aggregate',
    source: e.partner,
    destination: e.reporter,
    quantity: e.quantity?.value + ' ' + e.quantity?.unit,
    sourceLabel: e.evidence_ids[0],
    note: e.flow,
    status: 'ACCEPTED'
  }));

  const events = [];
  const nextScout = [
    {
      id: 'SCOUT-03A', title: 'Ghana contradiction', priority: 'HIGH',
      question: 'Compare the direct Benin Comtrade record with the Ghana mirror.',
      target: 'Bilateral Comtrade acquisition',
      output: 'Reporter-to-mirror comparison.'
    },
    {
      id: 'SCOUT-03B', title: 'Decompose aggregate flows', priority: 'HIGH',
      question: 'Which transaction-level records explain the aggregate partner flows?',
      target: 'Transaction-level trade evidence',
      output: 'Actor + product + transaction structure.'
    },
    {
      id: 'SCOUT-03C', title: 'India transaction layer', priority: 'MEDIUM',
      question: 'What buyers, suppliers, formats and prices sit behind the India flow?',
      target: 'Transaction records',
      output: 'Actor + product + price + corridor evidence.'
    },
    {
      id: 'SCOUT-03D', title: 'Senegal / Egypt decomposition', priority: 'MEDIUM',
      question: 'How do the aggregate flows decompose into transactions?',
      target: 'Transaction-level trade evidence',
      output: 'Counterparty and transaction structure.'
    }
  ];

  return Response.json({
    ...state,
    flows,
    events,
    nextScout,
    acquisition: {
      status: 'LIVE',
      source: acquisition.source,
      query: acquisition.query,
      source_url: acquisition.source_url,
      record_count: records.length
    },
    unknowns: state.unknowns.map(x => ({ ...x, id: x.unknown_id })),
    contradictions: state.contradictions.map(x => ({ ...x, id: x.contradiction_id })),
    source: 'reconstruction-kernel-v0.1',
    runtime: 'node-kernel-adapter',
    fixture_fallback: false
  }, {
    headers: { 'Cache-Control': 'no-store, max-age=0' }
  });
}
