import { createHash, randomUUID } from 'node:crypto';

export const LOOP_STAGES = ['SIGNAL','PULSE','EFFECT','DECISION','ACTION','OUTCOME','SIGNAL'];

function hashEvent(event) {
  const canonical = JSON.stringify({ id:event.id, sequence:event.sequence, stage:event.stage, at:event.at, actor:event.actor, payload:event.payload, prev_hash:event.prev_hash });
  return createHash('sha256').update(canonical).digest('hex');
}
function append(events, stage, payload, actor) {
  const previous = events.at(-1);
  const event = { id:randomUUID(), sequence:events.length+1, stage, at:new Date().toISOString(), actor, payload, prev_hash:previous?.hash ?? null };
  event.hash = hashEvent(event); events.push(event); return event;
}
export function createLoop({signal,source,actor='SCOUT'}) {
  if(!signal || !source) throw new Error('signal and source are required');
  const loop={loop_id:randomUUID(),version:'0.1.0',status:'SIGNAL_RECEIVED',state:{},events:[]};
  append(loop.events,'SIGNAL',{signal,source,verification:'UNVERIFIED'},actor); return loop;
}
export function createPulse(loop,{observed,facts=[],unknowns=[],assumptions=[],evidence=[]}) {
  assertStatus(loop,'SIGNAL_RECEIVED');
  const pulse={pulse_id:randomUUID(),observed,facts,unknowns,assumptions,evidence,status:unknowns.length?'OBSERVED_WITH_UNKNOWNS':'OBSERVED'};
  loop.state.pulse=pulse; append(loop.events,'PULSE',pulse,'PULSE'); loop.status='PULSE_CREATED'; return pulse;
}
export function mapEffect(loop,{effects,affected_nodes=[],propagation_paths=[],risks=[],opportunities=[]}) {
  assertStatus(loop,'PULSE_CREATED'); if(!Array.isArray(effects)||!effects.length) throw new Error('at least one effect is required');
  const effect={effect_id:randomUUID(),effects,affected_nodes,propagation_paths,risks,opportunities,causal_status:'HYPOTHESIS'};
  loop.state.effect=effect; append(loop.events,'EFFECT',effect,'ANA'); loop.status='EFFECT_MAPPED'; return effect;
}
export function recordDecision(loop,{choice,rationale='',decided_by,decided_at=new Date().toISOString()}) {
  assertStatus(loop,'EFFECT_MAPPED'); if(!['approve','reject','defer'].includes(choice)) throw new Error('invalid decision'); if(!decided_by) throw new Error('decided_by is required');
  const decision={decision_id:randomUUID(),choice,rationale,decided_by,decided_at}; loop.state.decision=decision; append(loop.events,'DECISION',decision,decided_by);
  loop.status=choice==='approve'?'DECISION_APPROVED':choice==='reject'?'DECISION_REJECTED':'DECISION_DEFERRED'; return decision;
}
export function authorizeAction(loop,{action,owner,due_at=null,authorization}) {
  assertStatus(loop,'DECISION_APPROVED'); if(!action||!owner||!authorization) throw new Error('action, owner, authorization required');
  const execution={action_id:randomUUID(),action,owner,due_at,authorization,execution_status:'AUTHORIZED'}; loop.state.action=execution; append(loop.events,'ACTION',execution,owner); loop.status='ACTION_AUTHORIZED'; return execution;
}
export function recordOutcome(loop,{status,observed_result,evidence=[],measured_impact=null,actor='FLYNN'}) {
  assertStatus(loop,'ACTION_AUTHORIZED'); if(!['success','partial','failed','unknown'].includes(status)) throw new Error('invalid outcome status');
  const outcome={outcome_id:randomUUID(),status,observed_result,evidence,measured_impact,actor}; loop.state.outcome=outcome; append(loop.events,'OUTCOME',outcome,actor); loop.status='CLOSED_WITH_OUTCOME'; return outcome;
}
export function emitNextSignal(loop,{signal,source='OUTCOME',actor='SCOUT'}) {
  assertStatus(loop,'CLOSED_WITH_OUTCOME'); if(!signal) throw new Error('next signal is required');
  const next={signal_id:randomUUID(),signal,source,prior_loop_id:loop.loop_id}; append(loop.events,'SIGNAL',next,actor); loop.status='SIGNAL_RECEIVED'; return next;
}
export function resumeLoop({loop_id,version='0.1.0',state={},events=[]}) {
  const loop={loop_id,version,status:lifecycleStatusFromState(state,events),state:structuredClone(state),events:events.map(e=>structuredClone(e))};
  const audit=verifyAuditTrail(loop); if(!audit.ok) throw new Error('invalid audit trail: '+audit.reason); return loop;
}
export function verifyAuditTrail(loop) {
  if(!loop?.events?.length) return {ok:false,reason:'empty event log'};
  for(let i=0;i<loop.events.length;i++){const e=loop.events[i]; if(e.sequence!==i+1)return{ok:false,reason:'sequence break'}; if(e.prev_hash!==(i?loop.events[i-1].hash:null))return{ok:false,reason:'previous-hash break'}; if(e.hash!==hashEvent(e))return{ok:false,reason:'hash mismatch at '+e.id};}
  return {ok:true,events:loop.events.length,head:loop.events.at(-1).hash};
}
function lifecycleStatusFromState(state,events){const s=state?.lifecycle;if(s)return s==='AWAITING_DECISION'?'EFFECT_MAPPED':s==='AWAITING_OUTCOME'?'ACTION_AUTHORIZED':s;const last=events.at(-1);return last?.stage==='PULSE'?'PULSE_CREATED':last?.stage==='EFFECT'?'EFFECT_MAPPED':last?.stage==='DECISION'?(last.payload.choice==='approve'?'DECISION_APPROVED':last.payload.choice==='reject'?'DECISION_REJECTED':'DECISION_DEFERRED'):last?.stage==='ACTION'?'ACTION_AUTHORIZED':last?.stage==='OUTCOME'?'CLOSED_WITH_OUTCOME':'SIGNAL_RECEIVED';}
function assertStatus(loop,expected){if(!loop||loop.status!==expected)throw new Error('expected status '+expected+', got '+(loop?.status??'missing'));}
