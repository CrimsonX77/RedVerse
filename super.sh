#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  SUPER.SH — RedVerse One-Shot Launcher                   ║
# ║  Updated for the current Laptop repo                     ║
# ║  Auto-starts Redverse.html and backend servers           ║
# ╚══════════════════════════════════════════════════════════╝

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_ROOT/venv"
REDVERSE_HTML="$REPO_ROOT/Redverse.html"
LOG_DIR="$REPO_ROOT/logs"
MCP_LOG_DIR="$LOG_DIR/mcp"

WAIFU_ROOT="/home/crimson/Desktop/w-AI-fu!"
WAIFU_LOG_DIR="$WAIFU_ROOT/.mega_logs"
WAIFU_PID_DIR="$WAIFU_ROOT/.mega_pids"

mkdir -p "$LOG_DIR" "$MCP_LOG_DIR" 2>/dev/null || true
mkdir -p "$REPO_ROOT/launchers" 2>/dev/null || true

BACKEND_SERVERS=(
  "Main App|app.py|8800|health"
  "FastAPI API|uvicorn:server:app|8801|openapi.json"
  "Control Hall Backend|control hall/crimson_control_backend.py|8933|health"
  "Checkout Shop|checkout_server.py|8915|health"
  "MultiTool|multitool_server.py|8913|api/status"
  "QuickCam|quickcam_server.py|8910|api/status"
  "Speaker|speaker_server.py|8911|api/status"
  "LoopPad|looppad_server.py|8912|api/status"
  "AudioCutter|audiocutter_server.py|8914|api/status"
  "Vision Switchboard|vision_switchboard_server.py|8920|api/status"
  "Dragon Forge|dragon_forge_server.py|8916|api/status"
  "Dragon Cleaner|dragon_cleaner_server.py|8917|api/status"
  "Gauntlet Protocol|gauntlet_server.py|8918|api/status"
  "Void Eater|void_eater_server.py|8919|api/status"
)

# ── Extended Laptop servers (new headless wrappers + embodiment) ──────────────
EXTENDED_SERVERS=(
  "Embodiment Server|embodiment_server.py|5000|api/status"
  "Narrator Server|narrator_server.py|8930|api/status"
  "Recorder Server|recorder_server.py|8931|api/status"
  "Screen Recorder|screen_recorder_server.py|8932|api/status"
  "Consciousness Server|consciousness_server.py|7777|"
)

# ── MCP servers (SSE/HTTP mode) ───────────────────────────────────────────────
# Format: "Name|script.py|port|sse_flags"
MCP_SERVERS=(
  "Embodiment MCP|embodiment_mcp_server.py|8940|--transport sse --port 8940"
  "Room MCP|room_mcp_server.py|8941|--transport sse --port 8941"
  "Tools MCP|redverse_tools_mcp.py|8942|--transport sse --port 8942"
)

# ── w-AI-fu! ecosystem ────────────────────────────────────────────────────────
# Special health: CHECK_ONLY = don't launch, just probe
# Special script: OLLAMA  = use 'ollama serve' instead of python
WAIFU_SERVERS=(
  "Ollama|OLLAMA|11434|CHECK_ONLY"
  "Room Server|Band_Lounge/server/room_server.py|7700|api/ping"
  "Lyra Forge|Sable/lyra_forge_server.py|8667|api/status"
  "Sable Agent|Sable/agent_server.py|8088|CHECK_ONLY"
  "WS Bridge|Sable/ws_bridge.py|8765|CHECK_ONLY"
)

HTML_FILES=(

  audiocutter.html
  cart.html
  catalog.html
  clock.html
  index1.html
  index_entrance.html
  index.html
  index_waifu.html
  login.html
  looppad.html
  luna-embodiment.html
  luna-fui-v3.html
  lunas-room.html
  lyra_forge_ui.html
  media_hud.html
  multitool.html
  obelisk_gate.html
  oracle.html
  profile.html
  quickcam.html
  RedGen.html
  Redverse.html
  redverse-shop.html
  setup.html
  signin.html
  speaker.html
  support.html
  vision-app.html
  vision_app.html
  dragon-cleaner-app.html
  dragon-forge-app.html
  gauntlet-app.html
  soul-schema-loader.html
  void-eater-app.html
  waifu_club.html
  waifu_support.html
)

