#!/usr/bin/env python3
"""
narrator_server.py — RedVerse Narrator Headless HTTP API
=========================================================
Exposes RedVerse Narrator's pure TTS/detection functions via Flask.
Zero PyQt6 imports — safe to run headlessly on a server.

Endpoints:
  GET  /api/status            — health check
  GET  /api/voices            — list default Edge-TTS voices
  GET  /api/config            — get current narrator config
  POST /api/config            — update narrator config
  POST /api/detect            — parse text into speaker segments
  POST /api/tts/segment       — render a single text segment to MP3
  POST /api/narrate           — full pipeline: detect + render + combine

Usage:
  python narrator_server.py             # port 8930
  python narrator_server.py 8931        # custom port
"""

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Optional deps (same guarded pattern as redverse_narrator.py) ──────────────
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Constants (ported from redverse_narrator.py — no Qt) ─────────────────────
CONFIG_PATH = Path.home() / ".config" / "redverse_narrator" / "config.json"
SERVICE_ID  = "redverse_narrator"

DEFAULT_EDGE_VOICES = [
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
    "en-US-AriaNeural",
    "en-US-DavisNeural",
    "en-US-AmberNeural",
    "en-US-TonyNeural",
]

PARSE_PROMPT = """You are a literary dialogue parser. Given prose text, split it into segments.
Each segment has a "speaker" (character name or "Narrator") and "text" (what gets spoken aloud).

Rules:
- Narration, description, action = speaker "Narrator"
- Quoted speech = speaker is whoever is speaking
- If speaker is implied by context (e.g. previous attribution) use that name
- Split at natural speaking boundaries
- Return ONLY valid JSON array, no markdown, no explanation

Known characters: {characters}

Example output:
[
  {{"speaker": "Narrator", "text": "The storm had no name."}},
  {{"speaker": "Callum", "text": "I don't want this."}},
  {{"speaker": "Narrator", "text": "He said quietly, his voice barely above a whisper."}}
]

Text to parse:
{text}"""

# ── Config helpers (ported — no Qt) ──────────────────────────────────────────
def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {
        "characters": [
            {"name": "Narrator", "voice_engine": "edge-tts", "voice": "en-GB-RyanNeural", "speed": 0},
            {"name": "Callum",   "voice_engine": "edge-tts", "voice": "en-US-DavisNeural", "speed": 0},
        ],
        "default_engine": "edge-tts",
        "ollama_model": "qwen2.5:3b",
        "ollama_url": "http://localhost:11434",
        "gptsovits_url": "http://localhost:9880",
        "external_api": "claude",
        "output_dir": str(Path.home() / "Music" / "RedVerse"),
        "silence_ms": 400,
    }

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

def get_api_key(service: str) -> str:
    if HAS_KEYRING:
        return keyring.get_password(SERVICE_ID, service) or ""
    return ""

# ── Speaker detection (ported — no Qt) ───────────────────────────────────────
def detect_speakers_ollama(text: str, characters: list, model: str, base_url: str) -> list:
    if not HAS_OLLAMA:
        raise RuntimeError("ollama package not installed")
    prompt = PARSE_PROMPT.format(characters=", ".join(characters), text=text[:6000])
    client = ollama.Client(host=base_url)
    response = client.generate(model=model, prompt=prompt)
    raw = response.get("response", "")
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)

def detect_speakers_claude(text: str, characters: list, api_key: str) -> list:
    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")
    prompt = PARSE_PROMPT.format(characters=", ".join(characters), text=text[:6000])
    resp = _requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"]
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)

def detect_speakers_openai(text: str, characters: list, api_key: str) -> list:
    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")
    prompt = PARSE_PROMPT.format(characters=", ".join(characters), text=text[:6000])
    resp = _requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else parsed.get("segments", [])

# ── TTS rendering (ported — no Qt) ───────────────────────────────────────────
async def _render_edge_tts(text: str, voice: str, speed: int, out_path: str):
    rate = f"+{speed}%" if speed >= 0 else f"{speed}%"
    comm = edge_tts.Communicate(text, voice, rate=rate)
    await comm.save(out_path)

def render_pyttsx3(text: str, out_path: str):
    engine = pyttsx3.init()
    engine.save_to_file(text, out_path)
    engine.runAndWait()

