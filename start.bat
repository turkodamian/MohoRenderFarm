@echo off
title Moho Render Farm
echo ============================================
echo   Moho Render Farm v1.2.1
echo   by Damian Turkieh
echo ============================================
echo.

:: Find Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: Launch the application
cd /d "%~dp0"
python main.py %*

if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