find_python() {
  if [ -x "$VENV_DIR/bin/python" ]; then
    echo "$VENV_DIR/bin/python"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    echo "$(command -v python)"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "$(command -v python3)"
    return
  fi
  echo ""
}

ensure_virtualenv() {
  if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    if command -v python3 >/dev/null 2>&1; then
      python3 -m venv "$VENV_DIR"
    elif command -v python >/dev/null 2>&1; then
      python -m venv "$VENV_DIR"
    else
      echo "ERROR: Python not found to create virtual environment."
      exit 1
    fi
  fi
}

find_waifu_python() {
  # Prefer w-AI-fu! .venv, then venv/, then fall back to system
  if [ -x "$WAIFU_ROOT/.venv/bin/python" ]; then
    echo "$WAIFU_ROOT/.venv/bin/python"
    return
  fi
  if [ -x "$WAIFU_ROOT/venv/bin/python" ]; then
    echo "$WAIFU_ROOT/venv/bin/python"
    return
  fi
  find_python
}

PYTHON="$(find_python)"
WAIFU_PYTHON="$(find_waifu_python)"
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python not found. Install Python 3."
  exit 1
fi
mkdir -p "$WAIFU_LOG_DIR" "$WAIFU_PID_DIR" 2>/dev/null || true

open_browser() {
  local target="$1"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$target" >/dev/null 2>&1 || true
  elif command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "$target" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$target" >/dev/null 2>&1 || true
  else
    echo "INFO: No browser opener found. Please open $target manually."
  fi
}

activate_venv() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    echo "✓ Virtual environment activated: $VENV_DIR"
    return 0
  fi
  echo "· No virtual environment found at $VENV_DIR"
  return 1
}

check_dependencies() {
  ensure_virtualenv
  PYTHON="$VENV_DIR/bin/python"
  if ! "$PYTHON" -c 'import flask, flask_cors, flask_session, uvicorn, fastapi, stripe, requests, pydub, PIL, bs4, edge_tts' >/dev/null 2>&1; then
    echo "Installing missing Python dependencies from requirements.txt..."
    "$PYTHON" -m pip install -q -r "$REPO_ROOT/requirements.txt" || {
      echo "ERROR: Dependency install failed."
      return 1
    }
  fi
  return 0
}

port_free() {
  local port="$1"
  "$PYTHON" -c 'import socket,sys
p=int(sys.argv[1])
s=socket.socket()
s.settimeout(0.2)
try:
    r=s.connect_ex(("127.0.0.1", p))
    sys.exit(0 if r else 1)
finally:
    s.close()' "$port"
  return $?
}

get_pid_on_port() {
  local port="$1"
  local pid=""
  if command -v lsof >/dev/null 2>&1; then
    pid=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $2}')
  elif command -v ss >/dev/null 2>&1; then
    pid=$(ss -ltnp "( sport = :$port )" 2>/dev/null | awk 'NR==2 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
  fi
  echo "$pid"
}

get_cmdline() {
  local pid="$1"
  if [ -z "$pid" ]; then
    echo ""
    return
  fi
  ps -p "$pid" -o args= 2>/dev/null | sed -e 's/^ *//'
}

kill_process() {
  local pid="$1"
  if [ -z "$pid" ]; then
    return
  fi
  echo "Stopping stale process PID $pid..."
  kill "$pid" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
}

verify_endpoint() {
  local port="$1"
  local path="$2"
  if [ -z "$path" ]; then
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/$path")
    if [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ]; then
      return 0
    fi
    return 1
  fi
  return 0
}

