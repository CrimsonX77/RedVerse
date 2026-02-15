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

# ─── Thorough Component Detection ──────────────────────────
Write-Host ""
Write-Step "Running thorough component detection..."

# Get script directory and potential RedVerse install location
$scriptDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$installDir = "$env:USERPROFILE\RedVerse"

# Detection results
$ollamaFound = $false
$oracleModelFound = $false
$pythonFound = $false
$pythonPackagesFound = $false
$ffmpegFound = $false
$redverseFound = $false
$pythonCmd = $null

# Check for Ollama
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaPath) {
    $ollamaFound = $true
    Write-Ok "✓ Ollama found on system"
} else {
    Write-Step "  Ollama not found on system"
}

# Check for Oracle model (only if Ollama is available)
if ($ollamaFound) {
    $models = ollama list 2>$null
    if ($models -match "(?i)crimsondragonx7/oracle") {
        $oracleModelFound = $true
        Write-Ok "✓ Oracle model found"
    } else {
        Write-Step "  Oracle model not found"
    }
}

# Check for Python 3.10+
foreach ($cmd in @("python", "python3", "py")) {
    $p = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($p) {
        $ver = & $cmd --version 2>&1
        if ($ver -match "3\.1[0-9]|3\.[2-9][0-9]") {
            $pythonCmd = $cmd
            $pythonFound = $true
            Write-Ok "✓ Python 3.10+ found: $ver"
            break
        }
    }
}
if (-not $pythonFound) {
    Write-Step "  Python 3.10+ not found"
}

# Check for Python packages (if Python is available)
if ($pythonFound) {
    $missingPackages = @()
    foreach ($pkg in @("edge-tts", "SpeechRecognition", "PyQt6", "Pillow", "flask", "ollama")) {
        $pkgImport = $pkg -replace "-", "_"
        $null = & $pythonCmd -c "import $pkgImport" 2>&1
        if ($LASTEXITCODE -ne 0) {
            $missingPackages += $pkg
        }
    }
    if ($missingPackages.Count -eq 0) {
        $pythonPackagesFound = $true
        Write-Ok "✓ All required Python packages found"
    } else {
        Write-Step "  Missing Python packages: $($missingPackages -join ', ')"
    }
}

# Check for ffmpeg
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $ffmpegFound = $true
    $ffmpegVer = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Ok "✓ ffmpeg found: $($ffmpegVer -replace 'ffmpeg version ', '')"
} else {
    Write-Step "  ffmpeg not found"
}

# Check for RedVerse repository (in script dir or standard install location)
if ((Test-Path "$scriptDir\.git") -and (Test-Path "$scriptDir\serve_edrive.py")) {
    $redverseFound = $true
    $installDir = $scriptDir
    Write-Ok "✓ RedVerse repository found at: $installDir"
} elseif ((Test-Path "$installDir\.git") -and (Test-Path "$installDir\serve_edrive.py")) {
    $redverseFound = $true
    Write-Ok "✓ RedVerse repository found at: $installDir"
} else {
    Write-Step "  RedVerse repository not found"
}

# Summary
Write-Host ""
Write-Step "Detection Summary:"
$allFound = $true
if (-not $ollamaFound) {
    Write-Warn "  ✗ Ollama needs installation"
    $allFound = $false
}
if ($ollamaFound -and -not $oracleModelFound) {
    Write-Warn "  ✗ Oracle model needs to be pulled"
    $allFound = $false
}
if (-not $pythonFound) {
    Write-Warn "  ✗ Python 3.10+ needs installation"
    $allFound = $false
}
if ($pythonFound -and -not $pythonPackagesFound) {
    Write-Warn "  ✗ Python packages need installation"
    $allFound = $false
}
if (-not $ffmpegFound) {
    Write-Warn "  ✗ ffmpeg needs installation"
    $allFound = $false
}
if (-not $redverseFound) {
    Write-Warn "  ✗ RedVerse repository needs cloning"
    $allFound = $false
}

if ($allFound) {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "    ✓ All components already installed!" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host ""
    
    # Check if RedVerse needs updating
    if ($redverseFound) {
        Write-Host "Checking for RedVerse updates..." -ForegroundColor Yellow
        Push-Location $installDir
        git fetch origin main 2>$null
        $local = git rev-parse @ 2>$null
        $remote = git rev-parse '@{u}' 2>$null
        
        if ($local -ne $remote) {
            Write-Step "Update available — pulling latest changes..."
            git pull origin main 2>$null
            Write-Ok "RedVerse updated to latest version"
        } else {
            Write-Ok "RedVerse is already up to date"
        }
        Pop-Location
    }
    
    Write-Host ""
    Write-Host "System is ready to use!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To start the RedVerse backend:" -ForegroundColor Yellow
    Write-Host "  cd $installDir"
    Write-Host "  $pythonCmd serve_edrive.py"
    Write-Host ""
    Write-Host "Then open in your browser:" -ForegroundColor Yellow
    Write-Host "  http://localhost:8666/EDrive.html"
    Write-Host "  http://localhost:8666/oracle.html"
    Write-Host ""
    
    # Offer to start server
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
    exit 0
}

Write-Host ""
Write-Step "Proceeding with installation of missing components..."
Start-Sleep -Seconds 2

# ─── 1. Install Ollama ────────────────────────────────
Write-Host ""
if ($ollamaFound) {
    Write-Step "Step 1/6 — Ollama already installed, skipping..."
} else {
    Write-Step "Step 1/6 — Installing Ollama..."

    $installerUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    Write-Step "Running Ollama installer (follow prompts)..."
    Start-Process -FilePath $installerPath -Wait
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Ok "Ollama installed successfully"
        $ollamaFound = $true
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
if ($oracleModelFound) {
    Write-Step "Step 2/6 — Oracle model already present, skipping..."
} else {
    Write-Step "Step 2/6 — Pulling Oracle model (this may take a few minutes)..."
    & ollama pull CrimsonDragonX7/Oracle:latest
    Write-Ok "Oracle model pulled"
}

# ─── 3. Install Python ────────────────────────────────
Write-Host ""
if ($pythonFound) {
    Write-Step "Step 3/6 — Python 3.10+ already installed, skipping..."
} else {
    Write-Step "Step 3/6 — Installing Python..."
    try {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $pythonCmd = "python"
        $pyVer = & $pythonCmd --version 2>&1
        Write-Ok "Python installed: $pyVer"
        $pythonFound = $true
    } catch {
        Write-Fail "Could not install Python — please install Python 3.10+ from python.org"
    }
}
if (-not $pythonCmd) {
    $pythonCmd = "python"
}

# ─── 4. Install pip packages ──────────────────────────
Write-Host ""
if ($pythonPackagesFound) {
    Write-Step "Step 4/6 — Python packages already installed, skipping..."
} else {
    Write-Step "Step 4/6 — Installing Python packages..."
    & $pythonCmd -m pip install --upgrade pip --quiet 2>$null
    & $pythonCmd -m pip install edge-tts SpeechRecognition --quiet
    Write-Ok "edge-tts and SpeechRecognition installed"
}

# ─── 5. Install ffmpeg ────────────────────────────────
Write-Host ""
if ($ffmpegFound) {
    Write-Step "Step 5/6 — ffmpeg already installed, skipping..."
} else {
    Write-Step "Step 5/6 — Installing ffmpeg..."
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
if ($redverseFound) {
    Write-Step "Step 6/6 — RedVerse already present, checking for updates..."
    Push-Location $installDir
    git pull origin main 2>$null
    Pop-Location
    Write-Ok "RedVerse updated"
} else {
    Write-Step "Step 6/6 — Cloning RedVerse..."
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
