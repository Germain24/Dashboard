@echo off
setlocal
chcp 65001 >nul
title Mission Control

set "MISSION_CONTROL_ROOT=C:\Users\germa\Documents\GitHub\mission-control"
if not exist "%MISSION_CONTROL_ROOT%\Makefile" (
    echo.
    echo [ERREUR] Depot Mission Control introuvable :
    echo %MISSION_CONTROL_ROOT%
    echo.
    pause
    exit /b 1
)

cd /d "%MISSION_CONTROL_ROOT%"

echo --- Migrations Alembic ---
make migrate
if errorlevel 1 goto :launch_error

echo.
echo --- Lancement backend + frontend ---
make dev
if errorlevel 1 goto :launch_error

exit /b 0

:launch_error
set "LAUNCH_EXIT_CODE=%errorlevel%"
echo.
echo [ERREUR] Le dashboard ne s'est pas lance correctement ^(code %LAUNCH_EXIT_CODE%^).
echo La fenetre reste ouverte pour permettre de lire le message ci-dessus.
echo.
pause
exit /b %LAUNCH_EXIT_CODE%
