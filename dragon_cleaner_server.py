#!/usr/bin/env python3
"""
Dragon Cleaner Server — Intelligent disk cleanup backend
Scan → categorize → consult Dave (Ollama) → stage → confirm → delete.

Port 8917 | Part of RedVerse Agency Scripts

Dependencies:
    pip install flask flask-cors requests

External:
    Ollama running locally with crimsondragonx7/dave pulled:
        ollama pull crimsondragonx7/dave
    (Falls back to pure-heuristic mode if Ollama is unreachable.)
"""
import sys
import os
import json
import time
import uuid
import hashlib
import fnmatch
import shutil
import threading
from pathlib import Path
from collections import defaultdict
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS

try:
    import requests
except ImportError:
    requests = None

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════
# CONFIG — ported from dragon_cleaner.py
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROTECTED = {
    "/proc", "/sys", "/dev", "/run", "/boot",
    "/usr/bin", "/usr/sbin", "/usr/lib", "/usr/lib64",
    "/bin", "/sbin", "/lib", "/lib64",
    "/etc", "/var/lib/dpkg", "/var/lib/apt",
    "/snap/core", "/snap/snapd",
    # Windows
    "c:\\windows", "c:\\program files", "c:\\program files (x86)",
    # macOS
    "/system", "/library/system", "/private/var/db",
}

JUNK_PATTERNS = [
    "*.tmp", "*.temp", "~$*", "*.bak", "*.old", "*.orig",
    "thumbs.db", ".ds_store", "desktop.ini", "*.log",
    "*.cache", "*.swp", "*.swo", "core.*", "*.pid",
    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache",
    "node_modules", ".npm", ".cache",
]

LARGE_FILE_MB = 100

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
DAVE_MODEL = os.environ.get('DAVE_MODEL', 'crimsondragonx7/dave:latest')

# ═══════════════════════════════════════════════════════════════
# STATE — in-memory scan sessions
# ═══════════════════════════════════════════════════════════════

SCANS = {}  # scan_id -> {'state','results','progress','started','root'}
SCAN_LOCK = threading.Lock()


def is_protected(path: str) -> bool:
    """Check if a path is system-protected. Uses canonicalized path to prevent bypasses."""
    try:
        # Canonicalize the path to resolve symlinks and relative paths
        canonical = os.path.realpath(path)
        p = canonical.lower().replace('\\', '/')
    except (OSError, ValueError):
        # If we can't resolve the path, treat it as protected (fail-safe)
        return True
    
    for proto in SYSTEM_PROTECTED:
        proto_canonical = proto.lower().replace('\\', '/')
        if p.startswith(proto_canonical):
            return True
    return False


def is_junk(path: str) -> bool:
    name = os.path.basename(path).lower()
    for pattern in JUNK_PATTERNS:
        if fnmatch.fnmatch(name, pattern.lower()):
            return True
    # Directory-style junk: anywhere in the path
    low = path.lower().replace('\\', '/')
    for seg in ('/__pycache__/', '/node_modules/', '/.pytest_cache/',
                '/.mypy_cache/', '/.ruff_cache/', '/.cache/'):
        if seg in low:
            return True
    return False


