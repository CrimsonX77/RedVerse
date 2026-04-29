#!/usr/bin/env bash
# ╔════════════════════════════════════════════════════════════════════════╗
# ║  LUNA EMBODIMENT SYSTEM — One-Click Launcher                        ║
# ║  Starts: HTTP Viewer → Embodiment Server → Navigator Buddy (Luna)   ║
# ║  Author: Crimson Valentine | Redverse Systems                       ║
# ║                                                                      ║
# ║  This script can live ANYWHERE on your system.                       ║
# ║  Just copy/symlink it to Desktop, ~/bin, wherever — it'll work.      ║
# ╚════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ─────────────────────────────────────────────────────────────
#  FLEXI FILE ROUTING: Find the project no matter where this script lives
# ─────────────────────────────────────────────────────────────

# Strategy 1: Hardcoded canonical path (fastest)
CANONICAL="/home/crimson/Desktop/embodiment"

# Strategy 2: Redverse mirror
REDVERSE="/home/crimson/Desktop/Redverse/Sables_Room/embodiment"

# Strategy 3: Resolve relative to this script's actual location (if script is in project)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# Strategy 4: Search common locations
SEARCH_PATHS=(
    "$CANONICAL"
    "$REDVERSE"
    "$SCRIPT_DIR"
    "$HOME/Desktop/embodiment"
    "$HOME/Projects/embodiment"
    "$HOME/embodiment"
)

PROJECT_DIR=""
for candidate in "${SEARCH_PATHS[@]}"; do
    if [[ -f "$candidate/embodiment_server.py" && -f "$candidate/navigator-buddy/navigator_buddy.py" ]]; then
        PROJECT_DIR="$candidate"
        break
    fi
done

if [[ -z "$PROJECT_DIR" ]]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ERROR: Cannot find embodiment project directory!        ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Searched:"
    for p in "${SEARCH_PATHS[@]}"; do
        echo "    ✗ $p"
    done
    echo ""
    echo "  Looking for: embodiment_server.py + navigator-buddy/navigator_buddy.py"
    echo "  Fix: Edit CANONICAL= at the top of this script."
    exit 1
fi

# ─────────────────────────────────────────────────────────────
#  FIND PYTHON VENV
# ─────────────────────────────────────────────────────────────

VENV_SEARCH=(
    "$PROJECT_DIR/.venv"
    "$PROJECT_DIR/venv"
    "$CANONICAL/.venv"
    "$REDVERSE/.venv"
)

VENV_DIR=""
for v in "${VENV_SEARCH[@]}"; do
    if [[ -f "$v/bin/python" ]]; then
        VENV_DIR="$v"
        break
    fi
done

if [[ -z "$VENV_DIR" ]]; then
    echo "  ⚠  No Python venv found. Trying system python3..."
    PYTHON="python3"
else
    PYTHON="$VENV_DIR/bin/python"
    # Activate the venv so child processes inherit the correct PATH/env
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate" 2>/dev/null || true
fi

# Verify Python works
if ! "$PYTHON" --version &>/dev/null; then
    echo "  ✗ Python not found at: $PYTHON"
    echo "  Fix: Create venv with: python3 -m venv $PROJECT_DIR/.venv"
    exit 1
fi

PYTHON_VER=$("$PYTHON" --version 2>&1)

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────

VIEWER_PORT=8000
EMBODIMENT_PORT=5000
VIEWER_URL="http://localhost:${VIEWER_PORT}/index.html"
EMBODIMENT_URL="http://localhost:${EMBODIMENT_PORT}"

# Generous timeouts (seconds)
PORT_WAIT_TIMEOUT=20       # How long to wait for a port to come up
STARTUP_SETTLE=1           # Pause between service launches
BROWSER_DELAY=2            # Wait before opening browser

# Process tracking
PIDS=()
SERVICES=()

# ─────────────────────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

log_ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
log_warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }
log_err()  { echo -e "  ${RED}✗${NC} $*"; }
log_info() { echo -e "  ${CYAN}→${NC} $*"; }
log_dim()  { echo -e "  ${DIM}$*${NC}"; }

