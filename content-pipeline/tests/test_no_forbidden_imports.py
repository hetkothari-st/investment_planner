"""Spec §1.1 / Phase 1 checklist: no source module may import third-party
social-video downloaders or headless browsers. Enforced mechanically."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
FORBIDDEN = ["yt_dlp", "instaloader", "selenium", "playwright"]
IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(" + "|".join(FORBIDDEN) + r")\b", re.MULTILINE
)


def test_no_forbidden_imports():
    offenders = []
    for path in SRC.rglob("*.py"):
        if IMPORT_RE.search(path.read_text()):
            offenders.append(str(path))
    assert not offenders, f"forbidden downloader/browser imports in: {offenders}"
