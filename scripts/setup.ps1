# CORPUS — one-shot local setup for Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#
# Checks each prerequisite, prepares .env, brings the schema up to date, and
# prints the two commands that start the app. Safe to re-run: every step is
# idempotent, and anything already done is reported and skipped.
#
# It never guesses. If something is missing it says which thing, and what to
# run to get it, then stops rather than failing three steps later.

$ErrorActionPreference = 'Continue'

$repo = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repo 'apps\api'
$envFile = Join-Path $repo '.env'

$ok = "[ ok ]"
$no = "[MISS]"
$problems = @()

function Test-Tcp($server, $port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $done = $client.ConnectAsync($server, $port).Wait(1500)
        $client.Close()
        return $done
    } catch { return $false }
}

function Have($name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "CORPUS local setup" -ForegroundColor Cyan
Write-Host "repo: $repo"
Write-Host ""

# --- 1. uv -----------------------------------------------------------------
if (Have 'uv') {
    Write-Host "$ok $(uv --version)"   # prints e.g. "uv 0.8.17"
} else {
    Write-Host "$no uv is not installed (or this terminal predates the install)" -ForegroundColor Yellow
    $problems += @"
uv is missing. Install it, then OPEN A NEW TERMINAL and run this script again:

    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
"@
}

# --- 2. node + pnpm --------------------------------------------------------
if (Have 'node') {
    Write-Host "$ok node $(node --version)"
} else {
    Write-Host "$no node is not installed" -ForegroundColor Yellow
    $problems += "Node 22+ is missing. Install from https://nodejs.org and reopen the terminal."
}

if (Have 'pnpm') {
    Write-Host "$ok pnpm $(pnpm --version)"
} elseif (Have 'corepack') {
    Write-Host "     pnpm missing; enabling via corepack..."
    corepack enable 2>&1 | Out-Null
    if (Have 'pnpm') {
        Write-Host "$ok pnpm $(pnpm --version)"
    } else {
        Write-Host "$no pnpm could not be enabled" -ForegroundColor Yellow
        $problems += "pnpm is missing. Try 'corepack enable' in an admin terminal, or 'npm install -g pnpm'."
    }
} else {
    Write-Host "$no pnpm is not installed" -ForegroundColor Yellow
    $problems += "pnpm is missing. Install Node 22+ (which bundles corepack), then run 'corepack enable'."
}

# --- 3. database -----------------------------------------------------------
$dbUp = Test-Tcp 'localhost' 5432
if ($dbUp) {
    Write-Host "$ok postgres is listening on localhost:5432"
} else {
    Write-Host "$no nothing is listening on localhost:5432" -ForegroundColor Yellow

    $dockerUp = $false
    if (Have 'docker') {
        docker info 2>&1 | Out-Null
        $dockerUp = ($LASTEXITCODE -eq 0)
    }

    if ($dockerUp) {
        Write-Host "     Docker is running — starting the db service..."
        Push-Location $repo
        docker compose up -d db 2>&1 | Out-Null
        $started = ($LASTEXITCODE -eq 0)
        Pop-Location
        if ($started) {
            # the container accepts connections a moment after it reports started
            for ($i = 0; $i -lt 30; $i++) {
                Start-Sleep -Seconds 1
                if (Test-Tcp 'localhost' 5432) { $dbUp = $true; break }
            }
        }
        if ($dbUp) {
            Write-Host "$ok postgres is up (docker compose service 'db')"
        } else {
            Write-Host "$no the db container did not become reachable" -ForegroundColor Yellow
            $problems += "Run 'docker compose up db' in $repo and read the container output."
        }
    } else {
        $problems += @"
PostgreSQL is not running. Pick one:

  Docker (simplest — already configured with the right user/password/database):
      docker compose up -d db

  Or install PostgreSQL 16 from https://www.postgresql.org/download/windows/
  then create the role and database once (it will prompt for the postgres
  password you chose during install):
      & 'C:\Program Files\PostgreSQL\16\bin\psql.exe' -U postgres -c "CREATE ROLE corpus LOGIN PASSWORD 'corpus';"
      & 'C:\Program Files\PostgreSQL\16\bin\psql.exe' -U postgres -c "CREATE DATABASE corpus OWNER corpus;"
"@
    }
}

# --- 4. .env ---------------------------------------------------------------
if (Test-Path $envFile) {
    Write-Host "$ok .env exists (left as-is)"
} else {
    Copy-Item (Join-Path $repo '.env.example') $envFile
    $text = Get-Content $envFile -Raw
    $text = $text -replace '(?m)^CORPUS_FEED=off', 'CORPUS_FEED=replay'
    Set-Content -Path $envFile -Value $text -NoNewline
    Write-Host "$ok .env created from .env.example (CORPUS_FEED=replay)"
}

# --- stop here if anything is missing --------------------------------------
if ($problems.Count -gt 0) {
    Write-Host ""
    Write-Host "Setup cannot continue until these are resolved:" -ForegroundColor Red
    foreach ($p in $problems) {
        Write-Host ""
        Write-Host $p
    }
    Write-Host ""
    Write-Host "Fix the above, then run this script again."
    exit 1
}

# --- 5. dependencies + schema ----------------------------------------------
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
Push-Location $apiDir
uv sync
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "uv sync failed — see above." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Applying database migrations..." -ForegroundColor Cyan
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Host ""
    Write-Host "Migrations failed. If the error ends in WinError 1225 or 'connection refused'," -ForegroundColor Red
    Write-Host "the database stopped or the credentials in .env do not match it." -ForegroundColor Red
    exit 1
}
Pop-Location

Write-Host ""
Write-Host "Installing web dependencies..." -ForegroundColor Cyan
Push-Location $repo
pnpm install
$pnpmOk = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $pnpmOk) { Write-Host "pnpm install failed — see above." -ForegroundColor Red; exit 1 }

# --- done ------------------------------------------------------------------
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Start the API in this terminal:"
Write-Host "    cd $apiDir"
Write-Host "    uv run uvicorn corpus.api.main:app --reload --port 8000"
Write-Host ""
Write-Host "And the web app in a second terminal:"
Write-Host "    cd $repo"
Write-Host "    pnpm dev"
Write-Host ""
Write-Host "Then open http://localhost:5173"
Write-Host ""
