#!/usr/bin/env python3
"""
Void Eater Server — Paranoid recycle bin with proper shred
Port 8919 | Part of RedVerse Agency Scripts

MODES:
  1. INGEST → files move to ~/.voideater/vault, manifest tracks origin + expiry
  2. RESTORE → move back to original path (or new path if origin is occupied)
  3. SHRED NOW → skip buffer, destroy immediately
  4. SWEEP → background thread shreds expired items

SHRED METHOD (applied on expiry or manual shred):
  - Multi-pass random overwrite (configurable, default 3)
  - Filename scramble to random hex
  - Truncate to zero
  - os.remove()
  Note: on modern SSDs with wear-leveling + TRIM, overwrite semantics are
  weaker than on spinning disks. This is documented to the user on the page.

Dependencies:
    pip install flask flask-cors
"""
import sys
import os
import io
import json
import time
import uuid
import shutil
import secrets
import threading
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB per upload

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

VAULT_ROOT = Path(os.environ.get('VOIDEATER_VAULT', os.path.expanduser('~/.voideater')))
VAULT_ITEMS = VAULT_ROOT / 'items'
MANIFEST_FILE = VAULT_ROOT / 'manifest.json'
CONFIG_FILE = VAULT_ROOT / 'config.json'

DEFAULT_CONFIG = {
    'retention_hours': 24,
    'shred_passes': 3,
    'sweep_interval_s': 300,      # check expiries every 5 min
    'max_vault_size_mb': 10240,   # 10GB soft cap — warn on hit
    'scramble_names': True,
}

# Hardcoded refuse list — Void Eater will not swallow these paths.
# Same spirit as Dragon Cleaner's SYSTEM_PROTECTED.
PROTECTED_ROOTS = [
    '/proc', '/sys', '/dev', '/run', '/boot',
    '/usr', '/bin', '/sbin', '/lib', '/lib64', '/etc',
    '/var/lib', '/var/log',
    'c:\\windows', 'c:\\program files', 'c:\\program files (x86)',
    '/system', '/library/system',
]

# ═══════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════

manifest_lock = threading.Lock()
manifest = {}   # item_id -> record
config = dict(DEFAULT_CONFIG)


def ensure_vault():
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    VAULT_ITEMS.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(VAULT_ROOT, 0o700)
    except Exception:
        pass  # non-fatal on Windows


def load_state():
    global manifest, config
    ensure_vault()
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, 'r') as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items():
                    if k in DEFAULT_CONFIG:
                        config[k] = v
        except Exception:
            pass


def save_manifest():
    with manifest_lock:
        try:
            with open(MANIFEST_FILE, 'w') as f:
                json.dump(manifest, f, indent=2)
            os.chmod(MANIFEST_FILE, 0o600)
        except Exception:
            pass


def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass


def is_protected_path(path: str) -> bool:
    """Reject attempts to swallow system locations."""
    try:
        real = os.path.realpath(path).lower().replace('\\', '/')
    except Exception:
        return True
    # Reject exact root
    if real in ('/', 'c:/', 'c:'):
        return True
    for proto in PROTECTED_ROOTS:
        p = proto.lower().replace('\\', '/').rstrip('/')
        if not p:  # '/' was here — already handled above
            continue
        if real == p or real.startswith(p + '/'):
            return True
    # Don't let the user feed the vault to itself
    vault_str = str(VAULT_ROOT.resolve()).lower().replace('\\', '/')
    if real == vault_str or real.startswith(vault_str + '/'):
        return True
    return False


# ═══════════════════════════════════════════════════════════════
# SHRED — the actual destruction
# ═══════════════════════════════════════════════════════════════

def shred_file(path: str, passes: int = 3) -> tuple:
    """
    Overwrite with random bytes N times, scramble name, truncate, unlink.
    Returns (ok: bool, note: str).
    """
    try:
        if not os.path.isfile(path):
            return False, 'not a file'
        size = os.path.getsize(path)

        # Multi-pass random overwrite
        for i in range(passes):
            with open(path, 'r+b', buffering=0) as f:
                written = 0
                chunk = 65536
                while written < size:
                    amount = min(chunk, size - written)
                    f.write(secrets.token_bytes(amount))
                    written += amount
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass

        # Truncate to zero
        with open(path, 'r+b') as f:
            f.truncate(0)
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

        # Scramble filename (rename within same dir)
        parent = os.path.dirname(path)
        scramble = os.path.join(parent, '_' + secrets.token_hex(8))
        try:
            os.rename(path, scramble)
            final = scramble
        except OSError:
            final = path

        os.remove(final)
        return True, f'{passes}-pass shred ok'
    except PermissionError:
        return False, 'permission denied'
    except Exception as e:
        return False, str(e)[:200]