def render_gptsovits(text: str, voice: str, base_url: str, out_path: str):
    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")
    resp = _requests.post(
        f"{base_url.rstrip('/')}/tts",
        json={"text": text, "speaker": voice},
        timeout=60,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)

def render_segment(text: str, char_config: dict, cfg: dict, tmp_dir: str, idx: int) -> str:
    engine   = char_config.get("voice_engine", "edge-tts")
    voice    = char_config.get("voice", "en-GB-RyanNeural")
    speed    = char_config.get("speed", 0)
    out_path = os.path.join(tmp_dir, f"seg_{idx:04d}.mp3")

    if engine == "edge-tts" and HAS_EDGE_TTS:
        asyncio.run(_render_edge_tts(text, voice, speed, out_path))
    elif engine == "gptsovits":
        render_gptsovits(text, voice, cfg.get("gptsovits_url", "http://localhost:9880"), out_path)
    elif HAS_PYTTSX3:
        render_pyttsx3(text, out_path)
    else:
        raise RuntimeError("No TTS engine available")
    return out_path

# ── Flask app ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("narrator-srv")

app = Flask(__name__)
CORS(app)

# ── Active jobs ───────────────────────────────────────────────────────────────
_jobs: dict = {}  # session_id → {status, segments, output_file, error}

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    return jsonify({
        "status": "ok",
        "service": "narrator_server",
        "port": PORT,
        "capabilities": {
            "edge_tts": HAS_EDGE_TTS,
            "pyttsx3": HAS_PYTTSX3,
            "pydub": HAS_PYDUB,
            "ollama": HAS_OLLAMA,
            "requests": HAS_REQUESTS,
            "keyring": HAS_KEYRING,
        },
    })


@app.get("/api/voices")
def voices():
    return jsonify({"voices": DEFAULT_EDGE_VOICES})


@app.get("/api/config")
def get_config():
    cfg = load_config()
    return jsonify(cfg)


@app.post("/api/config")
def post_config():
    data = request.get_json(force=True, silent=True) or {}
    cfg = load_config()
    cfg.update(data)
    save_config(cfg)
    return jsonify({"status": "saved"})


@app.post("/api/detect")
def detect():
    """
    Parse prose text into speaker segments.
    Body: {
        "text": "...",
        "characters": ["Narrator", "Callum", ...],   # optional, defaults from config
        "backend": "ollama" | "claude" | "openai",   # default: ollama
        "model":   "qwen2.5:3b",                     # ollama model
        "base_url": "http://localhost:11434",         # ollama URL
        "api_key": "sk-..."                          # claude/openai key
    }
    Returns: [{speaker, text}, ...]
    """
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    cfg = load_config()
    characters = data.get("characters") or [c["name"] for c in cfg.get("characters", [])]
    backend    = data.get("backend", "ollama")

    try:
        if backend == "ollama":
            segments = detect_speakers_ollama(
                text,
                characters,
                model    = data.get("model", cfg.get("ollama_model", "qwen2.5:3b")),
                base_url = data.get("base_url", cfg.get("ollama_url", "http://localhost:11434")),
            )
        elif backend == "claude":
            api_key = data.get("api_key") or get_api_key("claude")
            if not api_key:
                return jsonify({"error": "api_key required for claude backend"}), 400
            segments = detect_speakers_claude(text, characters, api_key)
        elif backend == "openai":
            api_key = data.get("api_key") or get_api_key("openai")
            if not api_key:
                return jsonify({"error": "api_key required for openai backend"}), 400
            segments = detect_speakers_openai(text, characters, api_key)
        else:
            return jsonify({"error": f"unknown backend: {backend}"}), 400

        return jsonify({"segments": segments, "count": len(segments)})
    except Exception as e:
        log.exception("detect error")
        return jsonify({"error": str(e)}), 500


@app.post("/api/tts/segment")
def tts_segment():
    """
    Render a single text segment to an MP3 file.
    Body: {
        "text": "...",
        "voice": "en-US-GuyNeural",       # edge-tts voice
        "voice_engine": "edge-tts",        # edge-tts | pyttsx3 | gptsovits
        "speed": 0,                        # % speed adjust (edge-tts)
        "gptsovits_url": "..."             # optional
    }
    Returns: {file_path, size_bytes}
    """
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    cfg = load_config()
    char_config = {
        "voice_engine": data.get("voice_engine", "edge-tts"),
        "voice":        data.get("voice", "en-GB-RyanNeural"),
        "speed":        int(data.get("speed", 0)),
    }
    if data.get("gptsovits_url"):
        cfg["gptsovits_url"] = data["gptsovits_url"]

    out_dir = Path(cfg.get("output_dir", str(Path.home() / "Music" / "RedVerse")))
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        out_path = render_segment(text, char_config, cfg, str(out_dir), int(time.time()))
        return jsonify({"file_path": out_path, "size_bytes": os.path.getsize(out_path)})
    except Exception as e:
        log.exception("tts/segment error")
        return jsonify({"error": str(e)}), 500