port_in_use() {
    # Returns 0 if port is in use, 1 if free
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":$1 " && return 0
    elif command -v lsof &>/dev/null; then
        lsof -i ":$1" &>/dev/null && return 0
    elif command -v netstat &>/dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":$1 " && return 0
    else
        # Fallback: try to connect
        (echo >/dev/tcp/localhost/"$1") 2>/dev/null && return 0
    fi
    return 1
}

wait_for_port() {
    local port="$1"
    local name="$2"
    local timeout="${3:-$PORT_WAIT_TIMEOUT}"
    local elapsed=0

    while ! port_in_use "$port"; do
        sleep 0.5
        elapsed=$((elapsed + 1))
        if (( elapsed >= timeout * 2 )); then
            log_warn "${name} didn't start within ${timeout}s (port ${port})"
            return 1
        fi
    done
    return 0
}

open_browser() {
    local url="$1"
    if command -v xdg-open &>/dev/null; then
        xdg-open "$url" 2>/dev/null &
    elif command -v sensible-browser &>/dev/null; then
        sensible-browser "$url" 2>/dev/null &
    elif command -v firefox &>/dev/null; then
        firefox "$url" 2>/dev/null &
    elif command -v chromium-browser &>/dev/null; then
        chromium-browser "$url" 2>/dev/null &
    elif command -v google-chrome &>/dev/null; then
        google-chrome "$url" 2>/dev/null &
    else
        log_warn "No browser found. Open manually: $url"
    fi
}

# ─────────────────────────────────────────────────────────────
#  PRE-FLIGHT CHECKS
# ─────────────────────────────────────────────────────────────

PREFLIGHT_PASS=true
PREFLIGHT_WARNS=0

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${BOLD}Pre-Flight Checks${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# --- Check 1: Required project files ---
REQUIRED_FILES=(
    "$PROJECT_DIR/main.py"
    "$PROJECT_DIR/embodiment_server.py"
    "$PROJECT_DIR/navigator-buddy/navigator_buddy.py"
)
for rf in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$rf" ]]; then
        log_ok "Found: $(basename "$rf")"
    else
        log_err "Missing: $rf"
        PREFLIGHT_PASS=false
    fi
done

# --- Check 2: Ollama daemon ---
if command -v ollama &>/dev/null; then
    if pgrep -x "ollama" &>/dev/null || systemctl is-active --quiet ollama 2>/dev/null; then
        log_ok "Ollama daemon running"
        # Check if a model is available
        MODELS=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' || true)
        if [[ -n "$MODELS" ]]; then
            MODEL_COUNT=$(echo "$MODELS" | wc -l)
            log_ok "Ollama has $MODEL_COUNT model(s) loaded"
        else
            log_warn "Ollama running but no models found — Luna needs at least one model"
            PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1))
        fi
    else
        log_warn "Ollama installed but daemon not running — starting it..."
        ollama serve &>/dev/null &
        sleep 2
        if pgrep -x "ollama" &>/dev/null; then
            log_ok "Ollama daemon started"
        else
            log_err "Failed to start Ollama daemon"
            PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1))
        fi
    fi
else
    log_warn "Ollama not installed — Luna's AI features won't work"
    PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1))
fi

# --- Check 3: Port conflicts ---
for check_port in $VIEWER_PORT $EMBODIMENT_PORT; do
    if port_in_use "$check_port"; then
        occupant=$(lsof -ti :"$check_port" 2>/dev/null || true)
        occupant_cmd=""
        if [[ -n "$occupant" ]]; then
            occupant_cmd=$(ps -p "$occupant" -o comm= 2>/dev/null || echo "unknown")
        fi
        # Check if it's one of our own services (safe to reuse)
        case "$check_port" in
            "$VIEWER_PORT")    expected="main.py" ;;
            "$EMBODIMENT_PORT") expected="embodiment" ;;
            *)                 expected="" ;;
        esac
        if [[ -n "$expected" ]] && ps -p "$occupant" -o args= 2>/dev/null | grep -q "$expected"; then
            log_ok "Port $check_port already occupied by our service ($occupant_cmd, PID $occupant)"
        else
            log_warn "Port $check_port in use by: $occupant_cmd (PID ${occupant:-?}) — will skip or reuse"
            PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1))
        fi
    else
        log_ok "Port $check_port is free"
    fi
done

