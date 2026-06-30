<#
.SYNOPSIS
  Installe (ou désinstalle) net-watchdog comme tâche planifiée Windows qui démarre
  au boot, en SYSTEM (droits admin, sans avoir besoin d'être connecté).

.EXAMPLE
  # PowerShell ADMINISTRATEUR, dans tools\ :
  powershell -ExecutionPolicy Bypass -File .\install-net-watchdog.ps1
  # Carte précise :
  .\install-net-watchdog.ps1 -AdapterName "Wi-Fi"
  # Désinstaller :
  .\install-net-watchdog.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string] $TaskName    = "NetWatchdog",
    [string] $AdapterName = "",
    [switch] $Uninstall
)

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Error "Lance ce script en ADMINISTRATEUR (clic droit PowerShell -> Exécuter en administrateur)."
    exit 1
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tâche '$TaskName' supprimée."
    exit 0
}

$script = Join-Path $PSScriptRoot "net-watchdog.ps1"
if (-not (Test-Path $script)) {
    Write-Error "Introuvable : $script"
    exit 1
}

$argline = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
if ($AdapterName) { $argline += " -AdapterName `"$AdapterName`"" }

$action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argline
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)   # 0 = pas de limite

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Tâche '$TaskName' installée et démarrée (au boot, en SYSTEM)."
Write-Host "Log : $(Join-Path $PSScriptRoot 'net-watchdog.log')"
Write-Host "Vérifier : Get-ScheduledTask -TaskName $TaskName ; désinstaller : -Uninstall"
