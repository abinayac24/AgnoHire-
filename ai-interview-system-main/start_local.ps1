$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $root "venv\Scripts\python.exe"
$fallbackPythonExe = Join-Path $root ".venv310\Scripts\python.exe"
$legacySitePackages = Join-Path $root ".venv310\Lib\site-packages"

if (-not (Test-Path $pythonExe)) {
    $pythonExe = $fallbackPythonExe
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "Missing Python environment. Checked:" -ForegroundColor Red
    Write-Host "  $($root)\venv\Scripts\python.exe"
    Write-Host "  $($root)\.venv310\Scripts\python.exe"
    Write-Host "Create a Python 3.10/3.11 virtual environment, then install dependencies." -ForegroundColor Yellow
    exit 1
}

if (Test-Path $legacySitePackages) {
    # This checkout stores the installed Windows wheels under .venv310\Lib\site-packages.
    # Prepending the path lets the compatible Python 3.10 runner import Flask/FastAPI/etc.
    $env:PYTHONPATH = "$legacySitePackages;$env:PYTHONPATH"
}

function Get-ListeningPid([int]$port) {
    $lines = netstat -ano | Select-String -Pattern "LISTENING"
    foreach ($line in $lines) {
        $text = $line.ToString()
        if ($text -match (":" + $port + "\s")) {
            $parts = ($text -split "\s+") | Where-Object { $_ -ne "" }
            $last = $parts[-1]
            if ($last -match "^\d+$") { return [int]$last }
        }
    }
    return $null
}

function Stop-PortIfBusy([int]$port) {
    $procId = Get-ListeningPid $port
    if ($procId) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "Stopped process $procId on port $port"
        } catch {
            Write-Host "Could not stop process $procId on port $port" -ForegroundColor Yellow
        }
    }
}

function Wait-Url([string]$url, [int]$timeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5 | Out-Null
            return $true
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

Write-Host "Preparing local services..."
Stop-PortIfBusy 5000
Stop-PortIfBusy 8000
Stop-PortIfBusy 9000

if (-not $env:USE_IN_MEMORY_DB) {
    # Prefer persistent DB path (Mongo if reachable; code already falls back to memory if not).
    $env:USE_IN_MEMORY_DB = "false"
}

$logDir = Join-Path $root "runtime_logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$flaskOut = Join-Path $logDir "flask.out.log"
$flaskErr = Join-Path $logDir "flask.err.log"
$apiOut = Join-Path $logDir "fastapi.out.log"
$apiErr = Join-Path $logDir "fastapi.err.log"
$speechOut = Join-Path $logDir "speech.out.log"
$speechErr = Join-Path $logDir "speech.err.log"
Remove-Item -LiteralPath $flaskOut,$flaskErr,$apiOut,$apiErr,$speechOut,$speechErr -ErrorAction SilentlyContinue

$flaskProc = Start-Process -FilePath $pythonExe -ArgumentList @("app.py") -WorkingDirectory $root -RedirectStandardOutput $flaskOut -RedirectStandardError $flaskErr -WindowStyle Hidden -PassThru
$apiProc = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory (Join-Path $root "backend") -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -WindowStyle Hidden -PassThru
$speechProc = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "9000") -WorkingDirectory (Join-Path $root "speech_service") -RedirectStandardOutput $speechOut -RedirectStandardError $speechErr -WindowStyle Hidden -PassThru

$ok5000 = Wait-Url "http://127.0.0.1:5000" 120
$ok8000 = Wait-Url "http://127.0.0.1:8000/api/health" 180
$ok9000 = Wait-Url "http://127.0.0.1:9000/health" 60

Write-Host ""
Write-Host "Flask    : http://127.0.0.1:5000   -> $ok5000"
Write-Host "FastAPI  : http://127.0.0.1:8000/api/health -> $ok8000"
Write-Host "Speech   : http://127.0.0.1:9000/health -> $ok9000"
Write-Host ""
Write-Host "PIDs: Flask=$($flaskProc.Id), FastAPI=$($apiProc.Id), Speech=$($speechProc.Id)"

if (-not ($ok5000 -and $ok8000 -and $ok9000)) {
    Write-Host "One or more services did not become healthy in time." -ForegroundColor Red
    Write-Host ""
    Write-Host "Recent FastAPI stderr:" -ForegroundColor Yellow
    if (Test-Path $apiErr) { Get-Content -Tail 30 $apiErr }
    Write-Host ""
    Write-Host "Recent Flask stderr:" -ForegroundColor Yellow
    if (Test-Path $flaskErr) { Get-Content -Tail 20 $flaskErr }
    Write-Host ""
    Write-Host "Recent Speech stderr:" -ForegroundColor Yellow
    if (Test-Path $speechErr) { Get-Content -Tail 20 $speechErr }
    Write-Host ""
    Write-Host "Full logs are in: $logDir" -ForegroundColor Cyan
    exit 1
}

Write-Host "Open in browser: http://127.0.0.1:5000/" -ForegroundColor Cyan

Write-Host "All services are up." -ForegroundColor Green
