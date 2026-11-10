@echo off
rem malhandaero run (Windows). Pulls the latest version, installs if needed, then starts.
rem   outside home: tools\run.bat --remote      skip update: tools\run.bat --no-update
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (py -3 tools\update.py %*) else (python tools\update.py %*)
if errorlevel 1 (
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Run tools\install.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe tools\run.py %*
pause
