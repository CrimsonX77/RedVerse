# ═══════════════════════════════════════════════════════════════
# RedVerse Setup Ritual — Windows Installer (PowerShell)
# Installs: Ollama, Oracle model, Python deps, ffmpeg, RedVerse
# Run as Administrator: irm <url> | iex
# ═══════════════════════════════════════════════════════════════
$ErrorActionPreference = "Stop"

function Write-Banner {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor DarkRed
    Write-Host "       ⧫  RedVerse Setup Ritual  ⧫" -ForegroundColor DarkRed
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor DarkRed
    Write-Host ""
}

function Write-Step  { param($msg) Write-Host "[RITUAL] $msg" -ForegroundColor Yellow }
function Write-Ok    { param($msg) Write-Host "[  ✓  ] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[  !  ] $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "[  ✗  ] $msg" -ForegroundColor Red; exit 1 }

Write-Banner

# ─── 1. Install Ollama ────────────────────────────────
Write-Host ""
Write-Step "Step 1/6 — Installing Ollama..."

$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaPath) {
    Write-Ok "Ollama already installed"
} else {
    Write-Step "Downloading Ollama installer..."
    $installerUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    Write-Step "Running Ollama installer (follow prompts)..."
    Start-Process -FilePath $installerPath -Wait
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Ok "Ollama installed successfully"
    } else {
        Write-Warn "Ollama may need a restart to be in PATH — continuing..."
    }
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
}

# Ensure Ollama is running
Write-Step "Ensuring Ollama service is running..."
Start-Sleep -Seconds 2
try {
    $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    Write-Ok "Ollama is running"
} catch {
    Write-Warn "Starting Ollama..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
        Write-Ok "Ollama started"
    } catch {
        Write-Warn "Ollama may need to be started manually: ollama serve"
    }
}

# ─── 2. Pull Oracle Model ─────────────────────────────
Write-Host ""
Write-Step "Step 2/6 — Pulling Oracle model (this may take a few minutes)..."

$models = ollama list 2>$null
if ($models -match "(?i)crimsondragonx7/oracle") {
    Write-Ok "Oracle model already present"
} else {
    & ollama pull CrimsonDragonX7/Oracle:latest
    Write-Ok "Oracle model pulled"
}

# ─── 3. Install Python ────────────────────────────────
Write-Host ""
Write-Step "Step 3/6 — Checking Python..."

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    $p = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($p) {
        $ver = & $cmd --version 2>&1
        if ($ver -match "3\.1[0-9]|3\.[2-9][0-9]") {
            $pythonCmd = $cmd
            break
        }
    }
}

if (-not $pythonCmd) {
    Write-Step "Python 3.10+ not found — installing via winget..."
    try {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $pythonCmd = "python"
    } catch {
        Write-Fail "Could not install Python — please install Python 3.10+ from python.org"
    }
}
$pyVer = & $pythonCmd --version 2>&1
Write-Ok "Python: $pyVer"

# ─── 4. Install pip packages ──────────────────────────
Write-Host ""
Write-Step "Step 4/6 — Installing Python packages..."
& $pythonCmd -m pip install --upgrade pip --quiet 2>$null
& $pythonCmd -m pip install edge-tts SpeechRecognition --quiet
Write-Ok "edge-tts and SpeechRecognition installed"

# ─── 5. Install ffmpeg ────────────────────────────────
Write-Host ""
Write-Step "Step 5/6 — Checking ffmpeg..."

if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Ok "ffmpeg already installed"
} else {
    Write-Step "Installing ffmpeg via winget..."
    try {
        winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        Write-Ok "ffmpeg installed"
    } catch {
        Write-Warn "ffmpeg install failed — STT will use browser fallback. Install manually from ffmpeg.org"
    }
}

# ─── 6. Clone / Update RedVerse ───────────────────────
Write-Host ""
Write-Step "Step 6/6 — Setting up RedVerse..."

$installDir = "$env:USERPROFILE\RedVerse"
if (Test-Path "$installDir\.git") {
    Write-Step "RedVerse already cloned — pulling latest..."
    Push-Location $installDir
    git pull origin main 2>$null
    Pop-Location
    Write-Ok "RedVerse updated"
} else {
    if (Test-Path $installDir) {
        Write-Warn "Backing up existing $installDir..."
        $ts = Get-Date -Format "yyyyMMddHHmmss"
        Rename-Item $installDir "${installDir}_backup_$ts"
    }
    git clone https://github.com/CrimsonX77/RedVerse.git $installDir
    Write-Ok "RedVerse cloned to $installDir"
}

# ─── Done ──────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor DarkRed
Write-Host "       ⧫  Setup Complete  ⧫" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor DarkRed
Write-Host ""
Write-Host "To start the RedVerse backend:" -ForegroundColor Yellow
Write-Host "  cd $installDir"
Write-Host "  $pythonCmd serve_edrive.py"
Write-Host ""
Write-Host "Then open in your browser:" -ForegroundColor Yellow
Write-Host "  http://localhost:8666/EDrive.html"
Write-Host "  http://localhost:8666/oracle.html"
Write-Host ""
Write-Host "Optional: Run the SD installer for scene generation:" -ForegroundColor DarkGray
Write-Host "  (See setup.html for instructions)"
Write-Host ""

# ─── Auto-start prompt ────────────────────────────────
$answer = Read-Host "Start the RedVerse server now? [Y/n]"
if ($answer -eq "" -or $answer -match "^[Yy]") {
    Write-Step "Starting serve_edrive.py..."
    Push-Location $installDir
    Start-Process $pythonCmd -ArgumentList "serve_edrive.py" -WindowStyle Normal
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8666/EDrive.html"
    Pop-Location
    Write-Ok "Server started — opening browser..."
}