def hash_file(path: str, chunk_size: int = 65536, max_size: int = 500 * 1024 * 1024):
    """Hash up to 500MB; skip anything bigger (dedup by hash is pointless)."""
    try:
        if os.path.getsize(path) > max_size:
            return None
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def fmt_size(b: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# ═══════════════════════════════════════════════════════════════
# SCANNER
# ═══════════════════════════════════════════════════════════════

def run_scan(scan_id: str, root: str, skip_system: bool = True, max_files: int = 100000):
    results = {
        "duplicates": {},
        "large_files": [],
        "junk_files": [],
        "total_size": 0,
        "total_files": 0,
        "errors": 0,
        "scan_root": root,
    }
    hash_map = defaultdict(list)
    count = 0

    with SCAN_LOCK:
        SCANS[scan_id]['state'] = 'scanning'

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            with SCAN_LOCK:
                if SCANS[scan_id].get('stop'):
                    results['state'] = 'stopped'
                    break
                SCANS[scan_id]['progress'] = {'current_dir': dirpath, 'files_seen': count}

            if skip_system and is_protected(dirpath):
                dirnames.clear()
                continue

            # Skip hidden dirs unless they're user config
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith('.') or d in {'.config', '.local', '.cache'}
            ]

            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    if os.path.islink(fpath):
                        continue
                    st = os.stat(fpath)
                    fsize = st.st_size
                except (PermissionError, OSError):
                    results["errors"] += 1
                    continue

                if fsize == 0:
                    continue

                count += 1
                if count > max_files:
                    results['truncated'] = True
                    break

                results["total_files"] += 1
                results["total_size"] += fsize

                # Junk
                if is_junk(fpath):
                    results["junk_files"].append({"path": fpath, "size": fsize})

                # Large
                if fsize > LARGE_FILE_MB * 1024 * 1024:
                    results["large_files"].append({
                        "path": fpath, "size": fsize,
                        "mtime": int(st.st_mtime),
                    })

                # Hash for dedup (skip huge files and junk)
                if fsize < 500 * 1024 * 1024 and not is_junk(fpath):
                    h = hash_file(fpath)
                    if h:
                        hash_map[h].append({"path": fpath, "size": fsize})

            if count > max_files:
                break

    except Exception as e:
        with SCAN_LOCK:
            SCANS[scan_id]['state'] = 'error'
            SCANS[scan_id]['error'] = str(e)
        return

    # Extract real duplicates
    for h, paths in hash_map.items():
        if len(paths) > 1:
            results["duplicates"][h] = paths

    # Sort large files biggest-first
    results["large_files"].sort(key=lambda x: x["size"], reverse=True)

    # Reclaimable estimate: all junk + duplicate redundancy
    reclaimable = sum(j["size"] for j in results["junk_files"])
    for paths in results["duplicates"].values():
        # Keep one of each duplicate group
        reclaimable += sum(p["size"] for p in paths[1:])
    results["reclaimable"] = reclaimable

    with SCAN_LOCK:
        SCANS[scan_id]['state'] = 'complete'
        SCANS[scan_id]['results'] = results


# ═══════════════════════════════════════════════════════════════
# DAVE — Ollama consultation (with graceful heuristic fallback)
# ═══════════════════════════════════════════════════════════════

def dave_available() -> bool:
    if not requests:
        return False
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=1.5)
        if r.status_code != 200:
            return False
        tags = r.json().get('models', [])
        return any(DAVE_MODEL.split(':')[0] in m.get('name', '') for m in tags)
    except Exception:
        return False


def heuristic_verdict(candidate: dict) -> dict:
    """Fallback verdict when Dave is unreachable."""
    path = candidate['path']
    kind = candidate.get('kind', 'file')
    size_mb = candidate.get('size', 0) / 1048576
    low = path.lower().replace('\\', '/')

    # Always-safe caches
    for cache in ('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
                  'thumbs.db', '.ds_store'):
        if cache in low:
            return {
                'verdict': 'yeet', 'confidence': 0.97,
                'reason': 'Regenerable cache. Always safe.',
                'risk_if_wrong': 'low', 'reclaim_mb': round(size_mb, 2),
            }
    # node_modules
    if '/node_modules/' in low or low.endswith('/node_modules'):
        return {
            'verdict': 'yeet', 'confidence': 0.80,
            'reason': 'node_modules. npm install rebuilds it.',
            'risk_if_wrong': 'medium', 'reclaim_mb': round(size_mb, 2),
        }
    # Duplicates
    if kind == 'duplicate':
        return {
            'verdict': 'yeet', 'confidence': 0.70,
            'reason': 'Exact duplicate by hash.',
            'risk_if_wrong': 'medium', 'reclaim_mb': round(size_mb, 2),
        }
    # Large files
    if kind == 'large':
        return {
            'verdict': 'ask_human', 'confidence': 0.50,
            'reason': f"Large file ({size_mb:.1f} MB). Your call.",
            'risk_if_wrong': 'high', 'reclaim_mb': round(size_mb, 2),
        }
    # Default
    return {
        'verdict': 'ask_human', 'confidence': 0.40,
        'reason': "Unfamiliar. Not guessing.",
        'risk_if_wrong': 'high', 'reclaim_mb': round(size_mb, 2),
    }


