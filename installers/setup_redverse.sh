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
info "Step 1/6 — Installing Ollama..."
if command -v ollama &>/dev/null; then
  success "Ollama already installed: $(ollama --version 2>/dev/null || echo 'found')"
else
  curl -fsSL https://ollama.com/install.sh | sh
  if command -v ollama &>/dev/null; then
    success "Ollama installed successfully"
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
info "Step 2/6 — Pulling Oracle model (this may take a few minutes)..."
if ollama list 2>/dev/null | grep -qi "crimsondragonx7/oracle"; then
  success "Oracle model already present"
else
  ollama pull CrimsonDragonX7/Oracle:latest
  success "Oracle model pulled"
fi

# ─── 3. Install Python ─────────────────────────────────
echo ""
info "Step 3/6 — Checking Python..."
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  warn "Python 3.10+ not found — installing..."
  if [[ "$PLATFORM" == "macos" ]]; then
    brew install python@3.12
    PYTHON="python3"
  else
    install_pkg python3
    install_pkg python3-pip
    PYTHON="python3"
  fi
fi
success "Python: $($PYTHON --version)"

# ─── 4. Install pip packages ───────────────────────────
echo ""
info "Step 4/6 — Installing Python packages..."
$PYTHON -m pip install --upgrade pip --quiet 2>/dev/null || true
$PYTHON -m pip install edge-tts SpeechRecognition --quiet
success "edge-tts and SpeechRecognition installed"

# ─── 5. Install ffmpeg ─────────────────────────────────
echo ""
info "Step 5/6 — Checking ffmpeg..."
if command -v ffmpeg &>/dev/null; then
  success "ffmpeg already installed"
else
  info "Installing ffmpeg..."
  install_pkg ffmpeg
  if command -v ffmpeg &>/dev/null; then
    success "ffmpeg installed"
  else
    warn "ffmpeg installation failed — STT will use browser fallback"
  fi
fi

# ─── 6. Clone / Update RedVerse ────────────────────────
echo ""
info "Step 6/6 — Setting up RedVerse..."
INSTALL_DIR="$HOME/RedVerse"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "RedVerse already cloned — pulling latest..."
  cd "$INSTALL_DIR"
  git pull origin main 2>/dev/null || warn "Git pull failed — continuing with existing version"
  success "RedVerse updated"
else
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
