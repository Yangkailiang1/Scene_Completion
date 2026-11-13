@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0python\python.exe" -X utf8 "%~dp0launcher.py" --background %*
if errorlevel 1 pause
