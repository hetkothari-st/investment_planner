#!/usr/bin/env bash
# CORPUS — one-shot local setup for macOS and Linux.
#
#   ./scripts/setup.sh
#
# Checks each prerequisite, prepares .env, brings the schema up to date, and
# prints the two commands that start the app. Safe to re-run: every step is
# idempotent, and anything already done is reported and skipped.
#
# It never guesses. If something is missing it says which thing, and what to
# run to get it, then stops rather than failing three steps later.
#
# The Windows twin is scripts/setup.ps1.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO/apps/api"
ENV_FILE="$REPO/.env"

OK="[ ok ]"
NO="[MISS]"
problems=()

have() { command -v "$1" >/dev/null 2>&1; }

tcp_open() {
    # bash's /dev/tcp needs no netcat; the subshell keeps a failure local
    (exec 3<>"/dev/tcp/$1/$2") >/dev/null 2>&1
}

echo
echo "CORPUS local setup"
echo "repo: $REPO"
echo

# --- 1. uv -----------------------------------------------------------------
if have uv; then
    echo "$OK uv $(uv --version | awk '{print $2}')"
else
    echo "$NO uv is not installed (or this shell predates the install)"
    problems+=("uv is missing. Install it, then open a new shell and re-run:

    curl -LsSf https://astral.sh/uv/install.sh | sh")
fi

# --- 2. node + pnpm --------------------------------------------------------
if have node; then
    echo "$OK node $(node --version)"
else
    echo "$NO node is not installed"
    problems+=("Node 22+ is missing. Install from https://nodejs.org or your package manager.")
fi

if have pnpm; then
    echo "$OK pnpm $(pnpm --version)"
elif have corepack; then
    echo "     pnpm missing; enabling via corepack..."
    corepack enable >/dev/null 2>&1
    if have pnpm; then
        echo "$OK pnpm $(pnpm --version)"
    else
        echo "$NO pnpm could not be enabled"
        problems+=("pnpm is missing. Try 'corepack enable', or 'npm install -g pnpm'.")
    fi
else
    echo "$NO pnpm is not installed"
    problems+=("pnpm is missing. Install Node 22+ (which bundles corepack), then 'corepack enable'.")
fi

# --- 3. database -----------------------------------------------------------
db_up=false
if tcp_open localhost 5432; then
    db_up=true
    echo "$OK postgres is listening on localhost:5432"
else
    echo "$NO nothing is listening on localhost:5432"

    docker_up=false
    if have docker && docker info >/dev/null 2>&1; then
        docker_up=true
    fi

    if $docker_up; then
        echo "     Docker is running — starting the db service..."
        if (cd "$REPO" && docker compose up -d db >/dev/null 2>&1); then
            # the container accepts connections a moment after it reports started
            for _ in $(seq 1 30); do
                sleep 1
                if tcp_open localhost 5432; then db_up=true; break; fi
            done
        fi
        if $db_up; then
            echo "$OK postgres is up (docker compose service 'db')"
        else
            echo "$NO the db container did not become reachable"
            problems+=("Run 'docker compose up db' in $REPO and read the container output.")
        fi
    else
        problems+=("PostgreSQL is not running. Pick one:

  Docker (simplest — already configured with the right user/password/database):
      docker compose up -d db

  Or your own PostgreSQL 16, then create the role and database once:
      createdb corpus
      psql -c \"CREATE ROLE corpus LOGIN PASSWORD 'corpus'; ALTER DATABASE corpus OWNER TO corpus;\"")
    fi
fi

# --- 4. .env ---------------------------------------------------------------
if [ -f "$ENV_FILE" ]; then
    echo "$OK .env exists (left as-is)"
else
    cp "$REPO/.env.example" "$ENV_FILE"
    # portable in-place edit: BSD sed needs an explicit backup suffix
    sed -i.bak 's/^CORPUS_FEED=off/CORPUS_FEED=replay/' "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    echo "$OK .env created from .env.example (CORPUS_FEED=replay)"
fi

# --- stop here if anything is missing --------------------------------------
if [ ${#problems[@]} -gt 0 ]; then
    echo
    echo "Setup cannot continue until these are resolved:"
    for p in "${problems[@]}"; do
        echo
        echo "$p"
    done
    echo
    echo "Fix the above, then run this script again."
    exit 1
fi

# --- 5. dependencies + schema ----------------------------------------------
echo
echo "Installing Python dependencies..."
cd "$API_DIR" || exit 1
uv sync || { echo "uv sync failed — see above."; exit 1; }

echo
echo "Applying database migrations..."
if ! uv run alembic upgrade head; then
    echo
    echo "Migrations failed. If the error ends in 'connection refused', the database"
    echo "stopped or the credentials in .env do not match it."
    exit 1
fi

echo
echo "Installing web dependencies..."
cd "$REPO" || exit 1
pnpm install || { echo "pnpm install failed — see above."; exit 1; }

# --- done ------------------------------------------------------------------
echo
echo "Setup complete."
echo
echo "Start the API in this terminal:"
echo "    cd $API_DIR"
echo "    uv run uvicorn corpus.api.main:app --reload --port 8000"
echo
echo "And the web app in a second terminal:"
echo "    cd $REPO"
echo "    pnpm dev"
echo
echo "Then open http://localhost:5173"
echo
