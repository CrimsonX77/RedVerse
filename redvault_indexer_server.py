#!/usr/bin/env python3
"""
RedVault Indexer Server — Project discovery backend
Scans directories for YOUR projects. Ignores node_modules.

Port 8920 | Part of RedVerse Agency Scripts

Wraps redvault_indexer.py's RedVaultIndexer class, exposes async scan,
searchable catalog, and report export over HTTP.

Dependencies:
    pip install flask flask-cors

No LLM, no heavy libs. Pure-stdlib indexer with a thin Flask jacket.
"""
import sys
import os
import json
import time
import uuid
import threading
import importlib.util
from pathlib import Path
from dataclasses import asdict
from flask import Flask, jsonify, request, Response, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════
# Load the indexer module from wherever it lives alongside us
# ═══════════════════════════════════════════════════════════════

def load_indexer_module():
    """Locate redvault_indexer.py next to this server or in cwd."""
    here = Path(__file__).resolve().parent
    for candidate in [
        here / 'redvault_indexer.py',
        Path.cwd() / 'redvault_indexer.py',
    ]:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location('redvault_indexer', candidate)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    # Fall back: allow users to drop it anywhere on PYTHONPATH
    try:
        import redvault_indexer
        return redvault_indexer
    except ImportError as e:
        raise RuntimeError(
            "redvault_indexer.py not found. Place it next to this server "
            "or on PYTHONPATH."
        ) from e

try:
    indexer_mod = load_indexer_module()
    RedVaultIndexer = indexer_mod.RedVaultIndexer
    IndexedFile = indexer_mod.IndexedFile
    print(f"✓ Loaded RedVaultIndexer from {indexer_mod.__file__}")
except RuntimeError as e:
    print(f"✗ {e}")
    RedVaultIndexer = None
    IndexedFile = None


# ═══════════════════════════════════════════════════════════════
# STATE — scan sessions
# ═══════════════════════════════════════════════════════════════

SCANS = {}        # scan_id -> session dict
SCAN_LOCK = threading.Lock()


def run_scan(scan_id: str, root: str, deep_scan: bool):
    """Background worker — runs indexer and stores the result."""
    try:
        with SCAN_LOCK:
            SCANS[scan_id]['state'] = 'scanning'

        idx = RedVaultIndexer(deep_scan=deep_scan, verbose=False)
        idx.scan(root)

        with SCAN_LOCK:
            SCANS[scan_id]['indexer'] = idx
            SCANS[scan_id]['state'] = 'complete'
            SCANS[scan_id]['finished_at'] = time.time()
    except Exception as e:
        with SCAN_LOCK:
            SCANS[scan_id]['state'] = 'error'
            SCANS[scan_id]['error'] = str(e)


# ═══════════════════════════════════════════════════════════════
# Serialization helpers
# ═══════════════════════════════════════════════════════════════

def file_to_dict(f) -> dict:
    return {
        'path': f.path,
        'name': f.name,
        'extension': f.extension,
        'category': f.category,
        'size': f.size_bytes,
        'modified': f.modified,
        'is_entrypoint': f.is_entrypoint,
        'is_soul_schema': f.is_soul_schema,
        'title': f.title,
        'description': f.description,
        'parent_project': f.parent_project,
    }


def project_to_dict(p) -> dict:
    return {
        'root_dir': p.root_dir,
        'name': p.name,
        'total_size': p.total_size,
        'last_modified': p.last_modified,
        'file_count': len(p.files),
        'categories': dict(p.categories),
        'has_entrypoint': p.has_entrypoint,
        'has_html': p.has_html,
        'has_python': p.has_python,
        'has_config': p.has_config,
    }


def fmt_size(b: int) -> str:
    for u in ('B','KB','MB','GB','TB'):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.route('/api/status')
def status():
    return jsonify({
        'online': True,
        'indexer_loaded': RedVaultIndexer is not None,
        'active_scans': sum(1 for s in SCANS.values() if s.get('state') == 'scanning'),
        'total_sessions': len(SCANS),
    })


@app.route('/api/scan/start', methods=['POST'])
def scan_start():
    if RedVaultIndexer is None:
        return jsonify({'error': 'indexer module not loaded'}), 500

    data = request.get_json(force=True)
    root = (data.get('path') or '').strip() or os.path.expanduser('~')
    deep = bool(data.get('deep_scan', False))

    if not os.path.isdir(root):
        return jsonify({'error': f'not a directory: {root}'}), 400

    scan_id = uuid.uuid4().hex[:12]
    with SCAN_LOCK:
        SCANS[scan_id] = {
            'state': 'queued',
            'root': root,
            'deep_scan': deep,
            'started_at': time.time(),
        }
    threading.Thread(target=run_scan, args=(scan_id, root, deep), daemon=True).start()
    return jsonify({'scan_id': scan_id, 'state': 'queued', 'root': root})


@app.route('/api/scan/status/<scan_id>')
def scan_status(scan_id):
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
        if not s: return jsonify({'error': 'unknown scan id'}), 404
        resp = {
            'scan_id': scan_id,
            'state': s.get('state'),
            'root': s.get('root'),
            'deep_scan': s.get('deep_scan'),
            'elapsed': round(time.time() - s.get('started_at', 0), 1),
        }
        if s.get('state') == 'scanning' and s.get('indexer'):
            # Live progress from the indexer's stats dict
            resp['progress'] = dict(s['indexer'].stats)
        if s.get('error'): resp['error'] = s['error']
        return jsonify(resp)


