@echo off
title Moho Render Farm - Installer
echo ============================================
echo   Moho Render Farm - Installer
echo   by Damian Turkieh
echo ============================================
echo.

:: Check for Python
echo [1/6] Checking Python installation...
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
echo [2/6] Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo   Dependencies installed successfully.

:: Check and pull Git LFS files (ffmpeg binaries)
echo.
echo [3/6] Checking Git LFS for bundled FFmpeg...
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo   Git not found - skipping LFS check.
    echo   If ffmpeg is missing, download it manually to the ffmpeg\ folder.
) else (
    git -C "%~dp0" lfs install >nul 2>&1
    git -C "%~dp0" lfs pull >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Git LFS pull completed.
    ) else (
        echo   Git LFS pull skipped (not a git repo or LFS not installed).
    )
)

:: Verify FFmpeg
echo.
echo [4/6] Checking bundled FFmpeg...
if exist "%~dp0ffmpeg\ffmpeg.exe" (
    echo   Found FFmpeg at %~dp0ffmpeg\ffmpeg.exe
) else (
    echo   WARNING: FFmpeg not found in ffmpeg\ folder.
    echo   Layer comp auto-composition will not be available.
    echo   If you cloned the repo, install Git LFS and run: git lfs pull
)

:: Verify Moho installation
echo.
echo [5/6] Checking Moho installation...
if exist "C:\Program Files\Moho 14\Moho.exe" (
    echo   Found Moho 14 at C:\Program Files\Moho 14\Moho.exe
) else (
    echo   WARNING: Moho 14 not found at default path.
    echo   You can configure the Moho path in the App Settings tab.
)

:: Register context menu
echo.
echo [6/6] Windows integration...
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
