@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\start_local.ps1"
if errorlevel 1 (
  endlocal
  exit /b 1
)
endlocal
