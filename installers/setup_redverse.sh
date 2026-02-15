#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# RedVerse Setup Ritual — Linux & macOS Installer
# Installs: Ollama, Oracle model, Python deps, ffmpeg, RedVerse
# ═══════════════════════════════════════════════════════════════
set -e

CRIMSON='\033[0;31m'
GOLD='\033[0;33m'
GREEN='\033[0;32m'
DIM='\033[0;90m'
RESET='\033[0m'
BOLD='\033[1m'

banner() {
  echo ""
  echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
  echo -e "${CRIMSON}${BOLD}       ⧫  RedVerse Setup Ritual  ⧫${RESET}"
  echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
  echo ""
}

info()    { echo -e "${GOLD}[RITUAL]${RESET} $1"; }
success() { echo -e "${GREEN}[  ✓  ]${RESET} $1"; }
warn()    { echo -e "${GOLD}[  !  ]${RESET} $1"; }
fail()    { echo -e "${CRIMSON}[  ✗  ]${RESET} $1"; exit 1; }

banner

# ─── Detect OS ──────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Linux*)  PLATFORM="linux";;
  Darwin*) PLATFORM="macos";;
  *)       fail "Unsupported OS: $OS — use the Windows installer (.ps1) instead.";;
esac
info "Platform detected: $PLATFORM"

# ─── Thorough Component Detection ──────────────────────────
echo ""
info "Running thorough component detection..."

# Get script directory and potential RedVerse install location
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$HOME/RedVerse"

# Detection results
OLLAMA_FOUND=false
ORACLE_MODEL_FOUND=false
PYTHON_FOUND=false
PYTHON_PACKAGES_FOUND=false
FFMPEG_FOUND=false
REDVERSE_FOUND=false
VENV_ACTIVATED=false
VENV_DIR=""

# ─── Virtual Environment Detection ────────────────────────
# Search common locations for an existing RedVerse venv and activate it.
# Priority: project dir → ~/Desktop/Redverse → ~/Desktop/RedVerse → ~/RedVerse
info "Searching for existing virtual environments..."
VENV_SEARCH_ROOTS=(
  "$SCRIPT_DIR"
  "$HOME/Desktop/Redverse"
  "$HOME/Desktop/RedVerse"
  "$HOME/Desktop/redverse"
  "$HOME/Redverse"
  "$HOME/RedVerse"
)
VENV_NAMES=("venv" ".venv" "env" "redverse-venv" "redverse_venv")

for root in "${VENV_SEARCH_ROOTS[@]}"; do
  for vname in "${VENV_NAMES[@]}"; do
    candidate="$root/$vname"
    if [[ -f "$candidate/bin/activate" ]]; then
      VENV_DIR="$candidate"
      break 2
    fi
  done
done

if [[ -n "$VENV_DIR" ]]; then
  info "Found virtual environment at: $VENV_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  VENV_ACTIVATED=true
  success "✓ Virtual environment activated: $VENV_DIR"
else
  info "  No existing virtual environment found"
fi

# Check for Ollama (system-wide or local)
if command -v ollama &>/dev/null; then
  OLLAMA_FOUND=true
  success "✓ Ollama found on system: $(ollama --version 2>/dev/null || echo 'installed')"
else
  info "  Ollama not found on system"
fi

# Check for Oracle model (only if Ollama is available)
if [ "$OLLAMA_FOUND" = true ]; then
  if ollama list 2>/dev/null | grep -qi "crimsondragonx7/oracle"; then
    ORACLE_MODEL_FOUND=true
    success "✓ Oracle model found"
  else
    info "  Oracle model not found"
  fi
fi

# Check for Python 3.10+
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" --version 2>&1 | sed -n 's/Python \([0-9]*\.[0-9]*\).*/\1/p')
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [[ $major -gt 3 || ($major -eq 3 && $minor -ge 10) ]]; then
      PYTHON="$cmd"
      PYTHON_FOUND=true
      success "✓ Python 3.10+ found: $($cmd --version)"
      break
    fi
  fi
done
if [ "$PYTHON_FOUND" = false ]; then
  info "  Python 3.10+ not found"
