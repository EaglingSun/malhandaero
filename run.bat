@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 말한대로 켜기 (Windows). 최신 판을 받고, 필요하면 설치한 뒤 켭니다.
rem   집 밖에서도: run.bat --remote      업데이트 건너뛰기: run.bat --no-update
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 tools\update.py %*) else (python tools\update.py %*)
if errorlevel 1 (
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo 먼저 install.bat 을 실행해 주세요.
  pause
  exit /b 1
)
.venv\Scripts\python.exe tools\run.py %*
pause
