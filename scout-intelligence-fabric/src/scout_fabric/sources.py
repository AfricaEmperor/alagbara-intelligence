"""SCOUT source registry. Nothing is acquired from a source that is not registered AND approved.

Authorization is a human decision recorded in the registry (approved_by); code never grants it.
Inaccessible/unauthorized sources produce an AcquisitionFailure with an authorized alternative.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PLATFORMS = ("upload", "facebook_page", "public_html", "approved_external")
AUTH_STATES = ("pending", "approved", "revoked")

ALTERNATIVES = {
    "facebook_page": "Upload the event poster/screenshot directly, or have the Page admin grant "
                     "pages_read_engagement to the PULSE Facebook app and register the Page here.",
    "public_html": "Obtain written permission / confirm robots+terms allow access, then register "
                   "the URL as an approved source; or upload a screenshot of the page.",
    "approved_external": "Request human approval for this source in the registry.",
    "upload": "Register an upload source and have an operator approve it.",
}


class UnauthorizedSource(PermissionError):
    def __init__(self, source_id: str, reason: str, alternative: str):
        super().__init__(f"source {source_id!r} rejected: {reason}")
        self.source_id, self.reason, self.alternative = source_id, reason, alternative


@dataclass
class Source:
    source_id: str
    platform: str
    label: str
    authorization: str = "pending"
    approved_by: str | None = None
    url: str | None = None  # page/URL for facebook_page/public_html
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AcquisitionFailure:
    source_id: str
    reason: str
    alternative: str
    at: str
    detail: dict[str, Any] = field(default_factory=dict)


class SourceRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path
        self._sources: dict[str, Source] = {}
        if path and path.exists():
            for row in json.loads(path.read_text()):
                self._sources[row["source_id"]] = Source(**row)

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps([s.to_dict() for s in self._sources.values()], indent=2))

    def register(self, source: Source) -> Source:
        if source.platform not in PLATFORMS:
            raise ValueError(f"unknown platform {source.platform!r}")
        if source.authorization not in AUTH_STATES:
            raise ValueError("invalid authorization state")
        if source.authorization == "approved" and not source.approved_by:
            raise ValueError("approved sources must record approved_by (human approval)")
        existing = self._sources.get(source.source_id)
        if existing:  # idempotent; never silently upgrade authorization on re-register
            return existing
        self._sources[source.source_id] = source
        self._save()
        return source

    def approve(self, source_id: str, approved_by: str) -> Source:
        if not approved_by.strip():
            raise ValueError("approved_by is required")
        s = self.get(source_id)
        s.authorization, s.approved_by = "approved", approved_by
        self._save()
        return s

    def revoke(self, source_id: str) -> None:
        self.get(source_id).authorization = "revoked"
        self._save()

    def get(self, source_id: str) -> Source:
        try:
            return self._sources[source_id]
        except KeyError:
            raise UnauthorizedSource(source_id, "source is not registered",
                                     ALTERNATIVES["approved_external"]) from None

    def require_authorized(self, source_id: str, platform: str | None = None) -> Source:
        s = self.get(source_id)
        if s.authorization != "approved":
            raise UnauthorizedSource(source_id, f"authorization is {s.authorization}",
                                     ALTERNATIVES.get(s.platform, ALTERNATIVES["approved_external"]))
        if platform and s.platform != platform:
            raise UnauthorizedSource(source_id, f"source platform is {s.platform}, not {platform}",
                                     ALTERNATIVES.get(platform, ""))
        return s

    def all(self) -> list[Source]:
        return list(self._sources.values())


class FacebookPageAdapter:
    """Authorized Facebook Page integration BOUNDARY.

    No network code ships in this slice: Graph API access needs an approved app, a Page access
    token with the permissions Meta has granted, and a registered+approved Page source. Until a
    token client is injected this adapter records a failure with an authorized alternative; it
    never scrapes, logs in, or bypasses access controls.
    """

    def __init__(self, registry: SourceRegistry, graph_client: Any | None = None):
        self.registry, self.graph_client = registry, graph_client

    def fetch_page_posts(self, source_id: str, now_iso: str) -> list[Any]:
        self.registry.require_authorized(source_id, "facebook_page")  # raises if not approved
        if self.graph_client is None:
            raise UnauthorizedSource(source_id, "Facebook Graph API client/permissions not configured",
                                     ALTERNATIVES["facebook_page"])
        return list(self.graph_client.page_posts(self.registry.get(source_id).url))
