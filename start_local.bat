@echo off
setlocal
set "ROOT=%~dp0ai-interview-system-main"
if not exist "%ROOT%\start_local.bat" (
  echo Could not find "%ROOT%\start_local.bat"
  exit /b 1
)
cd /d "%ROOT%"
call ".\start_local.bat"
endlocal
