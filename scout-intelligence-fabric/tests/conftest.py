import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from ana_engine.store import RadarStore
from scout_fabric.sources import Source, SourceRegistry


def make_png(path: Path, seed: int = 0, w: int = 8, h: int = 8) -> Path:
    raw = b"".join(b"\x00" + bytes([(seed + x + y) % 256 for x in range(w) for _ in range(3)]) for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def make_mp4(path: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture
def registry(tmp_path):
    r = SourceRegistry(tmp_path / "sources.json")
    r.register(Source("src-upload-1", "upload", "Operator uploads"))
    r.approve("src-upload-1", "principal@example")
    r.register(Source("src-upload-2", "upload", "Second uploader"))
    r.approve("src-upload-2", "principal@example")
    r.register(Source("src-pending", "upload", "Not approved"))
    r.register(Source("src-fb", "facebook_page", "Fictional page", url="https://www.facebook.com/example"))
    r.approve("src-fb", "principal@example")
    return r


@pytest.fixture
def store(tmp_path):
    s = RadarStore(tmp_path / "data")
    yield s
    s.close()


@pytest.fixture
def poster(tmp_path):
    def _make(name, text, seed=0):
        p = make_png(tmp_path / name, seed)
        if text is not None:
            (tmp_path / (name + ".txt")).write_text(text, encoding="utf-8")
        return p
    return _make


POSTER_A = """AFRO NIGHT VOL.3
Samedi 14 novembre 2026
De 22h à 04h
Lieu : Club Exemple, Haie Vive
Organisé par Studio Fictif
DJ Alpha - DJ Beta
Live : Artiste Demo
Entrée 3000 FCFA
Réservations +229 01 90 00 00 00
"""
# same event, different source; venue spelled differently and a different start time (contradiction)
POSTER_B = """AFRO NIGHT VOL.3
14/11/2026
à partir de 23h
@ Club Exemple Haie Vive
Organisé par Studio Fictif
DJ Alpha
"""
