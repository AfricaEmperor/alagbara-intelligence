"""Bounded tracking-infrastructure reconnaissance for public websites.

This module performs one explicit fetch, fingerprints common tracking technologies
from the returned HTML, and emits evidence-backed observations. It does not
crawl, execute JavaScript, bypass controls, or infer campaign performance.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .normalize import canonicalize_url

VERSION = "0.1.0"
MAX_BYTES = 1_000_000
TIMEOUT_SECONDS = 15
MAX_REDIRECTS = 4
USER_AGENT = "ALAGBARA-SCOUT-TRACKING/0.1 (+bounded public-page inspection)"


class _HTMLSignals(HTMLParser):
    """Collect only fingerprint-relevant HTML signals; do not retain full markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.script_srcs: list[str] = []
        self.inline_script_parts: list[str] = []
        self.meta: list[tuple[str, str]] = []
        self._script_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): v or "" for k, v in attrs}
        if tag.lower() == "script":
            self._script_depth += 1
            src = values.get("src")
            if src:
                self.script_srcs.append(src)
        elif tag.lower() == "meta":
            key = values.get("name") or values.get("property") or ""
            value = values.get("content") or ""
            if key or value:
                self.meta.append((key, value))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._script_depth:
            self._script_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._script_depth:
            self.inline_script_parts.append(data)


@dataclass(frozen=True)
class Detection:
    technology_id: str
    name: str
    category: str
    confidence: str
    evidence: list[str]
    interpretation: str


SIGNATURES: list[dict[str, object]] = [
    {
        "id": "meta_pixel", "name": "Meta Pixel", "category": "advertising",
        "rules": [r"connect\.facebook\.net/.*/fbevents\.js", r"\bfbq\s*\(", r"facebook\.com/tr\?"],
        "interpretation": "Meta Pixel infrastructure appears present; advertising activity and performance are not established.",
    },
    {
        "id": "google_tag_manager", "name": "Google Tag Manager", "category": "tag_management",
        "rules": [r"googletagmanager\.com/gtm\.js", r"\bGTM-[A-Z0-9]+"],
        "interpretation": "Google Tag Manager infrastructure appears present.",
    },
    {
        "id": "google_analytics_4", "name": "Google Analytics 4", "category": "analytics",
        "rules": [r"google-analytics\.com/g/collect", r"\bG-[A-Z0-9]{5,}", r"gtag\s*\(\s*['\"]config['\"]\s*,\s*['\"]G-"],
        "interpretation": "Google Analytics measurement identifiers or collection infrastructure appear present.",
    },
    {
        "id": "google_ads_conversion", "name": "Google Ads Conversion", "category": "advertising",
        "rules": [r"\bAW-[0-9]{5,}", r"googleadservices\.com/pagead/conversion", r"conversion\.googleadservices\.com"],
        "interpretation": "Google Ads conversion-tag infrastructure appears present.",
    },
    {
        "id": "tiktok_pixel", "name": "TikTok Pixel", "category": "advertising",
        "rules": [r"analytics\.tiktok\.com", r"\bttq\s*\(", r"tiktok\.com/i18n/pixel"],
        "interpretation": "TikTok Pixel infrastructure appears present.",
    },
    {
        "id": "linkedin_insight", "name": "LinkedIn Insight Tag", "category": "advertising",
        "rules": [r"linkedin\.com/insight", r"licdn\.com/li\.lms-analytics", r"_linkedin_partner_id"],
        "interpretation": "LinkedIn Insight Tag infrastructure appears present.",
    },
    {
        "id": "snap_pixel", "name": "Snap Pixel", "category": "advertising",
        "rules": [r"sc-static\.net/scevent\.min\.js", r"\bsnaptr\s*\(", r"tr\.snapchat\.com"],
        "interpretation": "Snap Pixel infrastructure appears present.",
    },
    {
        "id": "pinterest_tag", "name": "Pinterest Tag", "category": "advertising",
        "rules": [r"\bpintrk\s*\(", r"s\.pinimg\.com/ct/core\.js", r"ct\.pinterest\.com"],
        "interpretation": "Pinterest Tag infrastructure appears present.",
    },
    {
        "id": "microsoft_clarity", "name": "Microsoft Clarity", "category": "behavior_analytics",
        "rules": [r"clarity\.ms/tag", r"\bclarity\s*\(\s*['\"]init"],
        "interpretation": "Microsoft Clarity behavior-analytics infrastructure appears present.",
    },
    {
        "id": "hotjar", "name": "Hotjar", "category": "behavior_analytics",
        "rules": [r"static\.hotjar\.com", r"\bhj\s*\(" , r"hotjar\.com"],
        "interpretation": "Hotjar behavior-analytics infrastructure appears present.",
    },
    {
        "id": "mixpanel", "name": "Mixpanel", "category": "analytics",
        "rules": [r"cdn\.mxpnl\.com", r"mixpanel\.com/track", r"\bmixpanel\s*\.\s*init"],
        "interpretation": "Mixpanel analytics infrastructure appears present.",
    },
    {
        "id": "amplitude", "name": "Amplitude", "category": "analytics",
        "rules": [r"amplitude\.com/analytics", r"cdn\.amplitude\.com", r"\bamplitude\s*\.\s*init"],
        "interpretation": "Amplitude analytics infrastructure appears present.",
    },
    {
        "id": "segment", "name": "Segment", "category": "customer_data",
        "rules": [r"cdn\.segment\.com", r"api\.segment\.io", r"\banalytics\s*\.\s*load"],
        "interpretation": "Segment customer-data collection infrastructure appears present.",
    },
    {
        "id": "hubspot", "name": "HubSpot", "category": "crm_marketing",
        "rules": [r"js\.hs-scripts\.com", r"hsforms\.com", r"hubspot\.com"],
        "interpretation": "HubSpot web or marketing integration infrastructure appears present.",
    },
]


