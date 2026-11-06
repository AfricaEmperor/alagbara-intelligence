class ControlUnavailable(RuntimeError):pass
def require_control_approval(decision,provider):
 if provider is None:raise ControlUnavailable("CONTROL provider missing; deny by default")
 a=decision["authorization"]
 if a["state"]!="approved" or any(not a.get(k) for k in ("approved_by","approved_at","expires_at","evidence_reference","policy_reference")):raise PermissionError("Approval envelope incomplete or not approved")
 result=provider.verify_approval(decision_id=decision["decision_id"],policy_reference=a["policy_reference"],scope=a["scope"],approval_reference=a["evidence_reference"])
 if not isinstance(result,dict) or result.get("valid") is not True or result.get("decision_id")!=decision["decision_id"] or result.get("scope")!=a["scope"]:raise PermissionError("CONTROL did not verify exact decision and scope")
 return result
