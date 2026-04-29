#!/usr/bin/env python3
"""
Gauntlet Server — RAM cleansing + process monitoring backend
Wraps gauntlet.py's GauntletProtocol with a Flask control surface.

Port 8918 | Part of RedVerse Agency Scripts

Dependencies:
    pip install flask flask-cors psutil

The underlying purge actions require passwordless sudo for:
    sync, drop_caches, swapoff/swapon, pkill, ip link
If sudo isn't configured, the ops log "permission denied" but the
server itself stays alive.

⚠ SAFETY: The Gauntlet issues destructive system commands. Every
         action that alters system state requires explicit
         confirmation via POST + confirm:true. The /clear endpoint
         is the only "soft" op (drop_caches only).
"""
import sys
import os
import time
import json
import threading
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════
# CONFIG — mirrored from gauntlet.py
# ═══════════════════════════════════════════════════════════════

STATE_FILE = os.path.expanduser("~/.gauntlet_state.json")

SAFE_PROCESSES = [
    'systemd', 'Xorg', 'cinnamon', 'python3',
    'nvidia-persistenced', 'NetworkManager', 'pulseaudio',
    'kernel', 'init', 'gauntlet_server',
]

SUSPECT_PROCESSES = [
    'sshd', 'ssh', 'nc', 'netcat', 'socat',
    'vnc', 'teamviewer', 'anydesk', 'remmina',
]

# Browsers are more nuclear — require a separate flag to nuke them
NUCLEAR_PROCESSES = ['chrome', 'firefox', 'tor', 'brave', 'edge', 'safari']

OPS_LOG_MAX = 200

# ═══════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════

ops_log = []
ops_lock = threading.Lock()

observing = False
observe_thread = None
observe_stop = threading.Event()


def log_op(event: str, detail: str = ''):
    entry = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'event': event,
        'detail': detail,
    }
    with ops_lock:
        ops_log.append(entry)
        if len(ops_log) > OPS_LOG_MAX:
            del ops_log[:-OPS_LOG_MAX]
    return entry


def load_tracker():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_tracker(data: dict):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        os.chmod(STATE_FILE, 0o600)
    except Exception as e:
        log_op('state_save_error', str(e))


# ═══════════════════════════════════════════════════════════════
# MEMORY TELEMETRY — psutil-powered, non-destructive, pollable
# ═══════════════════════════════════════════════════════════════

def memory_snapshot():
    if not HAS_PSUTIL:
        return {'error': 'psutil not installed'}
    try:
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        load = list(os.getloadavg()) if hasattr(os, 'getloadavg') else None
        return {
            'virtual': {
                'total': vm.total,
                'available': vm.available,
                'used': vm.used,
                'free': vm.free,
                'percent': vm.percent,
                'cached': getattr(vm, 'cached', 0),
                'buffers': getattr(vm, 'buffers', 0),
            },
            'swap': {
                'total': sm.total,
                'used': sm.used,
                'free': sm.free,
                'percent': sm.percent,
            },
            'load_average': load,
            'cpu_percent': psutil.cpu_percent(interval=None),
            'boot_time': int(psutil.boot_time()),
        }
    except Exception as e:
        return {'error': str(e)}


