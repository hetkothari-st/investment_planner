"""Load the repo-root .env before any submodule reads os.environ.

Several runtime switches — CORPUS_FEED, CORPUS_SCHEDULER, WS_HUB_URL,
WS_HUB_SUBSCRIBE, CORPUS_REPLAY_*, CORPUS_WEB_DIST, CORPUS_BASIC_AUTH — are
read straight from os.environ, and pydantic-settings only ever populates a
Settings instance, never os.environ. Python runs this package __init__ before
any corpus.* submodule, so loading here is what makes a .env file reach those
readers at all.

override=False keeps real environment variables authoritative, so
docker-compose, shell exports, and monkeypatch.setenv still win over the file.
"""

from dotenv import load_dotenv

from corpus.paths import ENV_FILE

load_dotenv(ENV_FILE, override=False)