def ask_dave(candidates: list) -> list:
    """
    Send a batch of candidates to Dave. Returns list of verdicts
    in the same order. Falls back to heuristics on any failure.
    """
    if not dave_available():
        return [heuristic_verdict(c) for c in candidates]

    prompt = (
        "Review these filesystem candidates for deletion. Return a JSON "
        "array of verdict objects, one per candidate, in the same order.\n\n"
        "Candidates:\n" + json.dumps(candidates, indent=2)
    )

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": DAVE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.15, "num_ctx": 8192},
            },
            timeout=120,
        )
        if r.status_code != 200:
            return [heuristic_verdict(c) for c in candidates]
        content = r.json().get('message', {}).get('content', '')
        parsed = json.loads(content)
        # Dave might return {verdicts:[...]} or a bare list
        if isinstance(parsed, dict) and 'verdicts' in parsed:
            parsed = parsed['verdicts']
        if not isinstance(parsed, list) or len(parsed) != len(candidates):
            return [heuristic_verdict(c) for c in candidates]
        return parsed
    except Exception:
        return [heuristic_verdict(c) for c in candidates]


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.route('/api/status')
def status():
    return jsonify({
        'online': True,
        'dave_available': dave_available(),
        'ollama_url': OLLAMA_URL,
        'dave_model': DAVE_MODEL,
        'scan_sessions': len(SCANS),
    })


@app.route('/api/scan/start', methods=['POST'])
def scan_start():
    data = request.get_json(force=True)
    root = data.get('path', '').strip()
    if not root or not os.path.isdir(root):
        return jsonify({'error': 'Invalid path'}), 400
    if is_protected(root):
        return jsonify({'error': 'Path is system-protected. Pick a user directory.'}), 400

    scan_id = uuid.uuid4().hex[:12]
    with SCAN_LOCK:
        SCANS[scan_id] = {
            'state': 'queued',
            'root': root,
            'started': time.time(),
            'progress': {'current_dir': '', 'files_seen': 0},
        }
    threading.Thread(
        target=run_scan,
        args=(scan_id, root, data.get('skip_system', True)),
        daemon=True,
    ).start()
    return jsonify({'scan_id': scan_id, 'state': 'queued'})


@app.route('/api/scan/status/<scan_id>')
def scan_status(scan_id):
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
        if not s:
            return jsonify({'error': 'Unknown scan id'}), 404
        return jsonify({
            'scan_id': scan_id,
            'state': s.get('state'),
            'progress': s.get('progress', {}),
            'error': s.get('error'),
        })


@app.route('/api/scan/results/<scan_id>')
def scan_results(scan_id):
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
        if not s:
            return jsonify({'error': 'Unknown scan id'}), 404
        if s.get('state') != 'complete':
            return jsonify({'error': f"Scan not complete (state={s.get('state')})"}), 409

        r = s['results']
        # Trim for transport
        payload = {
            'scan_id': scan_id,
            'root': r['scan_root'],
            'total_files': r['total_files'],
            'total_size': r['total_size'],
            'total_size_human': fmt_size(r['total_size']),
            'errors': r['errors'],
            'reclaimable': r.get('reclaimable', 0),
            'reclaimable_human': fmt_size(r.get('reclaimable', 0)),
            'junk_count': len(r['junk_files']),
            'duplicate_groups': len(r['duplicates']),
            'large_count': len(r['large_files']),
            # Send detail payloads
            'junk_files': r['junk_files'][:500],
            'large_files': r['large_files'][:200],
            'duplicates': [
                {'hash': h[:12], 'paths': paths}
                for h, paths in list(r['duplicates'].items())[:200]
            ],
        }
        return jsonify(payload)


@app.route('/api/scan/stop/<scan_id>', methods=['POST'])
def scan_stop(scan_id):
    with SCAN_LOCK:
        s = SCANS.get(scan_id)
        if not s:
            return jsonify({'error': 'Unknown scan id'}), 404
        s['stop'] = True
    return jsonify({'ok': True})


@app.route('/api/dave/verdict', methods=['POST'])
def dave_verdict():
    """
    Batch-consult Dave on a list of candidates.
    Request: {"candidates": [{"path":..., "size":..., "kind": "junk"|"large"|"duplicate"|"file"}, ...]}
    Response: {"verdicts": [...], "source": "dave"|"heuristic"}
    """
    data = request.get_json(force=True)
    candidates = data.get('candidates', [])
    if not isinstance(candidates, list) or not candidates:
        return jsonify({'error': 'No candidates'}), 400
    if len(candidates) > 100:
        return jsonify({'error': 'Too many candidates (max 100 per batch)'}), 400

    verdicts = ask_dave(candidates)
    return jsonify({
        'verdicts': verdicts,
        'source': 'dave' if dave_available() else 'heuristic',
    })


