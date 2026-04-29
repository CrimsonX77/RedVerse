#!/usr/bin/env python3
"""
RedVox Transcription Server — Audio-to-text backend
Transcribes uploaded audio files using faster-whisper.
Streams live progress and completed segments via SSE.

Port 8921 | Part of RedVerse Agency Scripts

Endpoints:
  POST /api/transcribe            — upload audio, returns {"job_id": "..."}
  GET  /api/progress/<job_id>     — SSE stream with progress + segments
  GET  /api/status                — health check

Usage:
  python redvox_server.py          # port 8921
  python redvox_server.py 8921     # custom port
"""

import json
import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from queue import Empty, Queue

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

# ── Optional: faster-whisper ──────────────────────────────────────────────────
try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    WhisperModel = None
    HAS_WHISPER = False

# Per-job state: job_id -> {"status", "progress", "message", "segments", "queue", "created"}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# Remove completed jobs older than this many seconds
_JOB_TTL_SECONDS = 3600  # 1 hour

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".webm", ".mp4"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _cleanup_old_jobs():
    """Remove completed/errored jobs older than _JOB_TTL_SECONDS."""
    cutoff = time.time() - _JOB_TTL_SECONDS
    with _jobs_lock:
        to_delete = [
            jid for jid, job in _jobs.items()
            if job.get("status") in ("completed", "error")
            and job.get("created", 0) < cutoff
        ]
        for jid in to_delete:
            del _jobs[jid]


def _push(job_id: str, data: dict):
    """Push a progress update onto the job's SSE queue."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["queue"].put(data)


def _transcribe_worker(job_id: str, audio_path: str, model_size: str):
    """Background thread: transcribe audio and push SSE updates."""
    try:
        if not HAS_WHISPER:
            # Simulate transcription when faster-whisper is not installed
            _push(job_id, {"status": "running", "progress": 10,
                           "message": "faster-whisper not installed — running in demo mode"})
            time.sleep(1)
            _push(job_id, {"status": "running", "progress": 50,
                           "message": "Processing audio (demo)…",
                           "segments": ["[Demo] faster-whisper is not installed. Install it with: pip install faster-whisper"]})
            time.sleep(1)
            _push(job_id, {"status": "completed", "progress": 100,
                           "message": "Demo complete",
                           "segments": ["[Demo] faster-whisper is not installed. Install it with: pip install faster-whisper"]})
            return

        _push(job_id, {"status": "running", "progress": 5,
                       "message": f"Loading model '{model_size}'…"})

        model = WhisperModel(model_size, device="cpu", compute_type="int8")

        _push(job_id, {"status": "running", "progress": 15,
                       "message": "Transcribing…"})

        segments_text: list[str] = []
        segments_iter, info = model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
        )
        duration = info.duration or 1.0

        for seg in segments_iter:
            pct = min(95, int(15 + (seg.end / duration) * 80))
            text = seg.text.strip()
            if text:
                segments_text.append(text)
            _push(job_id, {
                "status": "running",
                "progress": pct,
                "message": f"[{seg.start:.1f}s → {seg.end:.1f}s]",
                "segments": list(segments_text),
            })

        _push(job_id, {
            "status": "completed",
            "progress": 100,
            "message": "Transcription complete",
            "segments": segments_text,
        })

    except Exception as exc:
        _push(job_id, {
            "status": "error",
            "progress": 0,
            "message": f"Error: {exc}",
        })
    finally:
        # Clean up temp file
        try:
            os.unlink(audio_path)
        except OSError:
            pass


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    """Health check."""
    return jsonify({
        "status": "ok",
        "server": "RedVox Transcription Server",
        "port": 8921,
        "whisper_available": HAS_WHISPER,
    })


@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    """Accept an audio file, start async transcription, return job_id."""
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return jsonify({"error": "No audio file provided"}), 400

    filename = secure_filename(audio_file.filename)
    if not _allowed(filename):
        return jsonify({"error": f"Unsupported format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    model_size = request.form.get("model", "small")
    valid_models = {"tiny", "base", "small", "medium", "large-v3"}
    if model_size not in valid_models:
        model_size = "small"

    # Save to temp file
    suffix = Path(filename).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    audio_file.save(tmp.name)
    tmp.close()

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "segments": [],
            "queue": Queue(),
            "created": time.time(),
        }

    # Opportunistically clean up expired jobs
    _cleanup_old_jobs()

    thread = threading.Thread(
        target=_transcribe_worker,
        args=(job_id, tmp.name, model_size),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def progress(job_id: str):
    """SSE stream for live transcription progress."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Unknown job"}), 404

    def generate():
        q: Queue = job["queue"]
        while True:
            try:
                data = q.get(timeout=30)
                # Track terminal status so cleanup can expire the job
                if data.get("status") in ("completed", "error"):
                    with _jobs_lock:
                        if job_id in _jobs:
                            _jobs[job_id]["status"] = data["status"]
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ("completed", "error"):
                    break
            except Empty:
                # Send a keepalive ping
                yield "data: {\"status\": \"running\", \"progress\": 0, \"message\": \"waiting…\"}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8921
    print(f"🩸 RedVox Transcription Server on http://127.0.0.1:{port}")
    print(f"   faster-whisper: {'✓ available' if HAS_WHISPER else '✗ not installed (demo mode)'}")
    app.run(host="127.0.0.1", port=port, threaded=True)
