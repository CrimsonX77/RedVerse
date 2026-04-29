#!/usr/bin/env python3
"""
QuickCam Server — Vision Portal Backend
Serves camera MJPEG stream with night vision processing.
Runs alongside the quickcam.html cathedral frontend.

Part of the RedVerse Agency Scripts suite.
"""

import cv2
import numpy as np
import json
import sys
import time
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════
camera_lock = threading.Lock()
camera = None
camera_index = 0
vision_mode = "normal"
intensity = 5
audio_muted = False
devices_cache = []
devices_cache_ts = 0.0

VISION_MODES = ["normal", "green", "thermal", "lowlight", "edge", "spectral"]


def _open_camera(index: int):
    """Try to open a camera index and configure common properties."""
    cap = cv2.VideoCapture(index)
    if not cap or not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap


def probe_devices(force: bool = False):
    """Probe available camera devices with short caching to reduce camera churn."""
    global devices_cache, devices_cache_ts
    now = time.time()
    if not force and (now - devices_cache_ts) < 5 and devices_cache:
        return devices_cache

    found = []
    for i in range(5):
        test = cv2.VideoCapture(i)
        if test.isOpened():
            found.append({"index": i, "name": f"Camera {i}"})
        test.release()

    # Fallback: if active camera is open but probing can't reopen it (driver lock), keep it visible.
    with camera_lock:
        active_ok = camera is not None and camera.isOpened()
        active_idx = camera_index
    if active_ok and not any(d["index"] == active_idx for d in found):
        found.insert(0, {"index": active_idx, "name": f"Camera {active_idx} (active)"})

    devices_cache = found
    devices_cache_ts = now
    return devices_cache


def get_camera():
    global camera
    if camera is None or not camera.isOpened():
        camera = _open_camera(camera_index)
    return camera


def apply_vision(frame, mode, power):
    """Apply night vision processing to frame."""
    factor = power / 10.0
    
    if mode == "green":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eq = cv2.equalizeHist(gray)
        result = np.zeros_like(frame)
        result[:, :, 1] = np.clip(eq * factor, 0, 255).astype(np.uint8)
        result[:, :, 0] = np.clip(eq * 0.1, 0, 255).astype(np.uint8)
        return result
    
    elif mode == "thermal":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thermal = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
        return np.clip(thermal * factor, 0, 255).astype(np.uint8)
    
    elif mode == "lowlight":
        enhanced = cv2.convertScaleAbs(frame, alpha=1.0 + factor, beta=50)
        gamma = 0.5 + factor * 0.5
        corrected = np.power(enhanced / 255.0, gamma) * 255
        return corrected.astype(np.uint8)
    
    elif mode == "edge":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        colored = np.zeros_like(frame)
        colored[:, :, 2] = np.clip(edges * factor, 0, 255).astype(np.uint8)
        colored[:, :, 0] = np.clip(edges * factor * 0.3, 0, 255).astype(np.uint8)
        blended = cv2.addWeighted(frame, 0.3, colored, 0.7, 0)
        return blended.astype(np.uint8)
    
    elif mode == "spectral":
        inverted = 255 - frame
        tinted = inverted.copy()
        tinted[:, :, 2] = np.clip(tinted[:, :, 2] * 1.2, 0, 255)
        tinted[:, :, 0] = np.clip(tinted[:, :, 0] * 1.3, 0, 255)
        return np.clip(tinted * factor, 0, 255).astype(np.uint8)
    
    return frame


def generate_frames():
    """MJPEG frame generator."""
    while True:
        with camera_lock:
            cam = get_camera()
            if cam is None or not cam.isOpened():
                time.sleep(0.15)
                continue
            ret, frame = cam.read()
        
        if not ret:
            time.sleep(0.05)
            continue
        
        if vision_mode != "normal":
            frame = apply_vision(frame, vision_mode, intensity)
        
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/stream')
def video_stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/status')
def status():
    with camera_lock:
        cam = get_camera()
        active_ok = cam is not None and cam.isOpened()
        active_idx = camera_index

    # Do not probe here (can disturb active stream). Use cached list + active fallback.
    devices = list(devices_cache)
    if active_ok and not any(d.get('index') == active_idx for d in devices):
        devices.insert(0, {"index": active_idx, "name": f"Camera {active_idx} (active)"})
    
    return jsonify({
        "camera_active": active_ok,
        "camera_index": camera_index,
        "vision_mode": vision_mode,
        "intensity": intensity,
        "audio_muted": audio_muted,
        "devices": devices,
        "modes": VISION_MODES
    })


@app.route('/api/devices')
def devices():
    refresh = request.args.get('refresh', '0') in {'1', 'true', 'yes'}
    return jsonify({"devices": probe_devices(force=refresh)})


@app.route('/api/vision', methods=['POST'])
def set_vision():
    global vision_mode, intensity
    data = request.json or {}
    if 'mode' in data and data['mode'] in VISION_MODES:
        vision_mode = data['mode']
    if 'intensity' in data:
        intensity = max(1, min(10, int(data['intensity'])))
    return jsonify({"vision_mode": vision_mode, "intensity": intensity})


@app.route('/api/camera', methods=['POST'])
def set_camera():
    global camera, camera_index
    data = request.json or {}
    if 'index' in data:
        requested = int(data['index'])
        with camera_lock:
            # Validate new camera before switching, to avoid broken stream state.
            new_cam = _open_camera(requested)
            if new_cam is None:
                return jsonify({"error": f"Camera {requested} not available", "camera_index": camera_index}), 400

            old_cam = camera
            camera = new_cam
            camera_index = requested
            if old_cam:
                old_cam.release()

        probe_devices(force=True)
        return jsonify({"camera_index": camera_index, "ok": True})
    return jsonify({"error": "No index provided"}), 400


@app.route('/api/snapshot')
def snapshot():
    """Capture a single frame as JPEG."""
    with camera_lock:
        cam = get_camera()
        ret, frame = cam.read()
    if ret:
        if vision_mode != "normal":
            frame = apply_vision(frame, vision_mode, intensity)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    return jsonify({"error": "Capture failed"}), 500


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8910
    print(f"🎥 QuickCam Server starting on http://127.0.0.1:{port}")
    print(f"📡 MJPEG stream: http://127.0.0.1:{port}/stream")
    app.run(host='127.0.0.1', port=port, threaded=True)
