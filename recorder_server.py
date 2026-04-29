#!/usr/bin/env python3
"""
recorder_server.py — RedVerse Voice Recorder Headless HTTP API
==============================================================
Exposes audio recording and processing functions via Flask.
Zero PyQt6 imports — safe to run headlessly on a server.

Endpoints:
  GET  /api/status              — health check + capabilities
  GET  /api/devices             — list audio input devices
  POST /api/record/start        — begin recording
  POST /api/record/stop         — stop recording, save WAV
  GET  /api/record/status       — current recording state
  POST /api/export              — process and export audio file

Usage:
  python recorder_server.py           # port 8931
  python recorder_server.py 8931      # custom port
"""

import json
import logging
import os
import sys
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Optional deps ──────────────────────────────────────────────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    from scipy import signal as scipy_signal
    from scipy.io import wavfile
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

# ── Constants ──────────────────────────────────────────────────────────────────
SAMPLE_RATE = 44100
CHANNELS    = 1
DTYPE       = "float32"
CHUNK_SIZE  = 1024

CONFIG_PATH = Path.home() / ".config" / "redverse_recorder" / "config.json"

# ── Config helpers ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {
        "output_dir": str(Path.home() / "Music" / "RedVerse" / "Recordings"),
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "default_device": None,
    }

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ── Audio processing helpers (ported from redverse_recorder.py — no Qt) ────────
def normalise(audio) -> object:
    if not HAS_NUMPY:
        raise RuntimeError("numpy not installed")
    peak = np.max(np.abs(audio))
    return (audio / peak * 0.95).astype(np.float32) if peak > 0 else audio

