@echo off
title Moho Render Farm
cd /d "%~dp0"
"%~dp0python\python.exe" main.py %*
if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
