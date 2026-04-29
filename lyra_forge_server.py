#!/usr/bin/env python3
"""
Lyra Forge Server — Image generation + AI chat backend
Bridges Stable Diffusion (A1111 WebUI) and Ollama for the Lyra Forge UI.

Port 8667 | Part of RedVerse Agency Scripts

Endpoints:
  GET  /api/status                     — SD + Ollama connectivity check
  GET  /api/query?category=models      — list SD checkpoints
  POST /api/chat                       — streaming Ollama chat (SSE)
  POST /api/generate                   — SD image generation
  GET  /api/gallery                    — list generated images
  GET  /api/images/<filename>          — serve a generated image
  DELETE /api/images/<filename>        — delete a generated image

Usage:
  python lyra_forge_server.py          # port 8667
  python lyra_forge_server.py 8667     # custom port

External dependencies (must be running separately):
  - Stable Diffusion A1111 WebUI at http://127.0.0.1:7860 (--api flag)
  - Ollama at http://127.0.0.1:11434
"""

import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ── Configuration ─────────────────────────────────────────────────────────────

SD_API = os.environ.get("SD_API", "http://127.0.0.1:7860")
OLLAMA_API = os.environ.get("OLLAMA_API", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
IMAGES_DIR = Path(os.environ.get("LYRA_IMAGES_DIR", Path.home() / ".lyra_forge" / "images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT_SHORT = 5   # seconds — quick connectivity checks
TIMEOUT_LONG = 300  # seconds — SD generation can be slow

# ── SD style presets ──────────────────────────────────────────────────────────

STYLE_PRESETS: dict[str, dict] = {
    "sable": {
        "positive_prefix": "masterpiece, best quality, ultra-detailed, gothic aesthetic, dark fantasy, ",
        "negative_append": "lowres, bad anatomy, blurry, watermark",
    },
    "photorealistic": {
        "positive_prefix": "photorealistic, 8k, cinematic lighting, ultra sharp, ",
        "negative_append": "painting, cartoon, anime, drawing",
    },
    "anime": {
        "positive_prefix": "anime style, vibrant colors, clean linework, ",
        "negative_append": "photorealistic, 3d render, ugly",
    },
    "noir": {
        "positive_prefix": "film noir, black and white, dramatic shadows, 1940s, ",
        "negative_append": "colorful, bright, cheerful",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_sd() -> bool:
    try:
        r = requests.get(f"{SD_API}/sdapi/v1/options", timeout=TIMEOUT_SHORT)
        return r.status_code == 200
    except Exception:
        return False


def _check_ollama() -> tuple[bool, str]:
    """Return (connected, current_model_name)."""
    try:
        r = requests.get(f"{OLLAMA_API}/api/tags", timeout=TIMEOUT_SHORT)
        if r.status_code != 200:
            return False, ""
        models = r.json().get("models", [])
        if not models:
            return True, ""
        # Prefer the configured model if it's available
        names = [m.get("name", "") for m in models]
        model = OLLAMA_MODEL if OLLAMA_MODEL in names else names[0]
        return True, model
    except Exception:
        return False, ""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    """Check SD and Ollama connectivity."""
    sd_ok = _check_sd()
    ollama_ok, ollama_model = _check_ollama()
    return jsonify({
        "sd_api": "connected" if sd_ok else "disconnected",
        "ollama": "connected" if ollama_ok else "disconnected",
        "ollama_model": ollama_model,
        "server": "Lyra Forge Server",
        "port": 8667,
    })


@app.route("/api/query")
def query():
    """Query SD for checkpoints (category=models)."""
    category = request.args.get("category", "")
    if category == "models":
        try:
            r = requests.get(f"{SD_API}/sdapi/v1/sd-models", timeout=TIMEOUT_SHORT)
            r.raise_for_status()
            models = [m.get("model_name", m.get("title", "")) for m in r.json()]
            return jsonify({"models": models})
        except Exception:
            return jsonify({"error": "Failed to fetch models from SD API", "models": []})
    return jsonify({"error": f"Unknown category: {category}"}), 400


@app.route("/api/chat", methods=["POST"])
def chat():
    """Stream an Ollama chat response as SSE (data: JSON lines)."""
    body = request.get_json(force=True) or {}
    model = body.get("model", OLLAMA_MODEL)
    messages = body.get("messages", [])

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    def generate():
        try:
            resp = requests.post(
                f"{OLLAMA_API}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
                stream=True,
                timeout=TIMEOUT_LONG,
            )
            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                try:
                    chunk = json.loads(decoded)
                except json.JSONDecodeError:
                    continue
                if chunk.get("done"):
                    yield "data: [DONE]\n\n"
                    break
                if "message" in chunk:
                    yield f"data: {json.dumps(chunk)}\n\n"
        except Exception:
            yield "data: {\"error\": \"Connection to Ollama failed\"}\n\n"
            yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/generate", methods=["POST"])
def generate_image():
    """Submit a txt2img request to SD and return saved image info."""
    body = request.get_json(force=True) or {}

    style_key = body.get("style_preset", "sable")
    style = STYLE_PRESETS.get(style_key, STYLE_PRESETS["sable"])

    prompt = style["positive_prefix"] + body.get("prompt", "")
    negative = body.get("negative_prompt", "") + ", " + style["negative_append"]

    checkpoint = body.get("checkpoint", "")
    loras_raw = body.get("loras", "").strip()
    if loras_raw:
        prompt += " " + loras_raw

    sd_payload: dict = {
        "prompt": prompt,
        "negative_prompt": negative.strip(", "),
        "width": body.get("width", 768),
        "height": body.get("height", 768),
        "steps": body.get("steps", 35),
        "cfg_scale": body.get("cfg_scale", 7.5),
        "seed": body.get("seed", -1),
        "sampler_name": "DPM++ 2M Karras",
        "batch_size": 1,
        "n_iter": 1,
    }

    # High-res fix
    if body.get("enable_hr"):
        sd_payload.update({
            "enable_hr": True,
            "hr_upscaler": "R-ESRGAN 4x+ Anime6B",
            "hr_scale": 1.5,
            "denoising_strength": 0.55,
        })

    # Override model checkpoint if requested
    if checkpoint:
        try:
            requests.post(
                f"{SD_API}/sdapi/v1/options",
                json={"sd_model_checkpoint": checkpoint},
                timeout=TIMEOUT_SHORT,
            )
        except Exception:
            pass  # Best effort

    t0 = time.time()
    try:
        r = requests.post(f"{SD_API}/sdapi/v1/txt2img",
                          json=sd_payload, timeout=TIMEOUT_LONG)
        r.raise_for_status()
        result = r.json()
    except Exception:
        return jsonify({"status": "error", "error": "SD API request failed"}), 500

    generation_time = round(time.time() - t0, 2)

    images = result.get("images", [])
    if not images:
        return jsonify({"status": "error", "error": "SD returned no images"}), 500

    # Decode and save the first image
    try:
        img_data = base64.b64decode(images[0].split(",", 1)[-1])
    except Exception:
        return jsonify({"status": "error", "error": "SD returned invalid image data"}), 500
    filename = f"lyra_{uuid.uuid4().hex[:12]}.png"
    save_path = IMAGES_DIR / filename
    save_path.write_bytes(img_data)

    # Parse SD info for seed
    info_raw = result.get("info", "{}")
    try:
        info = json.loads(info_raw)
    except Exception:
        info = {}
    seed_used = info.get("seed", sd_payload.get("seed", -1))

    # Get a short commentary from Ollama (best-effort)
    commentary = ""
    try:
        ollama_ok, model_name = _check_ollama()
        if ollama_ok:
            crq = requests.post(
                f"{OLLAMA_API}/api/generate",
                json={
                    "model": model_name or OLLAMA_MODEL,
                    "prompt": (
                        f"You are Lyra, an artistic AI. Comment very briefly (1-2 sentences) "
                        f"in character on this image you just generated: '{body.get('prompt', '')}'"
                    ),
                    "stream": False,
                },
                timeout=15,
            )
            commentary = crq.json().get("response", "").strip()
    except Exception:
        pass

    return jsonify({
        "status": "success",
        "filename": filename,
        "generation_time_s": generation_time,
        "metadata": {
            "prompt": prompt,
            "seed_used": seed_used,
            "width": sd_payload["width"],
            "height": sd_payload["height"],
            "steps": sd_payload["steps"],
        },
        "commentary": commentary,
    })


@app.route("/api/gallery")
def gallery():
    """List all generated images."""
    try:
        images = sorted(IMAGES_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = [{"filename": p.name, "url": f"/api/images/{p.name}"} for p in images]
        return jsonify({"images": result})
    except Exception:
        return jsonify({"error": "Failed to list gallery", "images": []}), 500


@app.route("/api/images/<filename>", methods=["GET", "DELETE"])
def image_file(filename: str):
    """Serve (GET) or delete (DELETE) a generated image."""
    # Reject any path separators — only allow bare filenames
    safe = Path(filename).name
    if safe != filename or not safe.endswith(".png") or "/" in safe or "\\" in safe:
        return jsonify({"error": "Invalid filename"}), 400

    # Resolve and verify the final path is inside IMAGES_DIR (defence in depth)
    path = (IMAGES_DIR / safe).resolve()
    if not str(path).startswith(str(IMAGES_DIR.resolve())):
        return jsonify({"error": "Access denied"}), 403

    if request.method == "DELETE":
        try:
            path.unlink(missing_ok=True)
            return jsonify({"status": "deleted", "filename": safe})
        except Exception:
            return jsonify({"error": "Failed to delete image"}), 500

    if not path.exists():
        return jsonify({"error": "Image not found"}), 404

    return send_from_directory(str(IMAGES_DIR), safe, mimetype="image/png")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8667
    print(f"🖼  Lyra Forge Server on http://127.0.0.1:{port}")
    print(f"   SD API   : {SD_API}")
    print(f"   Ollama   : {OLLAMA_API}  (model: {OLLAMA_MODEL})")
    print(f"   Images   : {IMAGES_DIR}")
    app.run(host="127.0.0.1", port=port, threaded=True)
