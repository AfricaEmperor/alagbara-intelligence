from .control import require_control_approval
def prepare_handoff(decision,registry,control_provider):
 require_control_approval(decision,control_provider)
 if registry is None:raise PermissionError("No verified executor registry")
 h=decision["execution_handoff"]; role=h.get("executor_role") or "Zuberi"; identity=registry.resolve(role)
 if not identity or identity.get("verified") is not True or not identity.get("identity_ref") or not identity.get("permissions"):raise PermissionError(f"No verified identity and permissions for {role}")
 return {"decision_id":decision["decision_id"],"executor_role":role,"executor_identity":identity["identity_ref"],"permissions":identity["permissions"],"task":h.get("task"),"approval_reference":decision["authorization"]["evidence_reference"],"state":"ready"}
