# dev.ps1 — orchestration dev sous Windows / PowerShell (équivalent du Makefile)
# Usage :
#   .\dev.ps1 install     # installe backend (uv) + frontend (npm)
#   .\dev.ps1 migrate     # applique les migrations Alembic
#   .\dev.ps1 import      # importe les données legacy dans SQLite
#   .\dev.ps1 seed        # affiche l'état actuel de la DB
#   .\dev.ps1 test        # lance pytest
#   .\dev.ps1 dev         # lance backend (:8000) + frontend (:3000) dans 2 fenêtres
#   .\dev.ps1 dev-backend # backend seul (au premier plan)
#   .\dev.ps1 dev-frontend# frontend seul (au premier plan)
#   .\dev.ps1 gen-types   # régénère frontend\lib\types.ts depuis OpenAPI

param(
    [Parameter(Position = 0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$Backend  = Join-Path $RepoRoot "backend"
$Frontend = Join-Path $RepoRoot "frontend"

function Show-Help {
    Write-Host "Cibles disponibles :" -ForegroundColor Cyan
    Write-Host "  install      -> uv sync + npm install"
    Write-Host "  migrate      -> alembic upgrade head"
    Write-Host "  import       -> python scripts\import_legacy.py"
    Write-Host "  seed         -> python scripts\seed_dev.py"
    Write-Host "  test         -> pytest -v"
    Write-Host "  dev          -> backend + frontend (2 fenêtres PowerShell)"
    Write-Host "  dev-backend  -> backend seul"
    Write-Host "  dev-frontend -> frontend seul"
    Write-Host "  gen-types    -> openapi-typescript -> frontend\lib\types.ts"
}

function Invoke-Backend {
    [CmdletBinding()]
    param([Parameter(Mandatory, ValueFromRemainingArguments)] [string[]]$ArgList)
    Push-Location $Backend
    try {
        & uv run @ArgList
        if ($LASTEXITCODE -ne 0) { throw "Échec backend : uv run $($ArgList -join ' ')" }
    } finally { Pop-Location }
}

function Invoke-Frontend {
    [CmdletBinding()]
    param([Parameter(Mandatory, ValueFromRemainingArguments)] [string[]]$ArgList)
    Push-Location $Frontend
    try {
        & npm @ArgList
        if ($LASTEXITCODE -ne 0) { throw "Échec frontend : npm $($ArgList -join ' ')" }
    } finally { Pop-Location }
}

switch ($Command.ToLower()) {
    "help"          { Show-Help }

    "install" {
        Write-Host "[1/2] uv sync (backend)..." -ForegroundColor Cyan
        Push-Location $Backend
        try { & uv sync; if ($LASTEXITCODE -ne 0) { throw "uv sync a échoué" } }
        finally { Pop-Location }

        Write-Host "[2/2] npm install (frontend)..." -ForegroundColor Cyan
        Invoke-Frontend install --no-audit --no-fund
        Write-Host "✓ Install terminé" -ForegroundColor Green
    }

    "migrate" {
        Write-Host "Alembic upgrade head..." -ForegroundColor Cyan
        Invoke-Backend alembic upgrade head
        Write-Host "✓ Migrations appliquées" -ForegroundColor Green
    }

    "import" {
        Write-Host "Import des données legacy depuis data\imports\..." -ForegroundColor Cyan
        Invoke-Backend python scripts/import_legacy.py
        Write-Host "✓ Import terminé" -ForegroundColor Green
    }

    "seed" {
        Invoke-Backend python scripts/seed_dev.py
    }

    "test" {
        Invoke-Backend pytest -v
    }

    "dev-backend" {
        Push-Location $Backend
        try { & uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 }
        finally { Pop-Location }
    }

    "dev-frontend" {
        Push-Location $Frontend
        try { & npm run dev }
        finally { Pop-Location }
    }

    "dev" {
        Write-Host "Lancement backend (:8000) + frontend (:3000) dans 2 fenêtres PowerShell..." -ForegroundColor Cyan
        $backCmd  = "Set-Location '$Backend';  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
        $frontCmd = "Set-Location '$Frontend'; npm run dev"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $backCmd  | Out-Null
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontCmd | Out-Null
        Write-Host "✓ Deux fenêtres ouvertes. Ferme-les pour arrêter les serveurs." -ForegroundColor Green
        Write-Host "  Backend  : http://127.0.0.1:8000/docs"
        Write-Host "  Frontend : http://localhost:3000"
    }

    "gen-types" {
        Push-Location $Frontend
        try {
            & npx --yes openapi-typescript http://127.0.0.1:8000/openapi.json -o lib/types.ts
            if ($LASTEXITCODE -ne 0) { throw "gen-types a échoué (le backend est-il lancé ?)" }
        } finally { Pop-Location }
        Write-Host "✓ frontend\lib\types.ts régénéré" -ForegroundColor Green
    }

    default {
        Write-Host "Commande inconnue : '$Command'" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
