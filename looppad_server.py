#!/usr/bin/env python3
"""
DJ Loop Pad Server — Audio loop backend
26-channel keyed audio loops with pygame.
Port 8912 | Part of RedVerse Agency Scripts
"""
import sys, os, pygame
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = os.path.expanduser("~/.looppad_sounds")
os.makedirs(UPLOAD_DIR, exist_ok=True)

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
pygame.mixer.set_num_channels(26)

sounds = {}    # key -> pygame.Sound
sound_paths = {}  # key -> file path
channels = {}  # key -> pygame.Channel
volume = 1.0

def get_channel(key):
    if key not in channels:
        channels[key] = pygame.mixer.Channel(ord(key) - 65)
    return channels[key]

@app.route('/api/status')
def status():
    active = {k: channels[k].get_busy() for k in channels if channels[k].get_busy()}
    loaded = {k: os.path.basename(sound_paths[k]) for k in sound_paths}
    return jsonify({"loaded": list(sounds.keys()), "playing": list(active.keys()), "volume": volume})

@app.route('/api/assign', methods=['POST'])
def assign():
    key = request.form.get('key', '').upper()
    if not key or len(key) != 1 or key < 'A' or key > 'Z':
        return jsonify({"error": "Invalid key"}), 400
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({"error": "No file"}), 400
    fn = secure_filename(f"{key}_{f.filename}")
    path = os.path.join(UPLOAD_DIR, fn)
    f.save(path)
    try:
        snd = pygame.mixer.Sound(path)
        snd.set_volume(volume)
        sounds[key] = snd
        sound_paths[key] = path
        return jsonify({"key": key, "file": fn})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/toggle', methods=['POST'])
def toggle():
    data = request.json or {}
    key = data.get('key', '').upper()
    if key not in sounds:
        return jsonify({"error": f"No sound on {key}"}), 400
    ch = get_channel(key)
    if ch.get_busy():
        ch.stop()
        return jsonify({"key": key, "state": "stopped"})
    else:
        ch.play(sounds[key], loops=-1)
        return jsonify({"key": key, "state": "playing"})

@app.route('/api/stop', methods=['POST'])
def stop_all():
    for ch in channels.values():
        ch.stop()
    return jsonify({"status": "all stopped"})

@app.route('/api/volume', methods=['POST'])
def set_volume():
    global volume
    data = request.json or {}
    volume = max(0, min(1, data.get('volume', 1.0)))
    for s in sounds.values():
        s.set_volume(volume)
    return jsonify({"volume": volume})

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8912
    print(f"🎵 Loop Pad Server on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, threaded=True)
