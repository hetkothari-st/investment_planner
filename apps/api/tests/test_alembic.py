"""Alembic is wired: config loads and the migration environment resolves."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

API_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_config_resolves():
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "corpus" / "db" / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    # No revisions yet at M0; the environment itself must still resolve cleanly.
    assert script.get_heads() == []
