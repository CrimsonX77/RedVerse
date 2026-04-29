#!/usr/bin/env python3
"""
embodiment_server.py — Embodiment Animation Control Server
Flask-SocketIO backend for AI-driven character control.

Serves:
  • WebSocket (Socket.IO) for real-time animation commands
  • REST API for command-based control
  • Static files for the embodiment viewer

Usage:
  python embodiment_server.py              # Start on port 5000
  python embodiment_server.py --port 5001  # Custom port
  python embodiment_server.py --viewer     # Also open viewer in browser
"""

import os
import sys
import json
import time
import argparse
import webbrowser
import logging
from pathlib import Path
from datetime import datetime

import yaml
import requests as http_req
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent.resolve()
MAPPING_FILE = BASE_DIR / "embodiment_mapping.yaml"
VIEWER_DIR = BASE_DIR  # index.html lives at project root

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("embodiment")

# ═══════════════════════════════════════════════════════════════
# Load semantic mapping
# ═══════════════════════════════════════════════════════════════

def load_mapping(path: Path) -> dict:
    """Load embodiment_mapping.yaml and return as dict."""
    if not path.exists():
        log.warning(f"Mapping file not found: {path}")
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}

mapping = load_mapping(MAPPING_FILE)

# ═══════════════════════════════════════════════════════════════
# Flask App + SocketIO
# ═══════════════════════════════════════════════════════════════

app = Flask(__name__, static_folder=str(VIEWER_DIR), static_url_path="")
CORS(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    logger=False,
    engineio_logger=False
)

# Track connected viewers
connected_viewers = set()
viewer_capabilities = {}
command_log = []

# ═══════════════════════════════════════════════════════════════
# Static File Serving (Viewer)
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def serve_viewer():
    """Serve the embodiment viewer."""
    return send_from_directory(str(VIEWER_DIR), "index.html")

@app.route("/<path:path>")
def serve_static(path):
    """Serve static files (JS, models, etc.)."""
    return send_from_directory(str(VIEWER_DIR), path)

# ═══════════════════════════════════════════════════════════════
# REST API — Command Endpoints
# ═══════════════════════════════════════════════════════════════

@app.route("/api/status", methods=["GET"])
def api_status():
    """Server and viewer status."""
    return jsonify({
        "server": "embodiment",
        "version": "1.0.0",
        "viewers_connected": len(connected_viewers),
        "capabilities": viewer_capabilities,
        "uptime": time.time(),
        "mapping_loaded": bool(mapping)
    })

@app.route("/api/command", methods=["POST"])
def api_command():
    """Send a single command to the viewer.
    
    Body: JSON matching animation-schema.json
    Example: {"type": "animation", "action": "wave"}
    """
    cmd = request.get_json(silent=True)
    if not cmd:
        return jsonify({"error": "Invalid JSON body"}), 400
    if "type" not in cmd:
        return jsonify({"error": "Missing 'type' field"}), 400

    # Resolve semantic names if needed
    resolved = resolve_command(cmd)

    # Broadcast to all connected viewers
    socketio.emit("command", resolved, namespace="/")
    log_command(resolved, source="REST")

    return jsonify({"status": "sent", "command": resolved, "viewers": len(connected_viewers)})

@app.route("/api/sequence", methods=["POST"])
def api_sequence():
    """Send a command sequence to the viewer.
    
    Body: {"commands": [...], "delay": 0.5}
    """
    data = request.get_json(silent=True)
    if not data or "commands" not in data:
        return jsonify({"error": "Missing 'commands' array"}), 400

    # Resolve each command
    resolved_cmds = [resolve_command(c) for c in data["commands"]]
    payload = {
        "commands": resolved_cmds,
        "delay": data.get("delay", 0)
    }

    socketio.emit("sequence", payload, namespace="/")
    log_command(payload, source="REST-sequence")

    return jsonify({"status": "sent", "count": len(resolved_cmds)})

@app.route("/api/composite/<name>", methods=["POST"])
def api_composite(name):
    """Trigger a pre-built composite action by name.
    
    Example: POST /api/composite/greet
    """
    composites = mapping.get("composites", {})
    if name not in composites:
        available = list(composites.keys())
        return jsonify({"error": f"Unknown composite: {name}", "available": available}), 404

    comp = composites[name]
    payload = {
        "commands": comp["commands"],
        "delay": comp.get("delay", 0)
    }

    socketio.emit("sequence", payload, namespace="/")
    log_command({"composite": name, **payload}, source="REST-composite")

    return jsonify({"status": "sent", "composite": name, "commands": len(comp["commands"])})

@app.route("/api/capabilities", methods=["GET"])
def api_capabilities():
    """Get current viewer capabilities (animations, morphs, bones)."""
    # Request fresh capabilities from viewer
    socketio.emit("query_capabilities", namespace="/")
    time.sleep(0.3)  # Brief wait for response
    return jsonify(viewer_capabilities)

@app.route("/api/mapping", methods=["GET"])
def api_mapping():
    """Return the current semantic mapping configuration."""
    return jsonify(mapping)

@app.route("/api/log", methods=["GET"])
def api_log():
    """Return recent command log (last 50)."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(command_log[-limit:])

@app.route("/api/ai-context", methods=["GET"])
def api_ai_context():
    """Return the AI prompt context string for injection into system prompts."""
    ctx = mapping.get("ai_context", "")
    return jsonify({"context": ctx})

# ═══════════════════════════════════════════════════════════════
# Speaker Proxy — TCP bridge for browser→speaker TTS
# ═══════════════════════════════════════════════════════════════

SPEAKER_HOST = os.getenv("SPEAKER_HOST", "localhost")
SPEAKER_PORT = int(os.getenv("SPEAKER_PORT", "9999"))

@app.route("/api/speak", methods=["POST"])
def api_speak():
    """Send text to the Speaker TTS module via TCP socket.

    Body: {"text": "Hello world"}
    """
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400
    text = data["text"].strip()
    if not text:
        return jsonify({"error": "Empty text"}), 400
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((SPEAKER_HOST, SPEAKER_PORT))
            s.sendall(text.encode("utf-8"))
        return jsonify({"status": "sent", "length": len(text)})
    except ConnectionRefusedError:
        return jsonify({"error": "Speaker not running", "port": SPEAKER_PORT}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/speaker/health", methods=["GET"])
def api_speaker_health():
    """Check if the Speaker TTS module is reachable."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((SPEAKER_HOST, SPEAKER_PORT))
        return jsonify({"status": "online", "port": SPEAKER_PORT})
    except Exception:
        return jsonify({"status": "offline", "port": SPEAKER_PORT}), 503

# ═══════════════════════════════════════════════════════════════
# Vision Proxy — image analysis via Ollama vision model
# ═══════════════════════════════════════════════════════════════

VISION_OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:7b")

@app.route("/api/vision/analyze", methods=["POST"])
def api_vision_analyze():
    """Analyze an image using the Ollama vision model.

    Body: {"image": "<base64>", "prompt": "Describe what you see...", "model": "llava:7b"}
    """
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        return jsonify({"error": "Missing 'image' (base64) field"}), 400

    b64 = data["image"]
    prompt = data.get("prompt", "Describe what you see in this image in detail. Be concise (2-3 sentences).")
    model = data.get("model", VISION_MODEL)

    try:
        import requests as req
        resp = req.post(
            f"{VISION_OLLAMA_BASE}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt, "images": [b64]}],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        caption = result.get("message", {}).get("content", "")
        return jsonify({"status": "ok", "caption": caption, "model": model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════════════
# Sable's Room Proxy — GUI can reach room server through here
# ═══════════════════════════════════════════════════════════════

ROOM_SERVER_URL = os.getenv("ROOM_SERVER_URL", "http://127.0.0.1:7700")

@app.route("/api/room/status", methods=["GET"])
def api_room_status():
    """Proxy: get Sable's Room status."""
    try:
        import requests as req
        r = req.get(f"{ROOM_SERVER_URL}/api/status", timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "room_url": ROOM_SERVER_URL}), 503

@app.route("/api/room/history", methods=["GET"])
def api_room_history():
    """Proxy: get Sable's Room conversation history."""
    limit = request.args.get("limit", 30, type=int)
    try:
        import requests as req
        r = req.get(f"{ROOM_SERVER_URL}/api/history", params={"limit": limit}, timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route("/api/room/message", methods=["POST"])
def api_room_message():
    """Proxy: send a message to Sable's Room."""
    data = request.get_json(silent=True)
    if not data or "content" not in data:
        return jsonify({"error": "Missing 'content' field"}), 400
    try:
        import requests as req
        payload = {
            "participant": data.get("participant", "LUNA-FUI"),
            "content": data["content"],
            "media": data.get("media"),
        }
        r = req.post(f"{ROOM_SERVER_URL}/api/message", json=payload, timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 503

# ═══════════════════════════════════════════════════════════════
# Ollama Proxy — eliminates CORS issues for browser→Ollama
# ═══════════════════════════════════════════════════════════════

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")

@app.route("/api/chat", methods=["POST"])
def api_chat_proxy():
    """Streaming proxy to Ollama /api/chat.
    Accepts the same JSON body as Ollama and streams the response back.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    is_stream = data.get("stream", True)

    try:
        resp = http_req.post(
            f"{OLLAMA_BASE}/api/chat",
            json=data,
            stream=is_stream,
            timeout=300,
        )
        resp.raise_for_status()

        if is_stream:
            def generate():
                for chunk in resp.iter_content(chunk_size=4096):
                    if chunk:
                        yield chunk
            return Response(
                stream_with_context(generate()),
                content_type=resp.headers.get("Content-Type", "application/x-ndjson"),
            )
        else:
            return jsonify(resp.json())
    except http_req.ConnectionError:
        return jsonify({"error": "Ollama not reachable", "url": OLLAMA_BASE}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tags", methods=["GET"])
def api_tags_proxy():
    """Proxy to Ollama /api/tags — list available models."""
    try:
        resp = http_req.get(f"{OLLAMA_BASE}/api/tags", timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json())
    except http_req.ConnectionError:
        return jsonify({"error": "Ollama not reachable", "url": OLLAMA_BASE}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════════════
# Vision Full Pipeline — auto-selects best vision model
# ═══════════════════════════════════════════════════════════════

# Ranked preference: best available vision model wins
VISION_MODEL_RANK = [
    "minicpm-v:8b",
    "llava:13b",
    "llava:7b",
    "ebdm/gemma3-enhanced:12b",
    "qwen3:8b",
]

@app.route("/api/vision/full", methods=["POST"])
def api_vision_full():
    """Full vision pipeline: auto-select best vision model, analyze, return result.

    Body: {"image": "<base64>", "prompt": "...(optional)"}
    Returns: {"caption": "...", "model_used": "...", "available_vision": [...]}
    """
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        return jsonify({"error": "Missing 'image' (base64) field"}), 400

    b64 = data["image"]
    prompt = data.get("prompt", "Describe what you see in this image in detail. Be concise (2-3 sentences).")

    # Step 1: Get available models
    available_vision = []
    try:
        tags_resp = http_req.get(f"{OLLAMA_BASE}/api/tags", timeout=10)
        tags_resp.raise_for_status()
        all_models = [m["name"] for m in tags_resp.json().get("models", [])]
        # Filter to known vision-capable models
        vision_keywords = ["llava", "minicpm-v", "gemma3", "bakllava", "moondream"]
        for m in all_models:
            if any(kw in m.lower() for kw in vision_keywords):
                available_vision.append(m)
    except Exception:
        available_vision = []

    # Step 2: Select best by rank
    selected = None
    for ranked in VISION_MODEL_RANK:
        if ranked in available_vision:
            selected = ranked
            break
    if not selected and available_vision:
        selected = available_vision[0]
    if not selected:
        selected = VISION_MODEL  # env fallback

    # Step 3: Run analysis
    try:
        resp = http_req.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": selected,
                "messages": [{"role": "user", "content": prompt, "images": [b64]}],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        caption = result.get("message", {}).get("content", "")
        return jsonify({
            "status": "ok",
            "caption": caption,
            "model_used": selected,
            "available_vision": available_vision,
        })
    except Exception as e:
        return jsonify({"error": str(e), "model_attempted": selected}), 500

# ═══════════════════════════════════════════════════════════════
# Shared Gallery + Bridge — real-time sync between all clients
# ═══════════════════════════════════════════════════════════════

shared_gallery = []  # In-memory shared gallery

@app.route("/api/gallery", methods=["GET"])
def api_gallery_list():
    """List shared gallery items."""
    return jsonify({"items": shared_gallery, "count": len(shared_gallery)})

@app.route("/api/gallery/add", methods=["POST"])
def api_gallery_add():
    """Add item to shared gallery and broadcast to all Socket.IO clients.

    Body: {"src": "...", "type": "image|video|audio", "name": "...", "source": "navigator|html"}
    """
    data = request.get_json(silent=True)
    if not data or "src" not in data:
        return jsonify({"error": "Missing 'src' field"}), 400

    item = {
        "id": f"{int(time.time()*1000)}_{os.urandom(3).hex()}",
        "ts": int(time.time() * 1000),
        "type": data.get("type", "image"),
        "name": data.get("name", "untitled"),
        "src": data["src"],
        "source": data.get("source", "api"),
    }
    shared_gallery.insert(0, item)
    # Keep bounded
    if len(shared_gallery) > 500:
        shared_gallery[:] = shared_gallery[:500]

    # Broadcast to all connected Socket.IO clients
    socketio.emit("gallery_item", item, namespace="/")
    return jsonify({"status": "added", "item": item})

@app.route("/api/bridge/chat", methods=["POST"])
def api_bridge_chat():
    """Broadcast a chat message to all connected clients.

    Body: {"role": "user|luna|sys", "content": "...", "source": "navigator|html"}
    """
    data = request.get_json(silent=True)
    if not data or "content" not in data:
        return jsonify({"error": "Missing 'content' field"}), 400
    msg = {
        "role": data.get("role", "sys"),
        "content": data["content"],
        "source": data.get("source", "api"),
        "ts": int(time.time() * 1000),
    }
    socketio.emit("chat_message", msg, namespace="/")
    return jsonify({"status": "broadcast", "msg": msg})

@app.route("/api/bridge/vision", methods=["POST"])
def api_bridge_vision():
    """Broadcast a vision context update to all connected clients.

    Body: {"caption": "...", "model": "...", "image_b64": "...(optional)", "source": "navigator|html"}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    evt = {
        "caption": data.get("caption", ""),
        "model": data.get("model", ""),
        "source": data.get("source", "api"),
        "ts": int(time.time() * 1000),
    }
    socketio.emit("vision_update", evt, namespace="/")
    return jsonify({"status": "broadcast", "event": evt})

# ═══════════════════════════════════════════════════════════════
# Avatar Model Directory — list .glb/.gltf for 3D hotswap
# ═══════════════════════════════════════════════════════════════

@app.route("/api/models/avatars", methods=["GET"])
def api_models_avatars():
    """List all .glb and .gltf avatar files in models/ for 3D hotswap.

    Returns: {"avatars": [{name, filename, path, size_mb}], "count": N}
    """
    avatars = []
    for ext in ("*.glb", "*.gltf"):
        for p in sorted(MODELS_DIR.glob(ext)):
            avatars.append({
                "name": p.stem.replace("_", " ").replace("-", " ").title(),
                "filename": p.name,
                "path": f"/models/{p.name}",
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            })
    return jsonify({"avatars": avatars, "count": len(avatars)})

# ═══════════════════════════════════════════════════════════════
# Room Media Proxy — file upload forwarding for Sable's Room
# ═══════════════════════════════════════════════════════════════

@app.route("/api/room/media", methods=["POST"])
def api_room_media():
    """Send a message with media attachment to Sable's Room.

    Body: {"content": "...", "participant": "...", "media_b64": "...", "media_type": "image", "media_name": "file.png"}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    try:
        payload = {
            "participant": data.get("participant", "LUNA-FUI"),
            "content": data.get("content", ""),
            "media": {
                "data": data.get("media_b64", ""),
                "type": data.get("media_type", "image"),
                "name": data.get("media_name", "attachment"),
            } if data.get("media_b64") else None,
        }
        r = http_req.post(f"{ROOM_SERVER_URL}/api/message", json=payload, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 503

# Bridge WebSocket events from Socket.IO clients

@socketio.on("gallery_item")
def on_gallery_item(data):
    """Receive gallery item from a client → rebroadcast to others."""
    emit("gallery_item", data, broadcast=True, include_self=False)

@socketio.on("chat_message")
def on_chat_message(data):
    """Receive chat message from a client → rebroadcast to others."""
    emit("chat_message", data, broadcast=True, include_self=False)

@socketio.on("vision_update")
def on_vision_update(data):
    """Receive vision update from a client → rebroadcast to others."""
    emit("vision_update", data, broadcast=True, include_self=False)

@socketio.on("room_message")
def on_room_message(data):
    """Receive room message from a client → rebroadcast to others."""
    emit("room_message", data, broadcast=True, include_self=False)

# ═══════════════════════════════════════════════════════════════
# Model Directory Scanner
# ═══════════════════════════════════════════════════════════════

MODELS_DIR = BASE_DIR / "models"

@app.route("/api/models/scan", methods=["GET"])
def api_models_scan():
    """List model/avatar files in the configured models directory.

    Query params:
      dir — optional subdirectory name (must be under models/)
    Returns: {"files": [...], "dir": "..."}
    """
    sub = request.args.get("dir", "")
    # Resolve and validate path stays under MODELS_DIR
    target = (MODELS_DIR / sub).resolve()
    if not str(target).startswith(str(MODELS_DIR.resolve())):
        return jsonify({"error": "Invalid directory"}), 400
    if not target.is_dir():
        return jsonify({"error": "Directory not found", "path": str(target)}), 404

    entries = []
    for p in sorted(target.iterdir()):
        entries.append({
            "name": p.name,
            "type": "dir" if p.is_dir() else "file",
            "size": p.stat().st_size if p.is_file() else None,
        })
    return jsonify({"files": entries, "dir": str(target)})

# ═══════════════════════════════════════════════════════════════
# WebSocket Events
# ═══════════════════════════════════════════════════════════════

@socketio.on("connect")
def on_connect():
    """Handle viewer connection."""
    sid = request.sid
    connected_viewers.add(sid)
    log.info(f"Viewer connected: {sid} (total: {len(connected_viewers)})")

@socketio.on("disconnect")
def on_disconnect():
    """Handle viewer disconnection."""
    sid = request.sid
    connected_viewers.discard(sid)
    log.info(f"Viewer disconnected: {sid} (total: {len(connected_viewers)})")

@socketio.on("capabilities")
def on_capabilities(data):
    """Receive viewer capabilities report."""
    global viewer_capabilities
    viewer_capabilities = data
    log.info(f"Capabilities updated: {len(data.get('animations', []))} anims, "
             f"{len(data.get('morphTargets', []))} morphs, "
             f"{len(data.get('bones', []))} bones")

@socketio.on("command")
def on_command(cmd):
    """Receive and broadcast a command (e.g., from another socket client)."""
    resolved = resolve_command(cmd)
    emit("command", resolved, broadcast=True, include_self=False)
    log_command(resolved, source="WebSocket")

@socketio.on("command_result")
def on_command_result(data):
    """Receive command execution result from viewer."""
    log.info(f"Command result: {data}")

# ═══════════════════════════════════════════════════════════════
# Command Resolution — Maps semantic names to actual clip/morph names
# ═══════════════════════════════════════════════════════════════

def resolve_command(cmd: dict) -> dict:
    """Resolve semantic names in a command using the mapping file.
    
    For example, 'greet' gesture → actual animation clip name.
    """
    cmd = dict(cmd)  # Don't mutate original

    if cmd.get("type") == "animation":
        action = cmd.get("action", "")
        gestures = mapping.get("gestures", {})
        if action in gestures:
            gesture = gestures[action]
            cmd["action"] = gesture.get("clip", action)
            # Merge params (command params override mapping defaults)
            mapped_params = gesture.get("params", {})
            cmd_params = cmd.get("params", {})
            cmd["params"] = {**mapped_params, **cmd_params}

    elif cmd.get("type") == "expression":
        expression = cmd.get("expression", "")
        expressions = mapping.get("expressions", {})
        if expression in expressions:
            # Expression resolution happens client-side via expressionMap,
            # but we pass mapping data through for advanced use
            expr_data = expressions[expression]
            cmd["_mapped_morphs"] = expr_data.get("morphs", [])

    elif cmd.get("type") == "camera":
        action = cmd.get("action", "")
        presets = mapping.get("camera_presets", {})
        if action in presets:
            preset = presets[action]
            if "position" not in cmd and "position" in preset:
                cmd["position"] = preset["position"]
            if "target" not in cmd and "target" in preset:
                cmd["target"] = preset["target"]
            cmd["action"] = "zoom"  # Override to zoom for preset positioning

    return cmd

def log_command(cmd: dict, source: str = "unknown"):
    """Log a command for debugging/replay."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "command": cmd
    }
    command_log.append(entry)
    # Keep log bounded
    if len(command_log) > 500:
        command_log[:] = command_log[-250:]
    log.info(f"[{source}] {cmd.get('type', '?')}: {json.dumps(cmd)[:120]}")

# ═══════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Embodiment Animation Control Server")
    parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--viewer", action="store_true", help="Open viewer in browser")
    args = parser.parse_args()

    os.chdir(BASE_DIR)

    print("╔════════════════════════════════════════════════════════════╗")
    print("║   Embodiment Animation Control Server                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"\n  WebSocket : ws://localhost:{args.port}")
    print(f"  REST API  : http://localhost:{args.port}/api/")
    print(f"  Viewer    : http://localhost:{args.port}/")
    print(f"  Mapping   : {'✓ loaded' if mapping else '✗ not found'}")
    if mapping:
        n_expr = len(mapping.get("expressions", {}))
        n_gest = len(mapping.get("gestures", {}))
        n_comp = len(mapping.get("composites", {}))
        print(f"              {n_expr} expressions, {n_gest} gestures, {n_comp} composites")
    print()
    print("  REST Endpoints:")
    print(f"    POST /api/command           — Send animation command")
    print(f"    POST /api/sequence          — Send command sequence")
    print(f"    POST /api/composite/<name>  — Trigger composite action")
    print(f"    GET  /api/capabilities      — Query viewer capabilities")
    print(f"    GET  /api/mapping           — Get semantic mapping")
    print(f"    GET  /api/status            — Server status")
    print(f"    GET  /api/ai-context        — AI prompt context string")
    print(f"    GET  /api/log               — Command log")
    print(f"    POST /api/speak             — Send text to Speaker TTS")
    print(f"    GET  /api/speaker/health    — Speaker health check")
    print(f"    POST /api/vision/analyze    — Vision analysis (Ollama)")
    print(f"    POST /api/chat              — Ollama chat proxy (streaming)")
    print(f"    GET  /api/tags              — Ollama model list proxy")
    print(f"    POST /api/vision/full       — Full vision pipeline (auto model)")
    print(f"    GET  /api/gallery           — Shared gallery list")
    print(f"    POST /api/gallery/add       — Add to shared gallery")
    print(f"    POST /api/bridge/chat       — Broadcast chat message")
    print(f"    POST /api/bridge/vision     — Broadcast vision update")
    print(f"    GET  /api/models/avatars    — List 3D avatar models (.glb/.gltf)")
    print(f"    GET  /api/room/status       — Sable's Room status")
    print(f"    GET  /api/room/history      — Sable's Room history")
    print(f"    POST /api/room/message      — Send to Sable's Room")
    print(f"    POST /api/room/media        — Room message with attachment")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Press Ctrl+C to stop.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if args.viewer:
        import threading
        def open_browser():
            time.sleep(1)
            webbrowser.open(f"http://localhost:{args.port}/")
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        socketio.run(app, host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n\n  Server stopped.\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
