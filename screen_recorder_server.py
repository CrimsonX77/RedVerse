#!/usr/bin/env python3
"""
screen_recorder_server.py — RedVerse Screen Recorder Headless HTTP API
=======================================================================
Exposes screen/window capture via Flask + ffmpeg subprocess.
Zero PyQt6 imports — safe to run headlessly on a server.
Reuses monitor/window detection logic from redverse-screen-recorder.py.

Endpoints:
  GET  /api/status           — health check + capabilities
  GET  /api/monitors         — list monitors + refresh rates (xrandr)
  GET  /api/windows          — list open windows (xdotool)
  POST /api/record/start     — start recording
  POST /api/record/stop      — stop recording (graceful ffmpeg shutdown)
  GET  /api/record/status    — current recording state

Usage:
  python screen_recorder_server.py        # port 8932
  python screen_recorder_server.py 8932   # custom port
"""

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("screen-rec-srv")

# ── Constants ──────────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".config" / "redverse_screen_recorder" / "config.json"
DEFAULT_OUTPUT_DIR = str(Path.home() / "Videos" / "RedVerse")

# ── Config helpers ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {
        "output_dir": DEFAULT_OUTPUT_DIR,
        "default_fps": 30.0,
        "use_nvenc": False,
        "audio_enabled": False,
        "audio_device": "default",
    }

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ── System detection (ported from redverse-screen-recorder.py — no Qt) ─────────
def get_monitors() -> list:
    monitors = []
    try:
        out = subprocess.check_output(["xrandr", "--current"], text=True, timeout=5)
        for line in out.splitlines():
            # Connected monitor with geometry e.g.: HDMI-1 connected 1920x1080+0+0
            m = re.match(
                r"(\S+)\s+connected\s+(?:primary\s+)?(\d+x\d+\+\d+\+\d+)?\s*.*",
                line,
            )
            if m and m.group(2):
                name     = m.group(1)
                geometry = m.group(2)
                # Extract available refresh rates
                rates    = []
                for rate_match in re.findall(r"(\d+\.\d+)([* ]?)", line):
                    rates.append(float(rate_match[0]))
                if not rates:
                    # parse from subsequent lines
                    rates = [60.0]
                current_rate = rates[0]
                monitors.append({
                    "name":         name,
                    "geometry":     geometry,
                    "rates":        sorted(set(rates), reverse=True),
                    "current_rate": current_rate,
                })
    except FileNotFoundError:
        log.warning("xrandr not found")
    except subprocess.TimeoutExpired:
        log.warning("xrandr timed out")
    except Exception as e:
        log.warning("Monitor detection error: %s", e)

    if not monitors:
        monitors.append({
            "name":         "default",
            "geometry":     "",
            "rates":        [60.0],
            "current_rate": 60.0,
        })
    return monitors


