"""Routes and pages of the operator console (see operator_app.py for scope and limits)."""
from __future__ import annotations

import hmac
import json
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from radar_contracts import EVENT_CATEGORIES, LINK_KINDS, VENUE_TYPES, ContractError, EvidenceRecord
from scout_fabric.intake import RejectedUpload
from scout_fabric.sources import ALTERNATIVES, Source, UnauthorizedSource

from . import ops
from .cli import write_atomic
from .curation import CORRECTABLE, UNKNOWN_TOKEN, apply_correction, corrections, effective, merge_venues, update_venue
from .operator_app import MAX_BODY, SOURCE_ID_RE, OperatorApp, Response, esc, parse_multipart, redirect
from .pipeline import process_evidence, run_upload
from .store import DecisionConflict, RadarStore, StaleWrite

MEDIA_RE = re.compile(r"^[0-9a-f]{64}\.(png|jpe?g|webp|mp4|mov|webm)$")
MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
FIELD_LABELS = {"title": "Title", "start_date": "Date (YYYY-MM-DD)", "start_time": "Start (HH:MM)", "end_time": "End (HH:MM)", "venue": "Venue",
                "district": "District", "category": "Category", "organizer": "Organizer", "performer": "Performers (comma-separated)",
                "ticket": "Ticket / price", "description": "Description"}
STATE_CLS = {"observed": "ok", "derived": "warn", "unverified": "warn", "unknown": "bad"}


class Req:
    def __init__(self, s, q, form, files, m):
        self.s, self.q, self.form, self.files, self.m = s, q, form, files, m

    def f(self, k: str, default: str = "") -> str:
        v = self.form.get(k)
        return (v[0] if v else default).strip() if isinstance(v, list) else default


@contextmanager
def store_ctx(app: OperatorApp):
    st = RadarStore(app.root)
    try:
        yield st
    finally:
        st.close()


