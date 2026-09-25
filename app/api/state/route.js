import { acquireComtrade, comtradeToKernelRecords } from '../../../../scout/comtrade_runtime';
import { runSaltReconstruction } from '../../../../kernel/salt_reconstruction_runtime';
import { saltKernelInput } from '../../../../data/salt_kernel_input_v0_1';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  let acquisition;
  let records;
  let acquisitionStatus = 'LIVE';

  try {
    acquisition = await acquireComtrade();
    records = comtradeToKernelRecords(acquisition);

    if (!records.length) {
      throw new Error('UN Comtrade returned no data rows');
    }
  } catch (error) {
    // Keep the endpoint observable during source outages, but never silently
    // promote the fixture to canonical live evidence.
    acquisitionStatus = 'SOURCE_UNAVAILABLE';
    acquisition = null;
    records = saltKernelInput;
  }

  const state = runSaltReconstruction(records, new Date().toISOString());

  const flows = state.tradeEvents
    .filter(e => e.product?.classification === 'aggregate')
    .map(e => ({
      id: e.event_id,
      type: 'aggregate',
      source: e.partner,
      destination: e.reporter,
      quantity: e.quantity?.value + ' ' + e.quantity?.unit,
      sourceLabel: e.evidence_ids[0],
      note: e.flow,
      status: 'ACCEPTED'
    }));

  const events = state.tradeEvents
    .filter(e => e.product?.classification !== 'aggregate')
    .map(e => ({
      id: e.event_id,
      exporter: e.exporter || 'UNKNOWN',
      importer: e.importer || 'UNKNOWN',
      origin: e.origin || 'UNKNOWN',
      destination: e.destination || 'UNKNOWN',
      quantity: e.quantity?.value + ' ' + e.quantity?.unit,
      product: e.product?.description || e.product?.hs_code || 'UNKNOWN',
      packaging: e.product?.packaging || 'UNKNOWN',
      date: e.period || 'UNKNOWN',
      source: e.evidence_ids[0],
      status: state.unknowns.some(u => u.context?.event_id === e.event_id) ? 'UNKNOWN' : 'ACCEPTED',
      reason: state.unknowns.find(u => u.context?.event_id === e.event_id)?.reason
    }));

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
      status: acquisitionStatus,
      source: acquisition?.source || 'UN Comtrade',
      query: acquisition?.query || {
        reporter: 204, period: 2024, hs: '2501', flow: 'M', partner: 0, partner2: 0
      },
      source_url: acquisition?.source_url || null,
      record_count: records.length
    },
    unknowns: state.unknowns.map(x => ({ ...x, id: x.unknown_id })),
    contradictions: state.contradictions.map(x => ({ ...x, id: x.contradiction_id })),
    source: 'reconstruction-kernel-v0.1',
    runtime: 'node-kernel-adapter'
  }, {
    headers: { 'Cache-Control': 'no-store, max-age=0' }
  });
}
