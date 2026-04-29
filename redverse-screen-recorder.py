#!/usr/bin/env python3
"""
RED VERSE SCREEN RECORDER
─────────────────────────
Window/screen capture with refresh-rate-aware framerate,
NVENC GPU encoding, and configurable output.

Requirements:
  pip install PyQt6
  System: ffmpeg, xdotool, xrandr, xwininfo (standard on Linux Mint)

Usage:
  python3 redverse-recorder.py
"""

import sys
import os
import re
import json
import subprocess
import signal
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QGroupBox, QGridLayout, QFileDialog, QCheckBox,
    QSlider, QFrame, QMessageBox, QSystemTrayIcon, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QProcess, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QAction


# ═══════════════════════════════════════════════════════════════
# SYSTEM DETECTION
# ═══════════════════════════════════════════════════════════════

def get_monitors():
    """Detect monitors and refresh rates via xrandr."""
    monitors = []
    try:
        out = subprocess.check_output(["xrandr", "--current"], text=True, timeout=5)
        current_monitor = None
        for line in out.splitlines():
            # Match connected monitors: "DP-0 connected primary 2560x1440+0+0 ..."
            m = re.match(r'^(\S+)\s+connected\s*(primary)?\s*(\d+x\d+\+\d+\+\d+)?', line)
            if m:
                name = m.group(1)
                geom = m.group(3) or ""
                current_monitor = {"name": name, "geometry": geom, "rates": [], "current_rate": 60.0}
                monitors.append(current_monitor)
                continue

            # Match active mode line: "  2560x1440  59.95*+  143.97  ..."
            if current_monitor and line.startswith("   "):
                parts = line.strip().split()
                if not parts:
                    continue
                for p in parts[1:]:  # skip resolution
                    rate_str = p.replace("*", "").replace("+", "")
                    try:
                        rate = float(rate_str)
                        current_monitor["rates"].append(rate)
                        if "*" in p:
                            current_monitor["current_rate"] = rate
                    except ValueError:
                        pass
    except Exception as e:
        print(f"[WARN] xrandr failed: {e}")
        monitors.append({"name": "default", "geometry": "", "rates": [60.0], "current_rate": 60.0})
    return monitors if monitors else [{"name": "default", "geometry": "", "rates": [60.0], "current_rate": 60.0}]


def get_windows():
    """Get list of open windows via xdotool."""
    windows = []
    try:
        out = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--name", ""],
            text=True, timeout=5
        ).strip()
        for wid in out.splitlines():
            wid = wid.strip()
            if not wid:
                continue
            try:
                name = subprocess.check_output(
                    ["xdotool", "getwindowname", wid],
                    text=True, timeout=2
                ).strip()
                geom = subprocess.check_output(
                    ["xdotool", "getwindowgeometry", "--shell", wid],
                    text=True, timeout=2
                )
                gdict = {}
                for line in geom.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        gdict[k.strip()] = v.strip()

                # Get actual window size via xwininfo for accuracy
                try:
                    wininfo = subprocess.check_output(
                        ["xwininfo", "-id", wid],
                        text=True, timeout=2
                    )
                    w_match = re.search(r'Width:\s*(\d+)', wininfo)
                    h_match = re.search(r'Height:\s*(\d+)', wininfo)
                    if w_match and h_match:
                        gdict["WIDTH"] = w_match.group(1)
                        gdict["HEIGHT"] = h_match.group(1)
                except Exception:
                    pass

                if name and gdict.get("WIDTH") and gdict.get("HEIGHT"):
                    w = int(gdict["WIDTH"])
                    h = int(gdict["HEIGHT"])
                    x = int(gdict.get("X", 0))
                    y = int(gdict.get("Y", 0))
                    if w > 50 and h > 50:  # skip tiny windows
                        windows.append({
                            "id": wid,
                            "name": name[:80],
                            "x": x, "y": y, "w": w, "h": h
                        })
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] xdotool failed: {e}")
    return windows


def detect_nvenc():
    """Check if NVENC is available via ffmpeg."""
    try:
        out = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-encoders"],
            text=True, stderr=subprocess.STDOUT, timeout=5
        )
        has_h264 = "h264_nvenc" in out
        has_hevc = "hevc_nvenc" in out
        return {"h264_nvenc": has_h264, "hevc_nvenc": has_hevc}
    except Exception:
        return {"h264_nvenc": False, "hevc_nvenc": False}