def _validate_public_target(url: str) -> str:
    canonical = canonicalize_url(url)
    parsed = urlsplit(canonical)
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are rejected")
    host = parsed.hostname
    if not host:
        raise ValueError("URL must contain a hostname")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)]
        except OSError as exc:
            raise ValueError(f"Hostname could not be resolved: {host}") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Target resolves to a non-public IP address; scan blocked")
    return canonical


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch_public_html(url: str) -> tuple[str, bytes, str]:
    """Fetch one public HTML page; manually validate every redirect destination."""
    opener = build_opener(_NoRedirect())
    current = _validate_public_target(url)
    for redirect_count in range(MAX_REDIRECTS + 1):
        req = Request(current, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            response = opener.open(req, timeout=TIMEOUT_SECONDS)
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    raise RuntimeError(f"Redirect {exc.code} missing Location header") from exc
                if redirect_count >= MAX_REDIRECTS:
                    raise RuntimeError("Redirect limit exceeded") from exc
                current = _validate_public_target(urljoin(current, location))
                continue
            raise RuntimeError(f"Source returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not retrieve source: {exc.reason}") from exc
        with response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError(f"Expected HTML, received {content_type}")
            payload = response.read(MAX_BYTES + 1)
            final_url = _validate_public_target(response.geturl())
            charset = response.headers.get_content_charset() or "utf-8"
        if len(payload) > MAX_BYTES:
            raise ValueError(f"Response exceeds {MAX_BYTES} byte limit")
        return final_url, payload, charset
    raise RuntimeError("Redirect limit exceeded")


def _detect(html: str, parser: _HTMLSignals) -> list[Detection]:
    signals = "\n".join([html, *parser.script_srcs, *parser.inline_script_parts, *[f"{k}={v}" for k, v in parser.meta]])
    detections: list[Detection] = []
    for signature in SIGNATURES:
        matches = [rule for rule in signature["rules"] if re.search(rule, signals, re.IGNORECASE)]
        if not matches:
            continue
        confidence = "high" if len(matches) >= 2 else "medium"
        evidence = [f"Matched fingerprint: {rule}" for rule in matches]
        detections.append(Detection(
            technology_id=str(signature["id"]),
            name=str(signature["name"]),
            category=str(signature["category"]),
            confidence=confidence,
            evidence=evidence,
            interpretation=str(signature["interpretation"]),
        ))
    return detections


def scan_tracking(url: str) -> dict[str, object]:
    """Run a single bounded public HTML scan and return an evidence-backed profile."""
    final_url, payload, charset = _fetch_public_html(url)
    html = payload.decode(charset, errors="replace")
    parser = _HTMLSignals()
    parser.feed(html)
    detected_at = datetime.now(timezone.utc).isoformat()
    detections = _detect(html, parser)
    digest = hashlib.sha256(payload).hexdigest()
    observations = []
    for detection in detections:
        observations.append({
            "observation_id": hashlib.sha256(
                f"{final_url}\n{detection.technology_id}\n{digest}".encode("utf-8")
            ).hexdigest(),
            "subject": detection.name,
            "claim": f"{detection.name} tracking infrastructure was fingerprinted in the returned page.",
            "state": "observed",
            "attributes": {
                "confidence": detection.confidence,
                "technology_id": detection.technology_id,
                "category": detection.category,
                "matched_evidence": detection.evidence,
                "interpretation": detection.interpretation,
                "detector_version": VERSION,
            },
            "provenance": {
                "source_url": final_url,
                "observed_at": detected_at,
                "collected_at": detected_at,
                "collection_method": "bounded_public_html_fingerprint",
                "adapter": "scout_tracking_stdlib_v0",
                "raw_record_ref": f"sha256:{digest}",
            },
        })
    if detections:
        assessment = "Tracking infrastructure was observed. Installation does not prove active campaigns, audience creation, conversion quality, or commercial performance."
        opportunities = ["Validate the actual event configuration and conversion definitions.", "Assess measurement coverage across the customer journey."]
    else:
        assessment = "No supported tracking signatures were observed in the returned HTML. This does not prove tracking is absent; dynamic, server-side, consent-gated, or blocked instrumentation may not be visible."
        opportunities = ["If measurement is a priority, verify instrumentation using authorized owner access or a consented browser session."]
    return {
        "scan_id": hashlib.sha256(f"{final_url}\n{digest}\n{detected_at}".encode("utf-8")).hexdigest(),
        "scan_version": VERSION,
        "target_url": canonicalize_url(url),
        "resolved_url": final_url,
        "scanned_at": detected_at,
        "source_integrity": {"sha256": digest, "bytes": len(payload)},
        "coverage": {
            "mode": "single_public_html_fetch",
            "javascript_executed": False,
            "links_crawled": 0,
            "redirects_followed": True,
            "max_redirects": MAX_REDIRECTS,
            "known_limitations": [
                "Static HTML only; no JavaScript execution or browser network capture.",
                "Server-side tracking and consent-gated/dynamic tags may be missed.",
                "A detected installation does not establish campaign activity or performance.",
            ],
        },
        "detections": [asdict(item) for item in detections],
        "observations": observations,
        "assessment": {
            "status": "observed_tracking" if detections else "no_supported_signatures_observed",
            "summary": assessment,
            "opportunities": opportunities,
            "unknowns": ["Campaign activity", "Audience size", "Conversion performance", "Server-side instrumentation"],
        },
    }


def render_markdown(report: dict[str, object]) -> str:
    detections = report["detections"]
    assessment = report["assessment"]
    lines = [
        "# SCOUT Tracking Intelligence Profile",
        "",
        f"- Target: {report['target_url']}",
        f"- Resolved URL: {report['resolved_url']}",
        f"- Scan time: {report['scanned_at']}",
        f"- Scan ID: {report['scan_id']}",
        "",
        "## Observed technologies",
        "",
    ]
    if detections:
        for item in detections:
            lines.extend([
                f"### {item['name']} — {item['confidence'].upper()} confidence",
                f"- Category: {item['category']}",
                f"- Interpretation: {item['interpretation']}",
                "- Evidence:",
                *[f"  - {ev}" for ev in item["evidence"]],
                "",
            ])
    else:
        lines.append("No supported signatures were observed in the returned HTML. This is not proof of absence.")
    lines.extend(["## Assessment", "", assessment["summary"], "", "## Opportunities", ""])
    lines.extend([f"- {item}" for item in assessment["opportunities"]])
    lines.extend(["", "## Unknowns", ""])
    lines.extend([f"- {item}" for item in assessment["unknowns"]])
    lines.extend(["", "## Coverage limitations", ""])
    lines.extend([f"- {item}" for item in report["coverage"]["known_limitations"]])
    lines.extend(["", f"Source HTML SHA-256: {report['source_integrity']['sha256']}", ""])
    return "\n".join(lines)


def json_dumps(report: dict[str, object]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
