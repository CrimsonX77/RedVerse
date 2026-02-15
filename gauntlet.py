#!/usr/bin/env python3
"""
THE GAUNTLET PROTOCOL
Silent chaos → Intelligent observation → Automated punishment
No mercy. Only patterns.
"""

import os
import sys
import time
import json
import subprocess
import threading
from datetime import datetime
from collections import defaultdict
import socket
import struct

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QTextEdit, QLabel, QGroupBox, QScrollArea, QFrame
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QFont, QColor, QPalette
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

class GauntletProtocol:
    def __init__(self):
        self.state_file = os.path.expanduser("~/.gauntlet_state.json")  # Hidden in home dir
        self.safe_processes = [
            'systemd', 'Xorg', 'cinnamon', 'python3',
            'nvidia-persistenced', 'NetworkManager', 'pulseaudio'
        ]
        self.connection_tracker = defaultdict(lambda: {
            'attempts': 0,
            'first_seen': None,
            'last_seen': None,
            'ports': set(),
            'processes': set(),
            'identified': False,
            'purpose': 'UNKNOWN',
            'pattern': []
        })
        self.load_state()
        
    def load_state(self):
        """Load tracking state (if exists)"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Reconstruct sets from lists
                    for ip, info in data.items():
                        info['ports'] = set(info.get('ports', []))
                        info['processes'] = set(info.get('processes', []))
                        self.connection_tracker[ip] = info
            except:
                pass
    
    def save_state(self):
        """Persist tracking data"""
        data = {}
        for ip, info in self.connection_tracker.items():
            data[ip] = {
                'attempts': info['attempts'],
                'first_seen': info['first_seen'],
                'last_seen': info['last_seen'],
                'ports': list(info['ports']),
                'processes': list(info['processes']),
                'identified': info['identified'],
                'purpose': info['purpose'],
                'pattern': info['pattern']
            }
        
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.chmod(self.state_file, 0o600)  # Only you can read
    
    def silent_purge(self):
        """The event itself - no traces, no logs"""
        # Drop caches
        subprocess.run(['sudo', 'sync'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=False)
        subprocess.run(['sudo', 'sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches'],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL,
                      check=False)
        
        # Massacre
        self.targeted_kill()
        
        # Swap cycle
        subprocess.run(['sudo', 'swapoff', '-a'],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL,
                      check=False)
        time.sleep(0.3)
        subprocess.run(['sudo', 'swapon', '-a'],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL,
                      check=False)
        
        # Network hiccup
        self.network_disconnect()
        
        # Now we watch
        threading.Thread(target=self.observe_reconnections, daemon=True).start()
    
    def targeted_kill(self):
        """Kill everything suspicious"""
        suspects = [
            'sshd', 'ssh', 'nc', 'netcat', 'socat',
            'vnc', 'teamviewer', 'anydesk', 'remmina',
            'chrome', 'firefox', 'tor'
        ]
        
        for proc in suspects:
            subprocess.run(['sudo', 'pkill', '-9', '-f', proc],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         check=False)
    
    def network_disconnect(self):
        """Brief network cycle"""
        result = subprocess.run(['ip', 'route', 'show', 'default'],
                              capture_output=True, text=True)
        
        if 'dev' in result.stdout:
            interface = result.stdout.split('dev')[1].split()[0]
            subprocess.run(['sudo', 'ip', 'link', 'set', interface, 'down'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         check=False)
            time.sleep(0.3)
            subprocess.run(['sudo', 'ip', 'link', 'set', interface, 'up'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         check=False)
    
    def observe_reconnections(self):
        """Watch everything that tries to connect after purge"""
        while True:
            # Check active connections
            connections = self.get_active_connections()
            
            for conn in connections:
                ip = conn['remote_ip']
                port = conn['remote_port']
                local_port = conn['local_port']
                process = conn['process']
                
                # Skip localhost
                if ip.startswith('127.') or ip == '::1':
                    continue
                
                # Track this connection
                tracker = self.connection_tracker[ip]
                now = datetime.now().isoformat()
                
                if tracker['first_seen'] is None:
                    tracker['first_seen'] = now
                
                tracker['last_seen'] = now
                tracker['attempts'] += 1
                tracker['ports'].add(f"{local_port}←{port}")
                tracker['processes'].add(process)
                tracker['pattern'].append({
                    'time': now,
                    'port': local_port,
                    'process': process
                })
                
                # Try to identify purpose
                if not tracker['identified']:
                    tracker['purpose'] = self.identify_purpose(tracker)
                    if tracker['purpose'] != 'UNKNOWN':
                        tracker['identified'] = True
                
                # If still unknown after 10 attempts... PURGE AGAIN
                if not tracker['identified'] and tracker['attempts'] >= 10:
                    self.save_state()
                    self.silent_purge()
                    return  # Restart observation
            
            self.save_state()
            time.sleep(5)  # Check every 5 seconds
    
    def get_active_connections(self):
        """Get all active network connections with process info"""
        connections = []
        
        try:
            # Use ss (socket statistics) to get connections
            result = subprocess.run(
                ['ss', '-tunap'],
                capture_output=True,
                text=True,
                check=False
            )
            
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) < 6:
                    continue
                
                # Parse local and remote addresses
                try:
                    local_addr = parts[4]
                    remote_addr = parts[5]
                    
                    # Extract process info (last field, format: users:(("process",pid=123,fd=4)))
                    process = 'unknown'
                    for part in parts:
                        if 'users:' in part:
                            # Extract process name
                            if '("' in part:
                                process = part.split('("')[1].split('"')[0]
                    
                    # Parse addresses
                    if ':' in remote_addr:
                        remote_parts = remote_addr.rsplit(':', 1)
                        remote_ip = remote_parts[0].strip('[]')
                        remote_port = remote_parts[1] if len(remote_parts) > 1 else '0'
                    else:
                        continue
                    
                    if ':' in local_addr:
                        local_parts = local_addr.rsplit(':', 1)
                        local_port = local_parts[1] if len(local_parts) > 1 else '0'
                    else:
                        continue
                    
                    connections.append({
                        'remote_ip': remote_ip,
                        'remote_port': remote_port,
                        'local_port': local_port,
                        'process': process
                    })
                except:
                    continue
                    
        except Exception as e:
            pass
        
        return connections
    
    def identify_purpose(self, tracker):
        """Try to give human-readable purpose to connection pattern"""
        processes = tracker['processes']
        ports = tracker['ports']
        
        # Known patterns
        if 'sshd' in processes or any('22' in p for p in ports):
            return "SSH_REMOTE_ACCESS"
        
        if 'chrome' in processes or 'firefox' in processes:
            return "BROWSER_BASED_ACCESS"
        
        if any(str(p) in ['5900', '5901', '5902'] for p in ports):
            return "VNC_SESSION"
        
        if 'nc' in processes or 'netcat' in processes or 'socat' in processes:
            return "REVERSE_SHELL"
        
        if any(str(p) in ['3389', '5938'] for p in ports):
            return "RDP_ACCESS"
        
        # Pattern analysis
        if tracker['attempts'] > 5:
            # Rapid reconnection = probably automated/malicious
            if len(tracker['pattern']) >= 5:
                times = [datetime.fromisoformat(p['time']) for p in tracker['pattern'][-5:]]
                intervals = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
                
                if all(i < 2 for i in intervals):
                    return "AUTOMATED_RECONNECT_BOT"
        
        return "UNKNOWN"
    
    def show_status(self):
        """Display what we've learned"""
        print("\n🔥 GAUNTLET STATUS 🔥\n")
        
        if not self.connection_tracker:
            print("No reconnection attempts detected yet.\n")
            return
        
        for ip, data in self.connection_tracker.items():
            print(f"📍 IP: {ip}")
            print(f"   Purpose: {data['purpose']}")
            print(f"   Attempts: {data['attempts']}")
            print(f"   First seen: {data['first_seen']}")
            print(f"   Last seen: {data['last_seen']}")
            print(f"   Ports: {', '.join(sorted(data['ports']))}")
            print(f"   Processes: {', '.join(sorted(data['processes']))}")
            print(f"   Identified: {'✅' if data['identified'] else '❌'}")
            print()
    
    def clear_ram(self):
        """Clear system RAM caches"""
        try:
            subprocess.run(['sudo', 'sync'], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL, 
                          check=False)
            subprocess.run(['sudo', 'sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches'],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,
                          check=False)
            return True
        except:
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# GUI INTERFACE — PyQt6 Control Panel
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_GUI:
    class GauntletSignals(QObject):
        """Signals for thread-safe GUI updates"""
        log = pyqtSignal(str)
        status_update = pyqtSignal(str)
    
    class GauntletGUI(QMainWindow):
        """The Gauntlet Protocol — Control Panel"""
        
        def __init__(self):
            super().__init__()
            self.protocol = GauntletProtocol()
            self.signals = GauntletSignals()
            self.signals.log.connect(self._append_log)
            self.signals.status_update.connect(self._update_status)
            self.observing = False
            self.observe_thread = None
            
            self.init_ui()
            self.load_initial_status()
            
            # Auto-refresh timer
            self.refresh_timer = QTimer()
            self.refresh_timer.timeout.connect(self.refresh_status)
            self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        def init_ui(self):
            """Build the interface"""
            self.setWindowTitle("🔥 THE GAUNTLET PROTOCOL")
            self.setMinimumSize(900, 700)
            
            # Dark theme
            self.setStyleSheet("""
                QMainWindow {
                    background: #050306;
                    color: #e8e0d8;
                }
                QGroupBox {
                    background: #0a0a0c;
                    border: 1px solid #c41230;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding: 10px;
                    font-family: 'Cinzel', serif;
                    font-weight: bold;
                    color: #c41230;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 #8b0a20, stop:1 #c41230);
                    border: 1px solid #c41230;
                    color: #e8e0d8;
                    font-family: 'Cinzel', serif;
                    font-size: 11px;
                    font-weight: bold;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                    padding: 10px 20px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 #c41230, stop:1 #ff1a3d);
                    border-color: #ff1a3d;
                }
                QPushButton:pressed {
                    background: #8b0a20;
                }
                QPushButton:disabled {
                    background: #2a2a2a;
                    border-color: #4a4a4a;
                    color: #6b7280;
                }
                QPushButton#ramBtn {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 #a8843a, stop:1 #d4a846);
                    border-color: #d4a846;
                }
                QPushButton#ramBtn:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 #d4a846, stop:1 #ffd25a);
                    border-color: #ffd25a;
                }
                QTextEdit {
                    background: #0a0a0c;
                    border: 1px solid #2a2a2a;
                    color: #b8c0cc;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 10px;
                    padding: 8px;
                    selection-background-color: #c41230;
                }
                QLabel {
                    color: #9b8e82;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 10px;
                }
            """)
            
            # Central widget
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(15)
            
            # Header
            header = QLabel("THE GAUNTLET PROTOCOL")
            header.setStyleSheet("""
                font-family: 'Cinzel', serif;
                font-size: 18px;
                font-weight: bold;
                color: #c41230;
                letter-spacing: 2px;
                padding: 10px;
            """)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(header)
            
            subtitle = QLabel("Silent chaos → Intelligent observation → Automated punishment")
            subtitle.setStyleSheet("""
                font-family: 'Crimson Pro', serif;
                font-size: 11px;
                font-style: italic;
                color: #6b7280;
                letter-spacing: 1px;
            """)
            subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(subtitle)
            
            # Control Panel
            control_group = QGroupBox("⚔ CONTROL PANEL")
            control_layout = QHBoxLayout()
            control_layout.setSpacing(10)
            
            self.purge_btn = QPushButton("🔥 PURGE")
            self.purge_btn.setToolTip("Deploy the gauntlet - kill processes, cycle network, observe")
            self.purge_btn.clicked.connect(self.on_purge)
            
            self.status_btn = QPushButton("📊 STATUS")
            self.status_btn.setToolTip("Display current tracking status")
            self.status_btn.clicked.connect(self.on_status)
            
            self.observe_btn = QPushButton("👁 OBSERVE")
            self.observe_btn.setToolTip("Start/stop passive observation")
            self.observe_btn.setCheckable(True)
            self.observe_btn.clicked.connect(self.on_observe)
            
            self.ram_btn = QPushButton("💾 CLEAR RAM")
            self.ram_btn.setObjectName("ramBtn")
            self.ram_btn.setToolTip("Drop system caches and clear RAM")
            self.ram_btn.clicked.connect(self.on_clear_ram)
            
            control_layout.addWidget(self.purge_btn)
            control_layout.addWidget(self.status_btn)
            control_layout.addWidget(self.observe_btn)
            control_layout.addWidget(self.ram_btn)
            control_group.setLayout(control_layout)
            layout.addWidget(control_group)
            
            # Status Display
            status_group = QGroupBox("📡 TRACKING STATUS")
            status_layout = QVBoxLayout()
            
            self.status_display = QTextEdit()
            self.status_display.setReadOnly(True)
            self.status_display.setMaximumHeight(200)
            status_layout.addWidget(self.status_display)
            
            status_group.setLayout(status_layout)
            layout.addWidget(status_group)
            
            # Log Console
            log_group = QGroupBox("📜 CONSOLE LOG")
            log_layout = QVBoxLayout()
            
            self.log_console = QTextEdit()
            self.log_console.setReadOnly(True)
            log_layout.addWidget(self.log_console)
            
            log_group.setLayout(log_layout)
            layout.addWidget(log_group)
            
        def _append_log(self, message):
            """Thread-safe log append"""
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_console.append(f"[{timestamp}] {message}")
            
        def _update_status(self, status_text):
            """Thread-safe status update"""
            self.status_display.setPlainText(status_text)
        
        def log(self, message):
            """Add message to log"""
            self.signals.log.emit(message)
        
        def format_status(self):
            """Format current tracking status"""
            if not self.protocol.connection_tracker:
                return "No connections tracked yet.\nDeploy PURGE or start OBSERVE to begin tracking."
            
            lines = []
            for ip, data in self.protocol.connection_tracker.items():
                lines.append(f"📍 {ip}")
                lines.append(f"   Purpose: {data['purpose']}")
                lines.append(f"   Attempts: {data['attempts']}")
                lines.append(f"   First: {data['first_seen']}")
                lines.append(f"   Last: {data['last_seen']}")
                lines.append(f"   Ports: {', '.join(sorted(list(data['ports'])[:5]))}")
                lines.append(f"   Processes: {', '.join(sorted(list(data['processes'])[:5]))}")
                lines.append(f"   Identified: {'✅ YES' if data['identified'] else '❌ NO'}")
                lines.append("")
            
            return "\n".join(lines)
        
        def load_initial_status(self):
            """Load initial status from saved state"""
            status = self.format_status()
            self.signals.status_update.emit(status)
            self.log("Gauntlet Protocol initialized")
            self.log(f"Loaded {len(self.protocol.connection_tracker)} tracked IPs")
        
        def refresh_status(self):
            """Auto-refresh status display"""
            if self.observing:
                status = self.format_status()
                self.signals.status_update.emit(status)
        
        def on_purge(self):
            """Deploy the gauntlet"""
            self.log("🔥 DEPLOYING GAUNTLET...")
            self.purge_btn.setEnabled(False)
            
            def purge_thread():
                self.protocol.silent_purge()
                self.signals.log.emit("✅ Purge complete - observation started")
                self.purge_btn.setEnabled(True)
                self.observing = True
                self.observe_btn.setChecked(True)
            
            threading.Thread(target=purge_thread, daemon=True).start()
        
        def on_status(self):
            """Display current status"""
            self.log("📊 Refreshing status...")
            status = self.format_status()
            self.signals.status_update.emit(status)
            self.log(f"Status updated - {len(self.protocol.connection_tracker)} tracked IPs")
        
        def on_observe(self, checked):
            """Toggle observation mode"""
            if checked:
                self.log("👁 Starting observation...")
                self.observing = True
                self.observe_thread = threading.Thread(
                    target=self.protocol.observe_reconnections,
                    daemon=True
                )
                self.observe_thread.start()
            else:
                self.log("🛑 Stopping observation...")
                self.observing = False
                self.protocol.connection_tracker.clear()
                self.protocol.save_state()
                status = self.format_status()
                self.signals.status_update.emit(status)
        
        def on_clear_ram(self):
            """Clear system RAM"""
            self.log("💾 Clearing RAM caches...")
            self.ram_btn.setEnabled(False)
            
            def clear_thread():
                success = self.protocol.clear_ram()
                if success:
                    self.signals.log.emit("✅ RAM cleared successfully")
                else:
                    self.signals.log.emit("❌ RAM clear failed - check sudo permissions")
                self.ram_btn.setEnabled(True)
            
            threading.Thread(target=clear_thread, daemon=True).start()