def shred_tree(path: str, passes: int = 3) -> dict:
    """Walk a directory bottom-up, shredding files, then rmdir the empties."""
    shredded = 0
    failed = 0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            if os.path.islink(fp):
                try: os.unlink(fp); shredded += 1
                except Exception: failed += 1
                continue
            try:
                total_bytes += os.path.getsize(fp)
            except OSError:
                pass
            ok, _ = shred_file(fp, passes=passes)
            if ok: shredded += 1
            else: failed += 1
        try:
            os.rmdir(dirpath)
        except OSError:
            pass
    try:
        os.rmdir(path)
    except OSError:
        pass
    return {'shredded': shredded, 'failed': failed, 'bytes': total_bytes}


# ═══════════════════════════════════════════════════════════════
# INGEST — accept files into the vault
# ═══════════════════════════════════════════════════════════════

def ingest_path(source: str) -> dict:
    """Move a filesystem path into the vault with manifest entry."""
    if not os.path.exists(source):
        return {'ok': False, 'error': 'path does not exist'}
    if is_protected_path(source):
        return {'ok': False, 'error': 'path is protected — Void Eater refuses'}
    if os.path.islink(source):
        return {'ok': False, 'error': 'symlinks not accepted (ambiguous target)'}

    item_id = uuid.uuid4().hex[:12]
    vault_path = VAULT_ITEMS / item_id

    try:
        size = _path_size(source)
        is_dir = os.path.isdir(source)
        shutil.move(source, str(vault_path))
    except Exception as e:
        return {'ok': False, 'error': str(e)}

    record = {
        'id': item_id,
        'original_path': os.path.abspath(source),
        'original_name': os.path.basename(source),
        'is_dir': is_dir,
        'size': size,
        'ingested_at': datetime.now().isoformat(timespec='seconds'),
        'expires_at': (datetime.now() + timedelta(hours=config['retention_hours'])).isoformat(timespec='seconds'),
        'vault_path': str(vault_path),
        'state': 'buffered',  # buffered | restored | shredded | shred_failed
    }
    with manifest_lock:
        manifest[item_id] = record
    save_manifest()
    return {'ok': True, 'record': record}


def ingest_upload(file_storage) -> dict:
    """Accept an uploaded file (from browser drop) directly into the vault."""
    item_id = uuid.uuid4().hex[:12]
    vault_path = VAULT_ITEMS / item_id
    vault_path.mkdir(parents=True, exist_ok=True)
    dest = vault_path / file_storage.filename
    try:
        file_storage.save(str(dest))
        size = os.path.getsize(dest)
    except Exception as e:
        return {'ok': False, 'error': str(e)}

    record = {
        'id': item_id,
        'original_path': None,  # no disk origin — came from browser
        'original_name': file_storage.filename,
        'is_dir': False,
        'size': size,
        'ingested_at': datetime.now().isoformat(timespec='seconds'),
        'expires_at': (datetime.now() + timedelta(hours=config['retention_hours'])).isoformat(timespec='seconds'),
        'vault_path': str(vault_path),
        'state': 'buffered',
        'source': 'upload',
    }
    with manifest_lock:
        manifest[item_id] = record
    save_manifest()
    return {'ok': True, 'record': record}


def _path_size(p: str) -> int:
    if os.path.isfile(p):
        try: return os.path.getsize(p)
        except OSError: return 0
    total = 0
    for dp, _, fns in os.walk(p):
        for fn in fns:
            try: total += os.path.getsize(os.path.join(dp, fn))
            except OSError: pass
    return total


# ═══════════════════════════════════════════════════════════════
# RESTORE
# ═══════════════════════════════════════════════════════════════

def restore_item(item_id: str, override_path: str = None) -> dict:
    with manifest_lock:
        rec = manifest.get(item_id)
    if not rec:
        return {'ok': False, 'error': 'unknown item id'}
    if rec['state'] != 'buffered':
        return {'ok': False, 'error': f"cannot restore — item is {rec['state']}"}

    target = override_path or rec.get('original_path')
    if not target:
        return {'ok': False, 'error': 'no original path — provide override_path'}
    if is_protected_path(target):
        return {'ok': False, 'error': 'restore target is protected'}

    # Find the actual payload inside vault_path
    vault_p = rec['vault_path']
    source = vault_p
    if rec.get('source') == 'upload':
        # upload mode wraps payload in a dir
        children = os.listdir(vault_p)
        if len(children) == 1:
            source = os.path.join(vault_p, children[0])

    # Handle collision
    if os.path.exists(target):
        base, ext = os.path.splitext(target)
        target = f"{base}_restored_{int(time.time())}{ext}"

    try:
        os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
        shutil.move(source, target)
        # If upload wrapper dir is now empty, clean it
        if rec.get('source') == 'upload':
            try: os.rmdir(vault_p)
            except OSError: pass
    except Exception as e:
        return {'ok': False, 'error': str(e)}

    with manifest_lock:
        rec['state'] = 'restored'
        rec['restored_to'] = target
        rec['restored_at'] = datetime.now().isoformat(timespec='seconds')
    save_manifest()
    return {'ok': True, 'restored_to': target}


