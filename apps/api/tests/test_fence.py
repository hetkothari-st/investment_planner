"""The architectural fence.

corpus/metrics is the deterministic spine. It may never import the LLM layer
or the anthropic SDK — see CLAUDE.md and docs/01-ARCHITECTURE.md. This test is
the CI enforcement of that boundary.
"""

from pathlib import Path

METRICS_DIR = Path(__file__).resolve().parents[1] / "corpus" / "metrics"


def test_metrics_never_imports_llm():
    assert METRICS_DIR.is_dir(), f"metrics package missing at {METRICS_DIR}"
    for f in METRICS_DIR.rglob("*.py"):
        src = f.read_text()
        assert "anthropic" not in src, f"{f} references anthropic"
        assert "corpus.llm" not in src, f"{f} imports corpus.llm"


CORPUS_DIR = METRICS_DIR.parent


def test_only_llm_package_imports_anthropic():
    """corpus/llm is the only package permitted to import the anthropic SDK."""
    import re

    sdk_import = re.compile(r"^\s*(import anthropic\b|from anthropic\b)", re.MULTILINE)
    for f in CORPUS_DIR.rglob("*.py"):
        if "llm" in f.parts:
            continue
        src = f.read_text()
        assert not sdk_import.search(src), f"{f} imports the anthropic SDK outside llm/"
