#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════╗
║          REDVERSE MASTER LAUNCHER v2.0                 ║
║          One command. All services. No excuses.        ║
║          Base: script directory                        ║
╚════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import signal
import subprocess
import socket
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# ANSI COLOURS
# ═══════════════════════════════════════════════════════════
R  = "\033[38;5;197m"   # Crimson
G  = "\033[38;5;46m"    # Green
Y  = "\033[38;5;220m"   # Gold
B  = "\033[38;5;75m"    # Blue
DIM= "\033[38;5;240m"   # Dim grey
W  = "\033[97m"         # Bright white
RST= "\033[0m"          # Reset
BOLD="\033[1m"

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
BASE_DIR  = Path(__file__).resolve().parent
HOME      = Path.home()
ASSETS    = BASE_DIR / "assets"
DOWNLOADS = BASE_DIR / "downloads"

ASSET_FOLDERS = {
    "music":     ASSETS / "music",
    "images":    ASSETS / "images",
    "videos":    ASSETS / "videos",
    "documents": ASSETS / "documents",
    "text":      ASSETS / "text",
    "downloads": DOWNLOADS,
}

# (display_name, script_file, port, emoji)
SERVERS = [
    ("Main API",           "server.py",                    8800, "🌐"),
    ("Audio Cutter",       "audiocutter_server.py",        8914, "✂️"),
    ("Loop Pad",           "looppad_server.py",            8912, "🎵"),
    ("MultiTool",          "multitool_server.py",          8913, "🔧"),
    ("QuickCam",           "quickcam_server.py",           8910, "🎥"),
    ("Speaker",            "speaker_server.py",            8911, "🔊"),
    ("Vision Switchboard", "vision_switchboard_server.py", 8920, "👁️"),
    ("Checkout / Shop",    "checkout_server.py",           8915, "🛒"),
    ("Dragon Forge",       "dragon_forge_server.py",       8916, "🐉"),
    ("Dragon Cleaner",     "dragon_cleaner_server.py",     8917, "🧹"),
    ("Gauntlet Protocol",  "gauntlet_server.py",           8918, "⚔️"),
    ("Void Eater",         "void_eater_server.py",         8919, "🕳️"),
    ("RedVox",             "redvox_server.py",             8921, "🩸"),
    ("RedVault Indexer",   "redvault_indexer_server.py",   8923, "📇"),
    ("Narrator",           "narrator_server.py",           8930, "🗣️"),
    ("Recorder",           "recorder_server.py",           8931, "🎙️"),
    ("Screen Recorder",    "screen_recorder_server.py",    8932, "🖥️"),
    ("OmniSensor HUD",     "omnisensor_server.py",         8933, "⚡"),
    ("Lyra Forge",         "lyra_forge_server.py",         8667, "🖼️"),
    ("Embodiment",         "embodiment_server.py",         5000, "🤖"),
    ("Consciousness",      "consciousness_server.py",      7777, "🧠"),
]

