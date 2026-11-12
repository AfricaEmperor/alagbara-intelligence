"""Online-only acquisition guarantees (no network: the fetcher is injected)."""
from __future__ import annotations

import pytest

from partner_intel.acquire import acquire_operator_url
from scout_fabric.models import Observation, Provenance
from scout_fabric.sources import Source, UnauthorizedSource

URL = "https://news.example.org/partners/story-1"


def fake_obs(url, text="Meridian Spirits Group is seeking a Lagos venue partner."):
    now = "2026-11-12T10:00:00+00:00"
    return Observation("obs-1", "Story", "Story", "observed", Provenance(url, now, now, "bounded_public_html_fetch", "stdlib_html_v0"),
                       captured_text=text)


class Counter:
    def __init__(self):
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return fake_obs(url)


@pytest.fixture
def reg(registry):
    registry.register(Source("pub-news", "public_html", "Example news", url="https://news.example.org/partners/"))
    registry.approve("pub-news", "principal@example")
    registry.register(Source("pub-pending", "public_html", "Pending", url="https://pending.example.org/"))
    return registry


def test_authorized_public_url_becomes_ledger_evidence(reg, store):
    fetch = Counter()
    ev, created = acquire_operator_url(URL, "pub-news", reg, store, fetch=fetch)
    assert created and fetch.calls == [URL]
    got = store.get_evidence(ev.observation_id)
    assert got["collection_method"] == "operator_supplied_public_url" and got["evidence_state"] == "observed"
    assert got["metadata"]["assertions_verified"] is False and "venue partner" in got["metadata"]["captured_text"]
    _again, created2 = acquire_operator_url(URL, "pub-news", reg, store, fetch=fetch)
    assert created2 is False and len(store.all_evidence()) == 1      # idempotent: same bytes, same source


@pytest.mark.parametrize("source_id,url", [
    ("pub-pending", "https://pending.example.org/x"),        # registered but not approved
    ("nope", URL),                                           # not registered
    ("pub-news", "https://other.example.org/partners/x"),    # outside the approved source's host
    ("pub-news", "https://news.example.org/private/x"),      # outside the approved path
    ("src-upload-1", URL),                                   # approved, but wrong platform
])
def test_unauthorized_requests_are_rejected_before_any_fetch(reg, store, source_id, url):
    fetch = Counter()
    with pytest.raises(UnauthorizedSource):
        acquire_operator_url(url, source_id, reg, store, fetch=fetch)
    assert fetch.calls == [] and store.all_evidence() == []
    assert store.failures() and store.failures()[-1]["alternative"]    # recorded with an authorized alternative


def test_credentialed_urls_are_not_accepted(reg, store):
    with pytest.raises((ValueError, UnauthorizedSource)):
        acquire_operator_url("https://user:pw@news.example.org/partners/x", "pub-news", reg, store)


def test_module_has_no_crawler_scheduler_login_or_messaging():
    import inspect

    import partner_intel.acquire as m
    src = inspect.getsource(m)
    for banned in ("sched", "crawl", "selenium", "playwright", "smtp", "login", "password=", "requests."):
        assert banned not in src.lower().replace("no crawler, scheduler, login", ""), banned
