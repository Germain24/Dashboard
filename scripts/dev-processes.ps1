param(
    [ValidateSet("Check", "Stop")]
    [string]$Action = "Check"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EscapedRoot = [regex]::Escape($RepoRoot)

function Get-MissionControlServerProcesses {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $roots = @(
        $all | Where-Object {
            $line = [string]$_.CommandLine
            $isNextTelemetry = $line -match "\\next\\dist\\telemetry\\"
            $line -match $EscapedRoot -and
            -not ($Action -eq "Check" -and $isNextTelemetry) -and (
                $line -match "uvicorn(?:\.exe)?\s+app\.main:app" -or
                # Ne jamais utiliser un simple `next ... dev` ici : le worker
                # détaché `next\dist\telemetry\detached-flush.js dev <repo>`
                # contient lui aussi ces deux mots et survivait parfois plusieurs
                # jours après l'arrêt du serveur. Il provoquait alors un faux
                # "dashboard déjà lancé". Seul le vrai CLI Next est une racine.
                $line -match '\\next\\dist\\bin\\next(?:\.js)?["]?\s+dev(?:\s|$)' -or
                $line -match "next\\dist\\server\\lib\\start-server\.js" -or
                ($Action -eq "Stop" -and $isNextTelemetry)
            )
        }
    )
    if (-not $roots) { return @() }

    # Le worker Uvicorn --reload est un multiprocessing.spawn dont la ligne de
    # commande ne contient plus le dépôt. Il reste néanmoins un descendant sûr
    # d'un processus déjà identifié ci-dessus.
    $selected = @{}
    $queue = [System.Collections.Generic.Queue[int]]::new()
    foreach ($process in $roots) {
        $selected[[int]$process.ProcessId] = $process
        $queue.Enqueue([int]$process.ProcessId)
    }
    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        foreach ($child in $all | Where-Object { [int]$_.ParentProcessId -eq $parent }) {
            $pidValue = [int]$child.ProcessId
            if (-not $selected.ContainsKey($pidValue)) {
                $selected[$pidValue] = $child
                $queue.Enqueue($pidValue)
            }
        }
    }
    return @($selected.Values)
}

$processes = @(Get-MissionControlServerProcesses)
if ($Action -eq "Check") {
    if ($processes.Count -gt 0) {
        Write-Host "[ERREUR] Un dashboard Mission Control est deja lance." -ForegroundColor Red
        $processes |
            Sort-Object ProcessId |
            Select-Object ProcessId, ParentProcessId, Name, CommandLine |
            Format-Table -Wrap
        Write-Host "Utilise 'make dev-stop' (ou '.\dev.ps1 stop') avant de relancer." -ForegroundColor Yellow
        exit 1
    }
    exit 0
}

if ($processes.Count -eq 0) {
    Write-Host "Aucun processus Mission Control a arreter."
    exit 0
}

# Enfants d'abord, puis lanceurs. Les cibles ont toutes été rattachées à une
# commande Uvicorn/Next située dans CE dépôt.
$ids = @($processes | Sort-Object ProcessId -Descending | ForEach-Object { [int]$_.ProcessId })
Stop-Process -Id $ids -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Write-Host "Dashboard arrete ($($ids.Count) processus)." -ForegroundColor Green
