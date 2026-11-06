"""MEMORY projection port. Ledger remains the authoritative append-only event log."""
from typing import Protocol
class MemorySink(Protocol):
    def append_memory_event(self, *, event_id: str, decision_id: str, event_type: str, payload: dict, evidence_references: list[str]) -> None: ...
def record_verified_outcome(ledger, decision_id: str, outcome: dict, memory_sink: MemorySink | None = None) -> str:
    """Append outcome locally first; optionally project to MEMORY with explicit sink."""
    digest = ledger.append_outcome(decision_id, outcome)
    if memory_sink is not None:
        rows = ledger.events(decision_id)
        event = rows[-1]
        memory_sink.append_memory_event(
            event_id=event["event_id"], decision_id=decision_id,
            event_type="outcome.verified", payload=outcome,
            evidence_references=outcome["evidence_references"]
        )
    return digest
