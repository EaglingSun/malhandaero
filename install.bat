@echo off
rem malhandaero install (Windows)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 tools\install.py) else (python tools\install.py)
echo.
pause