# ═══════════════════════════════════════════════════════════════
# SHRED (manual or expiry-driven)
# ═══════════════════════════════════════════════════════════════

def shred_item(item_id: str) -> dict:
    with manifest_lock:
        rec = manifest.get(item_id)
    if not rec:
        return {'ok': False, 'error': 'unknown item id'}
    if rec['state'] not in ('buffered',):
        return {'ok': False, 'error': f"already {rec['state']}"}

    passes = int(config['shred_passes'])
    vault_p = rec['vault_path']
    try:
        if os.path.isdir(vault_p):
            stats = shred_tree(vault_p, passes=passes)
            ok = stats['failed'] == 0
            note = f"{stats['shredded']} files, {stats['failed']} failed"
        else:
            ok, note = shred_file(vault_p, passes=passes)
    except Exception as e:
        ok, note = False, str(e)

    with manifest_lock:
        rec['state'] = 'shredded' if ok else 'shred_failed'
        rec['shredded_at'] = datetime.now().isoformat(timespec='seconds')
        rec['shred_note'] = note
    save_manifest()
    return {'ok': ok, 'note': note}


def shred_immediate(source: str) -> dict:
    """Skip the buffer entirely. Rare use — user has declared intent."""
    if not os.path.exists(source):
        return {'ok': False, 'error': 'path does not exist'}
    if is_protected_path(source):
        return {'ok': False, 'error': 'path is protected'}
    passes = int(config['shred_passes'])
    try:
        if os.path.isdir(source) and not os.path.islink(source):
            stats = shred_tree(source, passes=passes)
            return {'ok': stats['failed'] == 0, 'stats': stats}
        else:
            ok, note = shred_file(source, passes=passes)
            return {'ok': ok, 'note': note}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════════
# SWEEP — background expiry enforcement
# ═══════════════════════════════════════════════════════════════

sweep_stop = threading.Event()

def sweep_loop():
    while not sweep_stop.is_set():
        try:
            now = datetime.now()
            expired_ids = []
            with manifest_lock:
                for iid, rec in manifest.items():
                    if rec['state'] != 'buffered':
                        continue
                    exp = datetime.fromisoformat(rec['expires_at'])
                    if now >= exp:
                        expired_ids.append(iid)
            for iid in expired_ids:
                shred_item(iid)
        except Exception:
            pass
        sweep_stop.wait(config['sweep_interval_s'])


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.route('/api/status')
def status():
    with manifest_lock:
        buffered = sum(1 for r in manifest.values() if r['state'] == 'buffered')
        total_bytes = sum(r['size'] for r in manifest.values() if r['state'] == 'buffered')
    return jsonify({
        'online': True,
        'vault_root': str(VAULT_ROOT),
        'vault_exists': VAULT_ROOT.exists(),
        'buffered_count': buffered,
        'buffered_bytes': total_bytes,
        'total_records': len(manifest),
        'config': config,
    })


@app.route('/api/config', methods=['GET', 'POST'])
def cfg():
    if request.method == 'GET':
        return jsonify(config)
    data = request.get_json(force=True)
    allowed = {'retention_hours', 'shred_passes', 'sweep_interval_s', 'scramble_names'}
    for k, v in data.items():
        if k in allowed:
            # Clamp sane ranges
            if k == 'retention_hours':   v = max(0, min(720, int(v)))   # 0h..30d
            if k == 'shred_passes':      v = max(1, min(35, int(v)))    # 1..35 (Gutmann max)
            if k == 'sweep_interval_s':  v = max(30, min(3600, int(v))) # 30s..1h
            config[k] = v
    save_config()
    return jsonify(config)


@app.route('/api/manifest')
def get_manifest():
    state_filter = request.args.get('state')  # e.g. ?state=buffered
    now = datetime.now()
    with manifest_lock:
        items = []
        for rec in manifest.values():
            if state_filter and rec['state'] != state_filter:
                continue
            item = dict(rec)
            # Compute live seconds remaining
            if rec['state'] == 'buffered':
                try:
                    exp = datetime.fromisoformat(rec['expires_at'])
                    item['seconds_remaining'] = max(0, int((exp - now).total_seconds()))
                except Exception:
                    item['seconds_remaining'] = 0
            items.append(item)
    items.sort(key=lambda x: x.get('ingested_at', ''), reverse=True)
    return jsonify({'items': items, 'count': len(items)})