matches_expected_process() {
  local cmd="$1"
  local target="$2"
  if [[ "$target" == uvicorn:* ]]; then
    [[ "$cmd" == *uvicorn* && "$cmd" == *server:app* ]]
    return
  fi
  local expected="$(basename "$target")"
  [[ "$cmd" == *"$expected"* ]]
}

start_backend_server() {
  local name="$1"
  local target="$2"
  local port="$3"
  local health_path="$4"
  local log_file="$LOG_DIR/${name// /_}.log"
  local pid
  local cmd

  check_dependencies || return 1

  pid=$(get_pid_on_port "$port")
  if [ -n "$pid" ]; then
    cmd=$(get_cmdline "$pid")
    if matches_expected_process "$cmd" "$target"; then
      if verify_endpoint "$port" "$health_path"; then
        echo "OK: $name already running on http://127.0.0.1:$port"
        return 0
      fi
      echo "WARN: $name process on port $port is unresponsive or not healthy. Restarting."
      kill_process "$pid"
    else
      echo "WARN: port $port is used by unexpected process: $cmd"
      kill_process "$pid"
    fi
  fi

  if [[ "$target" == uvicorn:* ]]; then
    local module_app="${target#uvicorn:}"
    mkdir -p "$LOG_DIR"
    nohup "$PYTHON" -m uvicorn "$module_app" --port "$port" --reload >"$log_file" 2>&1 &
    echo "$!" >"$LOG_DIR/${name// /_}.pid"
    echo "Started $name on http://127.0.0.1:$port"
    return 0
  fi

  if [ ! -f "$REPO_ROOT/$target" ]; then
    echo "WARN: $target missing; skipping $name"
    return 1
  fi

  mkdir -p "$LOG_DIR"
  if [ "$target" = "consciousness_server.py" ]; then
    nohup "$PYTHON" "$REPO_ROOT/$target" --soul Sable_Cathedral_v5_3.yaml --port "$port" >"$log_file" 2>&1 &
  else
    nohup "$PYTHON" "$REPO_ROOT/$target" "$port" >"$log_file" 2>&1 &
  fi
  echo "$!" >"$LOG_DIR/${name// /_}.pid"
  echo "Started $name on http://127.0.0.1:$port"
  return 0
}

# ── MCP server launcher (SSE mode, Laptop venv) ───────────────────────────────
start_mcp_server() {
  local name="$1"
  local script="$2"
  local port="$3"
  local sse_flags="$4"
  local log_file="$MCP_LOG_DIR/${name// /_}.log"
  local pid cmd

  check_dependencies || return 1

  pid=$(get_pid_on_port "$port")
  if [ -n "$pid" ]; then
    cmd=$(get_cmdline "$pid")
    if [[ "$cmd" == *"$script"* ]]; then
      echo "OK: $name (MCP/SSE) already running on http://127.0.0.1:$port"
      return 0
    fi
    echo "WARN: port $port held by unexpected process: $cmd"
    kill_process "$pid"
  fi

  if [ ! -f "$REPO_ROOT/$script" ]; then
    echo "WARN: $script missing; skipping $name"
    return 1
  fi

  # shellcheck disable=SC2086
  nohup "$PYTHON" "$REPO_ROOT/$script" $sse_flags >"$log_file" 2>&1 &
  echo "$!" >"$MCP_LOG_DIR/${name// /_}.pid"
  echo "Started $name (MCP/SSE) on http://127.0.0.1:$port"
  return 0
}

