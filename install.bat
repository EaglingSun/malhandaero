@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 말한대로 설치 (Windows). 여러 번 실행해도 안전합니다.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 tools\install.py %*) else (python tools\install.py %*)
echo.
pause
