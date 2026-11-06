import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
SCHEMA=Path(__file__).resolve().parents[2]/"contracts/oracle/oracle-decision-v1.schema.json"
def validate_decision(d,schema=None):
 s=schema or json.loads(SCHEMA.read_text()); Draft202012Validator.check_schema(s)
 v=Draft202012Validator(s,format_checker=FormatChecker())
 errors=[f"{'.'.join(map(str,e.absolute_path)) or '$'}: {e.message}" for e in v.iter_errors(d)]
 if errors:return sorted(errors)
 a,h=d["authorization"],d["execution_handoff"]
 if h["state"] in {"ready","issued","accepted","completed"}:
  if a["state"]!="approved":errors.append("handoff requires approved authorization")
  if not h.get("executor_identity"):errors.append("handoff requires verified executor identity")
  if not h.get("approval_reference"):errors.append("handoff requires approval reference")
 if a["state"]=="approved" and any(not a.get(k) for k in ("approved_by","approved_at","expires_at","evidence_reference")):errors.append("approved authorization requires approver, timestamps and evidence reference")
 if d["status"] in {"authorized","handed_off","executing","verified","closed"} and a["state"]!="approved":errors.append("consequential status requires approved authorization")
 if d["status"] in {"handed_off","executing","verified","closed"} and h["state"]=="not_ready":errors.append("consequential status cannot have not_ready handoff")
 if any(r["severity"]=="critical" and r["blocks_handoff"] for r in d["risks"]) and h["state"]!="not_ready":errors.append("critical blocking risk requires not_ready handoff")
 return sorted(errors)
def assert_valid_decision(d):
 errors=validate_decision(d)
 if errors:raise ValueError("Invalid ORACLE decision: "+"; ".join(errors))