# ── w-AI-fu! server launcher (WAIFU_PYTHON + WAIFU_ROOT) ─────────────────────
start_waifu_server() {
  local name="$1"
  local rel_script="$2"
  local port="$3"
  local health_path="$4"
  local log_file="$WAIFU_LOG_DIR/${name// /_}.log"
  local pid cmd

  # Port 8800 conflict guard: Laptop Main App vs waifu.com API
  if [ "$port" = "8800" ]; then
    pid=$(get_pid_on_port "8800")
    if [ -n "$pid" ]; then
      cmd=$(get_cmdline "$pid")
      if [[ "$cmd" == *"app.py"* ]]; then
        echo "WARN: $name skipped - port 8800 held by Laptop Main App (app.py)."
        return 0
      fi
    fi
  fi

  # CHECK_ONLY: just probe, don't launch
  if [ "$health_path" = "CHECK_ONLY" ]; then
    if port_free "$port" 2>/dev/null; then
      echo "· $name not detected on port $port (CHECK_ONLY — start manually if needed)"
    else
      echo "OK: $name detected on port $port"
    fi
    return 0
  fi

  # OLLAMA: use 'ollama serve'
  if [ "$rel_script" = "OLLAMA" ]; then
    if ! port_free "$port" 2>/dev/null; then
      echo "OK: Ollama already running on port $port"
      return 0
    fi
    if command -v ollama >/dev/null 2>&1; then
      nohup ollama serve >"$WAIFU_LOG_DIR/ollama.log" 2>&1 &
      echo "$!" >"$WAIFU_PID_DIR/ollama.pid"
      echo "Started Ollama on port $port"
    else
      echo "· Ollama not installed; skipping"
    fi
    return 0
  fi

  pid=$(get_pid_on_port "$port")
  if [ -n "$pid" ]; then
    cmd=$(get_cmdline "$pid")
    if [[ "$cmd" == *"$(basename "$rel_script")"* ]]; then
      if verify_endpoint "$port" "$health_path"; then
        echo "OK: $name already running on http://127.0.0.1:$port"
        return 0
      fi
      echo "WARN: $name on port $port unresponsive. Restarting."
      kill_process "$pid"
    else
      echo "WARN: port $port held by unexpected: $cmd"
      kill_process "$pid"
    fi
  fi

  local abs_script="$WAIFU_ROOT/$rel_script"
  if [ ! -f "$abs_script" ]; then
    echo "WARN: $abs_script not found; skipping $name"
    return 1
  fi

  nohup "$WAIFU_PYTHON" "$abs_script" >"$log_file" 2>&1 &
  echo "$!" >"$WAIFU_PID_DIR/${name// /_}.pid"
  echo "Started $name (w-AI-fu!) on http://127.0.0.1:$port"
  return 0
}

start_all_backends() {
  ensure_virtualenv
  PYTHON="$VENV_DIR/bin/python"
  echo "--- Laptop Core Servers ---"
  if ! check_dependencies; then
    echo "ERROR: Could not install required dependencies."
    exit 1
  fi
  activate_venv
  for service in "${BACKEND_SERVERS[@]}"; do
    IFS='|' read -r name target port health <<< "$service"
    start_backend_server "$name" "$target" "$port" "$health" || true
  done
  echo "Laptop core start commands issued."
}

start_all_extended() {
  echo
  echo "--- Extended Laptop Servers ---"
  check_dependencies || return 1
  for service in "${EXTENDED_SERVERS[@]}"; do
    IFS='|' read -r name target port health <<< "$service"
    start_backend_server "$name" "$target" "$port" "$health" || true
  done
}

start_all_mcp() {
  echo
  echo "--- MCP Services (SSE/HTTP mode) ---"
  check_dependencies || return 1
  for service in "${MCP_SERVERS[@]}"; do
    IFS='|' read -r name script port flags <<< "$service"
    start_mcp_server "$name" "$script" "$port" "$flags" || true
  done
}

start_all_waifu() {
  echo
  echo "--- w-AI-fu! Ecosystem ---"
  if [ ! -d "$WAIFU_ROOT" ]; then
    echo "WARN: w-AI-fu! root not found at $WAIFU_ROOT - skipping"
    return 0
  fi
  for service in "${WAIFU_SERVERS[@]}"; do
    IFS='|' read -r name script port health <<< "$service"
    start_waifu_server "$name" "$script" "$port" "$health" || true
  done
}

