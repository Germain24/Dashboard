@echo off
chcp 65001 >nul
title Mission Control - Lancement
cd /d "%~dp0"

echo --- Migrations base de donnees ---
powershell -NoProfile -ExecutionPolicy Bypass -File dev.ps1 migrate
if errorlevel 1 (
    echo.
    echo [ERREUR] Les migrations ont echoue. Corrige avant de lancer.
    pause
    exit /b 1
)

echo.
echo --- Lancement backend (:8000) + frontend (:3000) ---
powershell -NoProfile -ExecutionPolicy Bypass -File dev.ps1 dev

echo.
echo Backend  : http://127.0.0.1:8000/docs
echo Frontend : http://localhost:3000
echo (Ferme les deux fenetres PowerShell pour arreter les serveurs.)
pause
