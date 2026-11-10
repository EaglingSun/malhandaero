@echo off
rem First run: download only this file, double-click: installs git/python via winget if missing, clones the repo, installs, starts.
rem Inside an already cloned folder: reinstalls (fills in missing parts) and starts.
rem ASCII only: cmd garbles UTF-8 batch files after chcp.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set REPO=https://github.com/EaglingSun/malhandaero.git
cd /d "%~dp0"
if exist .git\ if exist tools\run.py goto here
if exist malhandaero\.git\ goto sub
rem Install under the user profile (outside OneDrive-synced folders such as Desktop/Documents).
set DEST=%USERPROFILE%\malhandaero
if exist "%DEST%\.git\" goto dest

where git >nul 2>nul
if errorlevel 1 (
  echo git not found. Installing with winget...
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  echo.
  echo git installed. Close this window and run this file again so PATH is refreshed.
  pause
  exit /b 1
)
where py >nul 2>nul
if errorlevel 1 where python >nul 2>nul
if errorlevel 1 (
  echo python not found. Installing with winget...
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  echo.
  echo python installed. Close this window and run this file again.
  pause
  exit /b 1
)
echo Cloning %REPO% into %DEST% ...
git clone %REPO% "%DEST%"
if errorlevel 1 (
  echo Clone failed. Check that you are signed in to a GitHub account with access to the repo.
  pause
  exit /b 1
)
:dest
cd /d "%DEST%"
goto here
:sub
cd malhandaero
:here
call tools\install.bat
call tools\run.bat %*
