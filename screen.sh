#!/usr/bin/env bash
# ╔════════════════════════════════════════════════════════════════════════╗
# ║  RED VERSE SCREEN RECORDER — One-Shot Launcher                      ║
# ║  Auto venv · Dep check/fix · Flexi-path · Copy anywhere             ║
# ║  Author: Crimson Valentine | Redverse Systems                       ║
# ║                                                                      ║
# ║  This script can live ANYWHERE on your system.                       ║
# ║  Copy/symlink it to Desktop, ~/bin, wherever — it'll still work.     ║
# ╚════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ─────────────────────────────────────────────────────────────
#  FLEXI FILE ROUTING: Find the project no matter where this lives
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

SEARCH_PATHS=(
    "$SCRIPT_DIR"
    "/home/crimson/Desktop/embodiment"
    "$HOME/Desktop/embodiment"
    "$HOME/Projects/embodiment"
    "$HOME/embodiment"
)

# Fingerprint: project must have this file
_FINGERPRINT="redverse-screen-recorder.py"

PROJECT_DIR=""
for candidate in "${SEARCH_PATHS[@]}"; do
    if [[ -f "$candidate/$_FINGERPRINT" ]]; then
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
    echo "  Looking for: $_FINGERPRINT"
    echo "  Fix: Move this script into the project, or edit SEARCH_PATHS."
    exit 1
fi

echo "  ✓ Project found: $PROJECT_DIR"
cd "$PROJECT_DIR"

# ─────────────────────────────────────────────────────────────
#  VENV: Find or create
# ─────────────────────────────────────────────────────────────

VENV_SEARCH=(
    "$PROJECT_DIR/.venv"
    "$PROJECT_DIR/venv"
)

VENV_DIR=""
for v in "${VENV_SEARCH[@]}"; do
    if [[ -f "$v/bin/python" ]]; then
        VENV_DIR="$v"
        break
    fi
done

if [[ -z "$VENV_DIR" ]]; then
    echo "  ⚠  No venv found — creating one at $PROJECT_DIR/.venv ..."
    python3 -m venv "$PROJECT_DIR/.venv"
    VENV_DIR="$PROJECT_DIR/.venv"
    echo "  ✓ venv created"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" 2>/dev/null || true
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

if ! "$PYTHON" --version &>/dev/null; then
    echo "  ✗ Python broken in venv: $VENV_DIR"
    exit 1
fi

echo "  ✓ Python: $("$PYTHON" --version 2>&1)"

# ─────────────────────────────────────────────────────────────
#  PYTHON DEPENDENCY CHECK (PyQt6 — the only pip dep needed)
# ─────────────────────────────────────────────────────────────

REQUIRED_PKGS=("PyQt6")

missing=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! "$PYTHON" -c "import ${pkg//-/_}" &>/dev/null 2>&1; then
        missing+=("$pkg")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "  ⚠  Missing Python packages: ${missing[*]}"
    echo "  → Installing..."
    "$PIP" install --quiet "${missing[@]}"
    echo "  ✓ Installed: ${missing[*]}"
else
    echo "  ✓ Python deps OK"
fi

# ─────────────────────────────────────────────────────────────
#  SYSTEM DEPENDENCY CHECK (ffmpeg, xdotool, xrandr, xwininfo)
# ─────────────────────────────────────────────────────────────

SYS_DEPS=("ffmpeg" "xdotool" "xrandr" "xwininfo")
sys_missing=()

for dep in "${SYS_DEPS[@]}"; do
    if ! command -v "$dep" &>/dev/null; then
        sys_missing+=("$dep")
    fi
done

if [[ ${#sys_missing[@]} -gt 0 ]]; then
    echo "  ⚠  Missing system packages: ${sys_missing[*]}"

    # Map tool names to apt package names
    declare -A APT_MAP=(
        [ffmpeg]="ffmpeg"
        [xdotool]="xdotool"
        [xrandr]="x11-xserver-utils"
        [xwininfo]="x11-utils"
    )

    apt_pkgs=()
    for dep in "${sys_missing[@]}"; do
        apt_pkgs+=("${APT_MAP[$dep]:-$dep}")
    done

    # De-duplicate
    apt_pkgs=($(printf '%s\n' "${apt_pkgs[@]}" | sort -u))

    echo "  → Installing system packages: ${apt_pkgs[*]}"
    echo "    (may ask for sudo password)"
    sudo apt-get update -qq && sudo apt-get install -y -qq "${apt_pkgs[@]}"
    echo "  ✓ System deps installed"
else
    echo "  ✓ System deps OK"
fi

# ─────────────────────────────────────────────────────────────
#  ENSURE OUTPUT DIRECTORY EXISTS
# ─────────────────────────────────────────────────────────────

OUTPUT_DIR="$HOME/Videos/RedVerse"
mkdir -p "$OUTPUT_DIR"

# ─────────────────────────────────────────────────────────────
#  LAUNCH
# ─────────────────────────────────────────────────────────────

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   RED VERSE SCREEN RECORDER          ║"
echo "  ║   Launching...                       ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

exec "$PYTHON" "$PROJECT_DIR/redverse-screen-recorder.py" "$@"