fi

# Check for Python packages (if Python is available)
if [ "$PYTHON_FOUND" = true ]; then
  MISSING_PACKAGES=()
  # Map of package names to their import names
  declare -A PKG_MAP=(
    ["edge-tts"]="edge_tts"
    ["SpeechRecognition"]="speech_recognition"
    ["PyQt6"]="PyQt6"
    ["Pillow"]="PIL"
    ["flask"]="flask"
    ["ollama"]="ollama"
  )
  
  for pkg in edge-tts SpeechRecognition PyQt6 Pillow flask ollama; do
    import_name="${PKG_MAP[$pkg]}"
    if ! $PYTHON -c "import $import_name" &>/dev/null; then
      MISSING_PACKAGES+=("$pkg")
    fi
  done
  if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    PYTHON_PACKAGES_FOUND=true
    success "✓ All required Python packages found"
  else
    info "  Missing Python packages: ${MISSING_PACKAGES[*]}"
  fi
fi

# Check for ffmpeg
if command -v ffmpeg &>/dev/null; then
  FFMPEG_FOUND=true
  success "✓ ffmpeg found: $(ffmpeg -version | head -1 | cut -d' ' -f3)"
else
  info "  ffmpeg not found"
fi

# Check for RedVerse repository (in script dir, standard, or Desktop locations)
REDVERSE_SEARCH_DIRS=(
  "$SCRIPT_DIR"
  "$HOME/RedVerse"
  "$HOME/Redverse"
  "$HOME/Desktop/Redverse"
  "$HOME/Desktop/RedVerse"
  "$HOME/Desktop/redverse"
)
for rdir in "${REDVERSE_SEARCH_DIRS[@]}"; do
  if [[ -d "$rdir/.git" && -f "$rdir/serve_edrive.py" ]]; then
    REDVERSE_FOUND=true
    INSTALL_DIR="$rdir"
    success "✓ RedVerse repository found at: $INSTALL_DIR"
    break
  fi
done
if [ "$REDVERSE_FOUND" = false ]; then
  info "  RedVerse repository not found"
fi

# Summary
echo ""
info "Detection Summary:"
ALL_FOUND=true
if [ "$OLLAMA_FOUND" = false ]; then
  warn "  ✗ Ollama needs installation"
  ALL_FOUND=false
fi
if [ "$OLLAMA_FOUND" = true ] && [ "$ORACLE_MODEL_FOUND" = false ]; then
  warn "  ✗ Oracle model needs to be pulled"
  ALL_FOUND=false
fi
if [ "$PYTHON_FOUND" = false ]; then
  warn "  ✗ Python 3.10+ needs installation"
  ALL_FOUND=false
fi
if [ "$PYTHON_FOUND" = true ] && [ "$PYTHON_PACKAGES_FOUND" = false ]; then
  warn "  ✗ Python packages need installation"
  ALL_FOUND=false
fi
if [ "$FFMPEG_FOUND" = false ]; then
  warn "  ✗ ffmpeg needs installation"
  ALL_FOUND=false
fi
if [ "$REDVERSE_FOUND" = false ]; then
  warn "  ✗ RedVerse repository needs cloning"
  ALL_FOUND=false
fi