start_all() {
  start_all_backends
  start_all_extended
  start_all_mcp
  start_all_waifu
  echo
  echo "All startup commands issued."
  echo "  Laptop logs: $LOG_DIR"
  echo "  MCP logs:    $MCP_LOG_DIR"
  echo "  w-AI-fu!:    $WAIFU_LOG_DIR"
}

launch_mega_gui() {
  local gui_script="$WAIFU_ROOT/mega_server_gui.py"
  if [ ! -f "$gui_script" ]; then
    echo "WARN: mega_server_gui.py not found at $gui_script"
    return 1
  fi
  local term_cmd=""
  if command -v x-terminal-emulator >/dev/null 2>&1; then
    term_cmd="x-terminal-emulator -e"
  elif command -v gnome-terminal >/dev/null 2>&1; then
    term_cmd="gnome-terminal --"
  elif command -v xterm >/dev/null 2>&1; then
    term_cmd="xterm -e"
  fi
  if [ -z "$term_cmd" ]; then
    echo "Launching mega_server_gui.py directly (no terminal emulator found)..."
    nohup "$WAIFU_PYTHON" "$gui_script" >/dev/null 2>&1 &
    echo "mega_server_gui launched (PID $!)."
  else
    echo "Launching mega_server_gui in new terminal..."
    $term_cmd "$WAIFU_PYTHON" "$gui_script" &
    echo "mega_server_gui window opened."
  fi
}

