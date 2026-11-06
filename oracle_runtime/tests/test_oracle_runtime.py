import json,sqlite3
from pathlib import Path
import pytest
from oracle_runtime.validation import validate_decision
from oracle_runtime.ledger import DecisionLedger
from oracle_runtime.control import require_control_approval,ControlUnavailable
from oracle_runtime.handoff import prepare_handoff
from oracle_runtime.scout_adapter import read_scout_observation
ROOT=Path(__file__).resolve().parents[2]; FIXTURE=ROOT/"oracle_runtime/tests/fixtures/decision.pending.json"
def decision():return json.loads(FIXTURE.read_text())
def test_valid_fixture():assert validate_decision(decision())==[]
def test_ready_handoff_without_approval_fails():
 d=decision();d["execution_handoff"]["state"]="ready";assert any("approved authorization" in x for x in validate_decision(d))
def test_control_fails_closed():
 d=decision();d["authorization"].update(state="approved",approved_by="owner",approved_at="2026-11-06T10:00:00Z",expires_at="2026-11-06T11:00:00Z",evidence_reference="approval-1")
 with pytest.raises(ControlUnavailable):require_control_approval(d,None)
def test_role_is_not_identity():
 d=decision();d["authorization"].update(state="approved",approved_by="owner",approved_at="2026-11-06T10:00:00Z",expires_at="2026-11-06T11:00:00Z",evidence_reference="approval-1")
 class C:
  def verify_approval(self,**kw):return {"valid":True,"decision_id":d["decision_id"],"scope":d["authorization"]["scope"]}
 class R:
  def resolve(self,role):return None
 with pytest.raises(PermissionError):prepare_handoff(d,R(),C())
def test_ledger_append_only_hash_chain(tmp_path):
 l=DecisionLedger(tmp_path/"ledger.db");d=decision();l.append(d);l.append(d,"decision.reviewed");assert len(l.events())==2 and l.verify_chain()
 with sqlite3.connect(tmp_path/"ledger.db") as c:
  with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE oracle_events SET event_type='tampered' WHERE seq=1")
  with pytest.raises(sqlite3.IntegrityError):c.execute("DELETE FROM oracle_events WHERE seq=1")
def test_scout_read_only_adapter(tmp_path):
 x={"observation_id":"scout-1","subject":"Example Venue","claim":"Page captured; claims not verified.","state":"observed","provenance":{"source_url":"https://example.org/venue","observed_at":"2026-11-06T09:00:00Z","collected_at":"2026-11-06T09:01:00Z","collection_method":"bounded_public_html_fetch","adapter":"stdlib_html_v0"},"captured_text":"Venue page","attributes":{}}
 p=tmp_path/"scout.json";p.write_text(json.dumps(x));e=read_scout_observation(p,"Lagos","nightlife");assert e["source"]["system"]=="SCOUT" and e["market"]=="Lagos"
