#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / 'venv' / 'bin' / 'python'
SUPER_SH = ROOT / 'super.sh'
APP_PY = ROOT / 'app.py'


def find_python():
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    py = shutil.which('python3') or shutil.which('python')
    if py:
        return py
    raise FileNotFoundError('No Python executable found.')


def run_command(cmd):
    print('Running:', ' '.join(cmd))
    return subprocess.run(cmd, check=False)


def help_text():
    return '''Usage: python main.py [command]

Commands:
  --auto-start   Start backend servers and open Redverse.html
  server         Start the Flask app server (app.py)
  launcher       Run super.sh auto
  help           Show this message
'''


def main():
    if len(sys.argv) == 1 or sys.argv[1] in ('--auto-start', 'auto'):
        if SUPER_SH.exists():
            return run_command(['bash', str(SUPER_SH), 'auto'])
        if APP_PY.exists():
            return run_command([str(find_python()), str(APP_PY)])
        print('ERROR: No start target found.')
        return 1

    cmd = sys.argv[1].lower()
    if cmd == 'server':
        if not APP_PY.exists():
            print('ERROR: app.py not found in repo root.')
            return 1
        return run_command([str(find_python()), str(APP_PY)])
    if cmd == 'launcher':
        if not SUPER_SH.exists():
            print('ERROR: super.sh not found in repo root.')
            return 1
        return run_command(['bash', str(SUPER_SH), 'auto'])
    if cmd in ('help', '-h', '--help'):
        print(help_text())
        return 0

    print('Unknown command:', cmd)
    print(help_text())
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
