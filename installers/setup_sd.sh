#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# RedVerse SD Setup — Optional Stable Diffusion WebUI Installer
# Installs: AUTOMATIC1111 SD WebUI + anyorangemixAnything_mint
# ═══════════════════════════════════════════════════════════════
set -e

CRIMSON='\033[0;31m'
GOLD='\033[0;33m'
GREEN='\033[0;32m'
DIM='\033[0;90m'
RESET='\033[0m'
BOLD='\033[1m'

info()    { echo -e "${GOLD}[SD]${RESET} $1"; }
success() { echo -e "${GREEN}[ ✓ ]${RESET} $1"; }
warn()    { echo -e "${GOLD}[ ! ]${RESET} $1"; }
fail()    { echo -e "${CRIMSON}[ ✗ ]${RESET} $1"; exit 1; }

echo ""
echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
echo -e "${CRIMSON}${BOLD}  ⧫  RedVerse SD Setup — Scene Generator  ⧫${RESET}"
echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${DIM}This installs Stable Diffusion WebUI (AUTOMATIC1111) in API mode${RESET}"
echo -e "${DIM}with the anyorangemixAnything_mint checkpoint for E-Drive scenes.${RESET}"
echo -e "${DIM}Requires: GPU with 4GB+ VRAM (NVIDIA recommended), ~8GB disk.${RESET}"
echo ""

SD_DIR=""
MODEL_NAME="anyorangemixAnything_mint.safetensors"
# CivitAI direct download URL for anyorangemixAnything_mint
CIVITAI_URL="https://civitai.com/api/download/models/8099"

# ─── Detect existing SD installation ─────────────────────
# Search common locations for an existing stable-diffusion-webui
SD_SEARCH_DIRS=(
  "$HOME/stable-diffusion-webui"
  "$HOME/Desktop/Redverse/stable-diffusion-webui"
  "$HOME/Desktop/RedVerse/stable-diffusion-webui"
  "$HOME/Desktop/redverse/stable-diffusion-webui"
  "$HOME/Desktop/stable-diffusion-webui"
)
for sdir in "${SD_SEARCH_DIRS[@]}"; do
  if [[ -d "$sdir/.git" ]]; then
    SD_DIR="$sdir"
    success "Existing SD WebUI found at: $SD_DIR"
    break
  fi
done
# Default if not found
if [[ -z "$SD_DIR" ]]; then
  SD_DIR="$HOME/stable-diffusion-webui"
fi
MODEL_DIR="$SD_DIR/models/Stable-diffusion"

# ─── Detect OS ──────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Linux*)  PLATFORM="linux";;
  Darwin*) PLATFORM="macos";;
  *)       fail "Unsupported OS: $OS";;
esac

# ─── Check prerequisites ───────────────────────────────
info "Checking prerequisites..."

# Python
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
[[ -z "$PYTHON" ]] && fail "Python 3.10+ required — run the main RedVerse installer first"
success "Python: $($PYTHON --version)"

# Git
command -v git &>/dev/null || fail "Git is required — install it first"
success "Git: $(git --version)"

# GPU check (informational)
if command -v nvidia-smi &>/dev/null; then
  GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
  VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1)
  success "GPU: $GPU ($VRAM)"
else
  warn "No NVIDIA GPU detected — SD may be slow on CPU. Continuing anyway..."
fi

# ─── 1. Clone SD WebUI ─────────────────────────────────
echo ""
info "Step 1/3 — Setting up Stable Diffusion WebUI..."
if [[ -d "$SD_DIR/.git" ]]; then
  info "SD WebUI already cloned — pulling latest..."
  cd "$SD_DIR"
  git pull 2>/dev/null || warn "Git pull failed — continuing with existing version"
  success "SD WebUI updated"
else
  if [[ -d "$SD_DIR" ]]; then
    warn "Backing up existing $SD_DIR..."
    mv "$SD_DIR" "${SD_DIR}_backup_$(date +%s)"
  fi
  git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git "$SD_DIR"
  success "SD WebUI cloned to $SD_DIR"
fi

# ─── 2. Download model ─────────────────────────────────
echo ""
info "Step 2/3 — Downloading anyorangemixAnything_mint..."
mkdir -p "$MODEL_DIR"

if [[ -f "$MODEL_DIR/$MODEL_NAME" ]]; then
  success "Model already downloaded: $MODEL_NAME"
else
  info "Downloading from CivitAI (~2GB, this may take a while)..."
  if command -v wget &>/dev/null; then
    wget -q --show-progress -O "$MODEL_DIR/$MODEL_NAME" "$CIVITAI_URL"
  elif command -v curl &>/dev/null; then
    curl -L --progress-bar -o "$MODEL_DIR/$MODEL_NAME" "$CIVITAI_URL"
  else
    fail "Neither wget nor curl found — cannot download model"
  fi
  
  if [[ -f "$MODEL_DIR/$MODEL_NAME" && $(stat -c%s "$MODEL_DIR/$MODEL_NAME" 2>/dev/null || stat -f%z "$MODEL_DIR/$MODEL_NAME" 2>/dev/null) -gt 1000000 ]]; then
    success "Model downloaded: $MODEL_NAME"
  else
    fail "Model download appears incomplete — try again or download manually from CivitAI"
  fi
fi

# ─── 3. Create launcher script ─────────────────────────
echo ""
info "Step 3/3 — Creating API launcher..."

LAUNCHER="$SD_DIR/run_api.sh"
cat > "$LAUNCHER" << 'LAUNCH_EOF'
#!/usr/bin/env bash
# RedVerse SD WebUI — API-only mode launcher
cd "$(dirname "$0")"
export COMMANDLINE_ARGS="--api --nowebui --port 7860 --listen"
./webui.sh $COMMANDLINE_ARGS
LAUNCH_EOF
chmod +x "$LAUNCHER"
success "Launcher created: $LAUNCHER"

# ─── Done ───────────────────────────────────────────────
echo ""
echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}       ⧫  SD Setup Complete  ⧫${RESET}"
echo -e "${CRIMSON}${BOLD}═══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${GOLD}First run will take extra time (downloads PyTorch + dependencies).${RESET}"
echo ""
echo -e "${GOLD}To start SD WebUI in API mode:${RESET}"
echo -e "  cd $SD_DIR"
echo -e "  bash run_api.sh"
echo ""
echo -e "${GOLD}Then start the RedVerse backend in another terminal:${RESET}"
echo -e "  cd ~/RedVerse && $PYTHON serve_edrive.py"
echo ""
echo -e "${DIM}SD WebUI API will be proxied through serve_edrive.py on port 8666/sd/*${RESET}"
echo ""

# ─── Auto-run first setup? ─────────────────────────────
read -rp "Run initial SD WebUI setup now? (downloads ~5GB of PyTorch etc.) [y/N] " answer
if [[ "$answer" =~ ^[Yy] ]]; then
  info "Running first-time SD WebUI setup..."
  cd "$SD_DIR"
  bash run_api.sh
fi
