import hashlib,json,sqlite3
from datetime import datetime,timezone
from .validation import assert_valid_decision
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
class DecisionLedger:
 def __init__(self,path):
  self.path=str(path)
  with self.db() as c:
   c.execute("CREATE TABLE IF NOT EXISTS oracle_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,decision_id TEXT NOT NULL,event_type TEXT NOT NULL,payload_json TEXT NOT NULL,occurred_at TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT UNIQUE NOT NULL)")
   c.executescript("CREATE TRIGGER IF NOT EXISTS oracle_no_update BEFORE UPDATE ON oracle_events BEGIN SELECT RAISE(ABORT,'append-only ledger'); END; CREATE TRIGGER IF NOT EXISTS oracle_no_delete BEFORE DELETE ON oracle_events BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;")
 def db(self):
  c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;return c
 def append_event(self,decision_id,event_type,payload):
  with self.db() as c:
   row=c.execute("SELECT event_hash FROM oracle_events ORDER BY seq DESC LIMIT 1").fetchone();prev=row["event_hash"] if row else "GENESIS"
   at=datetime.now(timezone.utc).isoformat();eid=f'{decision_id}:{event_type}:{at}';body={"event_id":eid,"decision_id":decision_id,"event_type":event_type,"payload_json":canon(payload),"occurred_at":at,"previous_hash":prev};digest=hashlib.sha256(canon(body).encode()).hexdigest()
   c.execute("INSERT INTO oracle_events(event_id,decision_id,event_type,payload_json,occurred_at,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",(eid,decision_id,event_type,body["payload_json"],at,prev,digest));return digest
 def append(self,d,event_type="decision.proposed"):
  assert_valid_decision(d);return self.append_event(d["decision_id"],event_type,d)
 def append_outcome(self,decision_id,outcome):
  required=("result","observed_at","evidence_references","verified_by")
  if any(not outcome.get(k) for k in required):raise ValueError("Verified outcome requires result, observed_at, evidence_references and verified_by")
  if not isinstance(outcome["evidence_references"],list) or not outcome["evidence_references"]:raise ValueError("Outcome must cite at least one evidence reference")
  return self.append_event(decision_id,"outcome.verified",outcome)
 def events(self,decision_id=None):
  with self.db() as c:
   rows=c.execute("SELECT * FROM oracle_events WHERE decision_id=? ORDER BY seq",(decision_id,)).fetchall() if decision_id else c.execute("SELECT * FROM oracle_events ORDER BY seq").fetchall()
   return [dict(r) for r in rows]
 def verify_chain(self):
  prev="GENESIS"
  for row in self.events():
   body={k:row[k] for k in ("event_id","decision_id","event_type","payload_json","occurred_at","previous_hash")}
   if row["previous_hash"]!=prev or hashlib.sha256(canon(body).encode()).hexdigest()!=row["event_hash"]:return False
   prev=row["event_hash"]
  return True