def get_windows() -> list:
    windows = []
    try:
        raw_ids = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--name", ""],
            text=True, stderr=subprocess.DEVNULL, timeout=5
        ).strip().split("\n")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    except Exception as e:
        log.warning("xdotool search error: %s", e)
        return []

    for win_id in raw_ids:
        win_id = win_id.strip()
        if not win_id.isdigit():
            continue
        try:
            title = subprocess.check_output(
                ["xdotool", "getwindowname", win_id],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            geo_out = subprocess.check_output(
                ["xdotool", "getwindowgeometry", win_id],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            geo = ""
            gm = re.search(r"Geometry:\s*(\d+x\d+)", geo_out)
            pm = re.search(r"Position:\s*(\d+,\d+)", geo_out)
            if gm and pm:
                w_h  = gm.group(1)
                x, y = pm.group(1).split(",")
                geo  = f"{w_h}+{x}+{y}"
            windows.append({"id": int(win_id), "title": title, "geometry": geo})
        except Exception:
            continue

    return windows


def detect_nvenc() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=5
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


# ── ffmpeg command builder ─────────────────────────────────────────────────────
def _build_ffmpeg_cmd(
    mode: str,           # "screen" | "window"
    target: str,         # geometry string or window id
    fps: float,
    output_path: str,
    use_nvenc: bool,
    audio_enabled: bool,
    audio_device: str,
) -> list:
    cmd  = ["ffmpeg", "-y"]
    disp = os.environ.get("DISPLAY", ":0")

    if mode == "screen":
        # target is geometry "WxH+X+Y" or just "WxH" (defaults offset 0+0)
        if "+" not in target and "x" in target:
            target = f"{target}+0+0"
        cmd += [
            "-f", "x11grab",
            "-framerate", str(fps),
            "-video_size", target.split("+")[0],
            "-i", f"{disp}+{'+'.join(target.split('+')[1:])}",
        ]
    elif mode == "window":
        # target is numeric window ID
        cmd += [
            "-f", "x11grab",
            "-framerate", str(fps),
            "-follow_mouse", "centered",
            "-window_id", str(target),
            "-i", disp,
        ]
    else:
        raise ValueError(f"Unknown mode: {mode}")

    if audio_enabled:
        cmd += [
            "-f", "pulse",
            "-i", audio_device,
        ]

    # Video codec
    if use_nvenc and detect_nvenc():
        cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "28"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]

    if audio_enabled:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd += ["-movflags", "+faststart", output_path]
    return cmd


# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Recording sessions ─────────────────────────────────────────────────────────
_sessions: dict = {}
_lock = threading.Lock()

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    cfg    = load_config()
    has_ff = shutil.which("ffmpeg") is not None
    active = sum(1 for s in _sessions.values() if s.get("state") == "recording")
    return jsonify({
        "status":          "ok",
        "service":         "screen_recorder_server",
        "port":            PORT,
        "active_sessions": active,
        "capabilities": {
            "ffmpeg":        has_ff,
            "nvenc":         detect_nvenc() if has_ff else False,
            "xrandr":        shutil.which("xrandr") is not None,
            "xdotool":       shutil.which("xdotool") is not None,
        },
        "output_dir": cfg.get("output_dir"),
    })


@app.get("/api/monitors")
def monitors():
    try:
        return jsonify({"monitors": get_monitors()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/windows")
def windows():
    try:
        return jsonify({"windows": get_windows()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/record/start")
def record_start():
    """
    Start screen/window recording.
    Body: {
        "mode":          "screen" | "window",   # required
        "target":        "1920x1080+0+0",       # geometry or window id
        "fps":           30.0,
        "output_path":   "/abs/path/out.mp4",   # optional, auto-generated if absent
        "use_nvenc":     false,
        "audio_enabled": false,
        "audio_device":  "default"
    }
    Returns: {session_id, output_path, pid}
    """
    if not shutil.which("ffmpeg"):
        return jsonify({"error": "ffmpeg not found on PATH"}), 500

    data   = request.get_json(force=True, silent=True) or {}
    mode   = data.get("mode", "screen")
    target = data.get("target")
    if not target:
        # auto-select first monitor geometry
        mons = get_monitors()
        target = mons[0]["geometry"] if mons and mons[0]["geometry"] else "1920x1080+0+0"

    cfg           = load_config()
    fps           = float(data.get("fps", cfg.get("default_fps", 30.0)))
    use_nvenc     = bool(data.get("use_nvenc", cfg.get("use_nvenc", False)))
    audio_enabled = bool(data.get("audio_enabled", cfg.get("audio_enabled", False)))
    audio_device  = data.get("audio_device", cfg.get("audio_device", "default"))

    out_dir = Path(data.get("output_path") or cfg.get("output_dir", DEFAULT_OUTPUT_DIR))
    out_dir = out_dir if out_dir.suffix else out_dir  # keep if it's a directory
    if out_dir.is_dir() or not out_dir.suffix:
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(out_dir / f"recording_{timestamp}.mp4")
    else:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir)

    session_id = str(uuid.uuid4())[:8]

    try:
        cmd = _build_ffmpeg_cmd(mode, target, fps, output_path, use_nvenc, audio_enabled, audio_device)
        log.info("Starting ffmpeg: %s", " ".join(cmd))

        proc = subprocess.Popen(
            cmd,
            stdout    = subprocess.PIPE,
            stderr    = subprocess.PIPE,
            stdin     = subprocess.PIPE,
            preexec_fn = os.setsid,  # new process group for clean kill
        )

        with _lock:
            _sessions[session_id] = {
                "state":       "recording",
                "proc":        proc,
                "pid":         proc.pid,
                "output_path": output_path,
                "start_time":  time.time(),
                "mode":        mode,
                "target":      target,
                "error":       None,
            }

        log.info("Recording started: session=%s pid=%s → %s", session_id, proc.pid, output_path)
        return jsonify({
            "session_id":  session_id,
            "output_path": output_path,
            "pid":         proc.pid,
            "status":      "recording",
        })
    except Exception as e:
        log.exception("record/start error")
        return jsonify({"error": str(e)}), 500


@app.post("/api/record/stop")
def record_stop():
    """
    Stop recording gracefully (sends 'q' to ffmpeg stdin).
    Body: {"session_id": "..."}
    Returns: {output_file, size_bytes, duration_s}
    """
    data       = request.get_json(force=True, silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    with _lock:
        sess = _sessions.get(session_id)
    if not sess:
        return jsonify({"error": "unknown session_id"}), 404
    if sess["state"] != "recording":
        return jsonify({"error": "not currently recording", "state": sess["state"]}), 409

    proc      = sess["proc"]
    out_path  = sess["output_path"]
    duration  = time.time() - sess["start_time"]

    try:
        # Graceful: send 'q\n' to ffmpeg stdin
        proc.stdin.write(b"q\n")
        proc.stdin.flush()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            # Force kill the entire process group
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()

        sess["state"]    = "stopped"
        size             = os.path.getsize(out_path) if os.path.exists(out_path) else 0

        log.info("Recording stopped: %s (%.1fs, %s bytes)", out_path, duration, size)
        return jsonify({
            "session_id":  session_id,
            "output_file": out_path,
            "duration_s":  round(duration, 1),
            "size_bytes":  size,
        })
    except Exception as e:
        sess["state"] = "error"
        sess["error"] = str(e)
        log.exception("record/stop error")
        return jsonify({"error": str(e)}), 500


@app.get("/api/record/status")
def record_status():
    session_id = request.args.get("session_id")
    if session_id:
        with _lock:
            sess = _sessions.get(session_id)
        if not sess:
            return jsonify({"error": "unknown session_id"}), 404
        elapsed = time.time() - sess["start_time"] if sess["state"] == "recording" else 0
        return jsonify({
            "session_id":  session_id,
            "state":       sess["state"],
            "elapsed_s":   round(elapsed, 1),
            "output_path": sess.get("output_path"),
            "pid":         sess.get("pid"),
            "error":       sess.get("error"),
        })
    # Summary
    with _lock:
        summary = {
            sid: {
                "state":     s["state"],
                "elapsed_s": round(time.time() - s["start_time"], 1) if s["state"] == "recording" else 0,
            }
            for sid, s in _sessions.items()
        }
    return jsonify({"sessions": summary, "count": len(summary)})


# ── Entry ───────────────────────────────────────────────────────────────────────
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8932

if __name__ == "__main__":
    log.info("RedVerse Screen Recorder API on http://0.0.0.0:%s", PORT)
    log.info(
        "ffmpeg: %s | nvenc: %s | xrandr: %s | xdotool: %s",
        shutil.which("ffmpeg") is not None,
        detect_nvenc(),
        shutil.which("xrandr") is not None,
        shutil.which("xdotool") is not None,
    )
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