# --- Check 4: Key Python packages ---
REQUIRED_PKGS=("flask" "flask_socketio" "PyQt6")
for pkg in "${REQUIRED_PKGS[@]}"; do
    if "$PYTHON" -c "import ${pkg%%[A-Z]*}" 2>/dev/null || "$PYTHON" -c "import $pkg" 2>/dev/null; then
        log_ok "Python package: $pkg"
    else
        log_warn "Missing Python package: $pkg — install with: pip install $pkg"
        PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1))
    fi
done

# --- Check 5: Display / GUI availability ---
if [[ -n "${DISPLAY:-}" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    log_ok "Display server available (${DISPLAY:-$WAYLAND_DISPLAY})"
else
    log_err "No display server detected — Luna GUI requires X11 or Wayland"
    PREFLIGHT_PASS=false
fi

# --- Check 6: Disk space ---
AVAIL_MB=$(df -BM "$PROJECT_DIR" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'M' || echo "0")
if (( AVAIL_MB > 500 )); then
    log_ok "Disk space: ${AVAIL_MB}MB available"
elif (( AVAIL_MB > 100 )); then
    log_warn "Low disk space: ${AVAIL_MB}MB — may affect SD image generation"
    PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1))
else
    log_err "Critically low disk space: ${AVAIL_MB}MB"
    PREFLIGHT_PASS=false
fi

echo ""
if [[ "$PREFLIGHT_PASS" != true ]]; then
    log_err "Pre-flight checks FAILED — fix critical errors above before launching"
    exit 1
fi
if (( PREFLIGHT_WARNS > 0 )); then
    log_warn "Pre-flight passed with $PREFLIGHT_WARNS warning(s) — some features may be limited"
else
    log_ok "All pre-flight checks passed"
fi

# ─────────────────────────────────────────────────────────────
#  CLEANUP ON EXIT (Ctrl+C or close terminal)
# ─────────────────────────────────────────────────────────────

cleanup() {
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}Shutting down Luna Embodiment System...${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    for i in "${!PIDS[@]}"; do
        local pid="${PIDS[$i]}"
        local svc="${SERVICES[$i]:-unknown}"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            # Give it a moment to exit gracefully
            for _ in {1..10}; do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.2
            done
            # Force kill if still alive
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
                log_warn "${svc} (PID ${pid}) force-killed"
            else
                log_ok "${svc} (PID ${pid}) stopped"
            fi
        fi
    done

    # Clean up any orphaned processes on our ports
    for port in $VIEWER_PORT $EMBODIMENT_PORT; do
        if port_in_use "$port"; then
            local orphan_pid
            orphan_pid=$(lsof -ti :"$port" 2>/dev/null || true)
            if [[ -n "$orphan_pid" ]]; then
                kill "$orphan_pid" 2>/dev/null || true
                log_dim "Cleaned orphan on port $port (PID $orphan_pid)"
            fi
        fi
    done

    echo ""
    echo -e "  ${GREEN}All services stopped. See you next time.${NC}"
    echo ""
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ─────────────────────────────────────────────────────────────
#  BANNER
# ─────────────────────────────────────────────────────────────

clear 2>/dev/null || true
echo ""
echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}  ${BOLD}LUNA EMBODIMENT SYSTEM${NC} — One-Click Launcher             ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  ${DIM}Crimson Valentine | Redverse Systems${NC}                     ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${DIM}Project  :${NC} $PROJECT_DIR"
echo -e "  ${DIM}Python   :${NC} $PYTHON_VER"
echo -e "  ${DIM}Venv     :${NC} ${VENV_DIR:-system}"
echo ""
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ─────────────────────────────────────────────────────────────
#  SERVICE 1: 3D Viewer HTTP Server (main.py — port 8000)
# ─────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}[1/3] 3D Viewer HTTP Server (port ${VIEWER_PORT})${NC}"

# Kill any stale process on our port before starting
if port_in_use "$VIEWER_PORT"; then
    stale_pid=$(lsof -ti :"$VIEWER_PORT" 2>/dev/null || true)
    if [[ -n "$stale_pid" ]]; then
        # Check if it's OUR main.py or something else
        if ps -p "$stale_pid" -o args= 2>/dev/null | grep -q "main.py"; then
            log_ok "Already running on port ${VIEWER_PORT} (PID ${stale_pid}) — skipping"
            VIEWER_RUNNING=true
        else
            log_warn "Port ${VIEWER_PORT} in use by another process (PID ${stale_pid}) — skipping"
            VIEWER_RUNNING=true
        fi
    else
        log_ok "Already running on port ${VIEWER_PORT} — skipping"
        VIEWER_RUNNING=true
    fi
