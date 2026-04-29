#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  E-Drive Server Launcher                                    ║
# ║  Copy this script anywhere — it always finds home.          ║
# ╚══════════════════════════════════════════════════════════════╝

# ── Hardcoded project root (survives being copied anywhere) ──
EDRIVE_HOME="/home/crimson/Desktop/Redverse"

# ── Sanity check ──
if [ ! -f "$EDRIVE_HOME/serve_edrive.py" ]; then
    echo "[E-Drive] ERROR: serve_edrive.py not found at $EDRIVE_HOME"
    echo "          If you moved the project, update EDRIVE_HOME in this script."
    exit 1
fi

cd "$EDRIVE_HOME" || exit 1

# ── Activate venv if present ──
for VENV in "$EDRIVE_HOME/venv" "$EDRIVE_HOME/.venv" "$EDRIVE_HOME/env"; do
    if [ -f "$VENV/bin/activate" ]; then
        source "$VENV/bin/activate"
        break
    fi
done

# ── Launch ──
echo "[E-Drive] Starting server from $EDRIVE_HOME ..."
python3 "$EDRIVE_HOME/serve_edrive.py" "$@"
