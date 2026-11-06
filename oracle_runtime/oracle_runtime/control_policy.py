"""Read-only adapter for the authoritative Power Enterprise Control Room policy.

This evaluates policy permissions only. It cannot issue or verify a human approval.
"""
from pathlib import Path
import yaml

class PolicyUnavailable(RuntimeError): pass

class ControlPolicyReader:
    def __init__(self, authority_path, repositories_path):
        self.authority_path=Path(authority_path)
        self.repositories_path=Path(repositories_path)
        if not self.authority_path.is_file() or not self.repositories_path.is_file():
            raise PolicyUnavailable("CONTROL authority policy or repository registry is unavailable")
        self.policy=yaml.safe_load(self.authority_path.read_text(encoding="utf-8"))
        self.registry=yaml.safe_load(self.repositories_path.read_text(encoding="utf-8"))
        if not isinstance(self.policy,dict) or self.policy.get("mode")!="deny_by_default":
            raise PolicyUnavailable("CONTROL policy missing or not deny-by-default")
        if not isinstance(self.registry,dict) or not isinstance(self.registry.get("repositories"),list):
            raise PolicyUnavailable("CONTROL repository registry is invalid")

    def evaluate_repository_read(self, repository_full_name):
        registered={item.get("full_name") for item in self.registry["repositories"] if isinstance(item,dict)}
        capability=self.policy.get("capabilities",{}).get("repository_file_read",{})
        allowed=capability.get("allowed") is True and repository_full_name in registered
        return {
            "allowed":allowed,
            "capability":"repository_file_read",
            "target":repository_full_name,
            "policy_version":self.policy.get("policy_version"),
            "reason":"registered repository and policy permits read" if allowed else "deny by default: target unregistered or read capability not allowed",
            "policy_source":str(self.authority_path),
            "approval_granted":False
        }

    def evaluate_mutation(self, capability_name, target):
        capability=self.policy.get("capabilities",{}).get(capability_name,{})
        allowed=capability.get("allowed") is True
        return {
            "allowed":False if not allowed else False,
            "capability":capability_name,
            "target":target,
            "policy_version":self.policy.get("policy_version"),
            "reason":"CONTROL policy requires explicit approval and scoped permission; no approval endpoint is connected",
            "approval_granted":False
        }
