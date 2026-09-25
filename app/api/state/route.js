import { saltState } from '../../../../data/salt_reconstruction_v0_1';

export const dynamic = 'force-dynamic';

export async function GET() {
  return Response.json({
    ...saltState,
    generatedAt: new Date().toISOString(),
    source: 'reconstruction-kernel-v0.1'
  }, {
    headers: {
      'Cache-Control': 'no-store, max-age=0'
    }
  });
}
