#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  Oracle.sh — Smart Launcher for ORACLE Workbench               ║
# ║  Portable • Duplicatable • Self-Resolving • Async Preload      ║
# ║  Copy this anywhere — desktop, USB, another dir — it still     ║
# ║  finds home. Call from cron, .desktop files, other scripts.     ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# USAGE:
#   ./Oracle.sh                      Launch workbench (default)
#   ./Oracle.sh --check              Verify environment only
#   ./Oracle.sh --trace              Launch with full trace logging
#   ./Oracle.sh --meta '{"k":"v"}'   Forward metadata JSON to workbench
#   ./Oracle.sh --tool gauntlet      Launch a specific tool instead
#   ./Oracle.sh --dry-run            Validate everything, don't launch
#   ./Oracle.sh --repair             Recreate venv and reinstall deps
#   ./Oracle.sh --help               Show help
#
# CALLABLE API (source from other scripts):
#   source /path/to/Oracle.sh --lib
#   oracle_root          → prints resolved ORACLE root
#   oracle_python        → prints resolved python path
#   oracle_launch <args> → launches workbench with args
#
set -uo pipefail

# ─── Constants ──────────────────────────────────────────────────
readonly ORACLE_VERSION="1.0.0"
readonly MAIN_SCRIPT="Workbench/Prime/oracle_workbench.py"
readonly MARKER_FILES=("Agentfile" "requirements.txt" "Workbench/Prime/oracle_workbench.py")
readonly VENV_CANDIDATES=("venv" ".venv" "env")
readonly CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/oracle_workbench"
readonly CACHE_FILE="$CONFIG_HOME/oracle_root_cache"
readonly LOG_DIR="$CONFIG_HOME/logs"
readonly CORE_DEPS=("PyQt6" "psutil")

# ─── Runtime State ──────────────────────────────────────────────
ORACLE_ROOT=""
ORACLE_VENV=""
ORACLE_PYTHON=""
_TRACE=0
_VERBOSE=0
_DRY_RUN=0
_CHECK_ONLY=0
_REPAIR=0
_LIB_MODE=0
_FORWARD_META=""
_LAUNCH_TOOL=""
_EXTRA_ARGS=()
_LOG_FILE=""
_PRELOAD_PIDS=()

# ─── Colors (auto-disabled if not a terminal) ──────────────────
if [[ -t 1 ]]; then
    C_RED='\033[0;31m'    C_GREEN='\033[0;32m'  C_YELLOW='\033[0;33m'
    C_BLUE='\033[0;34m'   C_MAGENTA='\033[0;35m' C_CYAN='\033[0;36m'
    C_BOLD='\033[1m'      C_DIM='\033[2m'        C_RESET='\033[0m'
else
    C_RED='' C_GREEN='' C_YELLOW='' C_BLUE='' C_MAGENTA='' C_CYAN=''
    C_BOLD='' C_DIM='' C_RESET=''
fi

# ─── Logging & Tracing ─────────────────────────────────────────
_ensure_log_dir() {
    mkdir -p "$LOG_DIR" 2>/dev/null || true
    _LOG_FILE="$LOG_DIR/oracle_$(date +%Y%m%d_%H%M%S).log"
}

_log() {
    local level="$1"; shift
    local ts
    ts="$(date '+%H:%M:%S.%3N')"
    local msg="[$ts] [$level] $*"

    # Always write to log file if tracing
    if (( _TRACE )) && [[ -n "$_LOG_FILE" ]]; then
        echo "$msg" >> "$_LOG_FILE" 2>/dev/null
    fi

    # Print to terminal based on verbosity
    case "$level" in
        ERROR)   echo -e "${C_RED}${C_BOLD}✕ $*${C_RESET}" >&2 ;;
        WARN)    echo -e "${C_YELLOW}⚠ $*${C_RESET}" >&2 ;;
        OK)      echo -e "${C_GREEN}✓ $*${C_RESET}" ;;
        INFO)    (( _VERBOSE || _TRACE )) && echo -e "${C_CYAN}▸ $*${C_RESET}" ;;
        TRACE)   (( _TRACE )) && echo -e "${C_DIM}  · $*${C_RESET}" ;;
        BANNER)  echo -e "${C_MAGENTA}${C_BOLD}$*${C_RESET}" ;;
    esac
}

