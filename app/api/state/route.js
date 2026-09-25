import { runSaltReconstruction } from '../../../../kernel/salt_reconstruction_runtime';
import { saltKernelInput } from '../../../../data/salt_kernel_input_v0_1';

export const dynamic = 'force-dynamic';

export async function GET() {
  const state = runSaltReconstruction(saltKernelInput, new Date().toISOString());

  return Response.json({
    ...state,
    source: 'reconstruction-kernel-v0.1',
    runtime: 'node-kernel-adapter'
  }, {
    headers: {
      'Cache-Control': 'no-store, max-age=0'
    }
  });
}
