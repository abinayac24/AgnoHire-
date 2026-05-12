$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$speechRoot = Join-Path $projectRoot "speech_service"
$venvPath = Join-Path $speechRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$speechPort = 9000
$speechBaseUrl = "http://127.0.0.1:$speechPort"

function Write-Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Gray
}

function Get-PythonLauncherList {
    try {
        $output = & py -0p 2>&1
        return @($output)
    } catch {
        return @()
    }
}

function Find-Python310 {
    $launcherLines = Get-PythonLauncherList
    foreach ($line in $launcherLines) {
        if ($line -match "3\.10" -and $line -match "([A-Z]:\\.*python(?:\.exe)?)") {
            return $Matches[1]
        }
    }

    $candidates = @(
        "C:\Users\user\AppData\Local\Programs\Python\Python310\python.exe",
        "C:\Program Files\Python310\python.exe",
        "C:\Program Files (x86)\Python310\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Ensure-Python310 {
    $python310 = Find-Python310
    if ($python310) {
        return $python310
    }

    Write-Warn "Python 3.10 was not found."
    Write-Info "Trying to install Python 3.10 with winget..."

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is not available. Install Python 3.10 manually, then rerun this script."
    }

    try {
        & winget install --id Python.Python.3.10 --accept-source-agreements --accept-package-agreements
    } catch {
        throw "winget failed to install Python 3.10. Install it manually from python.org and rerun the script."
    }

    $python310 = Find-Python310
    if (-not $python310) {
        throw "Python 3.10 installation did not produce a usable python.exe. Fix the install, then rerun."
    }

    return $python310
}

function Get-PythonVersion($pythonPath) {
    return (& $pythonPath --version 2>&1).Trim()
}

function Ensure-Venv($python310Path) {
    if (-not (Test-Path $venvPython)) {
        Write-Info "Creating Python 3.10 virtual environment..."
        & $python310Path -m venv $venvPath
    }

    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment creation failed. No venv Python found."
    }

    $venvVersion = Get-PythonVersion $venvPython
    if ($venvVersion -notmatch "Python 3\.10") {
        Write-Warn "Existing venv is not Python 3.10. Recreating it..."
        Remove-Item -Recurse -Force $venvPath
        & $python310Path -m venv $venvPath
        $venvVersion = Get-PythonVersion $venvPython
        if ($venvVersion -notmatch "Python 3\.10") {
            throw "Recreated venv is still not Python 3.10."
        }
    }

    return $venvVersion
}

function Ensure-Dependencies {
    $requiredPackages = @(
        "fastapi",
        "uvicorn",
        "multipart",
        "whisper",
        "torch",
        "ffmpeg"
    )

    $missingPackages = @()
    foreach ($package in $requiredPackages) {
        & $venvPython -c "import $package" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            $missingPackages += $package
        }
    }

    if ($missingPackages.Count -eq 0) {
        Write-Info "Speech-service dependencies already available in the venv."
        return
    }

    Write-Info "Missing packages detected: $($missingPackages -join ', ')"
    Write-Info "Upgrading pip..."
    try {
        & $venvPython -m pip install --upgrade pip --disable-pip-version-check
    } catch {
        Write-Warn "pip upgrade failed. Continuing with the existing pip version."
    }

    if (Test-Path (Join-Path $speechRoot "requirements.txt")) {
        try {
            & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $speechRoot "requirements.txt")
            return
        } catch {
            Write-Warn "requirements.txt install failed. Falling back to manual package install..."
        }
    }

    & $venvPython -m pip install --disable-pip-version-check fastapi uvicorn python-multipart openai-whisper torch ffmpeg-python
}

function Ensure-Ffmpeg {
    try {
        & ffmpeg -version | Out-Null
        return
    } catch {
        Write-Warn "FFmpeg is not available in PATH."
    }

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "FFmpeg is missing and winget is unavailable. Install FFmpeg manually, then rerun."
    }

    Write-Info "Trying to install FFmpeg with winget..."
    try {
        & winget install ffmpeg --accept-source-agreements --accept-package-agreements
    } catch {
        try {
            & winget install --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
        } catch {
            throw "FFmpeg installation failed. Install FFmpeg manually, then rerun."
        }
    }

    & ffmpeg -version | Out-Null
}

function Stop-Port9000Process {
    $netstatLines = @(netstat -ano | findstr ":$speechPort")
    if (-not $netstatLines) {
        return
    }

    foreach ($line in $netstatLines) {
        $columns = ($line -replace "\s+", " ").Trim().Split(" ")
        if ($columns.Length -ge 5) {
            $processId = $columns[-1]
            if ($processId -match "^\d+$") {
                Write-Warn "Port $speechPort is already in use by PID $processId. Stopping it..."
                try {
                    taskkill /PID $processId /F | Out-Null
                } catch {
                    Write-Warn "Could not stop PID $processId automatically."
                }
            }
        }
    }
}

function Start-SpeechService {
    Start-Process -FilePath $venvPython -ArgumentList @(
        "-m",
        "uvicorn",
        "app:app",
        "--app-dir",
        $speechRoot,
        "--host",
        "127.0.0.1",
        "--port",
        "$speechPort"
    ) -WorkingDirectory $projectRoot | Out-Null
}

function Wait-ForHealth {
    $maxAttempts = 20
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt += 1) {
        Start-Sleep -Seconds 2
        try {
            $health = Invoke-RestMethod "$speechBaseUrl/health"
            if ($health.status -eq "ok") {
                return $health
            }
        } catch {
        }
    }

    throw "Speech service did not become healthy on $speechBaseUrl/health"
}

try {
    Write-Step "Verify Python 3.10"
    $python310Path = Ensure-Python310
    Write-Success "Python 3.10 installed at $python310Path"

    Write-Step "Create or verify speech-service virtual environment"
    $venvVersion = Ensure-Venv $python310Path
    Write-Success "Virtual environment ready ($venvVersion)"

    Write-Step "Install speech-service dependencies"
    Ensure-Dependencies
    Write-Success "Dependencies installed"

    Write-Step "Check FFmpeg"
    Ensure-Ffmpeg
    Write-Success "FFmpeg working"

    Write-Step "Resolve port conflicts"
    Stop-Port9000Process
    Write-Success "Port $speechPort is free"

    Write-Step "Start speech service"
    Start-SpeechService
    Write-Success "Speech service start command issued"

    Write-Step "Verify health endpoint"
    $health = Wait-ForHealth
    Write-Success "Health endpoint verified: $($health | ConvertTo-Json -Compress)"

    Write-Host ""
    Write-Host "[OK] Python 3.10 installed" -ForegroundColor Green
    Write-Host "[OK] Virtual environment active" -ForegroundColor Green
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
    Write-Host "[OK] FFmpeg working" -ForegroundColor Green
    Write-Host "[OK] Speech service running on port 9000" -ForegroundColor Green
    Write-Host "[OK] Health endpoint verified" -ForegroundColor Green
    Write-Host ""
    Write-Host "Speech service base URL: $speechBaseUrl" -ForegroundColor Cyan
} catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Suggested fix: review the failing step above and rerun setup_speech_service.ps1 after correcting it." -ForegroundColor Yellow
    exit 1
}
