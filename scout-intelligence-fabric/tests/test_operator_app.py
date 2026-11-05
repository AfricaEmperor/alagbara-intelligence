"""HTTP tests for the operator console (real server on an ephemeral loopback port)."""
import http.client
import json
import re
import threading
from urllib.parse import urlencode

import pytest

from ana_engine.operator_app import OperatorApp, run_server
from ana_engine.store import RadarStore
from conftest import POSTER_A, make_png
from scout_fabric.text_providers import TextResult

KEY = "test-launch-key-123"


class FakeOcr:
    def available(self):
        return False

    def extract(self, path, media_type):
        return TextResult(None, "ocr:fake", "unknown", "no ocr")


class Client:
    def __init__(self, port):
        self.port, self.cookie, self.csrf = port, None, None

    def req(self, method, path, fields=None, files=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = dict(headers or {})
        if self.cookie:
            h["Cookie"] = self.cookie
        body = raw
        if fields is not None and files is None:
            f = dict(fields)
            if self.csrf and "csrf" not in f and f.pop("_nocsrf", None) is None:
                f["csrf"] = self.csrf
            f.pop("_nocsrf", None)
            body = urlencode(f).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        if files is not None:
            b = "----bnd"
            parts = []
            for k, v in {**(fields or {}), "csrf": self.csrf or ""}.items():
                parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for name, fn, data in files:
                parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{name}"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
            body = b"".join(parts) + f"--{b}--\r\n".encode()
            h["Content-Type"] = f"multipart/form-data; boundary={b}"
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        sc = r.getheader("Set-Cookie")
        if sc and "op_session=" in sc and "Max-Age=0" not in sc:
            self.cookie = sc.split(";")[0]
        resp = (r.status, dict(r.getheaders()), data)
        c.close()
        if resp[0] == 200 and "text/html" in resp[1].get("Content-Type", ""):
            m = re.search(rb'name="csrf" value="([^"]+)"', data)
            if m:
                self.csrf = m.group(1).decode()
        return resp

    def login(self, name="Awa"):
        s, h, _ = self.req("POST", "/login", {"name": name, "key": KEY})
        assert s == 303 and h["Location"] == "/"
        self.req("GET", "/")


@pytest.fixture
def console(tmp_path):
    app = OperatorApp(tmp_path / "data", tmp_path / "feed.json", KEY)
    app.ocr = FakeOcr()
    srv = run_server(app, "127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    port = srv.server_address[1]
    yield app, (lambda: Client(port)), tmp_path
    srv.shutdown()
    srv.server_close()


def setup_source(c, sid="uploads-test"):
    c.req("POST", "/sources/register", {"source_id": sid, "label": "Test uploads"})
    c.req("POST", "/sources/approve", {"source_id": sid})


def upload(c, text=POSTER_A, sid="uploads-test", note="Organizer agreed by email on 2026-11-01", seed=1, name="poster.png", url=""):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        make_png(Path(td) / name, seed)
        data = (Path(td) / name).read_bytes()
    return c.req("POST", "/upload", {"source_id": sid, "permission_note": note, "source_url": url, "transcription": text}, files=[("files", name, data)])


def event_id(body):
    return re.search(rb"/events/(evt_[0-9a-f]+)", body).group(1).decode()


def test_nothing_is_reachable_without_signing_in(console):
    app, mk, _ = console
    c = mk()
    for p in ("/", "/sources", "/upload", "/events", "/venues", "/evidence", "/ops", "/feed.json", "/media/" + "a" * 64 + ".png", "/events/evt_abc"):
        s, h, b = c.req("GET", p)
        assert s == 303 and h["Location"] == "/login" and b == b""
    for p in ("/upload", "/publish", "/sources/approve", "/backup"):
        assert c.req("POST", p, {"x": "1"})[0] == 401
    assert json.loads(c.req("GET", "/health")[2]) == {"status": "ok"}


def test_login_cookie_flags_and_lockout(console):
    app, mk, _ = console
    c = mk()
    for _ in range(5):
        s, h, _ = c.req("POST", "/login", {"name": "Awa", "key": "wrong"})
        assert s == 303 and h["Location"] == "/login?e=1"
    s, h, _ = c.req("POST", "/login", {"name": "Awa", "key": KEY})          # right key, but locked
    assert h["Location"] == "/login?e=2" and c.cookie is None
    app.failures.clear()
    c2 = mk()
    conn = http.client.HTTPConnection("127.0.0.1", c2.port)
    conn.request("POST", "/login", body=urlencode({"name": "Awa", "key": KEY}), headers={"Content-Type": "application/x-www-form-urlencoded"})
    ck = conn.getresponse().getheader("Set-Cookie")
    assert "HttpOnly" in ck and "SameSite=Strict" in ck and "Path=/" in ck
    assert c.req("POST", "/login", {"name": "<script>", "key": KEY})[1]["Location"].startswith("/login")   # invalid name refused


def test_csrf_and_origin_are_enforced(console):
    app, mk, _ = console
    c = mk(); c.login()
    assert c.req("POST", "/sources/register", {"source_id": "abc-def", "label": "x", "_nocsrf": 1})[0] == 403
    assert c.req("POST", "/sources/register", {"source_id": "abc-def", "label": "x", "csrf": "wrong"})[0] == 403
    assert c.req("POST", "/sources/register", {"source_id": "abc-def", "label": "x"}, headers={"Origin": "http://evil.example"})[0] == 403
    assert c.req("POST", "/sources/register", {"source_id": "abc-def", "label": "x"})[0] == 303
    assert app.registry().get("abc-def").authorization == "pending"


def test_only_loopback_binding_is_allowed(tmp_path):
    with pytest.raises(ValueError):
        run_server(OperatorApp(tmp_path / "d", tmp_path / "f.json", KEY), "0.0.0.0", 0)


def test_full_workflow_upload_correct_decide_replay_publish(console):
    app, mk, tmp = console
    c = mk(); c.login("Awa")
    setup_source(c)
    s, _, body = upload(c, url="https://www.facebook.com/example/posts/1")
    assert s == 200 and b"evidence preserved, event extracted" in body
    eid = event_id(body)
    st = RadarStore(app.root)
    ev = st.all_evidence()[0]
    assert ev["metadata"]["permission_note"].startswith("Organizer agreed") and ev["source_url"] == "https://www.facebook.com/example/posts/1"
    assert ev["metadata"]["operator"] == "operator:Awa" and ev["evidence_state"] == "unverified"
    s, _, page = c.req("GET", f"/events/{eid}")
    assert s == 200 and b"AFRO NIGHT VOL.3" in page and b"Original evidence" in page and b"Club Exemple" in page
    media = re.search(rb'src="(/media/[0-9a-f]{64}\.png)"', page).group(1).decode()
    ms, mh, mb = c.req("GET", media)
    assert ms == 200 and mh["Content-Type"] == "image/png" and "sandbox" in mh["Content-Security-Policy"]
    assert mb == (app.root / media.lstrip("/")).read_bytes() and c.req("GET", "/media/../../etc/passwd")[0] == 404
    ver = int(re.search(rb'name="version" value="(\d+)"', page).group(1))
    # --- correct: title wording and end time that the poster shows
    n_claims_before = len(st.get_event(eid).field_claims)
    cid = re.search(rb'name="correction_id" value="([^"]+)"', page).group(1).decode()
    fields = {"version": ver, "correction_id": cid, "title": "NUIT AFRO VOL. 3", "end_time": "03:30", "note": "checked against poster"}
    s, h, _ = c.req("POST", f"/events/{eid}/correct", fields)
    assert s == 303
    s, _, page = c.req("GET", f"/events/{eid}")
    assert b"NUIT AFRO VOL. 3" in page and b"human-corrected" in page and b"03:30" in page
    assert c.req("POST", f"/events/{eid}/correct", fields)[0] == 303                      # replay of the same correction
    assert len(RadarStore(app.root).get_event(eid).field_claims) == n_claims_before + 2      # exactly the 2 changed fields, once
    # --- decide
    ver = int(re.search(rb'name="version" value="(\d+)"', page).group(1))
    did = re.search(rb'name="decision_id" value="([^"]+)"', page).group(1).decode()
    s, h, _ = c.req("POST", f"/events/{eid}/decide", {"version": ver, "decision_id": did, "decision": "approve", "note": "ok"})
    assert s == 303 and "Decision recorded" in h["Location"].replace("%20", " ")
    s, h, _ = c.req("POST", f"/events/{eid}/decide", {"version": ver, "decision_id": did, "decision": "approve", "note": "ok"})   # replay
    assert s == 303 and "already recorded" in h["Location"].replace("%20", " ")
    st2 = RadarStore(app.root)
    assert st2.get_event(eid).review_status == "approved"
    assert [h_["kind"] for h_ in st2.decisions(eid)] == ["human"] and sum(1 for a in st2.audit_log() if a["action"] == "review:approve") == 1
    assert len(st2.events()) == 1
    # --- stale decision (event changed after the form was rendered) is refused without changing anything
    s, _, pg = c.req("POST", f"/events/{eid}/decide", {"version": ver, "decision_id": "dec-" + "b" * 12, "decision": "reject"})
    assert s == 409 and b"NOT recorded" in pg and RadarStore(app.root).get_event(eid).review_status == "approved"
    # --- publish
    s, h, _ = c.req("POST", "/publish", {})
    assert s == 303
    feed = json.loads((tmp / "feed.json").read_text())
    assert feed["approved_only"] and feed["counts"] == {"events": 1, "venues": 1} and feed["contract_version"] == "1.1.0"
    e = feed["events"][0]
    assert e["title"] == "NUIT AFRO VOL. 3" and e["start_at"] == "2026-11-14T22:00:00+01:00" and e["end_at"] == "2026-11-15T03:30:00+01:00"
    assert e["venue"]["name"] == "Club Exemple" and e["review"]["human_corrected_fields"] == ["end_time", "title"]
    assert e["evidence"][0]["metadata"]["permission_note"] and e["evidence"][0]["source_id"] == "uploads-test"
    assert "operator:" not in json.dumps(feed)


def test_xss_in_extracted_text_is_escaped(console):
    app, mk, _ = console
    c = mk(); c.login(); setup_source(c)
    s, _, body = upload(c, '<script>alert(1)</script>\n14/11/2026\nLieu : <img src=x onerror=alert(2)>\n')
    eid = event_id(body)
    for p in (f"/events/{eid}", "/events", "/venues", "/"):
        _, _, page = c.req("GET", p)
        assert b"<script>alert(1)" not in page and b"<img src=x onerror" not in page
    assert b"&lt;script&gt;alert(1)" in c.req("GET", f"/events/{eid}")[2]


def test_upload_failures_store_nothing_and_explain(console):
    app, mk, _ = console
    c = mk(); c.login()
    s, _, b = upload(c)                                                  # no approved source exists
    assert s in (400, 200) and b"rejected" in b and len(RadarStore(app.root).all_evidence()) == 0
    setup_source(c)
    s, _, b = upload(c, note="no")                                       # permission note too short
    assert s == 400 and b"permission note is required" in b.lower()
    s, _, b = c.req("POST", "/upload", {"source_id": "uploads-test", "permission_note": "valid note here"}, files=[("files", "x.png", b"not an image")])
    assert s == 400 and b"rejected" in b
    s, _, b = upload(c, url="javascript:alert(1)")
    assert b"rejected" in b
    assert len(RadarStore(app.root).all_evidence()) == 0
    app.registry().revoke("uploads-test")
    assert b"rejected" in upload(c)[2]


def test_poster_without_text_waits_in_the_evidence_inbox_then_is_transcribed(console):
    app, mk, _ = console
    c = mk(); c.login(); setup_source(c)
    s, _, b = upload(c, text="")
    assert s == 200 and b"no text could be read" in b
    oid = re.search(rb"/evidence/([0-9a-f]{64})", b).group(1).decode()
    assert RadarStore(app.root).events() == [] and oid.encode() in c.req("GET", "/evidence")[2]
    s, h, _ = c.req("POST", f"/evidence/{oid}/transcribe", {"text": "BRUNCH TEST\n20/12/2026\nLieu : Bar Fictif, Akpakpa\n"})
    assert s == 303 and h["Location"].startswith("/events/evt_")
    ev = RadarStore(app.root).events()[0]
    assert ev.title == "BRUNCH TEST" and ev.field_claims[0].state == "unverified"      # typed by a person: unverified
    assert oid.encode() not in c.req("GET", "/evidence")[2].split(b"<table>")[1]


def test_venue_directory_edit_validation_and_merge(console):
    app, mk, _ = console
    c = mk(); c.login(); setup_source(c)
    a = event_id(upload(c, "SOIREE ONE\n10/12/2026\nLieu : Club Exemple, Haie Vive\n", seed=1)[2])
    b = event_id(upload(c, "SOIREE TWO\n11/12/2026\nLieu : Le Club Exemple\n", seed=2)[2])
    st = RadarStore(app.root)
    va, vb = st.get_event(a).venue_id, st.get_event(b).venue_id
    _, _, vp = c.req("GET", f"/venues/{vb}")
    assert b"candidate" in vp and va.encode() not in b"" and b"Merge a duplicate" in vp
    s, _, pg = c.req("POST", f"/venues/{va}/link", {"kind": "instagram", "url": "http://instagram.com/x", "official": "on"})
    assert s == 400 and b"Not saved" in pg and b"https" in pg
    s, _, pg = c.req("POST", f"/venues/{va}/contact", {"kind": "phone", "value": "+229 01 90 00 00 00", "authorized": "on", "authorization_note": ""})
    assert s == 400 and b"authorization_note" in pg
    s, _, pg = c.req("POST", f"/venues/{va}/verify", {"status": "verified", "note": ""})
    assert s == 400
    assert c.req("POST", f"/venues/{va}/link", {"kind": "instagram", "url": "https://www.instagram.com/club_exemple", "official": "on"})[0] == 303
    assert c.req("POST", f"/venues/{va}/contact", {"kind": "phone", "value": "+229 01 90 00 00 00", "authorized": "on", "authorization_note": "printed on its own poster"})[0] == 303
    assert c.req("POST", f"/venues/{va}/edit", {"venue_type": "club", "district": "Haie Vive", "address": "Rue Test"})[0] == 303
    assert c.req("POST", f"/venues/{va}/verify", {"status": "verified", "note": "official Instagram page matches the poster"})[0] == 303
    assert c.req("POST", f"/venues/{va}/merge", {"source": vb})[0] == 303
    st = RadarStore(app.root)
    assert st.get_venue(vb).merged_into == va and st.get_event(b).venue_id == va
    _, _, vp = c.req("GET", f"/venues/{va}")
    assert b"instagram" in vp and b"printed on its own poster" in vp and b"verified" in vp and b"SOIREE TWO" in vp
    s, h, _ = c.req("GET", f"/venues/{vb}")
    assert s == 303 and h["Location"] == f"/venues/{va}"                                  # merged record redirects
    assert c.req("POST", f"/venues/{va}/merge", {"source": vb})[0] == 400


def test_backup_from_the_console_is_verifiable(console):
    app, mk, _ = console
    c = mk(); c.login(); setup_source(c); upload(c)
    assert c.req("POST", "/backup", {})[0] == 303
    _, _, pg = c.req("GET", "/ops")
    assert b"all checks passed" in pg and b"verified" in pg and b"backup-" in pg
    # damage the evidence: the integrity check must say so
    next((app.root / "media").iterdir()).write_bytes(b"altered")
    assert b"problem(s)" in c.req("GET", "/ops")[2]


def test_unknown_route_and_oversized_body(console):
    app, mk, _ = console
    c = mk(); c.login()
    assert c.req("GET", "/nope")[0] == 404
    conn = http.client.HTTPConnection("127.0.0.1", c.port)
    conn.request("POST", "/upload", body=b"x", headers={"Cookie": c.cookie, "Content-Length": str(99 * 1024 * 1024), "Content-Type": "multipart/form-data; boundary=x"})
    assert conn.getresponse().status == 413