@app.route('/api/ingest_path', methods=['POST'])
def endpoint_ingest_path():
    data = request.get_json(force=True)
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'path required'}), 400
    result = ingest_path(path)
    return jsonify(result), (200 if result['ok'] else 400)


@app.route('/api/ingest_upload', methods=['POST'])
def endpoint_ingest_upload():
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'no file'}), 400
    result = ingest_upload(f)
    return jsonify(result), (200 if result['ok'] else 400)


@app.route('/api/restore/<item_id>', methods=['POST'])
def endpoint_restore(item_id):
    data = request.get_json(force=True, silent=True) or {}
    result = restore_item(item_id, override_path=data.get('path'))
    return jsonify(result), (200 if result['ok'] else 400)


@app.route('/api/shred/<item_id>', methods=['POST'])
def endpoint_shred(item_id):
    data = request.get_json(force=True, silent=True) or {}
    if data.get('confirm') is not True:
        return jsonify({'error': 'confirm: true required'}), 400
    result = shred_item(item_id)
    return jsonify(result), (200 if result['ok'] else 500)


@app.route('/api/shred_now', methods=['POST'])
def endpoint_shred_now():
    """Manual shred of a filesystem path — skips the buffer entirely."""
    data = request.get_json(force=True)
    if data.get('confirm') is not True:
        return jsonify({'error': 'confirm: true required'}), 400
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'path required'}), 400
    result = shred_immediate(path)
    return jsonify(result), (200 if result.get('ok') else 500)


@app.route('/api/preview/<item_id>')
def endpoint_preview(item_id):
    """Return a short preview of the item (text head / metadata / binary note)."""
    with manifest_lock:
        rec = manifest.get(item_id)
    if not rec:
        return jsonify({'error': 'unknown item'}), 404
    if rec['state'] != 'buffered':
        return jsonify({'error': f"item is {rec['state']}"}), 409

    vault_p = rec['vault_path']
    target = vault_p
    if rec.get('source') == 'upload' and os.path.isdir(vault_p):
        children = os.listdir(vault_p)
        if len(children) == 1:
            target = os.path.join(vault_p, children[0])

    if os.path.isdir(target):
        entries = []
        for e in sorted(os.listdir(target))[:50]:
            fp = os.path.join(target, e)
            try:
                s = os.path.getsize(fp) if os.path.isfile(fp) else 0
                entries.append({'name': e, 'size': s, 'is_dir': os.path.isdir(fp)})
            except OSError:
                continue
        return jsonify({'kind': 'directory', 'name': rec['original_name'],
                        'entry_count': len(entries), 'entries': entries})

    # File preview
    mime, _ = mimetypes.guess_type(target)
    mime = mime or 'application/octet-stream'
    try:
        size = os.path.getsize(target)
    except OSError:
        size = 0

    if mime.startswith('text/') or mime in ('application/json', 'application/xml'):
        try:
            with open(target, 'r', encoding='utf-8', errors='replace') as f:
                head = f.read(4096)
            return jsonify({'kind': 'text', 'name': rec['original_name'],
                            'mime': mime, 'size': size, 'preview': head,
                            'truncated': size > 4096})
        except Exception as e:
            return jsonify({'kind': 'error', 'error': str(e)})
    return jsonify({'kind': 'binary', 'name': rec['original_name'],
                    'mime': mime, 'size': size,
                    'note': 'Binary file — no text preview available.'})


@app.route('/api/shred_all_expired', methods=['POST'])
def endpoint_shred_all_expired():
    """Manually trigger the sweep now (useful for testing retention=0 cases)."""
    data = request.get_json(force=True, silent=True) or {}
    if data.get('confirm') is not True:
        return jsonify({'error': 'confirm: true required'}), 400
    now = datetime.now()
    count = 0
    with manifest_lock:
        expired_ids = [
            iid for iid, r in manifest.items()
            if r['state'] == 'buffered'
            and datetime.fromisoformat(r['expires_at']) <= now
        ]
    for iid in expired_ids:
        if shred_item(iid).get('ok'):
            count += 1
    return jsonify({'shredded': count, 'candidates': len(expired_ids)})


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    load_state()
    ensure_vault()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8919
    print(f'🕳️  Void Eater Server on http://127.0.0.1:{port}')
    print(f'   Vault:     {VAULT_ROOT}')
    print(f'   Retention: {config["retention_hours"]}h')
    print(f'   Shred:     {config["shred_passes"]} passes')
    print(f'   Buffered:  {sum(1 for r in manifest.values() if r["state"] == "buffered")} items')

    sweeper = threading.Thread(target=sweep_loop, daemon=True)
    sweeper.start()
    print(f'   Sweeper:   active ({config["sweep_interval_s"]}s interval)')

    try:
        app.run(host='127.0.0.1', port=port, threaded=True)
    finally:
        sweep_stop.set()
