import { runSaltReconstruction } from '../../../../kernel/salt_reconstruction_runtime';
import { saltKernelInput } from '../../../../data/salt_kernel_input_v0_1';

export const dynamic = 'force-dynamic';

export async function GET() {
  const state = runSaltReconstruction(saltKernelInput, new Date().toISOString());

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
      status: state.contradictions.some(c => c.evidence_ids.some(id => e.evidence_ids.includes(id)))
        ? 'CONTRADICTED' : 'ACCEPTED'
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
      question: 'Why does the 2024 Ghana→Benin quantity differ between reporters?',
      target: 'Bilateral transaction records',
      output: 'Resolved event set / explanation of discrepancy.'
    },
    {
      id: 'SCOUT-03B', title: 'Resolve transaction actors', priority: 'HIGH',
      question: 'Who imported the 100 t Ghana event and the 140 t India event?',
      target: 'Transaction-level records',
      output: 'Resolved importer / exporter identities.'
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
    unknowns: state.unknowns.map(x => ({ ...x, id: x.unknown_id })),
    contradictions: state.contradictions.map(x => ({ ...x, id: x.contradiction_id })),
    source: 'reconstruction-kernel-v0.1',
    runtime: 'node-kernel-adapter'
  }, {
    headers: { 'Cache-Control': 'no-store, max-age=0' }
  });
}
