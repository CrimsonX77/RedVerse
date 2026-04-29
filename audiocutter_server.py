#!/usr/bin/env python3
"""
Audio Cutter Server — Audio splitting backend
Split any audio file into N equal parts.
Port 8914 | Part of RedVerse Agency Scripts
"""
import sys, os, tempfile, shutil
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

def _ffprobe_duration(path):
    """Return duration in milliseconds using ffprobe."""
    import subprocess, json
    r = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', path],
        capture_output=True, text=True, timeout=30
    )
    data = json.loads(r.stdout)
    for s in data.get('streams', []):
        if s.get('codec_type') == 'audio' and s.get('duration'):
            return int(float(s['duration']) * 1000)
    return None


@app.route('/api/split', methods=['POST'])
def split_audio():
    import subprocess
    f = request.files.get('file')
    parts = int(request.form.get('parts', 2))
    if not f:
        return jsonify({"error": "No file"}), 400
    if parts < 1 or parts > 100:
        return jsonify({"error": "Parts must be 1-100"}), 400

    ext = os.path.splitext(f.filename)[1] or '.mp3'
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    f.save(tmp.name)
    tmp.close()

    try:
        duration_ms = _ffprobe_duration(tmp.name)
        if duration_ms is None:
            return jsonify({"error": "Cannot read audio duration"}), 400
        part_ms = duration_ms / parts
        base = os.path.splitext(f.filename)[0]
        out_dir = tempfile.mkdtemp()

        for i in range(parts):
            start_s = i * part_ms / 1000
            dur_s = part_ms / 1000
            out_path = os.path.join(out_dir, f"{base}_part{i+1}.mp3")
            subprocess.run(
                ['ffmpeg', '-y', '-ss', str(start_s), '-i', tmp.name,
                 '-t', str(dur_s), '-acodec', 'libmp3lame', '-q:a', '2', out_path],
                capture_output=True, timeout=120
            )

        zip_path = shutil.make_archive(os.path.join(tempfile.gettempdir(), 'split_audio'), 'zip', out_dir)
        shutil.rmtree(out_dir, ignore_errors=True)
        return send_file(zip_path, mimetype='application/zip', as_attachment=True, download_name=f'{base}_split.zip')
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp.name)

@app.route('/api/info', methods=['POST'])
def audio_info():
    import subprocess, json
    f = request.files.get('file')
    if not f:
        return jsonify({"error": "No file"}), 400
    ext = os.path.splitext(f.filename)[1] or '.mp3'
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    f.save(tmp.name)
    tmp.close()
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', tmp.name],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(r.stdout)
        audio_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), {})
        duration_s = float(audio_stream.get('duration', 0))
        return jsonify({
            "filename": f.filename,
            "duration_ms": int(duration_s * 1000),
            "duration_s": round(duration_s, 1),
            "channels": audio_stream.get('channels', 0),
            "sample_rate": int(audio_stream.get('sample_rate', 0)),
            "size_mb": round(os.path.getsize(tmp.name) / 1048576, 2)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp.name)

@app.route('/api/status')
def status():
    return jsonify({"online": True})

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8914
    print(f"✂️ Audio Cutter Server on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, threaded=True)