@app.post("/api/narrate")
def narrate():
    """
    Full pipeline: detect speakers → render each segment → combine into one MP3.
    Body: {
        "text": "...",
        "characters": [...],          # optional
        "backend": "ollama",          # detection backend
        "model": "qwen2.5:3b",
        "base_url": "...",
        "api_key": "...",
        "silence_ms": 400,
        "output_name": "episode_01"   # optional filename stem
    }
    Returns: {output_file, segments, duration_hint}
    """
    if not HAS_PYDUB:
        return jsonify({"error": "pydub not installed — cannot combine audio segments"}), 500

    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    cfg       = load_config()
    silence_ms = int(data.get("silence_ms", cfg.get("silence_ms", 400)))
    out_dir   = Path(cfg.get("output_dir", str(Path.home() / "Music" / "RedVerse")))
    out_dir.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())[:8]
    _jobs[session_id] = {"status": "detecting", "segments": [], "output_file": None, "error": None}

    def _run():
        try:
            # Step 1: detect
            characters = data.get("characters") or [c["name"] for c in cfg.get("characters", [])]
            backend    = data.get("backend", "ollama")
            if backend == "ollama":
                segments = detect_speakers_ollama(
                    text, characters,
                    model    = data.get("model", cfg.get("ollama_model", "qwen2.5:3b")),
                    base_url = data.get("base_url", cfg.get("ollama_url", "http://localhost:11434")),
                )
            elif backend == "claude":
                segments = detect_speakers_claude(text, characters, data.get("api_key", get_api_key("claude")))
            elif backend == "openai":
                segments = detect_speakers_openai(text, characters, data.get("api_key", get_api_key("openai")))
            else:
                raise RuntimeError(f"Unknown backend: {backend}")

            _jobs[session_id]["segments"] = segments
            _jobs[session_id]["status"]   = "rendering"

            # Build char_config lookup
            char_map = {c["name"]: c for c in cfg.get("characters", [])}

            with tempfile.TemporaryDirectory(prefix="narrator_") as tmp:
                combined = AudioSegment.empty()
                silence  = AudioSegment.silent(duration=silence_ms)

                for idx, seg in enumerate(segments):
                    speaker     = seg.get("speaker", "Narrator")
                    seg_text    = seg.get("text", "").strip()
                    if not seg_text:
                        continue
                    char_config = char_map.get(speaker, char_map.get("Narrator", {
                        "voice_engine": "edge-tts",
                        "voice": "en-GB-RyanNeural",
                        "speed": 0,
                    }))
                    seg_path = render_segment(seg_text, char_config, cfg, tmp, idx)
                    combined += AudioSegment.from_mp3(seg_path) + silence

            # Step 3: export
            stem     = data.get("output_name") or f"narration_{session_id}"
            out_file = str(out_dir / f"{stem}.mp3")
            combined.export(out_file, format="mp3")

            _jobs[session_id]["status"]      = "done"
            _jobs[session_id]["output_file"] = out_file

        except Exception as e:
            log.exception("narrate pipeline error")
            _jobs[session_id]["status"] = "error"
            _jobs[session_id]["error"]  = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"session_id": session_id, "status": "started"})


@app.get("/api/narrate/status/<session_id>")
def narrate_status(session_id: str):
    job = _jobs.get(session_id)
    if not job:
        return jsonify({"error": "unknown session_id"}), 404
    return jsonify({"session_id": session_id, **job})


# ── Entry ─────────────────────────────────────────────────────────────────────
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8930

if __name__ == "__main__":
    log.info("RedVerse Narrator API on http://0.0.0.0:%s", PORT)
    log.info("Edge-TTS: %s | pydub: %s | Ollama: %s", HAS_EDGE_TTS, HAS_PYDUB, HAS_OLLAMA)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
