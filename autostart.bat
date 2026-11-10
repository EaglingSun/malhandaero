@echo off
rem Register (or remove) malhandaero to start when you log in.  autostart.bat [install|remove|status]
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
if "%~1"=="" (set CMD=install) else (set CMD=%~1)
.venv\Scripts\python.exe tools\autostart.py %CMD%
pause
