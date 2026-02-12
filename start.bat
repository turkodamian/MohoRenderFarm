@echo off
cd /d "%~dp0"
start "" "%~dp0python\pythonw.exe" main.py %*
