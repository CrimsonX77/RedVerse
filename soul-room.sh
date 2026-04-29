#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  Soul Room Launcher — Crimson Consciousness Suite
# ═══════════════════════════════════════════════════════════
#
#  Drop this anywhere (desktop, ~/bin, /usr/local/bin).
#  It auto-locates the project, checks all deps, creates the
#  venv if missing, and launches the room GUI.
#
#  USAGE:
#    ./soul-room.sh                          # Normal launch
#    ./soul-room.sh --headless               # Server only (no GUI)
#    ./soul-room.sh --backend grok           # Override backend
#    ./soul-room.sh --model grok-3           # Override model
#    ./soul-room.sh --soul /path/to.yaml     # Load a soul
#    ./soul-room.sh --port 7700              # Set server port
#    ./soul-room.sh --context '{"k":"v"}'    # Pass JSON context
#    ./soul-room.sh --verbose                # Debug logging
#
#  3RD-PARTY INTEGRATION:
#    Other apps can source or call this script and pass context:
#      SOUL_ROOM_CONTEXT='{"caller":"myapp","session":"abc123"}' ./soul-room.sh
#    Or via CLI:
#      ./soul-room.sh --context '{"caller":"myapp"}'
#
#  ENV OVERRIDES:
#    SOUL_ROOM_DIR       Project root (auto-detected if unset)
#    SOUL_ROOM_VENV      Venv path     (default: $SOUL_ROOM_DIR/venv)
#    SOUL_ROOM_PORT      Server port   (default: 7700)
#    SOUL_ROOM_BACKEND   LLM backend
#    SOUL_ROOM_MODEL     Model name
#    SOUL_ROOM_CONTEXT   JSON context string
#    SOUL_ROOM_PYTHON    Python binary (default: python3)
# ═══════════════════════════════════════════════════════════

set -euo pipefail

# ── Colours ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}[soul-room]${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}[  ✓  ]${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}[ warn]${RESET} %s\n" "$*" >&2; }
fail()  { printf "${RED}[FATAL]${RESET} %s\n" "$*" >&2; exit 1; }

# ── Locate project root ──────────────────────────────────
find_project_root() {
    # 1. Explicit env var
    if [[ -n "${SOUL_ROOM_DIR:-}" ]] && [[ -f "$SOUL_ROOM_DIR/main.py" ]]; then
        echo "$SOUL_ROOM_DIR"; return
    fi
    # 2. Same directory as this script
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$script_dir/main.py" ]]; then
        echo "$script_dir"; return
    fi
    # 3. Known fallback path
    local fallback="$HOME/Desktop/soul-room"
    if [[ -f "$fallback/main.py" ]]; then
        echo "$fallback"; return
    fi
    # 4. Search upward from cwd
    local d="$PWD"
    while [[ "$d" != "/" ]]; do
        if [[ -f "$d/main.py" ]] && [[ -d "$d/soul_room" ]]; then
            echo "$d"; return
        fi
        d="$(dirname "$d")"
    done
    fail "Cannot find soul-room project. Set SOUL_ROOM_DIR or run from the project folder."
}

PROJECT_ROOT="$(find_project_root)"
cd "$PROJECT_ROOT"
info "Project root: ${BOLD}$PROJECT_ROOT${RESET}"

# ── Python check ──────────────────────────────────────────
PYTHON="${SOUL_ROOM_PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    # Try common alternatives
    for candidate in python3.12 python3.11 python3.10 python; do
        if command -v "$candidate" &>/dev/null; then
            PYTHON="$candidate"; break
        fi
    done
fi
command -v "$PYTHON" &>/dev/null || fail "Python 3.10+ required but not found."

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
if (( PY_MAJOR < 3 || PY_MINOR < 10 )); then
    fail "Python ≥ 3.10 required (found $PY_VER)."
fi
ok "Python $PY_VER ($PYTHON)"

# ── Venv ──────────────────────────────────────────────────
VENV="${SOUL_ROOM_VENV:-$PROJECT_ROOT/venv}"
if [[ ! -d "$VENV" ]]; then
    info "Creating virtual environment at $VENV …"
    "$PYTHON" -m venv "$VENV"
    ok "Venv created"
fi
# Activate
# shellcheck disable=SC1091
source "$VENV/bin/activate"
ok "Venv active: $(which python)"

# ── Dependencies ──────────────────────────────────────────
check_deps() {
    local missing=0
    while IFS= read -r pkg; do
        # Strip comments, version specs, whitespace
        pkg="$(echo "$pkg" | sed 's/#.*//' | sed 's/[<>=!].*//' | xargs)"
        [[ -z "$pkg" ]] && continue
        # Normalise: PyQt6-Qt6 → pyqt6_qt6 (pip's canonical form)
        local norm
        norm="$(echo "$pkg" | tr '[:upper:]' '[:lower:]' | tr '-' '_')"
        if ! python -c "import importlib; importlib.import_module('${norm%%_*}')" &>/dev/null 2>&1; then
            # Fallback: pip show (handles packages whose import name differs)
            if ! pip show "$pkg" &>/dev/null 2>&1; then
                missing=1; break
            fi
        fi
    done < "$PROJECT_ROOT/requirements.txt"
    return $missing
}

if ! check_deps; then
    info "Installing dependencies …"
    pip install --quiet --upgrade pip
    pip install --quiet -r "$PROJECT_ROOT/requirements.txt"
    ok "Dependencies installed"
else
    ok "Dependencies satisfied"
fi

# ── Verify critical imports ───────────────────────────────
python -c "
from soul_room.server.conversation_db import ConversationDB
from soul_room.server.media_db import MediaDB
from soul_room.engine.chat_engine import ChatEngine
from soul_room.connector import RoomConnector
" 2>/dev/null || {
    warn "Core imports failed — reinstalling deps"
    pip install --quiet -r "$PROJECT_ROOT/requirements.txt"
}

# ── Check Ollama (non-fatal) ─────────────────────────────
if command -v ollama &>/dev/null; then
    if curl -sf http://127.0.0.1:11434/api/tags &>/dev/null; then
        MODEL_COUNT=$(curl -sf http://127.0.0.1:11434/api/tags | python -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo 0)
        ok "Ollama running ($MODEL_COUNT models)"
    else
        warn "Ollama installed but not running — local models unavailable"
    fi
else
    warn "Ollama not installed — only API backends (grok/openai/anthropic) available"
fi

# ── Build CLI args from env overrides ─────────────────────
EXTRA_ARGS=()

[[ -n "${SOUL_ROOM_PORT:-}" ]]    && EXTRA_ARGS+=(--port "$SOUL_ROOM_PORT")
[[ -n "${SOUL_ROOM_BACKEND:-}" ]] && EXTRA_ARGS+=(--backend "$SOUL_ROOM_BACKEND")
[[ -n "${SOUL_ROOM_MODEL:-}" ]]   && EXTRA_ARGS+=(--model "$SOUL_ROOM_MODEL")
[[ -n "${SOUL_ROOM_CONTEXT:-}" ]] && EXTRA_ARGS+=(--context "$SOUL_ROOM_CONTEXT")

# ── Launch ────────────────────────────────────────────────
info "Launching Soul Room …"
echo ""
exec python "$PROJECT_ROOT/main.py" "${EXTRA_ARGS[@]}" "$@"
