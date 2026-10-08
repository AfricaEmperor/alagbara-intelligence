import { createClient } from '@supabase/supabase-js';
import { createLoop, createPulse, mapEffect, resumeLoop, recordDecision, authorizeAction, recordOutcome, emitNextSignal, verifyAuditTrail } from '../../../empireOpsLoop.js';

function client(){const url=process.env.SUPABASE_URL||process.env.NEXT_PUBLIC_SUPABASE_URL||'https://hbcxiyyuqgjokvypqrqr.supabase.co';const key=process.env.SUPABASE_ANON_KEY||process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_2XRZBSdnfnDep4yQAwYeFA_K8MCWzas';return createClient(url,key);}
function json(body,status=200){return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'} });}
export async function OPTIONS(){return new Response(null,{status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type','Access-Control-Allow-Methods':'POST,OPTIONS'}});}
export async function POST(request){
 try{
  const body=await request.json(); const id=body?.request_id; const transition=body?.transition; const token=body?.empire_ops_token;
  if(!id||!token) return json({error:'request_id and empire_ops_token are required'},400);
  const db=client(); const {data:row,error}=await db.rpc('read_big_intelligence_empire_ops',{p_id:id,p_token:token});
  if(error||!row) return json({error:'case not found',detail:error?.message},404);
  let loop;
  if(row.empire_ops_events?.length) loop=resumeLoop({loop_id:row.empire_ops_loop_id,version:'0.1.0',state:row.empire_ops_state||{},events:row.empire_ops_events});
  else return json({error:'case has no EmpireOps loop'},409);
  if(transition==='human_decision') recordDecision(loop,body.payload||{});
  else if(transition==='execution') authorizeAction(loop,body.payload||{});
  else if(transition==='result') recordOutcome(loop,body.payload||{});
  else if(transition==='next_signal') emitNextSignal(loop,body.payload||{});
  else return json({error:'transition must be human_decision, execution, result, or next_signal'},400);
  loop.state.lifecycle=loop.status;
  const audit=verifyAuditTrail(loop);
  if(!audit.ok) return json({error:'audit verification failed',detail:audit.reason},500);
  const {data:updated,error:updateError}=await db.rpc('write_big_intelligence_empire_ops',{p_id:id,p_token:token,p_loop_id:loop.loop_id,p_status:loop.status,p_state:loop.state,p_events:loop.events});
  if(updateError||updated!==true) return json({error:'could not persist EmpireOps transition',detail:updateError?.message||'not authorized'},502);
  return json({request_id:id,transition,status:loop.status,loop_id:loop.loop_id,audit});
 }catch(error){return json({error:error.message||'EmpireOps transition failed'},409);}
}
