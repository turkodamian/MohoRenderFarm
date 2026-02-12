@echo off
chcp 65001 >nul
title Moho Render Farm
echo ============================================
echo   Moho Render Farm v1.3.3
echo   by Damián Turkieh
echo ============================================
echo.

:: Check for portable Python first, then system Python
if exist "%~dp0python\python.exe" (
    set "PYTHON=%~dp0python\python.exe"
    goto :launch
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Run install.bat first to set up portable Python.
    pause
    exit /b 1
)
set "PYTHON=python"

:launch
cd /d "%~dp0"
"%PYTHON%" main.py %*

if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
