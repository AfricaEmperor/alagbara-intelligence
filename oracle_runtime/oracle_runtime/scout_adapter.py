import json
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
SCHEMA=Path(__file__).resolve().parents[2]/"scout-intelligence-fabric/schemas/observation.schema.json"
def read_scout_observation(path,market,domain):
 if market not in {"Lagos","Cotonou","Abuja","Benin","Nigeria","global"}:raise ValueError("Explicit recognized market required")
 raw=json.loads(Path(path).read_text(encoding="utf-8")); schema=json.loads(SCHEMA.read_text())
 Draft202012Validator(schema,format_checker=FormatChecker()).validate(raw); p=raw["provenance"]
 return {"evidence_id":raw["observation_id"],"claim":raw["claim"],"source":{"system":"SCOUT","source_type":p["collection_method"],"reference":p["source_url"]},"observed_at":p["observed_at"],"captured_at":p["collected_at"],"domain":domain,"market":market,"evidence_type":"direct_observation" if raw["state"]=="observed" else "derived" if raw["state"]=="derived" else "assumption","reliability":{"band":"unrated","basis":"SCOUT captures source content; it does not independently verify page assertions."},"limitations":["Read-only SCOUT import",f"Original SCOUT evidence state: {raw['state']}","Source claims not independently verified"],"content_hash":None}