def purge():
    """Deploy the gauntlet"""
    protocol = GauntletProtocol()
    protocol.silent_purge()

def status():
    """See what you've caught"""
    protocol = GauntletProtocol()
    protocol.show_status()

def observe():
    """Just watch (no purge)"""
    protocol = GauntletProtocol()
    protocol.observe_reconnections()

def gui():
    """Launch GUI interface"""
    if not HAS_GUI:
        print("❌ PyQt6 not available - install with: pip install PyQt6")
        return
    
    app = QApplication(sys.argv)
    window = GauntletGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "purge":
            purge()
        elif sys.argv[1] == "status":
            status()
        elif sys.argv[1] == "observe":
            observe()
        elif sys.argv[1] == "gui":
            gui()
        else:
            print("Usage: python3 gauntlet.py [purge|status|observe|gui]")
    else:
        # Default to GUI if available, otherwise show help
        if HAS_GUI:
            gui()
        else:
            print("THE GAUNTLET PROTOCOL")
            print("Usage: python3 gauntlet.py [purge|status|observe|gui]")
            print("\nCommands:")
            print("  purge   - Deploy the gauntlet (kill + observe)")
            print("  status  - Show current tracking status")
            print("  observe - Start passive observation")
            print("  gui     - Launch GUI interface (requires PyQt6)")
