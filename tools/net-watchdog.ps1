<#
.SYNOPSIS
  Surveille la connexion Internet et recycle la carte réseau quand elle coupe.

.DESCRIPTION
  Boucle infinie : ping des cibles fiables ; après N échecs consécutifs, désactive
  la carte réseau active, attend, la réactive, attend, et reprend la surveillance.
  Reproduit la manip manuelle (couper Internet, attendre 5 s, réactiver, attendre 5 s).

  REQUIERT LES DROITS ADMINISTRATEUR (Disable/Enable-NetAdapter).
  Pour le rendre permanent au démarrage, voir install-net-watchdog.ps1.

.EXAMPLE
  # En PowerShell ADMINISTRATEUR :
  powershell -ExecutionPolicy Bypass -File .\net-watchdog.ps1
  # Forcer une carte précise :
  .\net-watchdog.ps1 -AdapterName "Wi-Fi"
#>
[CmdletBinding()]
param(
    [string]   $AdapterName       = "",                       # vide = auto-détection
    [string[]] $PingTargets       = @("1.1.1.1", "8.8.8.8"),  # cibles de test
    [int]      $CheckIntervalSec  = 10,                       # fréquence du test
    [int]      $FailuresBeforeReset = 1,                      # échecs avant recyclage (1 = dès le 1er check raté)
    [int]      $DownWaitSec        = 5,                        # attente carte désactivée
    [int]      $UpWaitSec          = 5,                        # attente après réactivation
    [int]      $RecoverChecks      = 6,                        # nb de re-tests après recyclage
    [string]   $LogFile            = "$PSScriptRoot\net-watchdog.log"
)

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    try { Add-Content -Path $LogFile -Value $line -ErrorAction Stop } catch {}
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ActiveAdapter {
    if ($AdapterName) {
        return Get-NetAdapter -Name $AdapterName -ErrorAction SilentlyContinue
    }
    # 1) carte qui porte la route par défaut (passerelle) = celle réellement utilisée
    try {
        $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
                 Sort-Object RouteMetric | Select-Object -First 1
        if ($route) {
            $a = Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue
            if ($a) { return $a }
        }
    } catch {}
    # 2) repli : première carte physique « Up »
    return Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
           Where-Object { $_.Status -eq 'Up' } | Select-Object -First 1
}

function Test-Internet {
    foreach ($t in $PingTargets) {
        if (Test-Connection -ComputerName $t -Count 1 -Quiet -ErrorAction SilentlyContinue) {
            return $true
        }
    }
    return $false
}

function Reset-Adapter($adapter) {
    Write-Log "Connexion coupée -> recyclage de la carte '$($adapter.Name)'."
    try {
        Disable-NetAdapter -Name $adapter.Name -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds $DownWaitSec
        Enable-NetAdapter  -Name $adapter.Name -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds $UpWaitSec
        Write-Log "Carte '$($adapter.Name)' réactivée."
        return $true
    } catch {
        Write-Log "ECHEC du recyclage : $($_.Exception.Message)"
        return $false
    }
}

# ── Démarrage ─────────────────────────────────────────────────────────
if (-not (Test-IsAdmin)) {
    Write-Log "ATTENTION : pas en administrateur — Disable/Enable-NetAdapter échouera."
}
Write-Log ("net-watchdog démarré (interval={0}s, seuil={1} échecs, cibles={2})." -f `
           $CheckIntervalSec, $FailuresBeforeReset, ($PingTargets -join ","))

$fails = 0
while ($true) {
    if (Test-Internet) {
        if ($fails -gt 0) { Write-Log "Connexion rétablie." }
        $fails = 0
        Start-Sleep -Seconds $CheckIntervalSec
        continue
    }

    $fails++
    Write-Log "Ping échoué ($fails/$FailuresBeforeReset)."
    if ($fails -lt $FailuresBeforeReset) {
        Start-Sleep -Seconds 3
        continue
    }

    $adapter = Get-ActiveAdapter
    if (-not $adapter) {
        Write-Log "Aucune carte réseau active trouvée — nouvelle tentative."
        Start-Sleep -Seconds $CheckIntervalSec
        $fails = 0
        continue
    }

    [void](Reset-Adapter $adapter)
    # Laisser la connexion remonter avant de reprendre la surveillance normale.
    for ($i = 0; $i -lt $RecoverChecks; $i++) {
        if (Test-Internet) { Write-Log "Connexion OK après recyclage."; break }
        Start-Sleep -Seconds 5
    }
    $fails = 0
}
