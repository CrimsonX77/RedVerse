#!/usr/bin/env python3
"""
OmniSensor HUD Server — Desktop HUD process manager
Starts, stops, and monitors the OmniSensor HUD subprocess.
Streams structured trace/log events for display in the web UI.

Port 8933 | Part of RedVerse Agency Scripts

Endpoints:
  GET  /omnisensor/status    — HUD running state + PID
  POST /omnisensor/start     — launch HUD subprocess
  POST /omnisensor/stop      — terminate HUD subprocess
  GET  /trace/recent         — recent trace events (?limit=N)

Usage:
  python omnisensor_server.py          # port 8933
  python omnisensor_server.py 8933     # custom port
"""

import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ── HUD process management ────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent

# Known candidate scripts for the HUD process (in priority order)
HUD_CANDIDATES = [
    BASE_DIR / "omnisensor_hud.py",
    BASE_DIR / "redverse_void_eater.py",
]

_hud_proc: subprocess.Popen | None = None
_hud_lock = threading.Lock()

# Circular buffer of trace events {ts, level, category, message}
_traces: deque = deque(maxlen=500)
_traces_lock = threading.Lock()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_trace(level: str, category: str, message: str):
    with _traces_lock:
        _traces.append({
            "ts": time.time(),
            "level": level,
            "category": category,
            "message": message,
        })


def _drain_proc_output(proc: subprocess.Popen):
    """Background thread: read stdout/stderr from HUD and store as traces."""
    try:
        for raw in proc.stdout:
            line = raw.strip() if isinstance(raw, str) else raw.decode(errors="replace").strip()
            if line:
                _add_trace("INFO", "HUD", line)
    except Exception:
        pass


def _hud_running() -> bool:
    """Return True if the HUD subprocess is alive."""
    global _hud_proc
    if _hud_proc is None:
        return False
    return _hud_proc.poll() is None


def _find_hud_script() -> Path | None:
    for candidate in HUD_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/omnisensor/status")
def hud_status():
    """Return whether the HUD process is running and its PID."""
    with _hud_lock:
        running = _hud_running()
        pid = _hud_proc.pid if running else None
    return jsonify({"running": running, "pid": pid})


@app.route("/omnisensor/start", methods=["POST"])
def hud_start():
    """Launch the OmniSensor HUD subprocess."""
    global _hud_proc
    with _hud_lock:
        if _hud_running():
            return jsonify({"status": "already_running", "pid": _hud_proc.pid})

        script = _find_hud_script()
        if script is None:
            _add_trace("WARN", "Server", "No HUD script found — start request acknowledged but no process launched")
            return jsonify({
                "status": "no_script",
                "message": "OmniSensor HUD script not found. Place omnisensor_hud.py in the RedVerse directory.",
            }), 200

        try:
            _hud_proc = subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Drain output in background
            t = threading.Thread(target=_drain_proc_output, args=(_hud_proc,), daemon=True)
            t.start()
            _add_trace("INFO", "Server", f"HUD started — PID {_hud_proc.pid} — script {script.name}")
            return jsonify({"status": "started", "pid": _hud_proc.pid})
        except Exception as exc:
            _add_trace("ERROR", "Server", f"Failed to start HUD: {exc}")
            return jsonify({"status": "error", "message": "Failed to start HUD process"}), 500


@app.route("/omnisensor/stop", methods=["POST"])
def hud_stop():
    """Terminate the OmniSensor HUD subprocess."""
    global _hud_proc
    with _hud_lock:
        if not _hud_running():
            return jsonify({"status": "not_running"})
        pid = _hud_proc.pid
        try:
            _hud_proc.terminate()
            _hud_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _hud_proc.kill()
        except Exception as exc:
            _add_trace("ERROR", "Server", f"Error stopping HUD: {exc}")
            return jsonify({"status": "error", "message": "Failed to stop HUD process"}), 500
        _hud_proc = None
        _add_trace("INFO", "Server", f"HUD stopped (was PID {pid})")
    return jsonify({"status": "stopped", "pid": pid})


@app.route("/trace/recent")
def trace_recent():
    """Return recent trace events (newest last)."""
    limit = min(int(request.args.get("limit", 100)), 500)
    with _traces_lock:
        events = list(_traces)[-limit:]
    return jsonify({"events": events})


@app.route("/api/status")
def api_status():
    """Health check."""
    with _hud_lock:
        running = _hud_running()
        pid = _hud_proc.pid if running else None
    return jsonify({
        "status": "ok",
        "server": "OmniSensor HUD Server",
        "port": 8933,
        "hud_running": running,
        "hud_pid": pid,
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _add_trace("INFO", "Server", "OmniSensor HUD Server initialised")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8933
    print(f"⚡ OmniSensor HUD Server on http://127.0.0.1:{port}")
    script = _find_hud_script()
    if script:
        print(f"   HUD script: {script}")
    else:
        print("   ⚠  No HUD script found — server will respond but cannot launch HUD")
    app.run(host="127.0.0.1", port=port, threaded=True)
