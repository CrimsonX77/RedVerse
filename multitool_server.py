#!/usr/bin/env python3
"""
MultiTool Server — File conversion & utility backend
WEBP→JPG, JSON/JSONL merge, web scrape, PDF merge.
Port 8913 | Part of RedVerse Agency Scripts
"""
import sys, os, json, tempfile, shutil
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

@app.route('/api/convert-webp', methods=['POST'])
def convert_webp():
    from PIL import Image
    files = request.files.getlist('files')
    if not files:
        return jsonify({"error": "No files"}), 400
    results = []
    out_dir = tempfile.mkdtemp()
    for f in files:
        if f.filename.lower().endswith('.webp'):
            path = os.path.join(out_dir, secure_filename(f.filename))
            f.save(path)
            jpg_name = os.path.splitext(f.filename)[0] + '.jpg'
            jpg_path = os.path.join(out_dir, jpg_name)
            with Image.open(path) as img:
                img.convert("RGB").save(jpg_path, "JPEG", quality=92)
            results.append(jpg_name)
            os.remove(path)
    if len(results) == 1:
        return send_file(os.path.join(out_dir, results[0]), mimetype='image/jpeg', as_attachment=True, download_name=results[0])
    # Multiple: zip them
    zip_path = shutil.make_archive(os.path.join(tempfile.gettempdir(), 'converted'), 'zip', out_dir)
    return send_file(zip_path, mimetype='application/zip', as_attachment=True, download_name='converted.zip')

@app.route('/api/merge-json', methods=['POST'])
def merge_json():
    files = request.files.getlist('files')
    fmt = request.form.get('format', 'jsonl')
    consolidated = []
    for f in files:
        text = f.read().decode('utf-8', errors='ignore')
        if f.filename.endswith('.jsonl'):
            for line in text.strip().split('\n'):
                if line.strip():
                    try: consolidated.append(json.loads(line))
                    except: pass
        else:
            try:
                data = json.loads(text)
                if isinstance(data, list): consolidated.extend(data)
                else: consolidated.append(data)
            except: pass
    tmp = tempfile.NamedTemporaryFile(suffix='.'+fmt, delete=False, mode='w')
    if fmt == 'json':
        json.dump(consolidated, tmp, indent=2)
    else:
        for entry in consolidated:
            tmp.write(json.dumps(entry) + '\n')
    tmp.close()
    return send_file(tmp.name, as_attachment=True, download_name=f'merged.{fmt}')

@app.route('/api/scrape', methods=['POST'])
def scrape():
    from bs4 import BeautifulSoup
    import requests as req
    data = request.json or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({"error": "No URL"}), 400
    try:
        r = req.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return jsonify({"url": url, "chars": len(text), "text": text[:50000]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/merge-pdf', methods=['POST'])
def merge_pdf():
    from PyPDF2 import PdfMerger
    files = request.files.getlist('files')
    if not files:
        return jsonify({"error": "No files"}), 400
    merger = PdfMerger()
    for f in files:
        tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        f.save(tmp.name)
        merger.append(tmp.name)
    out = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    merger.write(out.name)
    merger.close()
    return send_file(out.name, mimetype='application/pdf', as_attachment=True, download_name='merged.pdf')

@app.route('/api/status')
def status():
    return jsonify({"online": True, "tools": ["webp-convert", "json-merge", "web-scrape", "pdf-merge"]})

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8913
    print(f"🔧 MultiTool Server on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, threaded=True)