# ═══════════════════════════════════════════════════════════════
# RECORDER THREAD
# ═══════════════════════════════════════════════════════════════

class RecorderWorker(QThread):
    status_update = pyqtSignal(str)
    time_update = pyqtSignal(float)
    error = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, cmd, output_path):
        super().__init__()
        self.cmd = cmd
        self.output_path = output_path
        self.process = None
        self._stop_flag = False
        self.start_time = 0

    def run(self):
        self.start_time = time.time()
        self.status_update.emit("Recording...")
        try:
            self.process = subprocess.Popen(
                self.cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Poll for output and timing
            while self.process.poll() is None and not self._stop_flag:
                elapsed = time.time() - self.start_time
                self.time_update.emit(elapsed)
                time.sleep(0.1)

            if self._stop_flag and self.process.poll() is None:
                # Graceful stop: send 'q' to ffmpeg
                try:
                    self.process.stdin.write(b'q')
                    self.process.stdin.flush()
                except Exception:
                    pass
                # Wait up to 5s for graceful shutdown
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    self.process.wait(timeout=3)

            retcode = self.process.returncode
            if retcode == 0 or retcode == 255 or self._stop_flag:
                # 255 is normal for ffmpeg quit via 'q'
                self.finished_signal.emit(self.output_path)
            else:
                stderr = self.process.stderr.read().decode(errors="replace")[-500:]
                self.error.emit(f"FFmpeg exited with code {retcode}\n{stderr}")

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop_flag = True


# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════

CRIMSON_STYLE = """
QMainWindow, QWidget {
    background-color: #0a0b10;
    color: #e0d0c8;
    font-family: 'Rajdhani', 'Segoe UI', sans-serif;
}
QGroupBox {
    border: 1px solid #3a1520;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: 600;
    font-size: 13px;
    color: #dc143c;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #dc143c;
}
QLabel {
    color: #b0a098;
    font-size: 12px;
}
QLabel#title-label {
    color: #dc143c;
    font-family: 'Orbitron', 'Rajdhani', monospace;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 4px;
}
QLabel#subtitle-label {
    color: #6a4040;
    font-size: 11px;
    letter-spacing: 2px;
}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #12101a;
    border: 1px solid #3a1520;
    border-radius: 4px;
    padding: 5px 10px;
    color: #e0d0c8;
    font-size: 12px;
    selection-background-color: #dc143c;
}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border-color: #dc143c;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #12101a;
    border: 1px solid #3a1520;
    color: #e0d0c8;
    selection-background-color: #5a1020;
}
QPushButton {
    background-color: #1a0a12;
    border: 1px solid #3a1520;
    border-radius: 5px;
    padding: 8px 18px;
    color: #dc143c;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 1px;
}
QPushButton:hover {
    background-color: #2a1020;
    border-color: #dc143c;
}
QPushButton:pressed {
    background-color: #dc143c;
    color: #0a0b10;
}
QPushButton#record-btn {
    font-size: 15px;
    padding: 12px 30px;
    border: 2px solid #dc143c;
    letter-spacing: 3px;
}
QPushButton#record-btn:hover {
    background-color: #3a0a15;
    box-shadow: 0 0 20px rgba(220,20,60,0.3);
}
QPushButton#record-btn[recording="true"] {
    background-color: #dc143c;
    color: #0a0b10;
    border-color: #ff4060;
}
QPushButton#stop-btn {
    font-size: 15px;
    padding: 12px 30px;
    border: 2px solid #888;
    color: #ccc;
    letter-spacing: 3px;
}
QCheckBox {
    color: #b0a098;
    spacing: 6px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #3a1520;
    border-radius: 3px;
    background: #12101a;
}
QCheckBox::indicator:checked {
    background: #dc143c;
    border-color: #dc143c;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #222;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px;
    margin: -5px 0;
    background: #dc143c;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #5a1020;
    border-radius: 2px;
}
QFrame#separator {
    background-color: #3a1520;
    max-height: 1px;
}
QLabel#status-label {
    color: #dc143c;
    font-size: 13px;
    font-weight: 600;
}
QLabel#timer-label {
    color: #ff6a50;
    font-family: 'Orbitron', monospace;
    font-size: 22px;
    letter-spacing: 2px;
}
"""


class RedVerseRecorder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RED VERSE • SCREEN RECORDER")
        self.setMinimumSize(520, 720)
        self.resize(520, 760)

        self.monitors = get_monitors()
        self.nvenc = detect_nvenc()
        self.windows = []
        self.worker = None
        self.recording = False

        self._build_ui()
        self.setStyleSheet(CRIMSON_STYLE)
        self._refresh_windows()
        self._update_rate_calc()

    # ── UI BUILD ──────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        # Title
        title = QLabel("RED VERSE RECORDER")
        title.setObjectName("title-label")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = QLabel("SCREEN · WINDOW · CAPTURE")
        sub.setObjectName("subtitle-label")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # ── SOURCE GROUP ──
        src_group = QGroupBox("SOURCE")
        src_lay = QGridLayout(src_group)
        src_lay.setColumnStretch(1, 1)

        src_lay.addWidget(QLabel("Mode"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Window", "Full Screen", "Region"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        src_lay.addWidget(self.mode_combo, 0, 1)

        src_lay.addWidget(QLabel("Window"), 1, 0)
        self.window_combo = QComboBox()
        self.window_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        src_lay.addWidget(self.window_combo, 1, 1)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._refresh_windows)
        src_lay.addWidget(refresh_btn, 1, 2)

        src_lay.addWidget(QLabel("Monitor"), 2, 0)
        self.monitor_combo = QComboBox()
        for m in self.monitors:
            rate = m["current_rate"]
            self.monitor_combo.addItem(f'{m["name"]}  ({m["geometry"]})  @ {rate:.1f}Hz')
        self.monitor_combo.currentIndexChanged.connect(self._update_rate_calc)
        src_lay.addWidget(self.monitor_combo, 2, 1, 1, 2)

        self.include_audio_cb = QCheckBox("Capture desktop audio (PulseAudio)")
        self.include_audio_cb.setChecked(True)
        src_lay.addWidget(self.include_audio_cb, 3, 0, 1, 3)

        root.addWidget(src_group)

        # ── FRAMERATE GROUP ──
        fps_group = QGroupBox("FRAMERATE")
        fps_lay = QGridLayout(fps_group)
        fps_lay.setColumnStretch(1, 1)

        fps_lay.addWidget(QLabel("Source Rate"), 0, 0)
        self.source_rate_label = QLabel("60.0 Hz")
        self.source_rate_label.setStyleSheet("color: #dc143c; font-weight: 600;")
        fps_lay.addWidget(self.source_rate_label, 0, 1)

        fps_lay.addWidget(QLabel("Boost %"), 1, 0)
        self.boost_slider = QSlider(Qt.Orientation.Horizontal)
        self.boost_slider.setRange(0, 50)
        self.boost_slider.setValue(0)
        self.boost_slider.setTickInterval(10)
        self.boost_slider.valueChanged.connect(self._update_rate_calc)
        fps_lay.addWidget(self.boost_slider, 1, 1)
        self.boost_label = QLabel("+0%")
        self.boost_label.setFixedWidth(45)
        fps_lay.addWidget(self.boost_label, 1, 2)

        fps_lay.addWidget(QLabel("Record FPS"), 2, 0)
        self.record_fps_label = QLabel("60")
        self.record_fps_label.setStyleSheet("color: #ff6a50; font-weight: 700; font-size: 14px;")
        fps_lay.addWidget(self.record_fps_label, 2, 1)

        self.fps_override_cb = QCheckBox("Manual override")
        self.fps_override_cb.toggled.connect(self._on_fps_override)
        fps_lay.addWidget(self.fps_override_cb, 3, 0)
        self.fps_manual = QSpinBox()
        self.fps_manual.setRange(10, 240)
        self.fps_manual.setValue(60)
        self.fps_manual.setEnabled(False)
        fps_lay.addWidget(self.fps_manual, 3, 1)

        root.addWidget(fps_group)

        # ── OUTPUT GROUP ──
        out_group = QGroupBox("OUTPUT")
        out_lay = QGridLayout(out_group)
        out_lay.setColumnStretch(1, 1)

        out_lay.addWidget(QLabel("Format"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4 (H.264)", "MP4 (H.265/HEVC)", "MKV (H.264)", "MKV (H.265)", "WebM (VP9)", "MOV (ProRes)", "AVI (Raw)"])
        out_lay.addWidget(self.format_combo, 0, 1, 1, 2)

        out_lay.addWidget(QLabel("Encoder"), 1, 0)
        self.encoder_combo = QComboBox()
        self._populate_encoders()
        out_lay.addWidget(self.encoder_combo, 1, 1, 1, 2)

        out_lay.addWidget(QLabel("Quality"), 2, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Lossless", "Ultra (CRF 14)", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"])
        self.quality_combo.setCurrentIndex(2)
        out_lay.addWidget(self.quality_combo, 2, 1, 1, 2)

        out_lay.addWidget(QLabel("Output FPS"), 3, 0)
        self.out_fps_combo = QComboBox()
        self.out_fps_combo.addItems(["Same as record", "24", "30", "60", "120"])
        out_lay.addWidget(self.out_fps_combo, 3, 1, 1, 2)

        out_lay.addWidget(QLabel("Save to"), 4, 0)
        self.output_dir = QLineEdit(str(Path.home() / "Videos" / "RedVerse"))
        out_lay.addWidget(self.output_dir, 4, 1)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(36)
        browse_btn.clicked.connect(self._browse_output)
        out_lay.addWidget(browse_btn, 4, 2)

        root.addWidget(out_group)

        # ── CONTROLS ──
        ctrl_lay = QHBoxLayout()
        ctrl_lay.setSpacing(12)

        self.record_btn = QPushButton("⏺  RECORD")
        self.record_btn.setObjectName("record-btn")
        self.record_btn.clicked.connect(self._toggle_record)
        ctrl_lay.addWidget(self.record_btn)

        self.stop_btn = QPushButton("⏹  STOP")
        self.stop_btn.setObjectName("stop-btn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_record)
        ctrl_lay.addWidget(self.stop_btn)

        root.addLayout(ctrl_lay)

        # ── STATUS ──
        status_lay = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status-label")
        status_lay.addWidget(self.status_label)
        status_lay.addStretch()
        self.timer_label = QLabel("00:00.0")
        self.timer_label.setObjectName("timer-label")
        status_lay.addWidget(self.timer_label)
        root.addLayout(status_lay)

        # ── CMD PREVIEW ──
        self.cmd_preview = QLabel("")
        self.cmd_preview.setWordWrap(True)
        self.cmd_preview.setStyleSheet("color: #444; font-size: 10px; font-family: monospace; padding: 4px;")
        root.addWidget(self.cmd_preview)

        root.addStretch()
        self.format_combo.currentIndexChanged.connect(self._populate_encoders)

    # ── REFRESH / DETECTION ──────────────────────────

    def _refresh_windows(self):
        self.windows = get_windows()
        self.window_combo.clear()
        for w in self.windows:
            self.window_combo.addItem(f'{w["name"]}  [{w["w"]}×{w["h"]}]', w)
        if not self.windows:
            self.window_combo.addItem("(no windows detected)")

    def _on_mode_change(self, idx):
        is_window = idx == 0
        self.window_combo.setEnabled(is_window)

    def _on_fps_override(self, checked):
        self.fps_manual.setEnabled(checked)
        self._update_rate_calc()

    def _update_rate_calc(self):
        idx = self.monitor_combo.currentIndex()
        if idx < 0 or idx >= len(self.monitors):
            return
        rate = self.monitors[idx]["current_rate"]
        self.source_rate_label.setText(f"{rate:.1f} Hz")

        boost_pct = self.boost_slider.value()
        self.boost_label.setText(f"+{boost_pct}%")

        calc_fps = rate * (1 + boost_pct / 100.0)
        # Round to nice number
        calc_fps = round(calc_fps)

        if self.fps_override_cb.isChecked():
            display_fps = self.fps_manual.value()
        else:
            display_fps = calc_fps

        self.record_fps_label.setText(str(display_fps))

    def _populate_encoders(self):
        self.encoder_combo.clear()
        fmt = self.format_combo.currentText()

        if "H.264" in fmt or "MKV (H.264)" in fmt:
            if self.nvenc.get("h264_nvenc"):
                self.encoder_combo.addItem("h264_nvenc (GPU)")
            self.encoder_combo.addItem("libx264 (CPU)")
        elif "H.265" in fmt or "HEVC" in fmt:
            if self.nvenc.get("hevc_nvenc"):
                self.encoder_combo.addItem("hevc_nvenc (GPU)")
            self.encoder_combo.addItem("libx265 (CPU)")
        elif "VP9" in fmt:
            self.encoder_combo.addItem("libvpx-vp9 (CPU)")
        elif "ProRes" in fmt:
            self.encoder_combo.addItem("prores_ks (CPU)")
        elif "Raw" in fmt:
            self.encoder_combo.addItem("rawvideo")

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Output Directory", self.output_dir.text())
        if d:
            self.output_dir.setText(d)

    # ── RECORDING ────────────────────────────────────

    def _get_record_fps(self):
        if self.fps_override_cb.isChecked():
            return self.fps_manual.value()
        idx = self.monitor_combo.currentIndex()
        rate = self.monitors[idx]["current_rate"] if idx >= 0 else 60.0
        boost = self.boost_slider.value()
        return round(rate * (1 + boost / 100.0))

    def _get_output_fps(self):
        txt = self.out_fps_combo.currentText()
        if txt == "Same as record":
            return self._get_record_fps()
        return int(txt)

    def _build_ffmpeg_cmd(self, output_path):
        rec_fps = self._get_record_fps()
        out_fps = self._get_output_fps()
        mode = self.mode_combo.currentIndex()
        encoder_text = self.encoder_combo.currentText()
        encoder = encoder_text.split(" ")[0]
        quality_text = self.quality_combo.currentText()
        fmt = self.format_combo.currentText()

        cmd = ["ffmpeg", "-y", "-hide_banner"]

        # ── Video input ──
        cmd += ["-framerate", str(rec_fps)]

        if mode == 0:  # Window
            idx = self.window_combo.currentIndex()
            if idx < 0 or idx >= len(self.windows):
                return None, "No window selected"
            w = self.windows[idx]
            # Ensure even dimensions (required by most encoders)
            width = w["w"] if w["w"] % 2 == 0 else w["w"] - 1
            height = w["h"] if w["h"] % 2 == 0 else w["h"] - 1
            cmd += [
                "-f", "x11grab",
                "-video_size", f'{width}x{height}',
                "-i", f':0.0+{w["x"]},{w["y"]}'
            ]
        elif mode == 1:  # Full screen
            idx = self.monitor_combo.currentIndex()
            m = self.monitors[idx] if idx >= 0 else self.monitors[0]
            geom = m.get("geometry", "")
            if geom:
                parts = geom.split("+")
                size = parts[0]
                offset_x = parts[1] if len(parts) > 1 else "0"
                offset_y = parts[2] if len(parts) > 2 else "0"
                cmd += [
                    "-f", "x11grab",
                    "-video_size", size,
                    "-i", f':0.0+{offset_x},{offset_y}'
                ]
            else:
                cmd += ["-f", "x11grab", "-video_size", "1920x1080", "-i", ":0.0"]
        else:  # Region — use slop if available, else default
            try:
                region = subprocess.check_output(["slop", "-f", "%x %y %w %h"], text=True, timeout=30).strip()
                rx, ry, rw, rh = region.split()
                rw = int(rw) if int(rw) % 2 == 0 else int(rw) - 1
                rh = int(rh) if int(rh) % 2 == 0 else int(rh) - 1
                cmd += [
                    "-f", "x11grab",
                    "-video_size", f"{rw}x{rh}",
                    "-i", f":0.0+{rx},{ry}"
                ]
            except FileNotFoundError:
                return None, "Region mode requires 'slop' (sudo apt install slop)"
            except Exception as e:
                return None, f"Region selection failed: {e}"

        # ── Audio input ──
        if self.include_audio_cb.isChecked():
            cmd += ["-f", "pulse", "-ac", "2", "-i", "default"]

        # ── Encoder settings ──
        if "nvenc" in encoder:
            cmd += ["-c:v", encoder]
            if "Lossless" in quality_text:
                cmd += ["-preset", "lossless"]
            else:
                cmd += ["-preset", "p4", "-tune", "hq"]
                cq_map = {"Ultra": "14", "High": "18", "Medium": "23", "Low": "28"}
                for k, v in cq_map.items():
                    if k in quality_text:
                        cmd += ["-cq", v, "-b:v", "0"]
                        break
        elif encoder == "libx264":
            cmd += ["-c:v", "libx264", "-preset", "fast"]
            if "Lossless" in quality_text:
                cmd += ["-crf", "0"]
            else:
                crf = re.search(r'CRF (\d+)', quality_text)
                cmd += ["-crf", crf.group(1) if crf else "18"]
        elif encoder == "libx265":
            cmd += ["-c:v", "libx265", "-preset", "fast"]
            crf = re.search(r'CRF (\d+)', quality_text)
            cmd += ["-crf", crf.group(1) if crf else "18"]
        elif encoder == "libvpx-vp9":
            cmd += ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0"]
        elif encoder == "prores_ks":
            cmd += ["-c:v", "prores_ks", "-profile:v", "3"]
        elif encoder == "rawvideo":
            cmd += ["-c:v", "rawvideo", "-pix_fmt", "bgr24"]

        # Audio codec
        if self.include_audio_cb.isChecked():
            if "WebM" in fmt:
                cmd += ["-c:a", "libopus"]
            elif "AVI" in fmt:
                cmd += ["-c:a", "pcm_s16le"]
            elif "MOV" in fmt:
                cmd += ["-c:a", "pcm_s16le"]
            else:
                cmd += ["-c:a", "aac", "-b:a", "192k"]

        # Output FPS (if different from record)
        if out_fps != rec_fps:
            cmd += ["-r", str(out_fps)]

        # Pixel format for compatibility
        if encoder not in ("rawvideo", "prores_ks"):
            cmd += ["-pix_fmt", "yuv420p"]

        cmd.append(output_path)
        return cmd, None

    def _toggle_record(self):
        if self.recording:
            return

        # Build output path
        out_dir = Path(self.output_dir.text())
        out_dir.mkdir(parents=True, exist_ok=True)

        fmt = self.format_combo.currentText()
        ext_map = {"MP4": ".mp4", "MKV": ".mkv", "WebM": ".webm", "MOV": ".mov", "AVI": ".avi"}
        ext = ".mp4"
        for k, v in ext_map.items():
            if k in fmt:
                ext = v
                break

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(out_dir / f"redverse_{timestamp}{ext}")

        cmd, err = self._build_ffmpeg_cmd(output_path)
        if err:
            QMessageBox.warning(self, "Error", err)
            return

        # Preview command
        self.cmd_preview.setText("$ " + " ".join(cmd))

        # Start recording
        self.worker = RecorderWorker(cmd, output_path)
        self.worker.status_update.connect(self._on_status)
        self.worker.time_update.connect(self._on_timer)
        self.worker.error.connect(self._on_error)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

        self.recording = True
        self.record_btn.setEnabled(False)
        self.record_btn.setProperty("recording", True)
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("⏺ RECORDING")
        self.status_label.setStyleSheet("color: #ff2040; font-size: 13px; font-weight: 700;")

    def _stop_record(self):
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopping...")

    def _on_status(self, msg):
        self.status_label.setText(msg)

    def _on_timer(self, elapsed):
        mins = int(elapsed) // 60
        secs = elapsed % 60
        self.timer_label.setText(f"{mins:02d}:{secs:04.1f}")

    def _on_error(self, msg):
        self.recording = False
        self.record_btn.setEnabled(True)
        self.record_btn.setProperty("recording", False)
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Error")
        self.status_label.setStyleSheet("color: #ff4040; font-size: 13px; font-weight: 600;")
        QMessageBox.critical(self, "Recording Error", msg)

    def _on_finished(self, path):
        self.recording = False
        self.record_btn.setEnabled(True)
        self.record_btn.setProperty("recording", False)
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(f"Saved → {Path(path).name}")
        self.status_label.setStyleSheet("color: #50ff80; font-size: 13px; font-weight: 600;")

        # Reset after a few seconds
        QTimer.singleShot(5000, lambda: (
            self.status_label.setText("Ready"),
            self.status_label.setStyleSheet("color: #dc143c; font-size: 13px; font-weight: 600;")
        ))


# ═══════════════════════════════════════════════════════════════
# ENTRY
# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RedVerse Recorder")

    # Try loading Orbitron / Rajdhani if available system-wide
    try:
        from PyQt6.QtGui import QFontDatabase
        for fam in ["Orbitron", "Rajdhani"]:
            QFontDatabase.addApplicationFont(f"/usr/share/fonts/truetype/google/{fam}.ttf")
    except Exception:
        pass

    win = RedVerseRecorder()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