processes: list[tuple[str, int, subprocess.Popen]] = []


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def port_free(port: int) -> bool:
    """Return True if the port is not already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


def print_banner():
    print(f"\n{R}╔{'═'*54}╗")
    print(f"║{W}{BOLD}{'REDVERSE MASTER LAUNCHER v2.0':^54}{RST}{R}║")
    print(f"║{DIM}{'One command. All services. No excuses.':^54}{R}║")
    print(f"╚{'═'*54}╝{RST}\n")
    print(f"  {DIM}Base   {RST}→ {Y}{BASE_DIR}{RST}")
    print(f"  {DIM}Assets {RST}→ {Y}{ASSETS}{RST}")
    print(f"  {DIM}DLs    {RST}→ {Y}{DOWNLOADS}{RST}\n")


def ensure_folders():
    print(f"{DIM}  Creating asset folders…{RST}")
    for name, path in ASSET_FOLDERS.items():
        path.mkdir(parents=True, exist_ok=True)
        print(f"  {DIM}{'✓':>2}  {name:<12}{RST} {path}")
    print()


def start_server(name: str, script: str, port: int, emoji: str) -> bool:
    script_path = BASE_DIR / script
    label = f"{emoji}  {name:<22}"
    vision_python = BASE_DIR / ".vision-venv" / "bin" / "python"

    if not script_path.exists():
        print(f"  {R}✗{RST}  {label} {DIM}script not found — skipping{RST}")
        return False

    if not port_free(port):
        print(f"  {Y}⚠{RST}  {label} {DIM}port {port} already in use — skipping{RST}")
        return False

    try:
        python_exec = str(vision_python) if script == "vision_switchboard_server.py" and vision_python.exists() else sys.executable
        cmd = [python_exec, str(script_path), str(port)]
        if script == "consciousness_server.py":
            cmd = [
                python_exec,
                str(script_path),
                "--soul", "Sable_Cathedral_v5_3.yaml",
                "--port", str(port),
            ]
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append((name, port, proc))
        print(f"  {G}✓{RST}  {label} {DIM}→{RST} {B}http://127.0.0.1:{port}{RST}")
        return True
    except Exception as e:
        print(f"  {R}✗{RST}  {label} {R}{e}{RST}")
        return False


def shutdown(sig=None, frame=None):
    print(f"\n\n{R}{'─'*56}")
    print(f"  Shutting down all services…{RST}")
    for name, port, proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=3)
            print(f"  {DIM}stopped{RST}  {name} (:{port})")
        except subprocess.TimeoutExpired:
            proc.kill()
            print(f"  {Y}killed {RST}  {name} (:{port})")
        except Exception:
            pass
    print(f"\n{G}  All clear.{RST}\n")
    sys.exit(0)


def health_check(delay: float = 1.5):
    """Quick pass to flag any processes that died immediately."""
    time.sleep(delay)
    any_dead = False
    for name, port, proc in processes:
        if proc.poll() is not None:
            err = proc.stderr.read(200).strip() if proc.stderr else ""
            print(f"  {R}✗ {name} exited early{RST} {DIM}— {err or 'no output'}{RST}")
            any_dead = True
    if any_dead:
        print()


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print_banner()
    ensure_folders()

    print(f"{DIM}  Launching servers…{RST}\n")
    ok = 0
    for name, script, port, emoji in SERVERS:
        if start_server(name, script, port, emoji):
            ok += 1
        time.sleep(0.5)

    health_check()

    print(f"\n{G}  {ok}/{len(SERVERS)} services running{RST}")
    print(f"\n  {DIM}Main site    {RST}→ {B}http://127.0.0.1:8800{RST}")
    print(f"  {DIM}Shop         {RST}→ {B}http://127.0.0.1:8915{RST}")
    print(f"  {DIM}Speaker      {RST}→ {B}http://127.0.0.1:8911{RST}")
    print(f"  {DIM}QuickCam     {RST}→ {B}http://127.0.0.1:8910{RST}")
    print(f"  {DIM}Dragon Forge {RST}→ {B}http://127.0.0.1:8916{RST}")
    print(f"  {DIM}Dragon Clean {RST}→ {B}http://127.0.0.1:8917{RST}")
    print(f"  {DIM}Gauntlet     {RST}→ {B}http://127.0.0.1:8918{RST}")
    print(f"  {DIM}Void Eater   {RST}→ {B}http://127.0.0.1:8919{RST}")
    print(f"  {DIM}Vision       {RST}→ {B}http://127.0.0.1:8920{RST}")
    print(f"  {DIM}RedVox       {RST}→ {B}http://127.0.0.1:8921{RST}")
    print(f"  {DIM}RedVault     {RST}→ {B}http://127.0.0.1:8923{RST}")
    print(f"  {DIM}OmniSensor   {RST}→ {B}http://127.0.0.1:8933{RST}")
    print(f"  {DIM}Lyra Forge   {RST}→ {B}http://127.0.0.1:8667{RST}")
    print(f"\n  {DIM}Ctrl+C to stop everything.{RST}\n")

    try:
        while True:
            time.sleep(30)
            # Restart any process that died
            for i, (name, port, proc) in enumerate(processes):
                if proc.poll() is not None:
                    script = next((s for n, s, p, e in SERVERS if n == name), None)
                    emoji  = next((em for n, s, p, em in SERVERS if n == name), "🔄")
                    if script and port_free(port):
                        print(f"  {Y}↻ restarting {name}…{RST}")
                        vision_python = BASE_DIR / ".vision-venv" / "bin" / "python"
                        python_exec = str(vision_python) if script == "vision_switchboard_server.py" and vision_python.exists() else sys.executable
                        cmd = [python_exec, str(BASE_DIR / script), str(port)]
                        if script == "consciousness_server.py":
                            cmd = [
                                python_exec,
                                str(BASE_DIR / script),
                                "--soul", "Sable_Cathedral_v5_3.yaml",
                                "--port", str(port),
                            ]
                        new_proc = subprocess.Popen(
                            cmd,
                            cwd=BASE_DIR,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        processes[i] = (name, port, new_proc)
    except KeyboardInterrupt:
        shutdown()
