#!/usr/bin/env bash
# ============================================================
# start_servers.sh — RedVerse: Launch all backend servers
# ============================================================
# Usage:
#   chmod +x start_servers.sh
#   ./start_servers.sh
#
# Stops all servers on Ctrl-C.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
PIDS=()

RED='\033[38;5;197m'
GRN='\033[38;5;46m'
YLW='\033[38;5;220m'
BLU='\033[38;5;75m'
DIM='\033[38;5;240m'
RST='\033[0m'
BOLD='\033[1m'

banner() {
  echo -e "${RED}${BOLD}"
  echo "  ╔══════════════════════════════════════════════╗"
  echo "  ║       REDVERSE — Starting All Servers        ║"
  echo "  ╚══════════════════════════════════════════════╝${RST}"
  echo ""
}

port_free() {
  ! ss -ltn 2>/dev/null | grep -q ":$1 " && \
  ! lsof -i ":$1" -sTCP:LISTEN -t 2>/dev/null | grep -q .
}

launch() {
  local name="$1"
  local script="$2"
  local port="$3"
  local emoji="$4"
  shift 4
  # remaining args are passed to the script
  local extra_args=("$@")

  local full_path="$SCRIPT_DIR/$script"

  if [[ ! -f "$full_path" ]]; then
    echo -e "  ${YLW}⚠${RST}  ${emoji} ${name} — script not found, skipping"
    return
  fi

  if ! port_free "$port"; then
    echo -e "  ${YLW}⚠${RST}  ${emoji} ${name} — port ${port} already in use, skipping"
    return
  fi

  "$PYTHON" "$full_path" "$port" "${extra_args[@]}" \
    >> "$SCRIPT_DIR/logs/${script%.py}.log" 2>&1 &
  local pid=$!
  PIDS+=("$pid")
  echo -e "  ${GRN}✓${RST}  ${emoji} ${DIM}${name}${RST}  ${BLU}http://127.0.0.1:${port}${RST}  ${DIM}(PID ${pid})${RST}"
}

shutdown_all() {
  echo ""
  echo -e "${RED}  Shutting down all servers…${RST}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null && echo -e "  ${DIM}stopped PID ${pid}${RST}" || true
  done
  echo -e "${GRN}  All clear.${RST}"
  exit 0
}

trap shutdown_all INT TERM

# ── Pre-flight ────────────────────────────────────────────────────────────────
banner
mkdir -p "$SCRIPT_DIR/logs"

echo -e "${DIM}  Python: $("$PYTHON" --version 2>&1)${RST}"
echo -e "${DIM}  Base  : $SCRIPT_DIR${RST}"
echo ""
echo -e "${DIM}  Launching servers…${RST}"
echo ""

# ── Core servers ──────────────────────────────────────────────────────────────
# The main FastAPI server (server.py) uses uvicorn — launch differently
if [[ -f "$SCRIPT_DIR/server.py" ]]; then
  if port_free 8800; then
    uvicorn server:app --host 127.0.0.1 --port 8800 \
      >> "$SCRIPT_DIR/logs/server.log" 2>&1 &
    PIDS+=("$!")
    echo -e "  ${GRN}✓${RST}  🌐 ${DIM}Main API${RST}  ${BLU}http://127.0.0.1:8800${RST}  ${DIM}(PID ${PIDS[-1]})${RST}"
  else
    echo -e "  ${YLW}⚠${RST}  🌐 Main API — port 8800 in use, skipping"
  fi
fi

# Flask servers
launch "QuickCam"             "quickcam_server.py"            8910 "🎥"
launch "Speaker"              "speaker_server.py"             8911 "🔊"
launch "Loop Pad"             "looppad_server.py"             8912 "🎵"
launch "MultiTool"            "multitool_server.py"           8913 "🔧"
launch "Audio Cutter"         "audiocutter_server.py"         8914 "✂️"
launch "Checkout / Shop"      "checkout_server.py"            8915 "🛒"
launch "Dragon Forge"         "dragon_forge_server.py"        8916 "🐉"
launch "Dragon Cleaner"       "dragon_cleaner_server.py"      8917 "🧹"
launch "Gauntlet Protocol"    "gauntlet_server.py"            8918 "⚔️"
launch "Void Eater"           "void_eater_server.py"          8919 "🕳️"
launch "Vision Switchboard"   "vision_switchboard_server.py"  8920 "👁️"
launch "RedVox Transcription" "redvox_server.py"              8921 "🩸"
launch "RedVault Indexer"     "redvault_indexer_server.py"    8923 "📇"
launch "Narrator"             "narrator_server.py"            8930 "🗣️"
launch "Recorder"             "recorder_server.py"            8931 "🎙️"
launch "Screen Recorder"      "screen_recorder_server.py"     8932 "🖥️"
launch "OmniSensor HUD"       "omnisensor_server.py"          8933 "⚡"
launch "Lyra Forge"           "lyra_forge_server.py"          8667 "🖼️"
launch "Embodiment"           "embodiment_server.py"          5000 "🤖"

# Consciousness server requires --soul argument — only launch if a soul file exists
SOUL_FILE="${REDVERSE_SOUL_FILE:-$HOME/Desktop/Souls/Sable/Sable_Cathedral_v5_3.yaml}"
if [[ -f "$SOUL_FILE" ]]; then
  launch "Consciousness" "consciousness_server.py" 7777 "🧠" \
    "--soul" "Sable_Cathedral_v5_3.yaml"
else
  echo -e "  ${YLW}⚠${RST}  🧠 Consciousness — soul file not found (set REDVERSE_SOUL_FILE to override), skipping"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}  ${#PIDS[@]} servers launched.${RST}"
echo ""
echo -e "  ${DIM}Main site  → ${BLU}http://127.0.0.1:8800${RST}"
echo -e "  ${DIM}Shop       → ${BLU}http://127.0.0.1:8915${RST}"
echo -e "  ${DIM}Speaker    → ${BLU}http://127.0.0.1:8911${RST}"
echo -e "  ${DIM}Vision     → ${BLU}http://127.0.0.1:8920${RST}"
echo -e "  ${DIM}Lyra Forge → ${BLU}http://127.0.0.1:8667${RST}"
echo ""
echo -e "  ${DIM}Ctrl-C to stop everything.${RST}"
echo ""

# Keep running until interrupted
wait
