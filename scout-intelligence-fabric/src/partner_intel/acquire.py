"""Online-only, operator-driven acquisition for Partner Intelligence.

Delegates to the existing SCOUT pieces: `scout_fabric.sources.SourceRegistry` (authorization is a recorded
human decision), `scout_fabric.acquire.acquire_public_page` (one bounded public HTML fetch, no credentials)
and the `ana_engine.RadarStore` evidence ledger. There is NO crawler, scheduler, login, browser automation or
contact capability here: one operator-supplied URL in, at most one EvidenceRecord out.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from urllib.parse import urlsplit

from ana_engine.store import RadarStore
from radar_contracts import EvidenceRecord, validate_evidence
from scout_fabric.acquire import acquire_public_page
from scout_fabric.models import Observation
from scout_fabric.normalize import canonicalize_url
from scout_fabric.sources import ALTERNATIVES, SourceRegistry, UnauthorizedSource

EXTRACTION_VERSION = "partner-intel-acquire-0.1"
MAX_TEXT_CHARS = 100_000


def _within_registered(url: str, registered: str | None) -> bool:
    if not registered:
        return False
    u, r = urlsplit(canonicalize_url(url)), urlsplit(canonicalize_url(registered))
    return u.scheme == r.scheme and u.netloc == r.netloc and u.path.startswith(r.path.rstrip("/") or "/")


def acquire_operator_url(url: str, source_id: str, registry: SourceRegistry, store: RadarStore, *,
                         fetch: Callable[[str], Observation] = acquire_public_page) -> tuple[EvidenceRecord, bool]:
    """Fetch ONE operator-supplied public URL that lies inside an APPROVED `public_html` source.

    Unauthorized, unregistered or out-of-scope requests are rejected BEFORE any network call and recorded
    as an acquisition failure with an authorized alternative (existing RadarStore.failures table).
    """
    try:
        src = registry.require_authorized(source_id, "public_html")
        if not _within_registered(url, src.url):
            raise UnauthorizedSource(source_id, "URL is outside the registered, approved source", ALTERNATIVES["public_html"])
    except UnauthorizedSource as exc:
        store.record_failure(exc.source_id, exc.reason, exc.alternative)
        raise
    obs = fetch(canonicalize_url(url))
    text = obs.captured_text or ""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    ev = EvidenceRecord(
        observation_id=hashlib.sha256(f"{source_id}\n{content_hash}".encode()).hexdigest(),
        source_id=source_id, source_platform="public_html", source_url=obs.provenance.source_url,
        collection_method="operator_supplied_public_url", collected_at=obs.provenance.collected_at,
        content_hash=content_hash,
        evidence_state="observed",   # what the page said at capture time; the truth of its claims is NOT verified
        raw_media_reference=None, extraction_version=EXTRACTION_VERSION, media_type="text",
        metadata={"captured_text": text[:MAX_TEXT_CHARS], "truncated": len(text) > MAX_TEXT_CHARS,
                  "title": obs.claim, "assertions_verified": False})
    validate_evidence(ev)
    return ev, store.add_evidence(ev)