else
    VIEWER_RUNNING=false
fi

if [[ "$VIEWER_RUNNING" != true ]]; then
    if [[ -f "$PROJECT_DIR/main.py" ]]; then
        cd "$PROJECT_DIR"
        "$PYTHON" "$PROJECT_DIR/main.py" &>/dev/null &
        PIDS+=($!)
        SERVICES+=("Viewer-HTTP")
        log_info "Started (PID ${PIDS[-1]})"

        if wait_for_port "$VIEWER_PORT" "Viewer HTTP"; then
            log_ok "Viewer HTTP ready on port ${VIEWER_PORT}"
            VIEWER_RUNNING=true
        else
            log_warn "Viewer may still be starting — continuing anyway"
            VIEWER_RUNNING=false
        fi
    else
        log_warn "main.py not found — viewer won't be available"
        log_dim "Expected: $PROJECT_DIR/main.py"
        VIEWER_RUNNING=false
    fi
fi

sleep "$STARTUP_SETTLE"

# ─────────────────────────────────────────────────────────────
#  SERVICE 2: Embodiment Animation Server (port 5000)
# ─────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}[2/3] Embodiment Animation Server (port ${EMBODIMENT_PORT})${NC}"

# Kill any stale process on our port before starting
if port_in_use "$EMBODIMENT_PORT"; then
    stale_pid=$(lsof -ti :"$EMBODIMENT_PORT" 2>/dev/null || true)
    if [[ -n "$stale_pid" ]]; then
        if ps -p "$stale_pid" -o args= 2>/dev/null | grep -q "embodiment_server"; then
            log_ok "Already running on port ${EMBODIMENT_PORT} (PID ${stale_pid}) — skipping"
            EMBODIMENT_RUNNING=true
        else
            log_warn "Port ${EMBODIMENT_PORT} in use by another process (PID ${stale_pid}) — skipping"
            EMBODIMENT_RUNNING=true
        fi
    else
        log_ok "Already running on port ${EMBODIMENT_PORT} — skipping"
        EMBODIMENT_RUNNING=true
    fi
else
    EMBODIMENT_RUNNING=false
fi

if [[ "$EMBODIMENT_RUNNING" != true ]]; then
    if [[ -f "$PROJECT_DIR/embodiment_server.py" ]]; then
        cd "$PROJECT_DIR"
        "$PYTHON" "$PROJECT_DIR/embodiment_server.py" &>/dev/null &
        PIDS+=($!)
        SERVICES+=("Embodiment-WS")
        log_info "Started (PID ${PIDS[-1]})"

        if wait_for_port "$EMBODIMENT_PORT" "Embodiment Server"; then
            log_ok "Embodiment server ready on port ${EMBODIMENT_PORT}"
            EMBODIMENT_RUNNING=true
        else
            log_warn "Embodiment server slow to start — Luna will fallback gracefully"
            EMBODIMENT_RUNNING=false
        fi
    else
        log_warn "embodiment_server.py not found — running without embodiment"
        log_dim "Luna will still work for file navigation, just no 3D animation"
        EMBODIMENT_RUNNING=false
    fi
fi

sleep "$STARTUP_SETTLE"

# ─────────────────────────────────────────────────────────────
#  OPEN BROWSER (3D Viewer — once, after embodiment is up)
# ─────────────────────────────────────────────────────────────

if [[ "$VIEWER_RUNNING" == true ]] && [[ "$EMBODIMENT_RUNNING" == true ]]; then
    echo ""
    log_info "Opening 3D viewer in browser..."
    sleep "$BROWSER_DELAY"
    open_browser "$VIEWER_URL"
    log_ok "Browser opened: ${VIEWER_URL}"
elif [[ "$VIEWER_RUNNING" == true ]]; then
    echo ""
    log_warn "Embodiment server not ready — opening viewer anyway"
    sleep "$BROWSER_DELAY"
    open_browser "$VIEWER_URL"
    log_ok "Browser opened: ${VIEWER_URL}"
fi

