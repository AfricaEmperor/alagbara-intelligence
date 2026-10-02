"""Small deterministic helpers; no inference or claim verification occurs here."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

def stable_observation_id(source_url: str, subject: str, claim: str) -> str:
    material = "\n".join((source_url.strip(), subject.strip(), claim.strip())).encode("utf-8")
    return hashlib.sha256(material).hexdigest()

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Expected an absolute HTTP(S) URL")
    # Preserve path and query; remove fragment only.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))
