"""Minimal, opt-in public HTML acquisition adapter using the Python standard library.

This is a bounded fetcher, not a browser or anti-bot bypass. Run only against
sources you are authorized to access and honor their terms and rate limits.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .models import Observation, Provenance
from .normalize import canonicalize_url, normalize_whitespace, stable_observation_id

MAX_BYTES = 1_000_000
TIMEOUT_SECONDS = 15
USER_AGENT = "ALAGBARA-SCOUT/0.1 (+evidence-first public research; contact repository owner)"

class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if not self._skip_depth:
            self.text_parts.append(data)

def acquire_public_page(url: str) -> Observation:
    canonical_url = canonicalize_url(url)
    parsed = urlsplit(canonical_url)
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not accepted")

    request = Request(canonical_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError(f"Expected HTML, received {content_type}")
            payload = response.read(MAX_BYTES + 1)
            final_url = canonicalize_url(response.geturl())
    except HTTPError as exc:
        raise RuntimeError(f"Source returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not retrieve source: {exc.reason}") from exc

    if len(payload) > MAX_BYTES:
        raise ValueError(f"Response exceeds {MAX_BYTES} byte limit")
    charset = "utf-8"
    try:
        charset = response.headers.get_content_charset() or charset
    except UnboundLocalError:
        pass
    html = payload.decode(charset, errors="replace")
    parser = _VisibleText()
    parser.feed(html)
    title = normalize_whitespace(" ".join(parser.title_parts)) or final_url
    text = normalize_whitespace(" ".join(parser.text_parts))
    captured_at = datetime.now(timezone.utc).isoformat()
    observation_id = stable_observation_id(final_url, title, text[:500])
    provenance = Provenance(
        source_url=final_url,
        observed_at=captured_at,
        collected_at=captured_at,
        collection_method="bounded_public_html_fetch",
        adapter="stdlib_html_v0",
    )
    provenance.validate()
    return Observation(
        observation_id=observation_id,
        subject=title,
        claim=f"Public page content captured at {captured_at}; this capture does not independently verify its claims.",
        state="observed",
        provenance=provenance,
        captured_text=text[:20_000],
        attributes={"content_type": "text/html", "truncated_text": len(text) > 20_000},
    )