# ─────────────────────────────────────────────────────────────
#  SERVICE 3: Navigator Buddy — Luna (PyQt6 GUI)
# ─────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}[3/3] Navigator Buddy — Luna (PyQt6 GUI)${NC}"

LUNA_SCRIPT="$PROJECT_DIR/navigator-buddy/navigator_buddy.py"

if [[ -f "$LUNA_SCRIPT" ]]; then
    cd "$PROJECT_DIR"

    # Check if Luna is already running
    if pgrep -f "navigator_buddy.py" &>/dev/null; then
        log_ok "Luna is already running — skipping"
        LUNA_RUNNING=true
    else
        # Set env vars Luna might need
        export EMBODIMENT_SERVER="$EMBODIMENT_URL"

        "$PYTHON" "$LUNA_SCRIPT" &
        PIDS+=($!)
        SERVICES+=("Luna-GUI")
        log_info "Started (PID ${PIDS[-1]})"

        # Give Luna a moment to initialize
        sleep 2

        if kill -0 "${PIDS[-1]}" 2>/dev/null; then
            log_ok "Luna is running"
            LUNA_RUNNING=true
        else
            log_err "Luna exited unexpectedly"
            LUNA_RUNNING=false
        fi
    fi
else
    log_err "navigator_buddy.py not found!"
    log_dim "Expected: $LUNA_SCRIPT"
    LUNA_RUNNING=false
fi

# ─────────────────────────────────────────────────────────────
#  STATUS SUMMARY
# ─────────────────────────────────────────────────────────────

echo ""
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${BOLD}System Status${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$VIEWER_RUNNING" == true ]]; then
    echo -e "  ${GREEN}●${NC} 3D Viewer         ${DIM}http://localhost:${VIEWER_PORT}${NC}"
else
    echo -e "  ${RED}●${NC} 3D Viewer         ${DIM}offline${NC}"
fi

if [[ "$EMBODIMENT_RUNNING" == true ]]; then
    echo -e "  ${GREEN}●${NC} Embodiment Server ${DIM}ws://localhost:${EMBODIMENT_PORT}${NC}"
else
    echo -e "  ${YELLOW}●${NC} Embodiment Server ${DIM}offline (Luna uses fallback)${NC}"
fi

if [[ "$LUNA_RUNNING" == true ]]; then
    echo -e "  ${GREEN}●${NC} Luna (Navigator)  ${DIM}PyQt6 GUI${NC}"
else
    echo -e "  ${RED}●${NC} Luna (Navigator)  ${DIM}failed to start${NC}"
fi

echo ""

# Count active services
ACTIVE=0
[[ "$VIEWER_RUNNING" == true ]] && ACTIVE=$((ACTIVE + 1))
[[ "$EMBODIMENT_RUNNING" == true ]] && ACTIVE=$((ACTIVE + 1))
[[ "$LUNA_RUNNING" == true ]] && ACTIVE=$((ACTIVE + 1))
TOTAL=3

if (( ACTIVE == TOTAL )); then
    echo -e "  ${GREEN}${BOLD}All systems go.${NC} Luna is ready. (${ACTIVE}/${TOTAL} services)"
elif (( ACTIVE >= 2 )); then
    echo -e "  ${YELLOW}${BOLD}Partial start.${NC} ${ACTIVE}/${TOTAL} services running."
elif (( ACTIVE >= 1 )); then
    echo -e "  ${YELLOW}${BOLD}Minimal start.${NC} ${ACTIVE}/${TOTAL} services running."
else
    echo -e "  ${RED}${BOLD}Launch failed.${NC} Check logs above."
fi

echo ""
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Press ${BOLD}Ctrl+C${NC} to shut down all services."
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ─────────────────────────────────────────────────────────────
#  KEEP ALIVE — Wait for all background processes
# ─────────────────────────────────────────────────────────────

# Wait for Luna (the main user-facing app). If Luna exits, shut everything down.
if [[ "$LUNA_RUNNING" == true ]]; then
    LUNA_PID="${PIDS[-1]}"
    wait "$LUNA_PID" 2>/dev/null || true
    echo ""
    log_info "Luna closed — shutting down remaining services..."
else
    # No Luna — just keep the servers alive until Ctrl+C
    log_info "Waiting... (Ctrl+C to stop)"
    wait
fi
