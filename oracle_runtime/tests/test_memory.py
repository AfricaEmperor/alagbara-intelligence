import json
from pathlib import Path
from oracle_runtime.ledger import DecisionLedger
from oracle_runtime.memory import record_verified_outcome
ROOT=Path(__file__).resolve().parents[2]
def test_verified_outcome_is_appended_to_memory_ledger(tmp_path):
 d=json.loads((ROOT/"oracle_runtime/tests/fixtures/decision.pending.json").read_text())
 ledger=DecisionLedger(tmp_path/"memory.db")
 ledger.append(d)
 outcome={"result":"sample review completed","observed_at":"2026-11-06T10:00:00Z","evidence_references":["evidence-001"],"verified_by":"human-reviewer","metrics":{"records_reviewed":1}}
 record_verified_outcome(ledger,d["decision_id"],outcome)
 events=ledger.events(d["decision_id"])
 assert events[-1]["event_type"]=="outcome.verified"
 assert ledger.verify_chain()
