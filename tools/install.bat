@echo off
rem malhandaero install (Windows). Safe to run again. ASCII only: cmd garbles UTF-8 batch files.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (py -3 tools\install.py %*) else (python tools\install.py %*)
echo.
pause