@app.route('/api/delete', methods=['POST'])
def delete_paths():
    """
    Delete paths that were discovered in a specific scan session.
    Requires explicit confirm=true and a valid scan_id.
    Request: {"scan_id": "...", "paths": [...], "confirm": true}
    
    Security: Only allows deletion of paths that:
    1. Were discovered in the specified scan session
    2. Are within the scan root directory (after canonicalization)
    3. Are not system-protected (checked on canonical path)
    """
    data = request.get_json(force=True)
    scan_id = data.get('scan_id', '').strip()
    paths = data.get('paths', [])
    
    if not data.get('confirm') is True:
        return jsonify({'error': 'Confirmation required (confirm: true)'}), 400
    if not isinstance(paths, list) or not paths:
        return jsonify({'error': 'No paths'}), 400
    if not scan_id:
        return jsonify({'error': 'scan_id required'}), 400

    # Verify scan session exists and is complete
    with SCAN_LOCK:
        scan = SCANS.get(scan_id)
        if not scan:
            return jsonify({'error': 'Unknown scan_id'}), 404
        if scan.get('state') != 'complete':
            return jsonify({'error': f"Scan not complete (state={scan.get('state')})"}), 409
        
        scan_results = scan.get('results')
        if not scan_results:
            return jsonify({'error': 'No scan results available'}), 409
        
        scan_root = scan_results.get('scan_root')
        if not scan_root:
            return jsonify({'error': 'Scan root not found'}), 500

    # Canonicalize scan root once
    try:
        canonical_scan_root = os.path.realpath(scan_root)
    except (OSError, ValueError):
        return jsonify({'error': 'Cannot resolve scan root'}), 500

    # Build a set of all paths discovered in this scan for validation
    discovered_paths = set()
    for junk in scan_results.get('junk_files', []):
        discovered_paths.add(junk['path'])
    for large in scan_results.get('large_files', []):
        discovered_paths.add(large['path'])
    for dup_group in scan_results.get('duplicates', {}).values():
        for dup in dup_group:
            discovered_paths.add(dup['path'])

    deleted, failed, freed = [], [], 0
    for p in paths:
        # Validate path was discovered in this scan
        if p not in discovered_paths:
            failed.append({'path': p, 'error': 'path not from this scan session'})
            continue
        
        # Canonicalize the path to prevent traversal attacks
        try:
            canonical_path = os.path.realpath(p)
        except (OSError, ValueError):
            failed.append({'path': p, 'error': 'cannot resolve path'})
            continue
        
        # Verify path is within scan root (containment check)
        if not canonical_path.startswith(canonical_scan_root + os.sep) and canonical_path != canonical_scan_root:
            failed.append({'path': p, 'error': 'path outside scan root'})
            continue
        
        # Check system protection on canonical path
        if is_protected(canonical_path):
            failed.append({'path': p, 'error': 'protected'})
            continue
        
        # Verify path still exists
        if not os.path.exists(canonical_path):
            failed.append({'path': p, 'error': 'not found'})
            continue
        
        # Perform deletion
        try:
            if os.path.isdir(canonical_path) and not os.path.islink(canonical_path):
                size = _dir_size(canonical_path)
                shutil.rmtree(canonical_path)
                freed += size
            else:
                size = os.path.getsize(canonical_path)
                os.remove(canonical_path)
                freed += size
            deleted.append(p)
        except Exception as e:
            failed.append({'path': p, 'error': str(e)})

    return jsonify({
        'deleted': deleted,
        'failed': failed,
        'freed': freed,
        'freed_human': fmt_size(freed),
    })


def _dir_size(path):
    total = 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                pass
    return total


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8917
    print(f'🐉 Dragon Cleaner Server on http://127.0.0.1:{port}')
    print(f'   Dave model: {DAVE_MODEL}')
    print(f'   Ollama URL: {OLLAMA_URL}')
    print(f'   Dave reachable: {"✓" if dave_available() else "✗ (heuristic fallback active)"}')
    app.run(host='127.0.0.1', port=port, threaded=True)