# ── Hypervigilant shutdown ──────────────────────────────────────────────────
purge_all() {
  local mode="${1:-graceful}"  # graceful or express
  echo
  if [ "$mode" = "express" ]; then
    echo "  EXPRESS SHUTDOWN - killing all managed processes immediately..."
  else
    echo "  GRACEFUL SHUTDOWN - sending SIGTERM, then waiting 10s..."
  fi
  echo

  # Phase A: SIGTERM all managed PIDs from known PID files
  local pid_files=() termed=0 pf pid
  while IFS= read -r -d '' pf; do
    pid_files+=("$pf")
  done < <(find "$LOG_DIR" "$MCP_LOG_DIR" "$WAIFU_LOG_DIR" "$WAIFU_PID_DIR" \
    -maxdepth 1 -name "*.pid" -print0 2>/dev/null || true)
  for pf in "${pid_files[@]:-}"; do
    [ -z "$pf" ] && continue
    pid=$(cat "$pf" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      termed=$((termed + 1))
    fi
  done
  echo "  Phase A: Sent SIGTERM to $termed managed processes."

  # Phase B: Wait for clean shutdown (graceful only)
  if [ "$mode" = "graceful" ]; then
    echo -n "  Phase B: Waiting for clean shutdown"
    for i in 10 9 8 7 6 5 4 3 2 1; do
      echo -n " [$i]"
      sleep 1
    done
    echo " done."
  fi

  # Phase C: SIGKILL any survivors found by port scan
  echo
  echo "  Phase C: Port scan -> SIGKILL survivors..."
  local all_ports=(
    8800 8801 8910 8911 8912 8913 8914 8915 8916 8917 8918 8919 8920 8933
    5000 8930 8931 8932 7777
    8940 8941 8942
    7700 8088 8667 8765
  )
  local killed_ports=0
  for port in "${all_ports[@]}"; do
    pid=$(get_pid_on_port "$port")
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
      echo "    Killed PID $pid on port $port"
      killed_ports=$((killed_ports + 1))
    fi
  done
  echo "  Phase C: Killed $killed_ports port-bound survivors."

  # Phase D: pkill by script name patterns (Ollama intentionally excluded)
  echo
  echo "  Phase D: Pattern kill..."
  local patterns=(
    "embodiment_server.py" "narrator_server.py" "recorder_server.py"
    "screen_recorder_server.py" "embodiment_mcp_server.py"
    "room_mcp_server.py" "redverse_tools_mcp.py" "consciousness_server.py"
    "audiocutter_server.py" "checkout_server.py"
    "dragon_cleaner_server.py" "dragon_forge_server.py"
    "gauntlet_server.py" "looppad_server.py" "multitool_server.py"
    "quickcam_server.py" "speaker_server.py"
    "vision_switchboard_server.py" "void_eater_server.py"
    "lyra_forge_server.py" "room_server.py" "ws_bridge.py"
    "mega_server_gui.py"
  )
  local killed_patterns=0
  local pattern
  for pattern in "${patterns[@]}"; do
    if pkill -9 -f "$pattern" 2>/dev/null; then
      killed_patterns=$((killed_patterns + 1))
    fi
  done
  pkill -9 -f "uvicorn.*server:app" 2>/dev/null || true
  echo "  Phase D: Pattern-killed $killed_patterns script families."

  # Phase E: Remove PID files and temp files
  echo
  echo "  Phase E: Cleaning up PID files and temp data..."
  rm -f "$LOG_DIR"/*.pid "$MCP_LOG_DIR"/*.pid \
    "$WAIFU_LOG_DIR"/*.pid "$WAIFU_PID_DIR"/*.pid 2>/dev/null || true
  rm -f /tmp/redverse_* /tmp/super_sh_* /tmp/narrator_* /tmp/recorder_* 2>/dev/null || true
  echo "  Phase E: Cleanup complete."

  # Phase F: Final port verification
  echo
  echo "  Phase F: Final port verification..."
  local check_ports=(8800 8801 5000 8930 8931 8932 8933 7777 8940 8941 8942 7700 8088 8667)
  local all_clear=true
  echo "  +--------------------------------+"
  printf "  | %-22s | %-7s |\n" "Port" "Status"
  echo "  +--------------------------------+"
  for port in "${check_ports[@]}"; do
    if port_free "$port" 2>/dev/null; then
      printf "  | port %-4s                    | %-7s |\n" "$port" "CLEAR"
    else
      printf "  | port %-4s                    | %-7s |\n" "$port" "STILL UP"
      all_clear=false
    fi
  done
  echo "  +--------------------------------+"
  if $all_clear; then
    echo
    echo "  All managed ports are clear."
  else
    echo
    echo "  Some ports still occupied. Run: sudo lsof -i :PORT"
  fi
  echo
}

open_redverse() {
  if [ ! -f "$REDVERSE_HTML" ]; then
    echo "ERROR: Redverse.html not found at $REDVERSE_HTML"
    exit 1
  fi
  echo "Opening served Redverse at http://127.0.0.1:8800/Redverse.html"
  open_browser "http://127.0.0.1:8800/Redverse.html"
}

list_html() {
  echo "Available HTML pages:"
  local i=1
  for page in "${HTML_FILES[@]}"; do
    echo "  [$i] $page"
    i=$((i + 1))
  done
}

select_html() {
  list_html
  echo
  read -rp "Choose a page number to open: " choice
  if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
    echo "Invalid selection."
    exit 1
  fi
  if [ "$choice" -lt 1 ] || [ "$choice" -gt "${#HTML_FILES[@]}" ]; then
    echo "Selection out of range."
    exit 1
  fi
  local page="${HTML_FILES[$((choice - 1))]}"
  local target="$REPO_ROOT/$page"
  if [ ! -f "$target" ]; then
    echo "ERROR: HTML file not found: $target"
    exit 1
  fi
  echo "Opening served page http://127.0.0.1:8800/$page"
  open_browser "http://127.0.0.1:8800/$page"
}

show_help() {
  cat <<'EOF'
Usage: super.sh [command]

Commands:
  auto         Start ALL servers + open Redverse.html + enter dashboard
  server       Start ALL servers, then enter dashboard
  extended     Start extended + MCP + w-AI-fu! only (skip Laptop core)
  waifu        Start w-AI-fu! ecosystem only
  mcp          Start MCP SSE services only
  html         Select and open one of the repo HTML pages
  purge        Gracefully shut down all managed servers
  nuke         Express nuclear shutdown (immediate SIGKILL + cleanup)
  cockpit      Launch mega_server_gui (w-AI-fu! visual cockpit)
  help         Show this message

Dashboard keybinds:
  [s] Status    [o] Open page  [r] Restart server
  [m] Cockpit   [x] Graceful shutdown+exit
  [e] Express shutdown+exit    [q] Quit (servers stay up)
EOF
}

# ──────────────────────────────────────────────────────────
# PERSISTENT DASHBOARD
# ──────────────────────────────────────────────────────────

check_all_status() {
  echo
  echo "  +-------------------------------------------------------+"
  printf "  | %-53s |\n" "LAPTOP CORE SERVERS"
  echo "  +----------------------------------+------+----------+"
  printf "  | %-32s | %-4s | %-8s |\n" "Name" "Port" "Status"
  echo "  +----------------------------------+------+----------+"
  for service in "${BACKEND_SERVERS[@]}"; do
    IFS='|' read -r name target port health <<< "$service"
    local status
    if port_free "$port" 2>/dev/null; then
      status="STOPPED"
    elif verify_endpoint "$port" "$health"; then
      status="  UP   "
    else
      status=" PORT? "
    fi
    printf "  | %-32s | %-4s | %-8s |\n" "$name" "$port" "$status"
  done
  echo "  +----------------------------------+------+----------+"
  printf "  | %-53s |\n" "EXTENDED + MEDIA SERVERS"
  echo "  +----------------------------------+------+----------+"
  for service in "${EXTENDED_SERVERS[@]}"; do
    IFS='|' read -r name target port health <<< "$service"
    local status
    if port_free "$port" 2>/dev/null; then
      status="STOPPED"
    elif verify_endpoint "$port" "$health"; then
      status="  UP   "
    else
      status=" PORT? "
    fi
    printf "  | %-32s | %-4s | %-8s |\n" "$name" "$port" "$status"
  done
  echo "  +----------------------------------+------+----------+"
  printf "  | %-53s |\n" "MCP SERVICES (SSE)"
  echo "  +----------------------------------+------+----------+"
  for service in "${MCP_SERVERS[@]}"; do
    IFS='|' read -r name script port flags <<< "$service"
    local status
    if port_free "$port" 2>/dev/null; then
      status="STOPPED"
    else
      status="  UP   "
    fi
    printf "  | %-32s | %-4s | %-8s |\n" "$name" "$port" "$status"
  done
  echo "  +----------------------------------+------+----------+"
  printf "  | %-53s |\n" "W-AI-FU! ECOSYSTEM"
  echo "  +----------------------------------+------+----------+"
  for service in "${WAIFU_SERVERS[@]}"; do
    IFS='|' read -r name script port health <<< "$service"
    local status
    if port_free "$port" 2>/dev/null; then
      status="STOPPED"
    elif [ "$health" = "CHECK_ONLY" ]; then
      status="  UP   "
    elif verify_endpoint "$port" "$health"; then
      status="  UP   "
    else
      status=" PORT? "
    fi
    printf "  | %-32s | %-4s | %-8s |\n" "$name" "$port" "$status"
  done
  echo "  +----------------------------------+------+----------+"
  echo
}

restart_menu() {
  echo
  echo "  Select a server to restart:"
  local i=1
  local all_services=()
  for s in "${BACKEND_SERVERS[@]}";  do all_services+=("LAPTOP|$s"); done
  for s in "${EXTENDED_SERVERS[@]}"; do all_services+=("EXTENDED|$s"); done
  for s in "${MCP_SERVERS[@]}";      do all_services+=("MCP|$s"); done
  for s in "${WAIFU_SERVERS[@]}";    do all_services+=("WAIFU|$s"); done
  for entry in "${all_services[@]}"; do
    local tier rest name port
    IFS='|' read -r tier rest <<< "$entry"
    IFS='|' read -r name _ port _ <<< "$rest"
    echo "    [$i] [$tier] $name (port $port)"
    i=$((i + 1))
  done
  echo "    [0] Cancel"
  echo
  read -rp "  Choice: " choice
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#all_services[@]}" ]; then
    echo "  Cancelled."
    echo
    return
  fi
  local entry="${all_services[$((choice - 1))]}"
  local tier rest name script port health
  IFS='|' read -r tier rest <<< "$entry"
  IFS='|' read -r name script port health <<< "$rest"
  echo "  Restarting [$tier] $name on port $port..."
  local pid
  pid=$(get_pid_on_port "$port")
  [ -n "$pid" ] && kill_process "$pid"
  case "$tier" in
    LAPTOP|EXTENDED)
      start_backend_server "$name" "$script" "$port" "$health" && echo "  $name restarted." || true ;;
    MCP)
      start_mcp_server "$name" "$script" "$port" "$health" && echo "  $name restarted." || true ;;
    WAIFU)
      start_waifu_server "$name" "$script" "$port" "$health" && echo "  $name restarted." || true ;;
  esac
  echo
}

confirm_exit() {
  echo
  read -rp "  Are you sure you want to exit? (Servers keep running.) [y/N] " confirm
  case "$confirm" in
    y|Y|yes|YES)
      echo
      echo "  Goodbye. All servers are still running in the background."
      echo
      exit 0
      ;;
    *)
      echo "  Cancelled."
      ;;
  esac
  echo
}

interactive_loop() {
  while true; do
    echo
    echo "  +===============================================+"
    echo "  |   RedVerse Unified Launcher - Dashboard       |"
    echo "  +===============================================+"
    echo "  |  [s] Status   - all server groups             |"
    echo "  |  [o] Open     - pick a page                   |"
    echo "  |  [r] Restart  - restart a server              |"
    echo "  |  [m] Cockpit  - open mega_server_gui          |"
    echo "  |  [x] Shutdown - graceful stop + exit          |"
    echo "  |  [e] Express  - nuclear stop + exit           |"
    echo "  |  [q] Quit     - exit (servers stay up)        |"
    echo "  +===============================================+"
    read -rp "  > " cmd
    case "$cmd" in
      s|S|status)
        check_all_status ;;
      o|O|open)
        select_html ;;
      r|R|restart)
        restart_menu ;;
      m|M|cockpit)
        launch_mega_gui ;;
      x|X|shutdown)
        purge_all graceful
        exit 0 ;;
      e|E|express|nuke)
        purge_all express
        exit 0 ;;
      q|Q|quit|exit)
        confirm_exit ;;
      "")
        ;;
      *)
        echo "  Unknown command. Use s / o / r / m / x / e / q" ;;
    esac
  done
}

main() {
  echo "RedVerse Unified Launcher v2"
  echo "Laptop root:    $REPO_ROOT"
  echo "w-AI-fu! root:  $WAIFU_ROOT"
  echo "Laptop Python:  $PYTHON"
  echo "w-AI-fu! Python: $WAIFU_PYTHON"
  echo

  if [ $# -eq 0 ] || [ "$1" = "auto" ]; then
    start_all
    open_redverse
    interactive_loop
    return
  fi

  case "$1" in
    server)
      start_all
      interactive_loop ;;
    extended)
      start_all_extended
      start_all_mcp
      start_all_waifu
      interactive_loop ;;
    waifu)
      start_all_waifu
      interactive_loop ;;
    mcp)
      start_all_mcp
      interactive_loop ;;
    html)
      select_html ;;
    purge)
      purge_all graceful ;;
    nuke)
      purge_all express ;;
    cockpit)
      launch_mega_gui ;;
    help|-h|--help)
      show_help ;;
    *)
      echo "Unknown command: $1"
      show_help
      exit 1 ;;
  esac
}

main "$@"
