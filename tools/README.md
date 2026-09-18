# tools/ — utilitaires système (hors dashboard)

## net-watchdog — relance auto de la connexion Internet

Surveille la connexion et, quand elle coupe, **recycle la carte réseau**
automatiquement (désactive → attend 5 s → réactive → attend 5 s), exactement comme
la manip manuelle. Tourne en arrière-plan en continu.

### Test rapide (ponctuel)

Ouvrir **PowerShell en administrateur**, puis :

```powershell
cd <repo>\tools
powershell -ExecutionPolicy Bypass -File .\net-watchdog.ps1
```

Laisser tourner ; couper le Wi-Fi/routeur pour vérifier qu'il recycle bien la carte.
Arrêter avec `Ctrl+C`. Tout est journalisé dans `net-watchdog.log`.

Forcer une carte précise (sinon auto-détection de celle qui porte la passerelle) :

```powershell
.\net-watchdog.ps1 -AdapterName "Wi-Fi"
```

Paramètres utiles : `-CheckIntervalSec 10`, `-FailuresBeforeReset 3`,
`-DownWaitSec 5`, `-UpWaitSec 5`, `-PingTargets 1.1.1.1,8.8.8.8`.

### Toujours actif (au démarrage de Windows)

Installe une **tâche planifiée** qui démarre au boot, en SYSTEM (admin, sans login) :

```powershell
# PowerShell ADMINISTRATEUR :
cd <repo>\tools
powershell -ExecutionPolicy Bypass -File .\install-net-watchdog.ps1
```

- Carte précise : `.\install-net-watchdog.ps1 -AdapterName "Wi-Fi"`
- Désinstaller : `.\install-net-watchdog.ps1 -Uninstall`
- État : `Get-ScheduledTask -TaskName NetWatchdog`
- Log : `tools\net-watchdog.log`

### Notes
- **Droits admin obligatoires** : `Disable/Enable-NetAdapter` les exige.
- Par défaut, il cycle **dès le premier test raté** (`FailuresBeforeReset=1`). Le
  test ping deux cibles (`1.1.1.1` et `8.8.8.8`) : « raté » = les deux ont échoué.
  Pour tolérer un micro-blip avant de cycler : `-FailuresBeforeReset 2` (ou plus).
- Le `.log` grossit avec le temps ; le purger de temps en temps si besoin.
- Pendant le recyclage, la connexion est volontairement coupée ~10 s (5 s + 5 s).
