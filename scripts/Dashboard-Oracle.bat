@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Mission Control - Oracle Cloud

rem Configuration de la VM Oracle
set "ORACLE_KEY=C:\Users\germa\Desktop\Clefs Oracle\ssh-key-2026-09-16.key"
set "ORACLE_IP=130.110.241.54"
set "REMOTE_ROOT=/home/ubuntu/mission-control"
set "COMPOSE=sudo docker compose --env-file .env.oracle -f docker-compose.oracle.yml"
set "REPO_ROOT=C:\Users\germa\Documents\GitHub\mission-control"
set "GIT_REMOTE=https://github.com/Germain24/Dashboard.git"

if not exist "%ORACLE_KEY%" (
    echo [ERREUR] Clef SSH introuvable : %ORACLE_KEY%
    pause
    exit /b 1
)

echo --- Publication du code local sur GitHub ---
cd /d "%REPO_ROOT%"
git config --global --add safe.directory "%REPO_ROOT%" >nul 2>&1
for /f "delims=" %%B in ('git branch --show-current') do set "GIT_BRANCH=%%B"
if not defined GIT_BRANCH (
    echo [ERREUR] Branche Git introuvable.
    pause
    exit /b 1
)
git add -A -- . ":(exclude).tmp" ":(exclude)backend/.tmp*" ":(exclude)backend/.pytest*" ":(exclude)backend/.test*" ":(exclude)data/pytest*"
git diff --cached --quiet
if errorlevel 1 git commit -m "Synchronisation dashboard %date% %time%"
git push --force "%GIT_REMOTE%" "%GIT_BRANCH%"
if errorlevel 1 (
    echo [ERREUR] Publication GitHub echouee. Verifie l'authentification Git.
    pause
    exit /b 1
)

echo --- Sauvegarde, arret propre, mise a jour GitHub et redemarrage Oracle ---
ssh -i "%ORACLE_KEY%" -o ConnectTimeout=15 ubuntu@%ORACLE_IP% ^
  "cd %REMOTE_ROOT% ^&^& sudo systemctl start mission-control-backup.service ^&^& if [ ! -d .git ]; then git init; fi ^&^& (git remote get-url origin >/dev/null 2>&1 || git remote add origin %GIT_REMOTE%) ^&^& git fetch origin %GIT_BRANCH% ^&^& git checkout -B %GIT_BRANCH% -f origin/%GIT_BRANCH% ^&^& %COMPOSE% down ^&^& %COMPOSE% up -d --build ^&^& %COMPOSE% ps"

if errorlevel 1 (
    echo.
    echo [ERREUR] La mise a jour ou le redemarrage a echoue.
    pause
    exit /b 1
)

echo.
echo Dashboard Oracle redemarre : http://%ORACLE_IP%
pause
