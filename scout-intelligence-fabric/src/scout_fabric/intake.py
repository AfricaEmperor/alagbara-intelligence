"""Authorized-source intake: HTML -> evidence-backed venue/event candidate bundle.

Offline/deterministic. It never fetches anything itself: the caller supplies HTML that was
obtained from a source with a recorded authorization (or a synthetic fixture). The bundle is
the SCOUT -> MUSE/PULSE hand-off contract (``scout-candidate/0.1``). Nothing here verifies a
claim; the candidate is an *observation* that humans must review downstream.
"""
from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .acquire import _VisibleText
from .models import Observation, Provenance, utc_now_iso
from .normalize import canonicalize_url, normalize_whitespace, stable_observation_id

CONTRACT = "scout-candidate/0.1"
VENUE_TYPES = {"NightClub": "CLUB", "BarOrPub": "BAR", "Restaurant": "RESTAURANT",
               "LocalBusiness": "EVENT_SPACE", "EntertainmentBusiness": "EVENT_SPACE"}


class IntakeRefused(ValueError):
    """Source not authorized / not enabled / host not allowed."""


def load_registry(path: str) -> dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {s["id"]: s for s in data["sources"]}


def check_authorized(source: dict, url: str) -> None:
    if not source.get("enabled"):
        raise IntakeRefused(f"source {source.get('id')} is not enabled")
    auth = source.get("authorization") or {}
    if not auth.get("basis") or not auth.get("reference"):
        raise IntakeRefused(f"source {source.get('id')} has no recorded authorization")
    host = urlsplit(canonicalize_url(url)).hostname or ""
    if host not in source.get("allowed_hosts", []):
        raise IntakeRefused(f"host {host!r} not in allowed_hosts for {source['id']}")


class _JsonLd(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._on = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self._on = True
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._on = False

    def handle_data(self, data):
        if self._on:
            self.blocks[-1] += data


def _nodes(html: str) -> list[dict]:
    p = _JsonLd()
    p.feed(html)
    out: list[dict] = []
    for block in p.blocks:
        try:
            doc = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in (doc if isinstance(doc, list) else doc.get("@graph", [doc])):
            if isinstance(node, dict):
                out.append(node)
    return out


def extract_candidate(html: str) -> dict:
    """Pull schema.org venue/event facts. Missing facts stay None (state 'unknown')."""
    venue = event = None
    for n in _nodes(html):
        t = n.get("@type")
        t = t[0] if isinstance(t, list) and t else t
        if t == "Event" and event is None:
            event = n
        elif t in VENUE_TYPES and venue is None:
            venue = n
    if event and not venue and isinstance(event.get("location"), dict):
        venue = event["location"]
    addr = (venue or {}).get("address")
    if isinstance(addr, dict):
        street = addr.get("streetAddress")
        hood = addr.get("addressLocality")
    else:
        street, hood = addr, None
    v = None
    if venue:
        v = {
            "name": normalize_whitespace(venue.get("name", "")) or None,
            "type": VENUE_TYPES.get(venue.get("@type"), "EVENT_SPACE"),
            "address": street, "neighborhood": hood,
            "publicUrl": venue.get("url"),
        }
    e = None
    if event:
        e = {
            "name": normalize_whitespace(event.get("name", "")) or None,
            "startAt": event.get("startDate"), "endAt": event.get("endDate"),
            "description": event.get("description"), "sourceUrl": event.get("url"),
        }
    return {"venue": v, "event": e}


def build_bundle(source: dict, url: str, html: str, *, collected_at: str | None = None) -> dict:
    check_authorized(source, url)
    final_url = canonicalize_url(url)
    collected_at = collected_at or utc_now_iso()
    raw = html.encode("utf-8")
    parser = _VisibleText()
    parser.feed(html)
    title = normalize_whitespace(" ".join(parser.title_parts)) or final_url
    text = normalize_whitespace(" ".join(parser.text_parts))
    sha = hashlib.sha256(raw).hexdigest()
    prov = Provenance(final_url, collected_at, collected_at, source.get("collection_method", "authorized_html_supplied"),
                      "scout_intake_v0", raw_record_ref=f"sha256:{sha}")
    prov.validate()
    obs = Observation(
        observation_id=stable_observation_id(final_url, title, sha),
        subject=title,
        claim="Authorized source page captured; contents are unverified self-description.",
        state="unverified", provenance=prov, captured_text=text[:5000],
        attributes={"bytes": len(raw), "source_id": source["id"]},
    )
    return {
        "contract": CONTRACT,
        "source": {"id": source["id"], "city": source["city"],
                   "authorization": source["authorization"]},
        "observation": obs.to_dict(),
        "candidate": extract_candidate(html),
    }
