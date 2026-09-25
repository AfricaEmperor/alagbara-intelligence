"""Immutable provenance wrapper for source observations."""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import hashlib, json

@dataclass(frozen=True)
class EvidencePassport:
    evidence_id: str
    source: str
    source_type: str
    retrieved_at: str
    raw_record: Dict[str, Any]
    observations: Dict[str, Any]
    epistemic_status: str = "OBSERVED"
    confidence: str = "MEDIUM"
    locator: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def make_id(source: str, raw_record: Dict[str, Any]) -> str:
        payload=json.dumps(raw_record,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        digest=hashlib.sha256(f"{source}|{payload}".encode()).hexdigest()[:16]
        return f"EVP_{digest.upper()}"

    @classmethod
    def from_record(cls, source: str, source_type: str, raw_record: Dict[str, Any],
                    observations: Optional[Dict[str, Any]]=None,
                    confidence: str="MEDIUM", locator: Optional[str]=None):
        return cls(
            evidence_id=cls.make_id(source,raw_record),
            source=source,
            source_type=source_type,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            raw_record=raw_record,
            observations=observations or {},
            confidence=confidence,
            locator=locator,
        )