@app.route('/api/scan/summary/<scan_id>')
def scan_summary(scan_id):
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
    if not s: return jsonify({'error': 'unknown scan id'}), 404
    if s.get('state') != 'complete':
        return jsonify({'error': f"scan not complete (state={s.get('state')})"}), 409

    idx = s['indexer']
    by_cat = {}
    for f in idx.all_files:
        by_cat[f.category] = by_cat.get(f.category, 0) + 1

    projects = [project_to_dict(p) for p in idx.projects.values()]
    projects.sort(key=lambda p: p['last_modified'], reverse=True)

    return jsonify({
        'scan_id': scan_id,
        'root': s['root'],
        'stats': idx.stats,
        'stats_human': {
            'total_size': fmt_size(idx.stats['total_size']),
            'scan_time_s': round(idx.stats['scan_time'], 2),
        },
        'category_counts': by_cat,
        'project_count': len(idx.projects),
        'projects': projects,
        'entrypoints':  [file_to_dict(f) for f in idx.all_files if f.is_entrypoint][:200],
        'soul_schemas': [file_to_dict(f) for f in idx.all_files if f.is_soul_schema][:200],
    })


@app.route('/api/scan/search/<scan_id>')
def scan_search(scan_id):
    """
    Fuzzy search across the indexed file list.
    Query params:
        q           — match on name/path/title/description (substring, case-insensitive)
        category    — filter by category
        project     — filter by project name
        entrypoint  — 'true' to only show entrypoints
        soul        — 'true' to only show soul schemas
        limit       — default 200, max 2000
    """
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
    if not s: return jsonify({'error': 'unknown scan id'}), 404
    if s.get('state') != 'complete':
        return jsonify({'error': 'scan not complete'}), 409

    q = (request.args.get('q') or '').lower().strip()
    cat = request.args.get('category')
    proj = request.args.get('project')
    entry_only = request.args.get('entrypoint') == 'true'
    soul_only = request.args.get('soul') == 'true'
    limit = max(1, min(2000, int(request.args.get('limit', 200))))

    out = []
    for f in s['indexer'].all_files:
        if cat and f.category != cat: continue
        if proj and f.parent_project != proj: continue
        if entry_only and not f.is_entrypoint: continue
        if soul_only and not f.is_soul_schema: continue
        if q:
            hay = ' '.join(filter(None, [
                f.name, f.path, f.title, f.description
            ])).lower()
            if q not in hay: continue
        out.append(file_to_dict(f))
        if len(out) >= limit: break
    return jsonify({'count': len(out), 'results': out, 'truncated': len(out) >= limit})


@app.route('/api/scan/project/<scan_id>/<path:project_key>')
def scan_project(scan_id, project_key):
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
    if not s: return jsonify({'error': 'unknown scan id'}), 404
    if s.get('state') != 'complete':
        return jsonify({'error': 'scan not complete'}), 409

    # project_key comes URL-encoded; match either by exact root_dir or by name
    idx = s['indexer']
    proj = idx.projects.get(project_key)
    if not proj:
        for k, p in idx.projects.items():
            if p.name == project_key or k.endswith(project_key):
                proj = p; break
    if not proj: return jsonify({'error': 'project not found'}), 404

    files_sorted = sorted(proj.files, key=lambda x: (x.category, x.name))
    return jsonify({
        'project': project_to_dict(proj),
        'files': [file_to_dict(f) for f in files_sorted],
    })


@app.route('/api/scan/report/<scan_id>')
def scan_report(scan_id):
    """Returns the indexer's report in the requested format (markdown|json)."""
    fmt = (request.args.get('format') or 'markdown').lower()
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
    if not s: return jsonify({'error': 'unknown scan id'}), 404
    if s.get('state') != 'complete':
        return jsonify({'error': 'scan not complete'}), 409

    body = s['indexer'].generate_report(output_format=fmt)
    if fmt == 'json':
        return Response(body, mimetype='application/json',
                        headers={'Content-Disposition': 'attachment; filename=redvault_report.json'})
    return Response(body, mimetype='text/markdown',
                    headers={'Content-Disposition': 'attachment; filename=redvault_report.md'})


@app.route('/api/drives')
def drives():
    """List external drives detected by the indexer's helper."""
    if not hasattr(indexer_mod, 'detect_external_drives'):
        return jsonify({'drives': []})
    try:
        drives = [str(d) for d in indexer_mod.detect_external_drives()]
    except Exception:
        drives = []
    return jsonify({'drives': drives})


@app.route('/api/scans')
def list_scans():
    with SCAN_LOCK:
        out = []
        for sid, s in SCANS.items():
            out.append({
                'scan_id': sid,
                'state': s.get('state'),
                'root': s.get('root'),
                'deep_scan': s.get('deep_scan'),
                'started_at': s.get('started_at'),
            })
    out.sort(key=lambda x: x.get('started_at', 0), reverse=True)
    return jsonify({'scans': out})


@app.route('/api/scan/delete/<scan_id>', methods=['POST'])
def scan_delete(scan_id):
    with SCAN_LOCK:
        if scan_id in SCANS:
            del SCANS[scan_id]
            return jsonify({'ok': True})
    return jsonify({'error': 'unknown'}), 404


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8920
    print(f'📇 RedVault Indexer Server on http://127.0.0.1:{port}')
    if RedVaultIndexer is None:
        print('   ⚠ indexer module not loaded — place redvault_indexer.py adjacent')
    app.run(host='127.0.0.1', port=port, threaded=True)
