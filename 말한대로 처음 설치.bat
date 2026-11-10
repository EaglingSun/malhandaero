@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 처음 한 번: 이 파일만 받아 더블클릭하면 저장소를 받고 설치한 뒤 켭니다.
rem 이미 받은 폴더 안에서 실행하면 그 폴더를 최신 판으로 맞추고 켭니다.
set REPO=https://github.com/EaglingSun/malhandaero.git
cd /d "%~dp0"
if exist .git\ if exist tools\run.py goto here
if exist malhandaero\.git\ goto sub
where git >nul 2>nul
if errorlevel 1 (
  echo git이 필요해요. https://git-scm.com/download/win 에서 설치한 뒤 다시 실행해 주세요.
  pause
  exit /b 1
)
echo 저장소를 받습니다: %REPO%
git clone %REPO% malhandaero
if errorlevel 1 (
  echo 받지 못했어요. 저장소 접근 권한이 있는 GitHub 계정으로 로그인되어 있는지 확인해 주세요.
  pause
  exit /b 1
)
:sub
cd malhandaero
:here
if not exist .venv\Scripts\python.exe call install.bat
call run.bat %*
