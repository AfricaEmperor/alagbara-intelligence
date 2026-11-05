"""AP-001 operator console: a LOCAL web application for the whole upload-to-published workflow.

  register source -> upload poster -> evidence preserved -> OCR/ANA extraction -> review & correct -> approve/reject
  -> persist -> publish approved feed (consumed by PULSE /radar)

Scope and limits (also in docs/ap-001/OPERATOR_GUIDE.md):
  * stdlib only; binds to loopback ONLY; one process, SQLite; not a production service and not a multi-user system.
  * Access needs a per-launch operator key (random unless supplied) + a chosen operator name, which is recorded on
    every action. This is a LOCAL control, NOT identity assurance: the production reviewer path is Supabase Auth in PULSE.
  * Every state-changing request needs a per-session CSRF token and a same-origin Origin header; every page escapes output.
  * Writes reuse the audited store operations (versioned, idempotent by client-generated ids).
"""
from __future__ import annotations

import hmac
import html
import re
import secrets
import threading
import time
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path

from scout_fabric.sources import SourceRegistry
from scout_fabric.text_providers import ChainProvider, StaticTextProvider, TesseractProvider

from .store import RadarStore

MAX_BODY = 30 * 1024 * 1024
SESSION_TTL = 8 * 3600
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
NAME_RE = re.compile(r"^[\w][\w .'-]{0,39}$")
CSS = """
:root{color-scheme:dark light;--bg:#101218;--panel:#1a1d27;--line:#2d3142;--fg:#eceef4;--mut:#9aa1b5;--acc:#ffb020;--ok:#3ecf8e;--bad:#ff6b6b}
@media (prefers-color-scheme:light){:root{--bg:#f6f7fb;--panel:#fff;--line:#d9dce8;--fg:#14161f;--mut:#5b6178;--acc:#b36b00;--ok:#0a7d4b;--bad:#c0392b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:14px 16px 70px}nav{display:flex;gap:8px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg)}
nav a,.btn,button{padding:9px 13px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--fg);text-decoration:none;font:inherit;min-height:40px;cursor:pointer}
button.go{background:var(--ok);color:#06210f;border-color:var(--ok);font-weight:600}button.no{background:var(--bad);color:#2a0606;border-color:var(--bad);font-weight:600}
h1{font-size:22px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:26px 0 8px}
table{width:100%;border-collapse:collapse}td,th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0}
input,select,textarea{width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);font:inherit;margin:4px 0}
label{display:block;font-size:13px;color:var(--mut);margin-top:8px}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.badge{display:inline-block;font-size:12px;padding:2px 8px;border:1px solid var(--line);border-radius:999px;margin-right:6px;color:var(--mut)}
.ok{color:var(--ok);border-color:var(--ok)}.bad{color:var(--bad);border-color:var(--bad)}.warn{color:var(--acc);border-color:var(--acc)}
.flash{border:1px solid var(--acc);padding:10px 12px;border-radius:10px;margin:10px 0}.mut{color:var(--mut)}img.poster{max-width:100%;max-height:480px;border-radius:10px;background:#000}
code{font-size:13px}.cols{display:grid;grid-template-columns:1fr;gap:16px}@media(min-width:820px){.cols{grid-template-columns:minmax(0,1fr) minmax(0,1.3fr)}}
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def parse_multipart(content_type: str, body: bytes):
    msg = BytesParser(policy=policy.default).parsebytes(b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    fields: dict[str, list[str]] = {}
    files: list[tuple[str, str, bytes]] = []
    for part in msg.iter_parts() if msg.is_multipart() else []:
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition") or ""
        fn = part.get_filename()
        data = part.get_payload(decode=True) or b""
        if fn is not None:
            if fn:
                files.append((name, Path(fn).name, data))
        else:
            fields.setdefault(name, []).append(data.decode("utf-8", errors="replace"))
    return fields, files


class Response:
    def __init__(self, body: str | bytes = "", status: int = 200, headers: dict | None = None, ctype: str = "text/html; charset=utf-8"):
        self.body = body.encode() if isinstance(body, str) else body
        self.status, self.headers, self.ctype = status, headers or {}, ctype


def redirect(to: str, cookies: list[str] | None = None) -> Response:
    r = Response("", 303, {"Location": to})
    r.cookies = cookies or []  # type: ignore[attr-defined]
    return r


class OperatorApp:
    def __init__(self, data_root: Path, feed_path: Path, operator_key: str | None = None, pulse_url: str | None = None):
        self.root, self.feed_path, self.pulse_url = Path(data_root), Path(feed_path), pulse_url
        self.root.mkdir(parents=True, exist_ok=True)
        self.key = operator_key or secrets.token_urlsafe(18)
        self.sessions: dict[str, dict] = {}
        self.failures: list[float] = []
        self.lock = threading.Lock()
        self.ocr = TesseractProvider()
        RadarStore(self.root).close()                         # create/migrate the database up front

    # ------------------------------------------------------------------ auth
    def session_of(self, handler) -> tuple[str | None, dict | None]:
        c = SimpleCookie(handler.headers.get("Cookie", ""))
        sid = c["op_session"].value if "op_session" in c else None
        s = self.sessions.get(sid) if sid else None
        if s and s["exp"] < time.time():
            self.sessions.pop(sid, None)
            return None, None
        return sid, s

    def login(self, name: str, key: str) -> tuple[str | None, str]:
        now = time.time()
        with self.lock:
            self.failures = [t for t in self.failures if now - t < 60]
            if len(self.failures) >= 5:
                return None, "locked"
            if not NAME_RE.match(name or "") or not hmac.compare_digest(key.encode(), self.key.encode()):
                self.failures.append(now)
                return None, "denied"
            sid = secrets.token_urlsafe(32)
            self.sessions[sid] = {"name": name.strip(), "csrf": secrets.token_urlsafe(24), "exp": now + SESSION_TTL}
            return sid, "ok"

    # ------------------------------------------------------------------ layout
    def layout(self, title: str, body: str, s: dict | None, msg: str = "") -> Response:
        nav = ""
        if s:
            nav = ("<nav>" + "".join(f'<a href="{u}">{t}</a>' for u, t in (("/", "Dashboard"), ("/upload", "Upload"), ("/evidence", "Evidence inbox"), ("/events", "Events"), ("/venues", "Venues"), ("/sources", "Sources"), ("/ops", "Backup &amp; checks"))) +
                   f'<form method="post" action="/logout" style="margin-left:auto">{self.csrf(s)}<button>Sign out ({esc(s["name"])})</button></form></nav>')
        flash = f'<div class="flash" role="status">{esc(msg)}</div>' if msg else ""
        return Response(f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{esc(title)} · AP-001 Operator</title><style>{CSS}</style>{nav}<main>{flash}<h1>{esc(title)}</h1>{body}</main></html>")

    @staticmethod
    def csrf(s: dict) -> str:
        return f'<input type="hidden" name="csrf" value="{esc(s["csrf"])}">'

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def op(s: dict) -> str:
        return f"operator:{s['name']}"

    def registry(self) -> SourceRegistry:
        return SourceRegistry(self.root / "sources.json")

    def provider(self, text: str | None):
        return StaticTextProvider(text) if text and text.strip() else ChainProvider(self.ocr)

    @staticmethod
    def status_badge(st: str) -> str:
        cls = {"approved": "ok", "rejected": "bad"}.get(st, "warn")
        return f'<span class="badge {cls}">{esc(st.replace("_", " "))}</span>'


def run_server(app: OperatorApp, host: str = "127.0.0.1", port: int = 8750) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("the operator console only binds to loopback")
    from .operator_routes import make_handler
    return ThreadingHTTPServer((host, port), make_handler(app))
