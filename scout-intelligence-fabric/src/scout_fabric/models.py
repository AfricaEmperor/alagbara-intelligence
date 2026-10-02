"""Canonical data contracts. Keep observations separate from interpretations."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

EvidenceState = Literal["observed", "derived", "unverified", "unknown"]

@dataclass(frozen=True)
class Provenance:
    source_url: str
    observed_at: str
    collected_at: str
    collection_method: str
    adapter: str
    raw_record_ref: str | None = None

    def validate(self) -> None:
        parsed = urlparse(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP(S) URL")
        for field_name in ("observed_at", "collected_at"):
            datetime.fromisoformat(getattr(self, field_name).replace("Z", "+00:00"))

@dataclass(frozen=True)
class Observation:
    observation_id: str
    subject: str
    claim: str
    state: EvidenceState
    provenance: Provenance
    captured_text: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