def noise_reduce(audio, sr: int) -> object:
    if not HAS_SCIPY or not HAS_NUMPY:
        raise RuntimeError("scipy/numpy not installed")
    noise_sample = audio[:sr // 4]
    noise_profile = np.mean(np.abs(noise_sample))
    b, a = scipy_signal.butter(4, 80.0 / (sr / 2), btype="high")
    filtered = scipy_signal.filtfilt(b, a, audio).astype(np.float32)
    return filtered

def mix_music_bed(voice, sr: int, music_path: str, vol_db: float) -> object:
    if not HAS_PYDUB or not HAS_NUMPY:
        raise RuntimeError("pydub/numpy not installed")
    voice_seg = AudioSegment(
        voice.tobytes(), frame_rate=sr, sample_width=2, channels=1
    )
    music_seg = AudioSegment.from_file(music_path) + vol_db
    if len(music_seg) < len(voice_seg):
        loops = (len(voice_seg) // len(music_seg)) + 1
        music_seg = music_seg * loops
    music_seg = music_seg[:len(voice_seg)]
    mixed = voice_seg.overlay(music_seg)
    return np.frombuffer(mixed.raw_data, dtype=np.int16).astype(np.float32) / 32768.0

# ── Flask app ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("recorder-srv")

app = Flask(__name__)
CORS(app)

# ── Recording state ────────────────────────────────────────────────────────────
_sessions: dict = {}  # session_id → {state, frames, sr, path, error, start_time}
_lock = threading.Lock()

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    cfg = load_config()
    active = sum(1 for s in _sessions.values() if s.get("state") == "recording")
    return jsonify({
        "status": "ok",
        "service": "recorder_server",
        "port": PORT,
        "active_sessions": active,
        "capabilities": {
            "sounddevice": HAS_SOUNDDEVICE,
            "numpy": HAS_NUMPY,
            "scipy": HAS_SCIPY,
            "pydub": HAS_PYDUB,
        },
        "output_dir": cfg.get("output_dir"),
    })


@app.get("/api/devices")
def devices():
    if not HAS_SOUNDDEVICE:
        return jsonify({"error": "sounddevice not installed"}), 500
    try:
        devs = sd.query_devices()
        result = []
        for i, d in enumerate(devs):
            if d["max_input_channels"] > 0:
                result.append({
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                    "default_sample_rate": d["default_samplerate"],
                    "is_default": (i == sd.default.device[0]),
                })
        return jsonify({"devices": result, "count": len(result)})
    except Exception as e:
        log.exception("devices error")
        return jsonify({"error": str(e)}), 500


@app.post("/api/record/start")
def record_start():
    """
    Start recording.
    Body: {
        "device": null | int,      # device index (null = system default)
        "sample_rate": 44100,
        "channels": 1
    }
    Returns: {"session_id": "..."}
    """
    if not HAS_SOUNDDEVICE or not HAS_NUMPY:
        return jsonify({"error": "sounddevice/numpy required"}), 500

    data    = request.get_json(force=True, silent=True) or {}
    cfg     = load_config()
    device  = data.get("device", cfg.get("default_device"))
    sr      = int(data.get("sample_rate", cfg.get("sample_rate", SAMPLE_RATE)))
    chans   = int(data.get("channels", cfg.get("channels", CHANNELS)))

    session_id = str(uuid.uuid4())[:8]
    frames     = []

    def _callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    try:
        stream = sd.InputStream(
            samplerate  = sr,
            channels    = chans,
            dtype       = DTYPE,
            blocksize   = CHUNK_SIZE,
            device      = device,
            callback    = _callback,
        )
        stream.start()
        with _lock:
            _sessions[session_id] = {
                "state":      "recording",
                "frames":     frames,
                "sr":         sr,
                "channels":   chans,
                "stream":     stream,
                "path":       None,
                "error":      None,
                "start_time": time.time(),
            }
        log.info("Recording started: session=%s sr=%s device=%s", session_id, sr, device)
        return jsonify({"session_id": session_id, "status": "recording"})
    except Exception as e:
        log.exception("record/start error")
        return jsonify({"error": str(e)}), 500


@app.post("/api/record/stop")
def record_stop():
    """
    Stop recording and save WAV.
    Body: {"session_id": "..."}
    Returns: {file, duration_s, samples, sample_rate}
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

    try:
        sess["stream"].stop()
        sess["stream"].close()
        sess["state"] = "stopped"

        if not sess["frames"]:
            return jsonify({"error": "no audio captured"}), 500

        audio = np.concatenate(sess["frames"], axis=0)
        if sess["channels"] == 1:
            audio = audio[:, 0] if audio.ndim > 1 else audio

        cfg     = load_config()
        out_dir = Path(cfg.get("output_dir", str(Path.home() / "Music" / "RedVerse" / "Recordings")))
        out_dir.mkdir(parents=True, exist_ok=True)
        wav_path = str(out_dir / f"recording_{session_id}.wav")

        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(wav_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sess["sr"])
            wf.writeframes(audio_int16.tobytes())

        duration  = len(audio) / sess["sr"]
        sess["path"] = wav_path

        log.info("Recording saved: %s (%.1fs)", wav_path, duration)
        return jsonify({
            "session_id":  session_id,
            "file":        wav_path,
            "duration_s":  round(duration, 2),
            "samples":     len(audio),
            "sample_rate": sess["sr"],
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
            "session_id": session_id,
            "state":      sess["state"],
            "elapsed_s":  round(elapsed, 1),
            "file":       sess.get("path"),
            "error":      sess.get("error"),
        })
    # Summary of all sessions
    with _lock:
        summary = {
            sid: {"state": s["state"], "elapsed_s": round(time.time() - s["start_time"], 1) if s["state"] == "recording" else 0}
            for sid, s in _sessions.items()
        }
    return jsonify({"sessions": summary, "count": len(summary)})


@app.post("/api/export")
def export_audio():
    """
    Process and export an audio file.
    Body: {
        "file": "/path/to/recording.wav",          # required
        "normalize": true,
        "noise_reduce": false,
        "format": "mp3" | "wav" | "flac",
        "music_path": "/path/to/music.mp3",        # optional
        "music_vol_db": -20.0,                      # optional, default -20
        "output_name": "episode_01"                 # optional stem
    }
    Returns: {output_file, size_bytes}
    """
    if not HAS_NUMPY or not HAS_SCIPY:
        return jsonify({"error": "numpy/scipy required for processing"}), 500

    data      = request.get_json(force=True, silent=True) or {}
    src_path  = data.get("file")
    if not src_path or not Path(src_path).exists():
        return jsonify({"error": "file not found or not provided"}), 400

    fmt         = data.get("format", "mp3")
    do_normalize = bool(data.get("normalize", True))
    do_denoise   = bool(data.get("noise_reduce", False))
    music_path   = data.get("music_path")
    music_vol    = float(data.get("music_vol_db", -20.0))

    try:
        sr, audio = wavfile.read(src_path)
        audio = audio.astype(np.float32) / 32767.0

        if do_denoise:
            audio = noise_reduce(audio, sr)
        if do_normalize:
            audio = normalise(audio)
        if music_path and Path(music_path).exists():
            audio = mix_music_bed(audio, sr, music_path, music_vol)

        cfg     = load_config()
        out_dir = Path(cfg.get("output_dir", str(Path.home() / "Music" / "RedVerse" / "Recordings")))
        out_dir.mkdir(parents=True, exist_ok=True)

        stem     = data.get("output_name") or Path(src_path).stem + "_export"
        out_path = str(out_dir / f"{stem}.{fmt}")

        if fmt == "wav":
            audio_int16 = (audio * 32767).astype(np.int16)
            with wave.open(out_path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(audio_int16.tobytes())
        else:
            if not HAS_PYDUB:
                return jsonify({"error": f"pydub required for {fmt} export"}), 500
            audio_int16 = (audio * 32767).astype(np.int16)
            seg = AudioSegment(audio_int16.tobytes(), frame_rate=sr, sample_width=2, channels=1)
            seg.export(out_path, format=fmt)

        log.info("Exported: %s (%s)", out_path, fmt)
        return jsonify({"output_file": out_path, "size_bytes": os.path.getsize(out_path)})
    except Exception as e:
        log.exception("export error")
        return jsonify({"error": str(e)}), 500


# ── Entry ───────────────────────────────────────────────────────────────────────
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8931

if __name__ == "__main__":
    log.info("RedVerse Recorder API on http://0.0.0.0:%s", PORT)
    log.info("sounddevice: %s | scipy: %s | pydub: %s", HAS_SOUNDDEVICE, HAS_SCIPY, HAS_PYDUB)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