_die() { _log ERROR "$@"; exit 1; }

# ─── Cleanup ────────────────────────────────────────────────────
_cleanup() {
    # Kill any background preload jobs
    for pid in "${_PRELOAD_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
}
trap _cleanup EXIT

# ─── Argument Parsing ──────────────────────────────────────────
_parse_args() {
    while (( $# )); do
        case "$1" in
            --trace)       _TRACE=1; _VERBOSE=1 ;;
            --verbose|-v)  _VERBOSE=1 ;;
            --dry-run)     _DRY_RUN=1; _VERBOSE=1 ;;
            --check)       _CHECK_ONLY=1; _VERBOSE=1 ;;
            --repair)      _REPAIR=1; _VERBOSE=1 ;;
            --lib)         _LIB_MODE=1 ;;
            --meta)
                shift
                [[ $# -gt 0 ]] || _die "--meta requires a JSON string argument"
                _FORWARD_META="$1"
                ;;
            --tool)
                shift
                [[ $# -gt 0 ]] || _die "--tool requires a tool name"
                _LAUNCH_TOOL="$1"
                ;;
            --help|-h)     _show_help; exit 0 ;;
            --)            shift; _EXTRA_ARGS+=("$@"); break ;;
            -*)            _die "Unknown option: $1 (try --help)" ;;
            *)             _EXTRA_ARGS+=("$1") ;;
        esac
        shift
    done
}

_show_help() {
    cat <<'EOF'
╔══════════════════════════════════════════════════════════════╗
║  Oracle.sh — ORACLE Workbench Launcher                     ║
╚══════════════════════════════════════════════════════════════╝

USAGE:
  ./Oracle.sh [OPTIONS] [-- extra_python_args...]

OPTIONS:
  --check          Verify environment, venv, and deps only
  --trace          Full trace logging (writes to ~/.config/oracle_workbench/logs/)
  --verbose, -v    Verbose stdout output
  --dry-run        Validate everything but don't launch
  --repair         Recreate venv and reinstall all dependencies
  --meta <json>    Forward JSON metadata to workbench via env var
  --tool <name>    Launch a specific tool (gauntlet, omnisensor, scribe, etc.)
  --lib            Library mode — source this script, don't execute
  --help, -h       Show this help

CALLABLE API (for other scripts):
  source /path/to/Oracle.sh --lib
  oracle_root              → resolved ORACLE project root
  oracle_python            → resolved Python interpreter path
  oracle_launch [args]     → launch workbench with optional args

ENVIRONMENT VARIABLES:
  ORACLE_ROOT              Override auto-detected project root
  ORACLE_META              JSON metadata (same as --meta)
  ORACLE_TRACE=1           Enable tracing (same as --trace)

EXAMPLES:
  ./Oracle.sh                           # Normal launch
  ./Oracle.sh --trace --meta '{"mode":"debug"}'
  ./Oracle.sh --tool gauntlet           # Launch gauntlet directly
  ./Oracle.sh --check                   # Just verify environment
  cp Oracle.sh ~/Desktop/ && ~/Desktop/Oracle.sh   # Works from copy
EOF
}

# ═══════════════════════════════════════════════════════════════
#  PHASE 1: ROOT DISCOVERY
#  Find ORACLE root from anywhere — script dir, cache, or search
# ═══════════════════════════════════════════════════════════════

_is_oracle_root() {
    local dir="$1"
    for marker in "${MARKER_FILES[@]}"; do
        [[ -f "$dir/$marker" ]] || return 1
    done
    return 0
}

