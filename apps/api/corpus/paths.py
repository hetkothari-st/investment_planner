"""Repo-root anchored paths.

Resolved from the package location, never from the current working directory:
the API is launched from apps/api (that is where pyproject.toml and
alembic.ini live) while config/ and .env sit at the repo root, so anything
CWD-relative silently resolves to the wrong place.
"""

from pathlib import Path

# corpus/paths.py -> corpus/ -> apps/api/ -> apps/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = REPO_ROOT / ".env"