def make_handler(app: OperatorApp):
    routes: list[tuple[str, re.Pattern, callable, bool]] = []

    def route(method: str, pattern: str, public: bool = False):
        def deco(fn):
            routes.append((method, re.compile("^" + pattern + "$"), fn, public))
            return fn
        return deco

    def op(r: Req) -> str:
        return app.op(r.s)

    def page(r: Req, title: str, body: str, msg: str = "", status: int = 200) -> Response:
        resp = app.layout(title, body, r.s, msg or r.q.get("msg", [""])[0])
        resp.status = status
        return resp

    def back(to: str, msg: str) -> Response:
        return redirect(f"{to}{'&' if '?' in to else '?'}msg={quote(msg)}")

    def fdt(iso: str | None) -> str:
        return esc((iso or "")[:16].replace("T", " ")) if iso else "—"

    # ================================================================= auth / health
    @route("GET", "/health", public=True)
    def health(r):
        return Response(json.dumps({"status": "ok"}), ctype="application/json")

    @route("GET", "/login", public=True)
    def login_form(r):
        msg = {"1": "Wrong name or key.", "2": "Too many attempts. Wait a minute."}.get(r.q.get("e", [""])[0], "")
        body = ('<p class="mut">Local operator console. Enter your name (recorded on every action) and the launch key printed when the console started.</p>'
                '<form method="post" action="/login"><label>Your name</label><input name="name" required maxlength="40" autocomplete="name">'
                '<label>Launch key</label><input name="key" type="password" required autocomplete="off"><button class="go">Sign in</button></form>')
        return app.layout("Operator sign-in", body, None, msg)

    @route("POST", "/login", public=True)
    def login(r):
        sid, why = app.login(r.f("name"), r.f("key"))
        if not sid:
            return redirect("/login?e=" + ("2" if why == "locked" else "1"))
        resp = redirect("/")
        resp.cookies = [f"op_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800"]  # type: ignore[attr-defined]
        return resp

    @route("POST", "/logout")
    def logout(r):
        for sid, s in list(app.sessions.items()):
            if s is r.s:
                app.sessions.pop(sid)
        resp = redirect("/login")
        resp.cookies = ["op_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"]  # type: ignore[attr-defined]
        return resp

    # ================================================================= dashboard
    @route("GET", "/")
    def dashboard(r):
        with store_ctx(app) as st:
            evs = st.events()
            by = {k: sum(1 for e in evs if e.review_status == k) for k in ("pending", "correction_requested", "approved", "rejected")}
            inbox = len(_inbox(st))
            cands = sum(1 for v in st.venues() if v.verification_status == "candidate" and not v.merged_into)
            srcs = app.registry().all()
            body = (f'<div class="row"><div class="card"><b>{len(srcs)}</b> sources ({sum(1 for s in srcs if s.authorization == "approved")} approved)</div>'
                    f'<div class="card"><b>{len(st.all_evidence())}</b> evidence records</div><div class="card"><b>{inbox}</b> awaiting transcription</div>'
                    f'<div class="card"><b>{by["pending"] + by["correction_requested"]}</b> to review · <b>{by["approved"]}</b> approved · <b>{by["rejected"]}</b> rejected</div>'
                    f'<div class="card"><b>{len([v for v in st.venues() if not v.merged_into])}</b> venues ({cands} possible duplicates)</div></div>'
                    '<h2>Workflow</h2><ol><li><a href="/sources">Register and approve a source</a></li><li><a href="/upload">Upload a poster</a></li>'
                    '<li>Open the event, check the extraction against the poster, correct it</li><li>Approve or reject</li><li>Publish</li></ol>'
                    f'<form method="post" action="/publish">{app.csrf(r.s)}<button class="go">Publish approved events to PULSE feed</button></form>')
            if app.feed_path.exists():
                try:
                    fd = json.loads(app.feed_path.read_text())
                    body += f'<p class="mut">Published feed: {fd["counts"]["events"]} events, {fd["counts"]["venues"]} venues, generated {fdt(fd["generated_at"])} UTC → {esc(app.feed_path)}</p>'
                except (OSError, ValueError, KeyError):
                    body += '<p class="badge bad">Published feed exists but is unreadable: publish again.</p>'
            if app.pulse_url:
                body += f'<p><a class="btn" href="{esc(app.pulse_url)}/radar">Open PULSE Radar</a></p>'
            body += '<h2>Latest events</h2>' + _event_table(st, evs[-5:][::-1])
        return page(r, "Dashboard", body)

    def _inbox(st):
        linked = {x[0] for x in st.db.execute("SELECT observation_id FROM obs_event")}
        return [e for e in st.all_evidence() if e["observation_id"] not in linked]

    # ================================================================= sources
    @route("GET", "/sources")
    def sources(r):
        rows = ""
        for s in app.registry().all():
            act = ""
            if s.authorization != "approved":
                act += f'<form method="post" action="/sources/approve" style="display:inline">{app.csrf(r.s)}<input type="hidden" name="source_id" value="{esc(s.source_id)}"><button class="go">Approve as {esc(r.s["name"])}</button></form>'
            if s.authorization == "approved":
                act += f'<form method="post" action="/sources/revoke" style="display:inline">{app.csrf(r.s)}<input type="hidden" name="source_id" value="{esc(s.source_id)}"><button class="no">Revoke</button></form>'
            cls = {"approved": "ok", "revoked": "bad"}.get(s.authorization, "warn")
            rows += f'<tr><td><code>{esc(s.source_id)}</code></td><td>{esc(s.platform)}</td><td>{esc(s.label)}</td><td><span class="badge {cls}">{esc(s.authorization)}</span>{"by " + esc(s.approved_by) if s.approved_by else ""}</td><td>{act}</td></tr>'
        body = ('<p class="mut">Nothing is acquired from a source that is not registered <b>and</b> approved by a named person. '
                f'Only operator uploads are enabled; other adapters stay disabled until separately authorized. {esc(ALTERNATIVES["facebook_page"])}</p>'
                f'<table><tr><th>ID</th><th>Type</th><th>Label</th><th>Authorization</th><th></th></tr>{rows or "<tr><td colspan=5 class=mut>No sources yet.</td></tr>"}</table>'
                f'<h2>Register a source</h2><form method="post" action="/sources/register">{app.csrf(r.s)}<div class="row"><div><label>ID (a-z, 0-9, -)</label><input name="source_id" required pattern="[a-z0-9][a-z0-9-]{{2,40}}"></div>'
                '<div><label>Label (who/what is this source?)</label><input name="label" required maxlength="80"></div></div><label>Page or website URL (optional, https)</label><input name="url" type="url"><button class="go">Register (pending approval)</button></form>')
        return page(r, "Sources", body)

    @route("POST", "/sources/register")
    def source_register(r):
        sid, label, url = r.f("source_id"), r.f("label"), r.f("url")
        if not SOURCE_ID_RE.match(sid) or not 1 <= len(label) <= 80 or (url and not url.startswith("https://")):
            return back("/sources", "Invalid source: id 3-41 chars a-z0-9-, label required, URL must be https.")
        app.registry().register(Source(sid, "upload", label, url=url or None))
        return back("/sources", f"Source {sid} registered. It is pending approval and cannot be used yet.")

    @route("POST", "/sources/approve")
    def source_approve(r):
        try:
            app.registry().approve(r.f("source_id"), op(r))
        except (UnauthorizedSource, ValueError) as exc:
            return back("/sources", f"Could not approve: {exc}")
        return back("/sources", "Source approved by " + op(r))

    @route("POST", "/sources/revoke")
    def source_revoke(r):
        try:
            app.registry().revoke(r.f("source_id"))
        except UnauthorizedSource as exc:
            return back("/sources", f"Could not revoke: {exc}")
        return back("/sources", "Source revoked. Existing evidence is kept.")

    # ================================================================= upload / evidence
    @route("GET", "/upload")
    def upload_form(r, msg="", status=200):
        approved = [s for s in app.registry().all() if s.authorization == "approved" and s.platform == "upload"]
        opts = "".join(f'<option value="{esc(s.source_id)}">{esc(s.label)} ({esc(s.source_id)})</option>' for s in approved)
        ocr = "available (Tesseract, French+English)" if app.ocr.available() else "NOT installed: paste a transcription, or the poster waits in the evidence inbox"
        body = (('<p class="badge bad">No approved source. <a href="/sources">Register and approve one first.</a></p>' if not approved else "") +
                f'<p class="mut">OCR: {esc(ocr)}. Originals are stored unchanged under their SHA-256; extraction never edits them.</p>'
                f'<form method="post" action="/upload" enctype="multipart/form-data">{app.csrf(r.s)}<label>Source</label><select name="source_id" required>{opts}</select>'
                '<label>Poster image or video (PNG, JPEG, WEBP, MP4, MOV, WEBM)</label><input type="file" name="files" multiple required accept="image/*,video/*">'
                '<label>Permission note (required): who authorized use of this poster, and how</label><textarea name="permission_note" required minlength="5" maxlength="300" rows="2" placeholder="e.g. Organizer confirmed by WhatsApp on 2026-11-02 that we may use this poster"></textarea>'
                '<label>Where was it found? (optional https link to the post/page)</label><input name="source_url" type="url">'
                '<label>Transcription (optional; single file only; marked UNVERIFIED because a person typed it)</label><textarea name="transcription" rows="5" maxlength="4000"></textarea>'
                '<button class="go">Upload and extract</button></form>')
        return page(r, "Upload poster", body, msg, status)

    @route("POST", "/upload")
    def upload(r):
        sid, note, url = r.f("source_id"), r.f("permission_note"), r.f("source_url")
        files = [f for f in r.files if f[0] == "files"][:20]
        if len(note) < 5:
            return upload_form(r, "A permission note is required (who authorized this poster, and how).", 400)
        if not files:
            return upload_form(r, "Choose at least one file.", 400)
        text = r.f("transcription") if len(files) == 1 else ""
        results = []
        with store_ctx(app) as st, tempfile.TemporaryDirectory() as td:
            for _, name, data in files:
                safe = re.sub(r"[^\w.-]", "_", name)[:80] or "upload"
                path = Path(td) / safe
                path.write_bytes(data)
                try:
                    res = run_upload(st, app.registry(), path, sid, app.provider(text), source_url=url or None,
                                     extra_metadata={"permission_note": note, "operator": op(r), "via": "operator_console", "original_name": name})
                    st.audit(op(r), "upload", res["observation_id"], {"file": safe, "created": res["evidence_created"], "event_id": res["event_id"]})
                    results.append((name, "ok", res))
                except UnauthorizedSource as exc:
                    results.append((name, "rejected", f"{exc.reason}. {exc.alternative}"))
                except (RejectedUpload, ValueError) as exc:
                    results.append((name, "rejected", str(exc)))
        rows = ""
        for name, st_, res in results:
            if st_ == "ok":
                if res["event_id"]:
                    link = f'<a href="/events/{esc(res["event_id"])}">Review the extraction →</a>'
                    note_ = "evidence already existed" if not res["evidence_created"] else "evidence preserved, event extracted"
                else:
                    link = f'<a href="/evidence/{esc(res["observation_id"])}">Add transcription →</a>'
                    note_ = "evidence preserved; no text could be read"
                rows += f'<tr><td>{esc(name)}</td><td><span class="badge ok">stored</span>{esc(note_)}</td><td>{link}</td></tr>'
            else:
                rows += f'<tr><td>{esc(name)}</td><td><span class="badge bad">rejected</span>{esc(res)}</td><td></td></tr>'
        any_bad = any(x[1] == "rejected" for x in results)
        return page(r, "Upload result", f'<table>{rows}</table><p><a class="btn" href="/upload">Upload more</a></p>', status=400 if any_bad and len(results) == 1 else 200)

    @route("GET", "/evidence")
    def evidence_list(r):
        with store_ctx(app) as st:
            items = _inbox(st)
        rows = "".join(f'<tr><td>{fdt(e["collected_at"])}</td><td>{esc(e.get("original_filename"))}</td><td>{esc(e["source_id"])}</td><td><a href="/evidence/{esc(e["observation_id"])}">Transcribe →</a></td></tr>' for e in items)
        return page(r, "Evidence inbox", '<p class="mut">Posters that are preserved as evidence but have no event yet (no readable text).</p>' +
                    f'<table><tr><th>Captured (UTC)</th><th>File</th><th>Source</th><th></th></tr>{rows or "<tr><td colspan=4 class=mut>Nothing waiting.</td></tr>"}</table>')

    @route("GET", "/evidence/([0-9a-f]{64})")
    def evidence_page(r):
        with store_ctx(app) as st:
            e = st.get_evidence(r.m.group(1))
            if not e:
                return page(r, "Not found", "<p>No such evidence.</p>", status=404)
            eid = st.event_for_observation(e["observation_id"])
            body = (_evidence_card(e, True) + (f'<p><a class="btn" href="/events/{esc(eid)}">Open its event →</a></p>' if eid else
                    f'<form method="post" action="/evidence/{esc(e["observation_id"])}/transcribe">{app.csrf(r.s)}<label>Type what the poster says (one line per line; this is stored as UNVERIFIED)</label>'
                    '<textarea name="text" rows="8" required minlength="3" maxlength="4000"></textarea><button class="go">Extract from transcription</button></form>'))
        return page(r, "Evidence", body)

    @route("POST", "/evidence/([0-9a-f]{64})/transcribe")
    def transcribe(r):
        text = r.f("text")
        with store_ctx(app) as st:
            e = st.get_evidence(r.m.group(1))
            if not e or len(text) < 3:
                return back("/evidence", "Evidence not found or text too short.")
            ev = process_evidence(st, EvidenceRecord(**e), app.provider(text), st.root / e["raw_media_reference"])
            st.audit(op(r), "transcribed", e["observation_id"], {"event_id": ev.event_id if ev else None})
        return redirect(f"/events/{ev.event_id}") if ev else back(f"/evidence/{r.m.group(1)}", "No event could be extracted from that text.")

    def _evidence_card(e: dict, big: bool = False) -> str:
        ref = (e.get("raw_media_reference") or "").split("/")[-1]
        media = ""
        if MEDIA_RE.match(ref):
            media = (f'<video controls class="poster" src="/media/{esc(ref)}"></video>' if e.get("media_type") == "video" else f'<img class="poster" alt="Original poster" src="/media/{esc(ref)}">')
        m = e.get("metadata", {})
        src = f' · <a href="{esc(e["source_url"])}" rel="noreferrer noopener">found at</a>' if e.get("source_url") else ""
        return (f'<div class="card">{media}<p class="mut">Source <code>{esc(e["source_id"])}</code> · captured {fdt(e["collected_at"])} UTC · {esc(e.get("original_filename"))}{src}<br>'
                f'<span class="badge {"warn" if e["evidence_state"] == "unverified" else "ok"}">{esc(e["evidence_state"])}</span> original social context not independently verified · '
                f'sha256 <code>{esc(e["content_hash"][:16])}…</code><br>Permission: {esc(m.get("permission_note", "—"))}</p></div>')

    @route("GET", "/media/([0-9a-f]{64}\\.[a-z0-9]+)")
    def media(r):
        name = r.m.group(1)
        f = app.root / "media" / name
        if not MEDIA_RE.match(name) or not f.is_file():
            return Response("Not found", 404, ctype="text/plain")
        return Response(f.read_bytes(), 200, {"Content-Security-Policy": "sandbox; default-src 'none'"}, MEDIA_TYPES[name.rsplit(".", 1)[1]])

    # ================================================================= events
    def _venue_name(st, vid):
        v = st.get_venue(vid) if vid else None
        return v.name if v else "unknown"

    def _event_table(st, evs):
        rows = "".join(f'<tr><td><a href="/events/{esc(e.event_id)}">{esc(e.title or "(title unknown)")}</a></td><td>{esc((e.start_at or "date unknown")[:16].replace("T", " "))}</td>'
                       f'<td>{esc(_venue_name(st, e.venue_id))}</td><td>{app.status_badge(e.review_status)}</td><td>{esc(e.confidence)}</td><td>{len(e.evidence_references)}</td></tr>' for e in evs)
        return f'<table><tr><th>Event</th><th>When</th><th>Venue</th><th>Status</th><th>Confidence</th><th>Sources</th></tr>{rows or "<tr><td colspan=6 class=mut>No events.</td></tr>"}</table>'

    @route("GET", "/events")
    def events(r):
        flt = r.q.get("status", [""])[0]
        with store_ctx(app) as st:
            evs = [e for e in st.events() if not flt or e.review_status == flt]
            chips = "".join(f'<a class="btn" href="/events{"?status=" + k if k else ""}">{lbl}</a> ' for k, lbl in (("", "All"), ("pending", "To review"), ("correction_requested", "Correction requested"), ("approved", "Approved"), ("rejected", "Rejected")))
            body = f"<p>{chips}</p>" + _event_table(st, evs[::-1])
        return page(r, "Events", body)

    @route("GET", "/events/(evt_[0-9a-f]+)")
    def event_page(r, msg="", status=200):
        with store_ctx(app) as st:
            return _render_event(r, st, r.m.group(1), msg, status)

    def _render_event(r, st, eid, msg="", status=200):
        ev = st.get_event(eid)
        if not ev:
            return page(r, "Not found", "<p>No such event.</p>", status=404)
        ver = st.event_version(eid)
        parties = {p.party_id: p for p in st.parties()}
        perf = ", ".join(parties[i].name for i in ev.performer_ids if i in parties)
        cur = {f: (perf if f == "performer" else (effective(ev.field_claims, f).value if effective(ev.field_claims, f) else "")) or "" for f in CORRECTABLE}
        eff_rows = ""
        for f in CORRECTABLE:
            c = effective(ev.field_claims, f)
            human = c is not None and c.method.startswith("human:")
            state = c.state if c else "unknown"
            eff_rows += (f'<tr><td>{esc(FIELD_LABELS[f])}</td><td>{esc(cur[f]) or "<span class=mut>unknown</span>"}</td><td><span class="badge {STATE_CLS.get(state, "warn")}">{esc(state)}</span>'
                         f'{"<span class=badge>human-corrected</span>" if human else ""}</td><td class="mut">{esc((c.method.split(":")[0] + ":" + c.method.split(":")[1]) if c and not human else ("human" if human else ""))}</td></tr>')
        claims = "".join(f'<tr><td>{esc(c.field)}</td><td>{esc(c.value)}</td><td>{esc(c.state)}</td><td>{esc(c.method.split(":")[0] if c.method.startswith("human") else c.method)}</td><td><code>{esc(c.evidence_ids[0][:8]) if c.evidence_ids else ""}</code></td><td class="mut">{esc(c.snippet)}</td></tr>' for c in ev.field_claims)
        conflicts = "".join(f'<div class="card"><b>{esc(c["field"])}</b>: ' + " ≠ ".join(esc(v["value"]) for v in c["values"]) +
                            (f' <span class="badge ok">resolved by reviewer → {esc(c.get("resolved_value"))}</span>' if c.get("resolved") else ' <span class="badge bad">unresolved: correct the field to settle it</span>') + "</div>" for c in ev.contradictions)
        evid = "".join(_evidence_card(e) for e in (st.get_evidence(x) for x in ev.evidence_references) if e)
        inputs = ""
        for f in CORRECTABLE:
            if f == "category":
                o = "".join(f'<option value="{c}"{" selected" if cur[f] == c else ""}>{c.replace("_", " ")}</option>' for c in EVENT_CATEGORIES)
                inputs += f'<div><label>{esc(FIELD_LABELS[f])}</label><select name="{f}"><option value="">(unchanged)</option>{o}</select></div>'
            else:
                inputs += f'<div><label>{esc(FIELD_LABELS[f])}</label><input name="{f}" value="{esc(cur[f])}" maxlength="{500 if f == "description" else 120}"><label style="display:inline"><input type="checkbox" name="clear_{f}" style="width:auto"> not on the poster (mark unknown)</label></div>'
        ev_opts = "".join(f'<option value="{esc(x)}">{esc(x[:10])}…</option>' for x in ev.evidence_references)
        hist = "".join(f'<tr><td>{fdt(h["at"])}</td><td>{esc(h["kind"])}</td><td>{esc(h["decision"])} → {esc(h["resulting_status"])}</td><td>{esc(h["reviewer"])}</td><td class="mut">{esc(h["note"])}</td></tr>' for h in st.decisions(eid))
        hist += "".join(f'<tr><td>{fdt(c["at"])}</td><td>correction</td><td>{esc(", ".join(c["changes"]))}</td><td>{esc(c["reviewer"])}</td><td class="mut">{esc(c["note"])}</td></tr>' for c in corrections(st, eid))
        body = (f'<p>{app.status_badge(ev.review_status)}<span class="badge">version {ver}</span><span class="badge">confidence {esc(ev.confidence)}</span>'
                f'<span class="badge">{len(ev.evidence_references)} source(s)</span></p><div class="cols"><div><h2>Original evidence</h2>{evid}</div><div><h2>What ANA read (current values)</h2>'
                f'<table><tr><th>Field</th><th>Value</th><th>State</th><th>How</th></tr>{eff_rows}</table>'
                f'<p class="mut">Organizer: {esc(parties[ev.organizer_id].name) if ev.organizer_id in parties else "unknown"} · Venue: <a href="/venues/{esc(ev.venue_id)}">{esc(_venue_name(st, ev.venue_id))}</a></p>{conflicts}</div></div>'
                f'<h2>Correct the extraction</h2><p class="mut">Compare with the original poster. Only changed fields are saved, as new human claims; what ANA read stays on record.</p>'
                f'<form method="post" action="/events/{esc(eid)}/correct">{app.csrf(r.s)}<input type="hidden" name="version" value="{ver}"><input type="hidden" name="correction_id" value="cor-{uuid.uuid4()}">'
                f'<div class="row">{inputs}</div><label>Checked against evidence</label><select name="evidence_id">{ev_opts}</select><label>Note (optional)</label><input name="note" maxlength="200"><button class="go">Save corrections</button></form>'
                f'<h2>Decision</h2><form method="post" action="/events/{esc(eid)}/decide">{app.csrf(r.s)}<input type="hidden" name="version" value="{ver}"><input type="hidden" name="decision_id" value="dec-{uuid.uuid4()}">'
                f'<label>Note (optional)</label><input name="note" maxlength="500"><p><button class="go" name="decision" value="approve">Approve</button> <button name="decision" value="request_correction">Request correction</button> <button class="no" name="decision" value="reject">Reject</button></p>'
                f'<p class="mut">Decisions are recorded under <b>{esc(op(r))}</b>. Approving does not publish; use Publish.</p></form>'
                f'<h2>History</h2><table><tr><th>When (UTC)</th><th>Kind</th><th>What</th><th>By</th><th>Note</th></tr>{hist or "<tr><td colspan=5 class=mut>No decisions yet.</td></tr>"}</table>'
                f'<details><summary>All extracted claims ({len(ev.field_claims)})</summary><table><tr><th>Field</th><th>Value</th><th>State</th><th>Method</th><th>Evidence</th><th>Snippet</th></tr>{claims}</table></details>')
        return page(r, ev.title or "(title unknown)", body, msg, status)

    @route("POST", "/events/(evt_[0-9a-f]+)/correct")
    def event_correct(r):
        eid = r.m.group(1)
        with store_ctx(app) as st:
            ev = st.get_event(eid)
            if not ev:
                return page(r, "Not found", "<p>No such event.</p>", status=404)
            seen = st.db.execute("SELECT event_id, reviewer FROM corrections WHERE correction_id=?", (r.f("correction_id"),)).fetchone()
            if seen and seen == (eid, op(r)):                  # double-submit of a form that was already saved: harmless
                return back(f"/events/{eid}", "That correction was already saved (replay ignored).")
            parties = {p.party_id: p for p in st.parties()}
            perf = ", ".join(parties[i].name for i in ev.performer_ids if i in parties)
            changes = {}
            for f in CORRECTABLE:
                c = effective(ev.field_claims, f)
                current = perf if f == "performer" else (c.value if c and c.value else "")
                if r.f(f"clear_{f}"):
                    if current:
                        changes[f] = UNKNOWN_TOKEN
                elif r.f(f) and r.f(f) != current:
                    changes[f] = r.f(f)
            try:
                _, status = apply_correction(st, eid, changes, op(r), r.f("note"), r.f("correction_id"), int(r.f("version") or 0), r.f("evidence_id") or None)
            except StaleWrite as exc:
                return _render_event(r, st, eid, f"Not saved: this event changed since you opened it ({exc}). Review the current values and try again.", 409)
            except DecisionConflict as exc:
                return _render_event(r, st, eid, f"Not saved: {exc}", 409)
            except (ContractError, PermissionError, ValueError) as exc:
                return _render_event(r, st, eid, f"Not saved: {exc}", 400)
        return back(f"/events/{eid}", "Corrections saved." if status == "applied" else "That correction was already saved (replay ignored).")

    @route("POST", "/events/(evt_[0-9a-f]+)/decide")
    def event_decide(r):
        eid = r.m.group(1)
        with store_ctx(app) as st:
            try:
                _, status = st.review_decision(eid, r.f("decision"), op(r), r.f("note"), r.f("decision_id"), int(r.f("version") or 0))
            except StaleWrite as exc:
                return _render_event(r, st, eid, f"Decision NOT recorded: the event changed since you opened it ({exc}). Review the current values.", 409)
            except DecisionConflict as exc:
                return _render_event(r, st, eid, f"Decision NOT recorded: {exc}", 409)
            except KeyError:
                return page(r, "Not found", "<p>No such event.</p>", status=404)
            except (ContractError, PermissionError, ValueError) as exc:
                return _render_event(r, st, eid, f"Decision NOT recorded: {exc}", 400)
        return back(f"/events/{eid}", "Decision recorded." if status == "applied" else "This decision was already recorded (replay ignored; nothing changed).")

    # ================================================================= venues
    def _venue_rows(st, vs):
        evs = st.events()
        rows = ""
        for v in vs:
            mine = [e for e in evs if e.venue_id == v.venue_id]
            last = max((x["collected_at"] for e in mine for x in (st.get_evidence(i) or {"collected_at": ""} for i in e.evidence_references)), default="")
            cls = {"verified": "ok", "candidate": "warn"}.get(v.verification_status, "")
            rows += (f'<tr><td><a href="/venues/{esc(v.venue_id)}">{esc(v.name)}</a></td><td>{esc(v.district) or "—"}</td><td>{esc(v.venue_type) or "—"}</td>'
                     f'<td><span class="badge {cls}">{esc(v.verification_status)}</span></td><td>{len(mine)}</td><td>{fdt(last)}</td></tr>')
        return f'<table><tr><th>Venue</th><th>District</th><th>Category</th><th>Verification</th><th>Events</th><th>Last observed (UTC)</th></tr>{rows or "<tr><td colspan=6 class=mut>No venues yet.</td></tr>"}</table>'

    @route("GET", "/venues")
    def venues(r):
        with store_ctx(app) as st:
            vs = [v for v in st.venues() if not v.merged_into]
            dup = [v for v in vs if v.verification_status == "candidate"]
            body = (f'<p class="badge warn">{len(dup)} possible duplicate(s): open the venue to merge or dismiss</p>' if dup else "") + _venue_rows(st, vs)
        return page(r, "Venue directory", body)

    @route("GET", "/venues/(ven_[0-9a-f]+)")
    def venue_page(r, msg="", status=200):
        with store_ctx(app) as st:
            return _render_venue(r, st, r.m.group(1), msg, status)

    def _render_venue(r, st, vid, msg="", status=200):
        v = st.get_venue(vid)
        if not v:
            return page(r, "Not found", "<p>No such venue.</p>", status=404)
        if v.merged_into:
            return redirect(f"/venues/{v.merged_into}")
        evs = [e for e in st.events() if e.venue_id == vid]
        ev_rows = "".join(f'<tr><td><a href="/events/{esc(e.event_id)}">{esc(e.title or "(title unknown)")}</a></td><td>{esc((e.start_at or "date unknown")[:10])}</td><td>{app.status_badge(e.review_status)}</td></tr>' for e in evs)
        links = "".join(f'<li><a href="{esc(k["url"])}" rel="noreferrer noopener">{esc(k["kind"])}</a> {"<span class=badge ok>official</span>" if k.get("official") else ""} <span class="mut">{esc(k["url"])}</span></li>' for k in v.links) or '<li class="mut">none recorded</li>'
        contacts = "".join(f'<li>{esc(c["kind"])}: {esc(c["value"])} <span class="badge {"ok" if c.get("authorized") else "warn"}">{"public: " + esc(c.get("authorization_note")) if c.get("authorized") else "internal only"}</span></li>' for c in v.contacts) or '<li class="mut">none recorded</li>'
        srcs = "".join(f'<li><a href="/evidence/{esc(s)}"><code>{esc(s[:12])}…</code></a></li>' for s in v.source_references)
        others = [x for x in st.venues() if x.venue_id != vid and not x.merged_into]
        cand = [x for x in others if x.venue_id in v.candidate_matches or vid in x.candidate_matches]
        merge = ""
        if others:
            merge = (f'<h2>Merge a duplicate into this venue</h2><p class="mut">{"Suggested: " + ", ".join(esc(c.name) for c in cand) if cand else "No automatic suggestion."} Nothing is deleted; the merged record is kept and redirects here.</p>'
                     f'<form method="post" action="/venues/{esc(vid)}/merge">{app.csrf(r.s)}<select name="source">{"".join(f"<option value={esc(x.venue_id)}>{esc(x.name)} ({len([e for e in st.events() if e.venue_id == x.venue_id])} events)</option>" for x in others)}</select><button class="no">Merge selected venue into {esc(v.name)}</button></form>')
        vt = "".join(f'<option value="{t}"{" selected" if v.venue_type == t else ""}>{t.replace("_", " ")}</option>' for t in VENUE_TYPES)
        lk = "".join(f"<option>{k}</option>" for k in LINK_KINDS)
        vs = "".join(f'<option{" selected" if v.verification_status == s else ""}>{s}</option>' for s in ("unverified", "candidate", "verified"))
        stamps = [x["collected_at"] for e in evs for x in (st.get_evidence(i) for i in e.evidence_references) if x]
        body = (f'<p><span class="badge {"ok" if v.verification_status == "verified" else "warn"}">{esc(v.verification_status)}</span>{esc(v.verification_note)}{" · verified by " + esc(v.verified_by) if v.verified_by else ""}</p>'
                f'<div class="cols"><div class="card"><b>Category:</b> {esc(v.venue_type) or "unknown"}<br><b>District:</b> {esc(v.district) or "unknown"}<br><b>Address:</b> {esc(v.address) or "unknown"}<br>'
                f'<b>Coordinates:</b> {esc(v.latitude) if v.latitude is not None else "unknown"}, {esc(v.longitude) if v.longitude is not None else ""}<br><b>Also seen as:</b> {esc(", ".join(v.aliases)) or "—"}<br>'
                f'<b>Last observed activity:</b> {fdt(max(stamps) if stamps else None)} UTC</div><div class="card"><b>Official links</b><ul>{links}</ul><b>Contacts</b><ul>{contacts}</ul></div></div>'
                f'<h2>Events</h2><table><tr><th>Event</th><th>Date</th><th>Status</th></tr>{ev_rows or "<tr><td colspan=3 class=mut>No events.</td></tr>"}</table><h2>Source evidence</h2><ul>{srcs}</ul>'
                f'<h2>Edit</h2><form method="post" action="/venues/{esc(vid)}/edit">{app.csrf(r.s)}<div class="row"><div><label>Category</label><select name="venue_type"><option value="">(unchanged)</option>{vt}</select></div>'
                f'<div><label>District</label><input name="district" value="{esc(v.district)}"></div><div><label>Address</label><input name="address" value="{esc(v.address)}"></div>'
                f'<div><label>Latitude</label><input name="latitude" value="{esc(v.latitude if v.latitude is not None else "")}" inputmode="decimal"></div><div><label>Longitude</label><input name="longitude" value="{esc(v.longitude if v.longitude is not None else "")}" inputmode="decimal"></div></div><button class="go">Save</button></form>'
                f'<h2>Add official link</h2><form method="post" action="/venues/{esc(vid)}/link">{app.csrf(r.s)}<div class="row"><div><label>Kind</label><select name="kind">{lk}</select></div><div><label>https URL</label><input name="url" type="url" required></div></div>'
                f'<label style="display:inline"><input type="checkbox" name="official" style="width:auto" required> I confirmed this is the venue\'s own official page</label><button class="go">Add link</button></form>'
                f'<h2>Add contact</h2><form method="post" action="/venues/{esc(vid)}/contact">{app.csrf(r.s)}<div class="row"><div><label>Kind</label><select name="kind"><option>phone</option><option>whatsapp</option><option>email</option></select></div><div><label>Value</label><input name="value" required></div></div>'
                f'<label style="display:inline"><input type="checkbox" name="authorized" style="width:auto"> May be shown publicly</label><label>Authorization note (required if public)</label><input name="authorization_note" maxlength="200"><button class="go">Add contact</button></form>'
                f'<h2>Verification</h2><form method="post" action="/venues/{esc(vid)}/verify">{app.csrf(r.s)}<select name="status">{vs}</select><label>Note: how was it verified? (required for verified)</label><input name="note" value="{esc(v.verification_note)}" maxlength="300"><button class="go">Save verification</button></form>{merge}')
        return page(r, v.name, body, msg, status)

    def _venue_post(fn):
        def run(r):
            vid = r.m.group(1)
            with store_ctx(app) as st:
                try:
                    fn(st, vid, r)
                except KeyError:
                    return page(r, "Not found", "<p>No such venue.</p>", status=404)
                except (ContractError, PermissionError, ValueError) as exc:
                    return _render_venue(r, st, vid, f"Not saved: {exc}", 400)
            return back(f"/venues/{vid}", "Saved.")
        return run

    def _edit(st, vid, r):
        def num(k):
            return float(r.f(k)) if r.f(k) else None
        update_venue(st, vid, op(r), venue_type=r.f("venue_type") or None, address=r.f("address") or None, district=r.f("district") or None, latitude=num("latitude"), longitude=num("longitude"))
    routes.append(("POST", re.compile(r"^/venues/(ven_[0-9a-f]+)/edit$"), _venue_post(_edit), False))
    routes.append(("POST", re.compile(r"^/venues/(ven_[0-9a-f]+)/link$"), _venue_post(lambda st, vid, r: update_venue(st, vid, op(r), add_links=[{"kind": r.f("kind"), "url": r.f("url"), "official": bool(r.f("official"))}])), False))
    routes.append(("POST", re.compile(r"^/venues/(ven_[0-9a-f]+)/contact$"), _venue_post(lambda st, vid, r: update_venue(st, vid, op(r), add_contacts=[{"kind": r.f("kind"), "value": r.f("value"), "authorized": bool(r.f("authorized")), "authorization_note": r.f("authorization_note")}])), False))
    routes.append(("POST", re.compile(r"^/venues/(ven_[0-9a-f]+)/verify$"), _venue_post(lambda st, vid, r: update_venue(st, vid, op(r), verification_status=r.f("status"), verification_note=r.f("note"))), False))
    routes.append(("POST", re.compile(r"^/venues/(ven_[0-9a-f]+)/merge$"), _venue_post(lambda st, vid, r: merge_venues(st, r.f("source"), vid, op(r))), False))

    # ================================================================= publish / ops
    @route("POST", "/publish")
    def publish(r):
        with store_ctx(app) as st:
            feed = st.export_feed(approved_only=True)
        write_atomic(app.feed_path, json.dumps(feed, indent=2, ensure_ascii=False))
        with store_ctx(app) as st:
            st.audit(op(r), "published", str(app.feed_path), feed["counts"])
        return back("/", f"Published {feed['counts']['events']} approved event(s) and {feed['counts']['venues']} venue(s) to {app.feed_path.name}.")

    @route("GET", "/feed.json")
    def feed_json(r):
        with store_ctx(app) as st:
            return Response(json.dumps(st.export_feed(approved_only=True), indent=2, ensure_ascii=False), ctype="application/json")

    @route("GET", "/ops")
    def ops_page(r):
        with store_ctx(app) as st:
            res = ops.verify_store(st)
        probs = "".join(f"<li>{esc(p)}</li>" for p in res["problems"])
        bdir = app.root / "backups"
        rows = ""
        for b in sorted(bdir.glob("backup-*"), reverse=True)[:10] if bdir.is_dir() else []:
            pr = ops.verify_backup(b)
            rows += f'<tr><td><code>{esc(b.name)}</code></td><td><span class="badge {"ok" if not pr else "bad"}">{"verified" if not pr else "FAILED"}</span></td></tr>'
        body = (f'<h2>Integrity check</h2><p><span class="badge {"ok" if res["ok"] else "bad"}">{"all checks passed" if res["ok"] else str(len(res["problems"])) + " problem(s)"}</span> {esc(res["counts"])}</p>{"<ul>" + probs + "</ul>" if probs else ""}'
                f'<h2>Backup</h2><form method="post" action="/backup">{app.csrf(r.s)}<button class="go">Back up now (database + originals + manifest)</button></form>'
                f'<table><tr><th>Backup</th><th>Hash check</th></tr>{rows or "<tr><td colspan=2 class=mut>No backups yet.</td></tr>"}</table>'
                f'<p class="mut">Restore from the command line: <code>radar restore PATH --force</code> (existing data is moved aside, never deleted). Feed recovery: <b>Publish</b> again; the feed is always rebuilt from the database.</p>'
                f'<h2>Recent activity</h2>' + _audit_table(st_rows()))
        return page(r, "Backup & checks", body)

    def st_rows():
        with store_ctx(app) as st:
            return st.audit_log()[-30:][::-1]

    def _audit_table(rows):
        return "<table><tr><th>When (UTC)</th><th>Who</th><th>Action</th><th>Subject</th></tr>" + "".join(f'<tr><td>{fdt(a["at"])}</td><td>{esc(a["actor"])}</td><td>{esc(a["action"])}</td><td class="mut">{esc(str(a["subject"])[:40])}</td></tr>' for a in rows) + "</table>"

    @route("POST", "/backup")
    def backup(r):
        dest = app.root / "backups" / f"backup-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        m = ops.backup(app.root, dest)
        with store_ctx(app) as st:
            st.audit(op(r), "backup", dest.name, {"files": len(m["files"])})
        return back("/ops", f"Backup written to {dest}.")

    # ================================================================= HTTP plumbing
    class Handler(BaseHTTPRequestHandler):
        server_version = "AP001-Operator"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _finish(self, resp: Response, path: str):
            self.send_response(resp.status)
            hdrs = {"Content-Type": resp.ctype, "Content-Length": str(len(resp.body)), "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                    "Content-Security-Policy": "default-src 'self'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'", **resp.headers}
            for k, v in hdrs.items():
                self.send_header(k, v)
            for c in getattr(resp, "cookies", []):
                self.send_header("Set-Cookie", c)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(resp.body)
            print(json.dumps({"t": datetime.now(UTC).isoformat(timespec="seconds"), "m": self.command, "p": path, "s": resp.status}), file=sys.stderr, flush=True)

        def _handle(self, method: str):
            u = urlparse(self.path)
            path, q = u.path, parse_qs(u.query)
            try:
                sid, s = app.session_of(self)
                for m, pat, fn, public in routes:
                    mt = pat.match(path)
                    if m != method or not mt:
                        continue
                    if not public and not s:
                        return self._finish(redirect("/login") if method == "GET" else Response("authentication required", 401, ctype="text/plain"), path)
                    form, files = {}, []
                    if method == "POST":
                        origin = self.headers.get("Origin")
                        if origin and urlparse(origin).netloc != self.headers.get("Host"):
                            return self._finish(Response("cross-site request refused", 403, ctype="text/plain"), path)
                        n = int(self.headers.get("Content-Length") or 0)
                        if n > MAX_BODY or n < 0:
                            return self._finish(Response("request too large", 413, ctype="text/plain"), path)
                        raw = self.rfile.read(n)
                        ct = self.headers.get("Content-Type", "")
                        if ct.startswith("multipart/form-data"):
                            form, files = parse_multipart(ct, raw)
                        else:
                            form = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
                        if not public:
                            tok = (form.get("csrf") or [""])[0]
                            if not hmac.compare_digest(tok.encode(), s["csrf"].encode()):
                                return self._finish(Response("missing or invalid CSRF token", 403, ctype="text/plain"), path)
                    return self._finish(fn(Req(s, q, form, files, mt)), path)
                return self._finish(Response("Not found", 404, ctype="text/plain"), path)
            except Exception as exc:  # noqa: BLE001 - never leak internals to the browser
                print(json.dumps({"error": type(exc).__name__, "p": path}), file=sys.stderr, flush=True)
                return self._finish(Response("Internal error. See the console log.", 500, ctype="text/plain"), path)

        def do_GET(self):
            self._handle("GET")

        def do_HEAD(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler
