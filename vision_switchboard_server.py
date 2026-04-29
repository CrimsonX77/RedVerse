#!/usr/bin/env python3
"""
Vision Switchboard Server — Multi-model image perception engine
Port 8920 | Part of RedVerse Agency Tools

Exposes PerceptionTab-style logic via REST API + serves vision_app HTML.
"""

import base64
import os
import sys
import socket
import time
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import requests

# Optional heavy deps (server still runs if unavailable)
try:
    import cv2
except Exception:
    cv2 = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import torch
except Exception:
    torch = None

try:
    from transformers import BlipProcessor, BlipForConditionalGeneration
except Exception:
    BlipProcessor = None
    BlipForConditionalGeneration = None

# Lazy loading globals (mirrors vision_switchboard_tab.py)
ci = None
CLIP_AVAILABLE = True
blip_processor = None
blip_model = None
yolo_model = None
device = None

models_loading = {
    'clip': False,
    'blip': False,
    'yolo': False,
}
models_ready = {
    'clip': False,
    'blip': False,
    'yolo': False,
}

STRATEGY_MODELS = {
    "Literal": "llava:latest",
    "Symbolic": "granite3.2-vision:latest",
    "Emotional": "bakllava:latest",
    "OllamaVision": None,
}

BASE_DIR = Path(__file__).resolve().parent
APP_HTML_CANDIDATES = ["vision_app.html", "vision-app.html"]

TESS_PATH = r"C:/Program Files/Tesseract-OCR/tesseract.exe"
if pytesseract and os.path.exists(TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESS_PATH


def _resolve_app_html() -> Path | None:
    for name in APP_HTML_CANDIDATES:
        p = BASE_DIR / name
        if p.exists():
            return p
    return None


def _get_lan_ip() -> str:
    """Best-effort local LAN IP detection."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_available_ollama_models():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            vision_models = [
                m for m in models
                if any(v in m.lower() for v in ["llava", "vision", "bakllava", "granite", "minicpm", "qwen", "gemma"])
            ]
            return vision_models if vision_models else models
        return []
    except Exception:
        return []


def get_clip_interrogator():
    global ci, CLIP_AVAILABLE, models_loading, models_ready
    if ci is None and CLIP_AVAILABLE and not models_loading['clip']:
        try:
            models_loading['clip'] = True
            from clip_interrogator import Config as ClipConfig, Interrogator as ClipInterrogator
            ci = ClipInterrogator(ClipConfig(clip_model_name="ViT-L-14/openai"))
            models_ready['clip'] = True
        except Exception:
            CLIP_AVAILABLE = False
            ci = None
        finally:
            models_loading['clip'] = False
    return ci


def get_blip_models():
    global blip_processor, blip_model, device, models_loading, models_ready
    if BlipProcessor is None or BlipForConditionalGeneration is None or torch is None:
        return None, None, None

    if blip_processor is None and not models_loading['blip']:
        try:
            models_loading['blip'] = True
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
            models_ready['blip'] = True
        except Exception:
            return None, None, None
        finally:
            models_loading['blip'] = False
    return blip_processor, blip_model, device


def get_yolo_model():
    global yolo_model, models_loading, models_ready
    if yolo_model is None and not models_loading['yolo']:
        try:
            models_loading['yolo'] = True
            from ultralytics import YOLO
            yolo_model = YOLO("yolov8n.pt")
            models_ready['yolo'] = True
        except Exception:
            yolo_model = False
        finally:
            models_loading['yolo'] = False
    return yolo_model if yolo_model is not False else None


def preload_models_async():
    threading.Thread(target=get_blip_models, daemon=True, name="BLIP-Loader").start()
    threading.Thread(target=get_clip_interrogator, daemon=True, name="CLIP-Loader").start()
    threading.Thread(target=get_yolo_model, daemon=True, name="YOLO-Loader").start()


def run_ocr(image_path):
    if cv2 is None or pytesseract is None:
        return "[OCR Unavailable] Install opencv-python + pytesseract"
    try:
        image = cv2.imread(image_path)
        if image is None:
            return "[OCR Error] Could not read image"
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        return f"[OCR Error] {str(e)}"


def generate_clip_caption(image_path, mode="fast"):
    interrogator = get_clip_interrogator()
    if interrogator is None:
        return "[CLIP Unavailable] Install clip-interrogator package"
    if Image is None:
        return "[CLIP Error] Pillow not available"
    try:
        img = Image.open(image_path).convert("RGB")
        if mode == "best":
            return interrogator.interrogate(img)
        if mode == "classic":
            return interrogator.interrogate_classic(img)
        return interrogator.interrogate_fast(img)
    except Exception as e:
        return f"[CLIP Error] {str(e)}"


def generate_blip_caption(image_path):
    try:
        processor, model, dev = get_blip_models()
        if processor is None or model is None or dev is None:
            return "[BLIP Unavailable]"
        if Image is None:
            return "[BLIP Error] Pillow not available"
        image = Image.open(image_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(dev)
        out = model.generate(**inputs)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"[BLIP Error] {str(e)}"


def generate_yolo_detection(image_path):
    try:
        yolo = get_yolo_model()
        if yolo is None:
            return "[YOLO Unavailable]"
        results = yolo(image_path)
        detections = []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                name = r.names[cls]
                detections.append(f"{name} ({conf:.2f})")
        return f"[YOLO] Detected: {', '.join(detections)}" if detections else "[YOLO] No objects detected"
    except Exception as e:
        return f"[YOLO Error] {str(e)}"


def generate_ollama_caption(image_path, model_name="llava:latest"):
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        payload = {
            "model": model_name,
            "prompt": "Describe the image in detail.",
            "images": [encoded],
            "stream": False,
        }
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "response" in data:
            return data["response"].strip()
        if isinstance(data, list):
            return "".join(chunk.get("response", "") for chunk in data).strip()
        return "[Ollama Error] Unexpected response format."
    except Exception as e:
        return f"[Ollama Error] {e}"


app = Flask(__name__)
CORS(app)
executor = ThreadPoolExecutor(max_workers=4)


@app.route('/api/status')
def status():
    return jsonify({
        "online": True,
        "models_ready": models_ready,
        "ollama_models": get_available_ollama_models(),
        "timestamp": datetime.now().isoformat(),
    })


@app.route('/api/ollama_models')
def ollama_models():
    return jsonify(get_available_ollama_models())


@app.route('/api/interpret', methods=['POST'])
def interpret():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    strategy = request.form.get('strategy', 'Literal')
    ollama_model = request.form.get('ollama_model')
    user_note = (request.form.get('user_note') or '').strip()

    temp_path = f"/tmp/vision_{int(time.time() * 1000)}.jpg"
    file.save(temp_path)

    try:
        results = []
        ocr = run_ocr(temp_path)

        if ocr and not ocr.startswith("[OCR Error]") and not ocr.startswith("[OCR Unavailable]"):
            results.append(f"[OCR]\n{ocr}")

        model_name = STRATEGY_MODELS.get(strategy)
        if model_name is None and strategy == "OllamaVision":
            model_name = ollama_model or "llava:latest"

        if model_name:
            ollama = generate_ollama_caption(temp_path, model_name)
            if ollama:
                results.append(f"[Ollama - {strategy} using {model_name}]\n{ollama}")

        is_ollama_only = strategy == "OllamaVision"
        if not is_ollama_only:
            try:
                future = executor.submit(generate_clip_caption, temp_path, "fast")
                clip = future.result(timeout=30)
                if clip:
                    results.append(f"[CLIP Interrogator]\n{clip}")
            except FuturesTimeoutError:
                results.append("[CLIP] Timed out after 30s")
            except Exception as e:
                results.append(f"[CLIP Error] {e}")

            try:
                future = executor.submit(generate_blip_caption, temp_path)
                blip = future.result(timeout=30)
                if blip:
                    results.append(f"[BLIP]\n{blip}")
            except FuturesTimeoutError:
                results.append("[BLIP] Timed out after 30s")
            except Exception as e:
                results.append(f"[BLIP Error] {e}")

            try:
                future = executor.submit(generate_yolo_detection, temp_path)
                yolo = future.result(timeout=30)
                if yolo:
                    results.append(yolo)
            except FuturesTimeoutError:
                results.append("[YOLO] Timed out after 30s")
            except Exception as e:
                results.append(f"[YOLO Error] {e}")

        if user_note:
            results.append(f"[User Notes]\n{user_note}")

        final_summary = "\n\n".join(results).strip() or "[No result]"

        return jsonify({
            "success": True,
            "strategy": strategy,
            "results": final_summary,
            "ocr": ocr,
            "image_path": temp_path,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


@app.route('/')
def serve_root():
    app_html = _resolve_app_html()
    if app_html is None:
        return jsonify({"error": "vision_app.html not found"}), 404
    return send_from_directory(str(BASE_DIR), app_html.name)


@app.route('/vision_app.html')
def serve_vision_app_underscore():
    p = BASE_DIR / 'vision_app.html'
    if p.exists():
        return send_from_directory(str(BASE_DIR), p.name)
    app_html = _resolve_app_html()
    if app_html is None:
        return jsonify({"error": "vision_app.html not found"}), 404
    return send_from_directory(str(BASE_DIR), app_html.name)


@app.route('/vision-app.html')
def serve_vision_app_hyphen():
    p = BASE_DIR / 'vision-app.html'
    if p.exists():
        return send_from_directory(str(BASE_DIR), p.name)
    app_html = _resolve_app_html()
    if app_html is None:
        return jsonify({"error": "vision-app.html not found"}), 404
    return send_from_directory(str(BASE_DIR), app_html.name)


@app.route('/<path:filename>')
def serve_static(filename):
    if filename.startswith('api/'):
        abort(404)
    target = BASE_DIR / filename
    if target.exists() and target.is_file():
        return send_from_directory(str(BASE_DIR), filename)
    abort(404)


if __name__ == '__main__':
    preload_models_async()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8920
    host = os.environ.get("VISION_HOST", "0.0.0.0")
    lan_ip = _get_lan_ip()
    print(f"🧠 Vision Switchboard Server starting on http://127.0.0.1:{port}")
    print(f"🌐 LAN access: http://{lan_ip}:{port}")
    app.run(host=host, port=port, threaded=True)
