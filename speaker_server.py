#!/usr/bin/env python3
"""
Speaker Server — Edge-TTS Backend
Serves voice listing, TTS generation, and audio playback.
Runs alongside the speaker.html cathedral frontend.

Part of the RedVerse Agency Scripts suite.
"""

import asyncio
import tempfile
import os
import json
import sys
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS

import edge_tts
import pygame

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════
CONFIG_FILE = Path.home() / ".aetherion_tts_config.json"
voice_cache = []
is_speaking = False

current_thread = None

# Initialize pygame mixer
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
except:
    pygame.mixer.init()


def load_config():
    defaults = {"voice": "en-GB-SoniaNeural", "rate": 0, "volume": 0, "pitch": 0, "chunk_size": 200}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                defaults.update(json.load(f))
        except:
            pass
    return defaults


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except:
        pass


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/api/voices')
def get_voices():
    """Fetch available Edge-TTS voices."""
    global voice_cache
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voices = loop.run_until_complete(edge_tts.list_voices())
        loop.close()
        voice_cache = voices
        sorted_v = sorted(voices, key=lambda v: (v['Locale'], v['ShortName']))
        return jsonify({"voices": sorted_v, "count": len(sorted_v)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/speak', methods=['POST'])
def speak():
    """Generate TTS and play it."""
    global is_speaking
    data = request.json or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    voice = data.get('voice', 'en-GB-SoniaNeural')
    rate = data.get('rate', 0)
    volume = data.get('volume', 0)
    pitch = data.get('pitch', 0)

    # Save config
    save_config({"voice": voice, "rate": rate, "volume": volume, "pitch": pitch})

    try:
        is_speaking = True
        temp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp.close()

        rate_str = f"{rate:+d}%"
        volume_str = f"{volume:+d}%"
        pitch_str = f"{pitch:+d}Hz"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def generate():
            comm = edge_tts.Communicate(text, voice, rate=rate_str, volume=volume_str, pitch=pitch_str)
            await comm.save(temp.name)

        loop.run_until_complete(generate())
        loop.close()

        # Play audio
        if os.path.exists(temp.name) and os.path.getsize(temp.name) > 100:
            pygame.mixer.music.load(temp.name)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            os.remove(temp.name)
            is_speaking = False
            return jsonify({"status": "complete", "chars": len(text)})
        else:
            is_speaking = False
            return jsonify({"error": "Audio generation failed"}), 500

    except Exception as e:
        is_speaking = False
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate_audio():
    """Generate TTS and return the audio file for download."""
    data = request.json or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    voice = data.get('voice', 'en-GB-SoniaNeural')
    rate = data.get('rate', 0)
    volume = data.get('volume', 0)
    pitch = data.get('pitch', 0)

    try:
        temp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def gen():
            comm = edge_tts.Communicate(text, voice, rate=f"{rate:+d}%", volume=f"{volume:+d}%", pitch=f"{pitch:+d}Hz")
            await comm.save(temp.name)

        loop.run_until_complete(gen())
        loop.close()

        return send_file(temp.name, mimetype='audio/mpeg', as_attachment=True, download_name='lyra-speech.mp3')

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_speech():
    """Stop current playback."""
    global is_speaking
    try:
        pygame.mixer.music.stop()
    except:
        pass
    is_speaking = False
    return jsonify({"status": "stopped"})


@app.route('/api/status')
def status():
    return jsonify({
        "speaking": is_speaking,
        "voices_loaded": len(voice_cache),
        "config": load_config()
    })


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8911
    print(f"🔊 Speaker Server starting on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, threaded=True)