if [ "$ALL_FOUND" = true ]; then
  echo ""
  echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${RESET}"
  echo -e "${GREEN}${BOLD}    ✓ All components already installed!${RESET}"
  echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${RESET}"
  echo ""
  
  # Check if RedVerse needs updating
  if [ "$REDVERSE_FOUND" = true ]; then
    echo -e "${GOLD}Checking for RedVerse updates...${RESET}"
    cd "$INSTALL_DIR"
    git fetch origin main 2>/dev/null || true
    LOCAL=$(git rev-parse @ 2>/dev/null)
    REMOTE=$(git rev-parse @{u} 2>/dev/null)
    
    if [ "$LOCAL" != "$REMOTE" ]; then
      info "Update available — pulling latest changes..."
      git pull origin main 2>/dev/null || warn "Git pull failed"
      success "RedVerse updated to latest version"
    else
      success "RedVerse is already up to date"
    fi
  fi
  
  echo ""
  echo -e "${GOLD}System is ready to use!${RESET}"
  echo ""
  echo -e "${GOLD}To start the RedVerse backend:${RESET}"
  echo -e "  cd $INSTALL_DIR"
  echo -e "  $PYTHON serve_edrive.py"
  echo ""
  echo -e "${GOLD}Then open in your browser:${RESET}"
  echo -e "  http://localhost:8666/EDrive.html"
  echo -e "  http://localhost:8666/oracle.html"
  echo ""
  
  # Offer to start server
  read -rp "Start the RedVerse server now? [Y/n] " answer
  answer=${answer:-Y}
  if [[ "$answer" =~ ^[Yy] ]]; then
    info "Starting serve_edrive.py..."
    cd "$INSTALL_DIR"
    $PYTHON serve_edrive.py &
    SERVER_PID=$!
    sleep 2
    if kill -0 $SERVER_PID 2>/dev/null; then
      success "Server running at http://localhost:8666 (PID: $SERVER_PID)"
      if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:8666/EDrive.html" 2>/dev/null &
      elif command -v open &>/dev/null; then
        open "http://localhost:8666/EDrive.html" 2>/dev/null &
      fi
    else
      warn "Server may have failed to start — check logs"
    fi
  fi
  exit 0
fi

echo ""
info "Proceeding with installation of missing components..."
sleep 2

# ─── Check for package manager ──────────────────────────
install_pkg() {
  local pkg="$1"
  if [[ "$PLATFORM" == "macos" ]]; then
    if ! command -v brew &>/dev/null; then
      warn "Homebrew not found — installing..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install "$pkg" 2>/dev/null || true
  else
    if command -v apt-get &>/dev/null; then
      sudo apt-get install -y "$pkg"
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y "$pkg"
    elif command -v pacman &>/dev/null; then
      sudo pacman -S --noconfirm "$pkg"
    else
      warn "No supported package manager found — please install '$pkg' manually."
    fi
  fi
}

# ─── 1. Install Ollama ─────────────────────────────────
echo ""
if [ "$OLLAMA_FOUND" = true ]; then
  info "Step 1/6 — Ollama already installed, skipping..."
else
  info "Step 1/6 — Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
  if command -v ollama &>/dev/null; then
    success "Ollama installed successfully"
    OLLAMA_FOUND=true
  else
    fail "Ollama installation failed — visit https://ollama.com for manual install"
  fi
fi

# Ensure ollama service is running
info "Ensuring Ollama service is running..."
if [[ "$PLATFORM" == "linux" ]]; then
  # Try systemd first, then manual start
  if command -v systemctl &>/dev/null; then
    sudo systemctl start ollama 2>/dev/null || true
    sudo systemctl enable ollama 2>/dev/null || true
  fi
fi
# Give it a moment to start
sleep 2
# Verify it's responding
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
  success "Ollama is running"
else
  warn "Starting Ollama manually..."
  nohup ollama serve &>/dev/null &
  sleep 3
  if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    success "Ollama started"
  else
    warn "Ollama may need to be started manually: ollama serve"
  fi
fi

# ─── 2. Pull Oracle Model ──────────────────────────────
echo ""
if [ "$ORACLE_MODEL_FOUND" = true ]; then
  info "Step 2/6 — Oracle model already present, skipping..."
else
  info "Step 2/6 — Pulling Oracle model (this may take a few minutes)..."
  ollama pull CrimsonDragonX7/Oracle:latest
  success "Oracle model pulled"
fi

# ─── 3. Install Python ─────────────────────────────────
echo ""
if [ "$PYTHON_FOUND" = true ]; then
  info "Step 3/6 — Python 3.10+ already installed, skipping..."
else
  info "Step 3/6 — Installing Python..."
  if [[ "$PLATFORM" == "macos" ]]; then
    brew install python@3.12
    PYTHON="python3"
  else
    install_pkg python3
    install_pkg python3-pip
    PYTHON="python3"
  fi
  # Verify installation
  if command -v "$PYTHON" &>/dev/null; then
    success "Python installed: $($PYTHON --version)"
    PYTHON_FOUND=true
  else
    fail "Python installation failed"
  fi