def top_memory_processes(limit: int = 15):
    if not HAS_PSUTIL:
        return []
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'username', 'memory_info', 'cpu_percent']):
        try:
            info = p.info
            rss = info['memory_info'].rss if info['memory_info'] else 0
            procs.append({
                'pid': info['pid'],
                'name': info['name'] or 'unknown',
                'user': info['username'] or 'unknown',
                'rss': rss,
                'cpu': info.get('cpu_percent', 0) or 0,
                'is_safe': any(s in (info['name'] or '') for s in SAFE_PROCESSES),
                'is_suspect': any(s in (info['name'] or '') for s in SUSPECT_PROCESSES),
                'is_nuclear': any(s in (info['name'] or '').lower() for s in NUCLEAR_PROCESSES),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x['rss'], reverse=True)
    return procs[:limit]


# ═══════════════════════════════════════════════════════════════
# OPS — the destructive verbs, gated by confirm
# ═══════════════════════════════════════════════════════════════

def run_silent(cmd: list) -> tuple:
    """Run a command, swallow output, return (returncode, stderr_snippet)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
        return r.returncode, r.stderr.strip()[:200]
    except subprocess.TimeoutExpired:
        return -1, 'timeout'
    except FileNotFoundError:
        return -1, 'command not found'
    except Exception as e:
        return -1, str(e)[:200]


def op_clear_ram() -> dict:
    """Drop the page cache. Soft, recoverable, no process impact."""
    before = memory_snapshot()
    before_avail = before.get('virtual', {}).get('available', 0)

    rc1, _ = run_silent(['sudo', '-n', 'sync'])
    rc2, err2 = run_silent(['sudo', '-n', 'sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches'])

    time.sleep(0.2)
    after = memory_snapshot()
    after_avail = after.get('virtual', {}).get('available', 0)
    freed = after_avail - before_avail

    entry = log_op(
        'clear_ram',
        f"rc=({rc1},{rc2}) freed={freed} bytes" + (f" stderr={err2}" if rc2 != 0 else ''),
    )
    return {
        'ok': rc2 == 0,
        'freed_bytes': max(0, freed),
        'before': before, 'after': after,
        'log': entry,
    }


def op_swap_cycle() -> dict:
    """swapoff -a → swapon -a. Forces everything paged out back in."""
    rc1, err1 = run_silent(['sudo', '-n', 'swapoff', '-a'])
    time.sleep(0.5)
    rc2, err2 = run_silent(['sudo', '-n', 'swapon', '-a'])
    entry = log_op('swap_cycle', f"off_rc={rc1} on_rc={rc2}")
    return {'ok': rc1 == 0 and rc2 == 0, 'log': entry,
            'errors': [e for e in (err1, err2) if e]}


def op_targeted_kill(include_nuclear: bool = False) -> dict:
    """pkill against suspect list (+nuclear if explicitly allowed)."""
    targets = list(SUSPECT_PROCESSES)
    if include_nuclear:
        targets += NUCLEAR_PROCESSES
    killed = []
    for proc in targets:
        rc, _ = run_silent(['sudo', '-n', 'pkill', '-9', '-f', proc])
        if rc == 0:
            killed.append(proc)
    entry = log_op('targeted_kill',
                   f"hit={len(killed)} nuclear={include_nuclear} procs={','.join(killed) or '-'}")
    return {'ok': True, 'killed': killed, 'log': entry}


def op_network_bounce() -> dict:
    """Brief interface down/up — breaks active connections, refreshes lease."""
    # Discover default interface
    try:
        r = subprocess.run(['ip', 'route', 'show', 'default'],
                           capture_output=True, text=True, timeout=3)
        if 'dev' not in r.stdout:
            entry = log_op('network_bounce', 'no default interface')
            return {'ok': False, 'reason': 'no default route', 'log': entry}
        interface = r.stdout.split('dev')[1].split()[0]
    except Exception as e:
        entry = log_op('network_bounce', f'discovery failed: {e}')
        return {'ok': False, 'reason': str(e), 'log': entry}

    rc1, _ = run_silent(['sudo', '-n', 'ip', 'link', 'set', interface, 'down'])
    time.sleep(0.4)
    rc2, _ = run_silent(['sudo', '-n', 'ip', 'link', 'set', interface, 'up'])
    entry = log_op('network_bounce', f"iface={interface} down_rc={rc1} up_rc={rc2}")
    return {'ok': rc2 == 0, 'interface': interface, 'log': entry}


def op_full_purge(include_nuclear: bool = False, bounce_net: bool = False) -> dict:
    """The full DDT. Sequences all destructive ops."""
    results = {}
    results['clear_ram']    = op_clear_ram()
    results['kill']         = op_targeted_kill(include_nuclear=include_nuclear)
    results['swap_cycle']   = op_swap_cycle()
    if bounce_net:
        results['network'] = op_network_bounce()
    log_op('full_purge', f"nuclear={include_nuclear} net={bounce_net}")
    return {'ok': True, 'phases': results}


# ═══════════════════════════════════════════════════════════════
# CONNECTION OBSERVATION — the "watch what crawls back" loop
# ═══════════════════════════════════════════════════════════════

def get_connections():
    """Read active connections via ss (fast, widely available)."""
    try:
        r = subprocess.run(['ss', '-tunap'], capture_output=True, text=True, timeout=5)
    except Exception:
        return []
    conns = []
    for line in r.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            local, remote = parts[4], parts[5]
            process = 'unknown'
            for p in parts:
                if 'users:' in p and '("' in p:
                    process = p.split('("')[1].split('"')[0]
                    break
            if ':' not in remote:
                continue
            rip, rport = remote.rsplit(':', 1)
            rip = rip.strip('[]')
            lport = local.rsplit(':', 1)[1] if ':' in local else '0'
            if rip in ('*', '0.0.0.0', '::', '127.0.0.1'):
                continue
            conns.append({'ip': rip, 'remote_port': rport,
                          'local_port': lport, 'process': process})
        except Exception:
            continue
    return conns


def observe_loop():
    """Run while observing; record every connection attempt."""
    log_op('observe_start')
    tracker = load_tracker()
    while not observe_stop.is_set():
        try:
            for c in get_connections():
                ip = c['ip']
                if ip not in tracker:
                    tracker[ip] = {
                        'attempts': 0,
                        'first_seen': datetime.now().isoformat(timespec='seconds'),
                        'last_seen': None, 'ports': [], 'processes': [],
                        'purpose': 'UNKNOWN',
                    }
                rec = tracker[ip]
                rec['attempts'] += 1
                rec['last_seen'] = datetime.now().isoformat(timespec='seconds')
                if c['remote_port'] not in rec['ports']:
                    rec['ports'].append(c['remote_port'])
                if c['process'] not in rec['processes']:
                    rec['processes'].append(c['process'])
                rec['purpose'] = classify_purpose(rec)
            save_tracker(tracker)
        except Exception as e:
            log_op('observe_error', str(e))
        observe_stop.wait(3.0)
    log_op('observe_stop')


def classify_purpose(rec: dict) -> str:
    procs = set(rec.get('processes', []))
    ports = set(rec.get('ports', []))
    if 'sshd' in procs or '22' in ports:
        return 'SSH_REMOTE_ACCESS'
    if procs & {'chrome', 'firefox', 'brave'}:
        return 'BROWSER_ACCESS'
    if ports & {'5900', '5901', '5902'}:
        return 'VNC_SESSION'
    if procs & {'nc', 'netcat', 'socat'}:
        return 'REVERSE_SHELL'
    if ports & {'3389', '5938'}:
        return 'RDP_ACCESS'
    if rec.get('attempts', 0) > 20:
        return 'PERSISTENT_RECONNECT'
    return 'UNKNOWN'


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

def require_confirm():
    data = request.get_json(force=True, silent=True) or {}
    if data.get('confirm') is not True:
        return data, jsonify({'error': 'confirm: true required for this op'}), 400
    return data, None, None


@app.route('/api/status')
def status():
    return jsonify({
        'online': True,
        'psutil': HAS_PSUTIL,
        'observing': observing,
        'platform': sys.platform,
        'ops_log_size': len(ops_log),
        'state_file': STATE_FILE,
        'state_file_exists': os.path.exists(STATE_FILE),
    })


@app.route('/api/memory')
def memory():
    return jsonify(memory_snapshot())


@app.route('/api/processes')
def processes():
    limit = int(request.args.get('limit', 15))
    return jsonify({'processes': top_memory_processes(limit=limit)})


@app.route('/api/ops_log')
def get_ops_log():
    n = int(request.args.get('n', 50))
    with ops_lock:
        return jsonify({'log': ops_log[-n:]})


@app.route('/api/tracker')
def get_tracker():
    data = load_tracker()
    entries = [{'ip': ip, **rec} for ip, rec in data.items()]
    entries.sort(key=lambda x: x.get('attempts', 0), reverse=True)
    return jsonify({'connections': entries, 'count': len(entries)})


@app.route('/api/clear', methods=['POST'])
def clear():
    # No confirm needed — drop_caches is soft; kernel regenerates them
    return jsonify(op_clear_ram())


@app.route('/api/swap_cycle', methods=['POST'])
def swap_cycle():
    data, err, code = require_confirm()
    if err: return err, code
    return jsonify(op_swap_cycle())


@app.route('/api/kill', methods=['POST'])
def kill():
    data, err, code = require_confirm()
    if err: return err, code
    nuclear = bool(data.get('include_nuclear', False))
    return jsonify(op_targeted_kill(include_nuclear=nuclear))


@app.route('/api/network_bounce', methods=['POST'])
def network_bounce():
    data, err, code = require_confirm()
    if err: return err, code
    return jsonify(op_network_bounce())


@app.route('/api/purge', methods=['POST'])
def purge():
    data, err, code = require_confirm()
    if err: return err, code
    return jsonify(op_full_purge(
        include_nuclear=bool(data.get('include_nuclear', False)),
        bounce_net=bool(data.get('bounce_net', False)),
    ))


@app.route('/api/observe/start', methods=['POST'])
def observe_start():
    global observing, observe_thread
    if observing:
        return jsonify({'ok': True, 'already_running': True})
    observe_stop.clear()
    observe_thread = threading.Thread(target=observe_loop, daemon=True)
    observe_thread.start()
    observing = True
    return jsonify({'ok': True})


@app.route('/api/observe/stop', methods=['POST'])
def observe_stop_endpoint():
    global observing
    if not observing:
        return jsonify({'ok': True, 'already_stopped': True})
    observe_stop.set()
    observing = False
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8918
    print(f'🧤 Gauntlet Server on http://127.0.0.1:{port}')
    print(f'   psutil: {"✓" if HAS_PSUTIL else "✗ (install: pip install psutil)"}')
    print(f'   platform: {sys.platform}')
    print(f'   state file: {STATE_FILE}')
    print()
    print('   ⚠  Destructive ops (purge/kill/swap_cycle/net_bounce) require')
    print('      passwordless sudo for: sync, tee /proc/sys/vm/drop_caches,')
    print('      swapoff/swapon, pkill, ip link')
    log_op('server_start')
    app.run(host='127.0.0.1', port=port, threaded=True)
