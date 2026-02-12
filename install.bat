@echo off
title Moho Render Farm - Installer
echo ============================================
echo   Moho Render Farm - Installer
echo   by Damian Turkieh
echo ============================================
echo.

cd /d "%~dp0"

:: Step 1: Set up portable Python
echo [1/5] Setting up portable Python...

if exist "%~dp0python\python.exe" (
    echo   Portable Python already installed.
    set "PYTHON=%~dp0python\python.exe"
    goto :deps
)

:: Try using system Python to bootstrap portable Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    python scripts\setup_python.py
    if exist "%~dp0python\python.exe" (
        set "PYTHON=%~dp0python\python.exe"
        goto :deps
    )
)

:: Fallback: use PowerShell to download Python embeddable
echo   System Python not found. Using PowerShell to download...
set "PY_URL=https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
set "PY_ZIP=%~dp0python-download.zip"
set "PY_DIR=%~dp0python"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"

powershell -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP%'" 2>nul
if not exist "%PY_ZIP%" (
    echo   ERROR: Failed to download Python. Check your internet connection.
    pause
    exit /b 1
)

echo   Extracting Python...
powershell -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PY_DIR%' -Force" 2>nul
del "%PY_ZIP%" 2>nul

if not exist "%PY_DIR%\python.exe" (
    echo   ERROR: Python extraction failed.
    pause
    exit /b 1
)

:: Enable site-packages
powershell -Command "(Get-Content '%PY_DIR%\python310._pth') -replace '#import site','import site' | Set-Content '%PY_DIR%\python310._pth'"

:: Install pip
echo   Installing pip...
powershell -Command "Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%PY_DIR%\get-pip.py'" 2>nul
"%PY_DIR%\python.exe" "%PY_DIR%\get-pip.py" --no-warn-script-location >nul 2>&1
del "%PY_DIR%\get-pip.py" 2>nul

set "PYTHON=%PY_DIR%\python.exe"
echo   Portable Python installed successfully.

:deps
:: Step 2: Install dependencies
echo.
echo [2/5] Installing dependencies...
"%PYTHON%" -m pip install --upgrade pip >nul 2>&1
"%PYTHON%" -m pip install -r "%~dp0requirements.txt" --no-warn-script-location
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo   Dependencies installed successfully.

:: Step 3: Download FFmpeg
echo.
echo [3/5] Setting up FFmpeg...
"%PYTHON%" scripts\setup_ffmpeg.py
if %errorlevel% neq 0 (
    echo   WARNING: FFmpeg setup failed.
    echo   Layer comp auto-composition will not be available.
)

:: Step 4: Verify Moho installation
echo.
echo [4/5] Checking Moho installation...
if exist "C:\Program Files\Moho 14\Moho.exe" (
    echo   Found Moho 14 at C:\Program Files\Moho 14\Moho.exe
) else (
    echo   WARNING: Moho 14 not found at default path.
    echo   You can configure the Moho path in the App Settings tab.
)

:: Step 5: Register context menu
echo.
echo [5/5] Windows integration...
set /p REGISTER="Register right-click context menu for .moho files? (Y/N): "
if /i "%REGISTER%"=="Y" (
    "%PYTHON%" main.py --register-context-menu
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