_find_oracle_root() {
    _log TRACE "Resolving ORACLE root..."

    # 0. Env override
    if [[ -n "${ORACLE_ROOT:-}" ]] && _is_oracle_root "$ORACLE_ROOT"; then
        _log TRACE "Root from ORACLE_ROOT env: $ORACLE_ROOT"
        echo "$ORACLE_ROOT"
        return 0
    fi

    # 1. Relative to this script's real location (handles symlinks)
    local script_real
    script_real="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # If this script was a copy, BASH_SOURCE gives the copy's dir — that's fine,
    # we just need to check if the ORACLE tree is there or walk up.
    _log TRACE "Script directory: $script_real"

    if _is_oracle_root "$script_real"; then
        echo "$script_real"
        return 0
    fi

    # Walk up from script dir (handles being inside Workbench/Prime/ etc.)
    local walk="$script_real"
    for _ in {1..6}; do
        walk="$(dirname "$walk")"
        if _is_oracle_root "$walk"; then
            _log TRACE "Found root walking up: $walk"
            echo "$walk"
            return 0
        fi
    done

    # 2. Cached root from last successful run
    if [[ -f "$CACHE_FILE" ]]; then
        local cached
        cached="$(cat "$CACHE_FILE" 2>/dev/null)"
        if [[ -n "$cached" ]] && _is_oracle_root "$cached"; then
            _log TRACE "Root from cache: $cached"
            echo "$cached"
            return 0
        fi
        _log WARN "Cached root is stale, ignoring"
    fi

    # 3. Search common locations
    local search_dirs=(
        "$HOME/Desktop/ORACLE"
        "$HOME/ORACLE"
        "$HOME/Projects/ORACLE"
        "$HOME/dev/ORACLE"
        "/opt/ORACLE"
    )
    for candidate in "${search_dirs[@]}"; do
        if _is_oracle_root "$candidate"; then
            _log TRACE "Root from search: $candidate"
            echo "$candidate"
            return 0
        fi
    done

    # 4. Last resort: find command (bounded, fast)
    _log TRACE "Searching filesystem (bounded)..."
    local found
    found="$(find "$HOME" -maxdepth 4 -name "oracle_workbench.py" -path "*/Workbench/Prime/*" -print -quit 2>/dev/null)"
    if [[ -n "$found" ]]; then
        local dir
        dir="$(dirname "$(dirname "$(dirname "$found")")")"
        if _is_oracle_root "$dir"; then
            _log TRACE "Root from find: $dir"
            echo "$dir"
            return 0
        fi
    fi

    return 1
}

_cache_root() {
    mkdir -p "$(dirname "$CACHE_FILE")" 2>/dev/null || true
    echo "$1" > "$CACHE_FILE" 2>/dev/null || true
    _log TRACE "Cached root → $1"
}

# ═══════════════════════════════════════════════════════════════
#  PHASE 2: VENV & PYTHON RESOLUTION
# ═══════════════════════════════════════════════════════════════

_find_venv() {
    local root="$1"
    for name in "${VENV_CANDIDATES[@]}"; do
        local vpath="$root/$name"
        if [[ -f "$vpath/bin/activate" ]]; then
            _log TRACE "Found venv: $vpath"
            echo "$vpath"
            return 0
        fi
    done
    return 1
}

_create_venv() {
    local root="$1"
    local vpath="$root/venv"
    _log INFO "Creating virtual environment at $vpath..."
    python3 -m venv "$vpath" || _die "Failed to create venv"
    echo "$vpath"
}

_resolve_python() {
    local root="$1"

    # Try to find existing venv
    if ORACLE_VENV="$(_find_venv "$root")"; then
        ORACLE_PYTHON="$ORACLE_VENV/bin/python"
        _log TRACE "Python from venv: $ORACLE_PYTHON"
        return 0
    fi

    # No venv found — create one (unless dry-run/check)
    if (( _DRY_RUN || _CHECK_ONLY )); then
        _log WARN "No venv found — would create one on real run"
        ORACLE_PYTHON="$(command -v python3)"
        return 0
    fi

    _log WARN "No virtual environment found"
    ORACLE_VENV="$(_create_venv "$root")"
    ORACLE_PYTHON="$ORACLE_VENV/bin/python"
    _log OK "Created venv at $ORACLE_VENV"
}

# ═══════════════════════════════════════════════════════════════
#  PHASE 3: DEPENDENCY CHECKING (async-capable)
# ═══════════════════════════════════════════════════════════════

_check_dep() {
    # Check a single Python package — used as background job
    local python="$1" pkg="$2"
    "$python" -c "import importlib; importlib.import_module('${pkg%%[>=<]*}')" 2>/dev/null
}

_check_all_deps() {
    local python="$1" root="$2"
    local missing=()

    _log INFO "Checking core dependencies..."

    # Fire off checks in parallel
    local pids=() pkgs=()
    for dep in "${CORE_DEPS[@]}"; do
        _check_dep "$python" "$dep" &
        pids+=($!)
        pkgs+=("$dep")
    done

    # Collect results
    for i in "${!pids[@]}"; do
        if ! wait "${pids[$i]}"; then
            missing+=("${pkgs[$i]}")
            _log TRACE "Missing: ${pkgs[$i]}"
        else
            _log TRACE "Found: ${pkgs[$i]}"
        fi
    done

    if (( ${#missing[@]} == 0 )); then
        _log OK "All core dependencies satisfied"
        return 0
    fi

    _log WARN "Missing dependencies: ${missing[*]}"
    return 1
}

_install_deps() {
    local python="$1" root="$2"
    local req_file="$root/requirements.txt"

    if [[ ! -f "$req_file" ]]; then
        _log WARN "No requirements.txt found — installing core deps only"
        "$python" -m pip install --quiet "${CORE_DEPS[@]}" || _die "Dependency install failed"
        return
    fi

    _log INFO "Installing from requirements.txt..."
    "$python" -m pip install --quiet -r "$req_file" 2>&1 | while IFS= read -r line; do
        _log TRACE "pip: $line"
    done

    if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
        _log WARN "Some packages may have failed — trying core deps individually"
        for dep in "${CORE_DEPS[@]}"; do
            "$python" -m pip install --quiet "$dep" 2>/dev/null || true
        done
    fi

    _log OK "Dependencies installed"
}

# ═══════════════════════════════════════════════════════════════
#  PHASE 4: ASYNC PRELOADING
#  Pre-warm things in parallel while we finish other checks
# ═══════════════════════════════════════════════════════════════

_preload_start() {
    local python="$1" root="$2"
    _log TRACE "Starting async preloads..."

    # Pre-import heavy modules so they're in disk cache
    "$python" -c "
import sys
try:
    import PyQt6.QtWidgets
    import PyQt6.QtCore
except: pass
try:
    import psutil
except: pass
" &>/dev/null &
    _PRELOAD_PIDS+=($!)

    # Pre-warm filesystem cache for key directories
    find "$root/Workbench/Prime" -name "*.py" -type f -exec cat {} + > /dev/null 2>&1 &
    _PRELOAD_PIDS+=($!)
}

_preload_wait() {
    for pid in "${_PRELOAD_PIDS[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    _PRELOAD_PIDS=()
    _log TRACE "Preloads complete"
}

# ═══════════════════════════════════════════════════════════════
#  PHASE 5: LAUNCH
# ═══════════════════════════════════════════════════════════════

_resolve_tool_script() {
    local root="$1" tool="$2"
    local candidates=()

    case "$tool" in
        gauntlet)          candidates=("$root/gauntlet.py") ;;
        omnisensor|hud)    candidates=("$root/omnisensor_hud_v2.py") ;;
        scribe)            candidates=("$root/Workbench/Prime/scribe.py") ;;
        speaker)           candidates=("$root/Workbench/Prime/speaker.py") ;;
        sigrow)            candidates=("$root/Workbench/Prime/sigrow.py") ;;
        navigator*)        candidates=("$root/navigator_buddy.py" "$root/Workbench/navigator_buddy.py") ;;
        sanctum)           candidates=("$root/Workbench/Sanctum/sanctum.py") ;;
        quickcam)          candidates=("$root/Workbench/quickcam.py") ;;
        glass*|fang)       candidates=("$root/Workbench/Prime/webtools/glass_fang.py") ;;
        parallax)          candidates=("$root/Workbench/Prime/webtools/parallax_qt6_interface.py") ;;
        manga*)            candidates=("$root/Workbench/Prime/webtools/manga_scraper_gui.py") ;;
        vision*)           candidates=("$root/Workbench/vision_switchboard_tab.py") ;;
        *)
            # Generic: search common locations
            candidates=(
                "$root/$tool.py"
                "$root/Workbench/$tool.py"
                "$root/Workbench/Prime/$tool.py"
                "$root/Workbench/Prime/webtools/$tool.py"
                "$root/Workbench/Sanctum/$tool.py"
            )
            ;;
    esac

    for c in "${candidates[@]}"; do
        if [[ -f "$c" ]]; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

_build_env() {
    local root="$1"
    # Set environment variables the workbench can read
    export ORACLE_ROOT="$root"
    export ORACLE_LAUNCHER_VERSION="$ORACLE_VERSION"
    export ORACLE_LAUNCHED_AT="$(date -Iseconds)"
    export ORACLE_LAUNCHED_BY="${BASH_SOURCE[0]}"

    if [[ -n "$_FORWARD_META" ]]; then
        export ORACLE_META="$_FORWARD_META"
    elif [[ -n "${ORACLE_META:-}" ]]; then
        export ORACLE_META
    fi

    if (( _TRACE )); then
        export ORACLE_TRACE="1"
        export ORACLE_LOG="$_LOG_FILE"
    fi
}

_launch() {
    local python="$1" script="$2"
    shift 2

    _log INFO "Launching: $script"
    _log TRACE "Python: $python"
    _log TRACE "Args: $*"

    if (( _DRY_RUN )); then
        _log OK "[DRY RUN] Would execute: $python $script $*"
        return 0
    fi

    # Wait for preloads to finish
    _preload_wait

    exec "$python" "$script" "$@"
}

# ═══════════════════════════════════════════════════════════════
#  REPAIR MODE
# ═══════════════════════════════════════════════════════════════

_repair() {
    local root="$1"
    _log BANNER "🔧 ORACLE Repair Mode"

    # Remove existing venv
    for name in "${VENV_CANDIDATES[@]}"; do
        local vpath="$root/$name"
        if [[ -d "$vpath" ]]; then
            _log INFO "Removing old venv: $vpath"
            rm -rf "$vpath"
        fi
    done

    # Create fresh venv
    ORACLE_VENV="$(_create_venv "$root")"
    ORACLE_PYTHON="$ORACLE_VENV/bin/python"
    _log OK "Fresh venv created"

    # Upgrade pip
    "$ORACLE_PYTHON" -m pip install --quiet --upgrade pip 2>/dev/null || true

    # Install deps
    _install_deps "$ORACLE_PYTHON" "$root"

    _log OK "Repair complete"
}

# ═══════════════════════════════════════════════════════════════
#  CALLABLE API (when sourced with --lib)
# ═══════════════════════════════════════════════════════════════

oracle_root() {
    if [[ -z "$ORACLE_ROOT" ]]; then
        ORACLE_ROOT="$(_find_oracle_root)" || { echo "ERROR: Cannot find ORACLE root" >&2; return 1; }
    fi
    echo "$ORACLE_ROOT"
}

oracle_python() {
    if [[ -z "$ORACLE_PYTHON" ]]; then
        local root
        root="$(oracle_root)" || return 1
        _resolve_python "$root"
    fi
    echo "$ORACLE_PYTHON"
}

oracle_launch() {
    local root python
    root="$(oracle_root)" || return 1
    python="$(oracle_python)" || return 1
    _build_env "$root"
    "$python" "$root/$MAIN_SCRIPT" "$@"
}

# ═══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

_main() {
    _parse_args "$@"

    # Lib mode: just define functions, don't execute
    if (( _LIB_MODE )); then
        return 0
    fi

    # Honor env-based trace
    if [[ "${ORACLE_TRACE:-}" == "1" ]]; then
        _TRACE=1; _VERBOSE=1
    fi

    # Setup logging
    if (( _TRACE )); then
        _ensure_log_dir
        _log TRACE "Oracle.sh v$ORACLE_VERSION — trace session started"
        _log TRACE "PID: $$ | User: $(whoami) | Host: $(hostname)"
        _log TRACE "Invoked as: ${BASH_SOURCE[0]} $*"
    fi

    _log BANNER "🔮 ORACLE Workbench Launcher v$ORACLE_VERSION"

    # ── Phase 1: Find root ──
    _log INFO "Resolving project root..."
    ORACLE_ROOT="$(_find_oracle_root)" || _die \
        "Cannot find ORACLE project root. Set ORACLE_ROOT env or run from the project directory."
    _cache_root "$ORACLE_ROOT"
    _log OK "Root: $ORACLE_ROOT"

    # ── Phase 2: Repair mode (early exit) ──
    if (( _REPAIR )); then
        _repair "$ORACLE_ROOT"
        exit 0
    fi

    # ── Phase 3: Resolve Python/venv ──
    _log INFO "Resolving Python environment..."
    _resolve_python "$ORACLE_ROOT"
    _log OK "Python: $ORACLE_PYTHON"

    # ── Phase 4: Async preload (fire and forget while we check deps) ──
    if (( ! _CHECK_ONLY && ! _DRY_RUN )); then
        _preload_start "$ORACLE_PYTHON" "$ORACLE_ROOT"
    fi

    # ── Phase 5: Dependency check ──
    if ! _check_all_deps "$ORACLE_PYTHON" "$ORACLE_ROOT"; then
        if (( _CHECK_ONLY || _DRY_RUN )); then
            _log WARN "Dependencies incomplete — run without --check/--dry-run to auto-install"
        else
            _install_deps "$ORACLE_PYTHON" "$ORACLE_ROOT"
            # Re-verify
            _check_all_deps "$ORACLE_PYTHON" "$ORACLE_ROOT" || \
                _log WARN "Some deps still missing — workbench may have limited functionality"
        fi
    fi

    # ── Phase 6: Check-only exit ──
    if (( _CHECK_ONLY )); then
        _log BANNER "✅ Environment check complete"
        echo ""
        echo "  Root:   $ORACLE_ROOT"
        echo "  Python: $ORACLE_PYTHON"
        echo "  Venv:   ${ORACLE_VENV:-system}"
        if (( _TRACE )); then
            echo "  Log:    $_LOG_FILE"
        fi
        exit 0
    fi

    # ── Phase 7: Build environment & launch ──
    _build_env "$ORACLE_ROOT"

    local target_script
    if [[ -n "$_LAUNCH_TOOL" ]]; then
        target_script="$(_resolve_tool_script "$ORACLE_ROOT" "$_LAUNCH_TOOL")" || \
            _die "Tool not found: $_LAUNCH_TOOL"
        _log INFO "Tool mode: $_LAUNCH_TOOL → $target_script"
    else
        target_script="$ORACLE_ROOT/$MAIN_SCRIPT"
    fi

    [[ -f "$target_script" ]] || _die "Target script missing: $target_script"

    _launch "$ORACLE_PYTHON" "$target_script" "${_EXTRA_ARGS[@]}"
}

# Only run main if not being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
elif (( _LIB_MODE )); then
    # Sourced in lib mode — parse args to set _LIB_MODE and return
    _parse_args "$@"
fi