fi

# ─── 4. Install pip packages ───────────────────────────
echo ""
if [ "$PYTHON_PACKAGES_FOUND" = true ]; then
  info "Step 4/6 — Python packages already installed, skipping..."
else
  # Create a venv if we don't already have one active
  if [ "$VENV_ACTIVATED" = false ] && [ "$REDVERSE_FOUND" = true ]; then
    VENV_DIR="$INSTALL_DIR/venv"
    info "Creating virtual environment at $VENV_DIR..."
    $PYTHON -m venv "$VENV_DIR" 2>/dev/null || true
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
      # shellcheck disable=SC1091
      source "$VENV_DIR/bin/activate"
      VENV_ACTIVATED=true
      success "✓ Virtual environment created and activated"
    fi
  fi
  info "Step 4/6 — Installing Python packages..."
  $PYTHON -m pip install --upgrade pip --quiet 2>/dev/null || true
  $PYTHON -m pip install edge-tts SpeechRecognition --quiet
  success "edge-tts and SpeechRecognition installed"
fi

# ─── 5. Install ffmpeg ─────────────────────────────────
echo ""
if [ "$FFMPEG_FOUND" = true ]; then
  info "Step 5/6 — ffmpeg already installed, skipping..."
else
  info "Step 5/6 — Installing ffmpeg..."
  install_pkg ffmpeg
  if command -v ffmpeg &>/dev/null; then
    success "ffmpeg installed"
  else
    warn "ffmpeg installation failed — STT will use browser fallback"
  fi
fi

# ─── 6. Clone / Update RedVerse ────────────────────────
echo ""
if [ "$REDVERSE_FOUND" = true ]; then
  info "Step 6/6 — RedVerse already present, checking for updates..."
  cd "$INSTALL_DIR"
  git pull origin main 2>/dev/null || warn "Git pull failed — continuing with existing version"
  success "RedVerse updated"
else
  info "Step 6/6 — Cloning RedVerse..."
  if [[ -d "$INSTALL_DIR" ]]; then
    warn "$INSTALL_DIR exists but is not a git repo — backing up..."
    mv "$INSTALL_DIR" "${INSTALL_DIR}_backup_$(date +%s)"
  fi
  git clone https://github.com/CrimsonX77/RedVerse.git "$INSTALL_DIR"
  cd "$INSTALL_DIR"
  success "RedVerse cloned to $INSTALL_DIR"
fi

# ─── Done ───────────────────────────────────────────────
echo ""
echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}       ⧫  Setup Complete  ⧫${RESET}"
echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${GOLD}To start the RedVerse backend:${RESET}"
echo -e "  cd $INSTALL_DIR"
echo -e "  $PYTHON serve_edrive.py"
echo ""
echo -e "${GOLD}Then open in your browser:${RESET}"
echo -e "  http://localhost:8666/EDrive.html"
echo -e "  http://localhost:8666/oracle.html"
echo ""
echo -e "${DIM}Optional: Run the SD installer for scene generation:${RESET}"
echo -e "  bash $INSTALL_DIR/installers/setup_sd.sh"
echo ""

# ─── Auto-start server? ────────────────────────────────
read -rp "Start the RedVerse server now? [Y/n] " answer
answer=${answer:-Y}
if [[ "$answer" =~ ^[Yy] ]]; then
  info "Starting serve_edrive.py..."
  cd "$INSTALL_DIR"
  $PYTHON serve_edrive.py &
  SERVER_PID=$!
  sleep 2
  if kill -0 $SERVER_PID 2>/dev/null; then
    success "Server running at http://localhost:8666 (PID: $SERVER_PID)"
    # Try to open browser
    if command -v xdg-open &>/dev/null; then
      xdg-open "http://localhost:8666/EDrive.html" 2>/dev/null &
    elif command -v open &>/dev/null; then
      open "http://localhost:8666/EDrive.html" 2>/dev/null &
    fi
  else
    warn "Server may have failed to start — check logs"
  fi
fi
