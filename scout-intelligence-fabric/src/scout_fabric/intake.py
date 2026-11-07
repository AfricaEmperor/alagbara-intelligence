"""Upload intake: poster / screenshot / video -> content-addressed media + EvidenceRecord.

Evidence semantics: the file's existence, hash and technical metadata are OBSERVED. Anything about
its original social-platform context (who posted it, when, where) is NOT verified by an upload, so
the record is marked `unverified` for provenance of context and carries `context_verified: false`.
"""
from __future__ import annotations

import hashlib
import shutil
import struct
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radar_contracts import EvidenceRecord, validate_evidence

from .sources import SourceRegistry

EXTRACTION_VERSION = "scout-intake-1.0.0"
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
VIDEO_EXT = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}


class RejectedUpload(ValueError):
    pass


def sniff(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        return "video/quicktime" if head[8:12] == b"qt  " else "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def _image_dims(data: bytes, mime: str) -> tuple[int, int] | None:
    if mime == "image/png" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if mime == "image/jpeg":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def _video_meta(path: Path) -> dict[str, Any]:
    if not shutil.which("ffprobe"):
        return {"ffprobe": "unavailable"}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name",
             "-of", "default=nw=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True).stdout
        return {k: v for k, v in (ln.split("=", 1) for ln in out.splitlines() if "=" in ln)}
    except Exception as exc:  # noqa: BLE001 - metadata is best-effort and recorded as such
        return {"ffprobe_error": type(exc).__name__}


def ingest_upload(path: Path, source_id: str, registry: SourceRegistry, media_dir: Path,
                  now: datetime | None = None, source_url: str | None = None,
                  extra_metadata: dict[str, Any] | None = None) -> tuple[EvidenceRecord, bool]:
    """Returns (evidence, created). Re-ingesting identical bytes from the same source is a no-op."""
    registry.require_authorized(source_id, "upload")  # AT-12: unauthorized acquisition rejected
    path = Path(path)
    if not path.is_file():
        raise RejectedUpload(f"not a file: {path}")
    size = path.stat().st_size
    if size == 0 or size > MAX_UPLOAD_BYTES:
        raise RejectedUpload(f"file size {size} outside accepted range")
    data = path.read_bytes()
    mime = sniff(data[:16])
    declared = {**IMAGE_EXT, **VIDEO_EXT}.get(path.suffix.lower())
    if mime is None or declared is None:
        raise RejectedUpload("unsupported or unrecognised media type")
    if mime.split("/")[0] != declared.split("/")[0]:
        raise RejectedUpload("file extension does not match file content")
    media_type = mime.split("/")[0]

    content_hash = hashlib.sha256(data).hexdigest()
    observation_id = hashlib.sha256(f"{source_id}\n{content_hash}".encode()).hexdigest()
    dest = media_dir / f"{content_hash}{path.suffix.lower()}"
    created = not dest.exists()
    if created:
        media_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    meta: dict[str, Any] = {"mime": mime, "bytes": size, "context_verified": False}
    if source_url:                       # where the poster was found (provenance claim, not verified)
        from urllib.parse import urlparse
        u = urlparse(source_url)
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
            raise RejectedUpload("source_url must be an http(s) URL without embedded credentials")
    for k, v in (extra_metadata or {}).items():   # e.g. permission_note, operator
        meta[str(k)[:40]] = str(v)[:300]
    if media_type == "image":
        dims = _image_dims(data, mime)
        meta["dimensions"] = {"width": dims[0], "height": dims[1]} if dims else "unknown"
    else:
        meta.update(_video_meta(dest))

    ev = EvidenceRecord(
        observation_id=observation_id, source_id=source_id, source_platform="upload",
        source_url=source_url, collection_method="operator_upload",
        collected_at=(now or datetime.now(UTC)).isoformat(),
        content_hash=content_hash,
        evidence_state="unverified",  # file is observed; its social-platform context is not verified
        raw_media_reference=f"media/{dest.name}", extraction_version=EXTRACTION_VERSION,
        media_type=media_type, original_filename=path.name, metadata=meta)
    validate_evidence(ev)
    return ev, created
