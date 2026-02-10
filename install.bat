@echo off
title Moho Render Farm - Installer
echo ============================================
echo   Moho Render Farm - Installer
echo   by Damian Turkieh
echo ============================================
echo.

:: Check for Python
echo [1/4] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.10 or higher from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   Found Python %PYVER%

:: Install dependencies
echo.
echo [2/4] Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo   Dependencies installed successfully.

:: Verify Moho installation
echo.
echo [3/4] Checking Moho installation...
if exist "C:\Program Files\Moho 14\Moho.exe" (
    echo   Found Moho 14 at C:\Program Files\Moho 14\Moho.exe
) else (
    echo   WARNING: Moho 14 not found at default path.
    echo   You can configure the Moho path in the App Settings tab.
)

:: Register context menu
echo.
echo [4/4] Windows integration...
set /p REGISTER="Register right-click context menu for .moho files? (Y/N): "
if /i "%REGISTER%"=="Y" (
    cd /d "%~dp0"
    python main.py --register-context-menu
    echo   Context menu registered.
) else (
    echo   Skipped context menu registration.
)

echo.
echo ============================================
echo   Installation complete!
echo.
echo   To start the application:
echo     - Double-click start.bat
echo     - Or run: python main.py
echo.
echo   For CLI usage:
echo     python main.py --help
echo ============================================
echo.
pause
