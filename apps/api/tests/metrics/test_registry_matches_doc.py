"""The registry and docs/06 drift unless a test stops them."""

import re
from pathlib import Path

from corpus.metrics.registry import REGISTRY

DOC = Path(__file__).resolve().parents[3].parent / "docs" / "06-METRIC-REGISTRY.md"


def test_registry_matches_doc_exactly():
    text = DOC.read_text()
    doc_ids = set(re.findall(r"\| `([a-z]+\.[a-z0-9_]+)`", text))
    reg_ids = set(REGISTRY)
    assert doc_ids - reg_ids == set(), f"in doc, missing from registry: {doc_ids - reg_ids}"
    assert reg_ids - doc_ids == set(), f"in registry, missing from doc: {reg_ids - doc_ids}"


def test_specs_are_coherent():
    for field_id, spec in REGISTRY.items():
        assert spec.field_id == field_id
        assert spec.label
        assert spec.precision >= 0
        assert spec.sources
