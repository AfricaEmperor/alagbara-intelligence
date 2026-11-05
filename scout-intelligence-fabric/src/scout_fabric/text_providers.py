"""Text providers: turn media into text with an explicit provenance label.

Output text is DERIVED (machine OCR / transcription) or UNVERIFIED (operator-supplied sidecar).
A missing engine is reported as unavailable; nothing is faked.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TextResult:
    text: str | None
    method: str  # e.g. ocr:tesseract, transcription:operator, sidecar:txt
    state: str   # derived | unverified | unknown
    note: str = ""


class TextProvider(Protocol):
    def extract(self, media_path: Path, media_type: str) -> TextResult: ...


class SidecarTextProvider:
    """Reads `<media>.txt` placed beside the upload by an operator (manual transcription of the
    poster). Marked unverified: a human typed it, nothing checked it against the image."""

    def extract(self, media_path: Path, media_type: str) -> TextResult:
        side = media_path.with_name(media_path.name + ".txt")
        alt = media_path.with_suffix(".txt")
        for cand in (side, alt):
            if cand.is_file():
                return TextResult(cand.read_text(encoding="utf-8"), "sidecar:txt", "unverified",
                                  "operator-supplied transcription")
        return TextResult(None, "sidecar:txt", "unknown", "no sidecar text found")


class TesseractProvider:
    """Optional OCR via the `tesseract` binary (fra+eng). Videos: sample frames with ffmpeg."""

    def __init__(self, langs: str = "fra+eng"):
        self.langs = langs

    @staticmethod
    def available() -> bool:
        return shutil.which("tesseract") is not None

    def _ocr(self, image: Path) -> str:
        r = subprocess.run(["tesseract", str(image), "-", "-l", self.langs],
                           capture_output=True, text=True, timeout=120)
        return r.stdout

    def extract(self, media_path: Path, media_type: str) -> TextResult:
        if not self.available():
            return TextResult(None, "ocr:tesseract", "unknown", "tesseract not installed")
        if media_type == "image":
            return TextResult(self._ocr(media_path), "ocr:tesseract", "derived")
        if not shutil.which("ffmpeg"):
            return TextResult(None, "ocr:tesseract", "unknown", "ffmpeg not installed")
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(media_path), "-vf", "fps=1/3",
                            "-frames:v", "8", f"{td}/f%02d.png"], timeout=120, check=False)
            texts = [self._ocr(f) for f in sorted(Path(td).glob("f*.png"))]
        joined = "\n".join(t for t in texts if t.strip())
        return TextResult(joined or None, "ocr:tesseract:video-frames",
                          "derived" if joined else "unknown")


class ChainProvider:
    """First provider that yields text wins; records which one."""

    def __init__(self, *providers: TextProvider):
        self.providers = providers

    def extract(self, media_path: Path, media_type: str) -> TextResult:
        last = TextResult(None, "none", "unknown", "no providers")
        for p in self.providers:
            last = p.extract(media_path, media_type)
            if last.text and last.text.strip():
                return last
        return last
