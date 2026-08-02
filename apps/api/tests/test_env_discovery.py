"""The .env file must be found from the repo root, not the working directory.

The API is launched from apps/api (pyproject.toml and alembic.ini live there)
while .env lives at the repo root. A CWD-relative env_file resolves to
apps/api/.env, finds nothing, and every setting silently falls back to its
default — a misconfigured run that looks like a working one.
"""

import os

from dotenv import load_dotenv

from corpus.config import Settings
from corpus.paths import ENV_FILE, REPO_ROOT

PROBE_URL = "postgresql+asyncpg://probe:x@localhost:5432/probe"


def test_repo_root_is_the_directory_holding_config_and_docs():
    assert (REPO_ROOT / "config").is_dir()
    assert (REPO_ROOT / "docs").is_dir()
    assert (REPO_ROOT / "apps" / "api" / "pyproject.toml").is_file()


def test_env_file_is_absolute_and_at_the_repo_root():
    assert ENV_FILE.is_absolute()
    assert ENV_FILE == REPO_ROOT / ".env"


def test_settings_env_file_is_the_repo_root_path():
    """The regression itself: a bare ".env" here is what broke local runs."""
    assert Settings.model_config["env_file"] == ENV_FILE


def test_env_file_resolves_the_same_from_any_working_directory(tmp_path, monkeypatch):
    env_file = tmp_path / "dotenv-probe"
    env_file.write_text(f"DATABASE_URL={PROBE_URL}\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    monkeypatch.chdir(tmp_path)
    assert Settings(_env_file=env_file).database_url == PROBE_URL

    monkeypatch.chdir(REPO_ROOT / "apps" / "api")
    assert Settings(_env_file=env_file).database_url == PROBE_URL


def test_real_environment_wins_over_the_file(monkeypatch):
    """docker-compose passes real env vars; they must beat any local .env."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://realenv:x@db:5432/corpus")
    assert Settings().database_url == "postgresql+asyncpg://realenv:x@db:5432/corpus"


def test_os_environ_switches_are_populated_from_the_file(tmp_path, monkeypatch):
    """CORPUS_FEED and friends are read via os.environ, which pydantic-settings
    never touches. Loading the file into os.environ is what reaches them."""
    monkeypatch.delenv("CORPUS_FEED", raising=False)
    env_file = tmp_path / "dotenv-probe"
    env_file.write_text("CORPUS_FEED=replay\n")

    try:
        load_dotenv(env_file, override=False)

        from corpus.live.feed import feed_kind

        assert feed_kind() == "replay"
    finally:
        # load_dotenv mutates the real environment; monkeypatch only restores
        # what it set itself, so drop this before its teardown runs.
        os.environ.pop("CORPUS_FEED", None)
