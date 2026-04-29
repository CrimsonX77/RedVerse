#!/usr/bin/env python3
"""
RedVerse Voice Recorder
-----------------------
Voiceover recording studio for RedVerse Canon YouTube production.
Records, edits, processes and exports voice tracks for KDEnlive.

Features:
  - Live waveform display during recording
  - Pause/resume recording
  - Visual region selection for chop/trim/replace
  - Chapter/scene markers
  - Optional: noise reduction, normalisation, music bed
  - Export: MP3 / WAV / FLAC (chosen at export time)
  - Teleprompter panel with scrolling story text
"""

import sys
import os
import json
import time
import threading
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.io import wavfile
from scipy import signal as scipy_signal

import sounddevice as sd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QComboBox, QTabWidget,
    QFileDialog, QMessageBox, QProgressBar, QSpinBox, QGroupBox,
    QSlider, QSplitter, QCheckBox, QDialog, QDialogButtonBox,
    QFormLayout, QListWidget, QListWidgetItem, QScrollArea,
    QDoubleSpinBox, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QFontMetrics,
    QMouseEvent, QPaintEvent, QKeySequence, QShortcut
)

# ── optional deps ─────────────────────────────────────────────────────────────
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

try:
    import noisereduce as nr
    HAS_NR = True
except ImportError:
    HAS_NR = False

# ── constants ─────────────────────────────────────────────────────────────────
APP_NAME    = "RedVerse Voice Recorder"
CONFIG_PATH = Path.home() / ".config" / "redverse_recorder" / "config.json"
SAMPLE_RATE = 44100
CHANNELS    = 1
DTYPE       = np.float32
CHUNK_SIZE  = 1024

DARK_BG      = "#0d0d1a"
PANEL_BG     = "#16213e"
ACCENT       = "#e94560"
ACCENT2      = "#0f3460"
TEXT_COL     = "#e0e0e0"
MUTED        = "#888"
WAVEFORM_COL = "#e94560"
REGION_COL   = "#0f346088"
MARKER_COL   = "#f5a623"
PLAYHEAD_COL = "#ffffff"

DARK_STYLE = f"""
QMainWindow, QWidget {{ background-color: {DARK_BG}; color: {TEXT_COL}; }}
QTabWidget::pane {{ border: 1px solid #333; background: {DARK_BG}; }}
QTabBar::tab {{ background: {PANEL_BG}; color: #aaa; padding: 8px 18px; border-radius: 4px 4px 0 0; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {ACCENT2}; color: {ACCENT}; font-weight: bold; }}
QTextEdit, QLineEdit {{ background: {PANEL_BG}; color: {TEXT_COL}; border: 1px solid #333; border-radius: 4px; padding: 4px; }}
QPushButton {{ background: {ACCENT2}; color: {TEXT_COL}; border: none; border-radius: 5px; padding: 8px 18px; font-size: 13px; }}
QPushButton:hover {{ background: {ACCENT}; }}
QPushButton:disabled {{ background: #222; color: #555; }}
QPushButton#rec_btn {{ background: {ACCENT}; font-weight: bold; font-size: 15px; }}
QPushButton#rec_btn:checked {{ background: #8b0000; }}
QComboBox {{ background: {PANEL_BG}; color: {TEXT_COL}; border: 1px solid #333; border-radius: 4px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: {PANEL_BG}; color: {TEXT_COL}; selection-background-color: {ACCENT2}; }}
QGroupBox {{ border: 1px solid #333; border-radius: 6px; margin-top: 10px; padding-top: 8px; }}
QGroupBox::title {{ color: {ACCENT}; subcontrol-origin: margin; left: 10px; font-weight: bold; }}
QProgressBar {{ background: {PANEL_BG}; border: 1px solid #333; border-radius: 4px; text-align: center; height: 16px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QSlider::groove:horizontal {{ background: #333; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QListWidget {{ background: {PANEL_BG}; color: {TEXT_COL}; border: 1px solid #333; border-radius: 4px; }}
QListWidget::item:selected {{ background: {ACCENT2}; color: {ACCENT}; }}
QLabel {{ color: {TEXT_COL}; }}
QCheckBox {{ color: {TEXT_COL}; spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #555; border-radius: 3px; background: {PANEL_BG}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QSpinBox, QDoubleSpinBox {{ background: {PANEL_BG}; color: {TEXT_COL}; border: 1px solid #333; border-radius: 4px; padding: 4px; }}
QScrollBar:vertical {{ background: {PANEL_BG}; width: 8px; }}
QScrollBar::handle:vertical {{ background: #444; border-radius: 4px; min-height: 20px; }}
QSplitter::handle {{ background: #333; }}
"""

# ── config ────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try: return json.loads(CONFIG_PATH.read_text())
        except: pass
    return {
        "input_device": None,
        "output_dir": str(Path.home() / "Videos" / "RedVerse" / "voiceovers"),
        "noise_reduce": False,
        "normalise": True,
        "music_bed_path": "",
        "music_bed_volume": -18,
        "teleprompter_size": 16,
        "scroll_speed": 3,
    }

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ── waveform widget ───────────────────────────────────────────────────────────
class WaveformWidget(QWidget):
    """Interactive waveform display with region selection and markers."""

    region_changed  = pyqtSignal(float, float)   # start_s, end_s
    marker_added    = pyqtSignal(float, str)      # pos_s, label

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.audio:    Optional[np.ndarray] = None
        self.sr:       int   = SAMPLE_RATE
        self.duration: float = 0.0

        self.playhead:   float = 0.0
        self.region_start: Optional[float] = None
        self.region_end:   Optional[float] = None
        self.markers:    list  = []       # [{pos_s, label}]

        self._drag_start: Optional[int] = None
        self._peaks: Optional[np.ndarray] = None

        self._redraw_timer = QTimer(self)
        self._redraw_timer.timeout.connect(self.update)
        self._redraw_timer.start(50)

    # ── data ──────────────────────────────────────────────────────────────────
    def set_audio(self, audio: np.ndarray, sr: int):
        self.audio    = audio
        self.sr       = sr
        self.duration = len(audio) / sr
        self.region_start = None
        self.region_end   = None
        self.playhead     = 0.0
        self._compute_peaks()
        self.update()

    def _compute_peaks(self):
        if self.audio is None or len(self.audio) == 0:
            self._peaks = None
            return
        w = max(self.width(), 100)
        chunk = max(1, len(self.audio) // w)
        n = len(self.audio) // chunk
        peaks = np.abs(self.audio[:n * chunk].reshape(n, chunk)).max(axis=1)
        self._peaks = peaks / (peaks.max() + 1e-9)

    def resizeEvent(self, e):
        self._compute_peaks()

    # ── coordinate helpers ────────────────────────────────────────────────────
    def _x_to_sec(self, x: int) -> float:
        if self.duration <= 0: return 0.0
        return max(0.0, min(self.duration, x / self.width() * self.duration))

    def _sec_to_x(self, s: float) -> int:
        if self.duration <= 0: return 0
        return int(s / self.duration * self.width())

    # ── mouse ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position().x()
            self.region_start = self._x_to_sec(int(e.position().x()))
            self.region_end   = None
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_start is not None:
            self.region_end = self._x_to_sec(int(e.position().x()))
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self.region_end = self._x_to_sec(int(e.position().x()))
            if self.region_start is not None and self.region_end is not None:
                s = min(self.region_start, self.region_end)
                en = max(self.region_start, self.region_end)
                if en - s > 0.05:
                    self.region_start, self.region_end = s, en
                    self.region_changed.emit(s, en)
                else:
                    self.region_start = self.region_end = None
            self._drag_start = None
            self.update()

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        pos = self._x_to_sec(int(e.position().x()))
        label, ok = _quick_input(self, "Marker label", f"Mark {pos:.1f}s")
        if ok:
            self.markers.append({"pos_s": pos, "label": label})
            self.marker_added.emit(pos, label)
            self.update()

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid = h // 2

        # background
        p.fillRect(0, 0, w, h, QColor(PANEL_BG))

        # region highlight
        if self.region_start is not None and self.region_end is not None:
            rx = self._sec_to_x(min(self.region_start, self.region_end))
            rw = self._sec_to_x(max(self.region_start, self.region_end)) - rx
            p.fillRect(rx, 0, rw, h, QColor(ACCENT2 + "99"))
            p.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DashLine))
            p.drawRect(rx, 0, rw, h - 1)

        # waveform
        if self._peaks is not None and len(self._peaks) > 0:
            p.setPen(QPen(QColor(WAVEFORM_COL), 1))
            step = w / len(self._peaks)
            for i, peak in enumerate(self._peaks):
                x = int(i * step)
                ph = int(peak * (mid - 4))
                p.drawLine(x, mid - ph, x, mid + ph)
        else:
            p.setPen(QPen(QColor(MUTED), 1, Qt.PenStyle.DashLine))
            p.drawLine(0, mid, w, mid)
            p.setPen(QColor(MUTED))
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No audio — press ● to record")

        # markers
        p.setFont(QFont("Monospace", 8))
        for mk in self.markers:
            mx = self._sec_to_x(mk["pos_s"])
            p.setPen(QPen(QColor(MARKER_COL), 2))
            p.drawLine(mx, 0, mx, h)
            p.setPen(QColor(MARKER_COL))
            p.drawText(mx + 3, 12, mk["label"])

        # playhead
        if self.duration > 0:
            px = self._sec_to_x(self.playhead)
            p.setPen(QPen(QColor(PLAYHEAD_COL), 2))
            p.drawLine(px, 0, px, h)

        # timecode
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Monospace", 9))
        p.drawText(4, h - 4, f"{self.duration:.2f}s  |  {'drag to select region  |  dbl-click to add marker' if self.duration > 0 else ''}")

    # ── public helpers ────────────────────────────────────────────────────────
    def set_playhead(self, sec: float):
        self.playhead = sec
        self.update()

    def clear_region(self):
        self.region_start = self.region_end = None
        self.update()

    def get_region(self) -> Optional[tuple]:
        if self.region_start is not None and self.region_end is not None:
            return min(self.region_start, self.region_end), max(self.region_start, self.region_end)
        return None

    def remove_marker_at(self, idx: int):
        if 0 <= idx < len(self.markers):
            self.markers.pop(idx)
            self.update()


# ── live recording buffer ─────────────────────────────────────────────────────
class RecordWorker(QThread):
    chunk_ready = pyqtSignal(np.ndarray)
    stopped     = pyqtSignal()

    def __init__(self, device=None):
        super().__init__()
        self.device   = device
        self._paused  = False
        self._running = False
        self._lock    = threading.Lock()
        self.buffer: list[np.ndarray] = []

    def run(self):
        self._running = True
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            device=self.device,
            blocksize=CHUNK_SIZE,
        ) as stream:
            while self._running:
                data, _ = stream.read(CHUNK_SIZE)
                chunk = data[:, 0] if data.ndim > 1 else data.flatten()
                with self._lock:
                    if not self._paused:
                        self.buffer.append(chunk.copy())
                        self.chunk_ready.emit(chunk.copy())
                time.sleep(0)
        self.stopped.emit()

    def pause(self):
        with self._lock: self._paused = True

    def resume(self):
        with self._lock: self._paused = False

    def stop(self):
        self._running = False

    def get_audio(self) -> np.ndarray:
        with self._lock:
            if not self.buffer: return np.zeros(0, dtype=DTYPE)
            return np.concatenate(self.buffer)


# ── playback worker ───────────────────────────────────────────────────────────
class PlaybackWorker(QThread):
    position_update = pyqtSignal(float)
    finished        = pyqtSignal()
    error           = pyqtSignal(str)

    def __init__(self, audio: np.ndarray, sr: int, start: float = 0.0):
        super().__init__()
        self.audio      = audio
        self.sr         = sr
        self.start_pos  = start
        self._stop      = False

    def run(self):
        try:
            start_sample = int(self.start_pos * self.sr)
            chunk = 2048
            pos   = start_sample
            # Find a working output device
            device = None
            try:
                for i, d in enumerate(sd.query_devices()):
                    if d["max_output_channels"] > 0 and d["hostapi"] == sd.default.hostapi:
                        device = i
                        break
            except Exception:
                pass
            with sd.OutputStream(samplerate=self.sr, channels=1, dtype=DTYPE, device=device) as stream:
                while pos < len(self.audio) and not self._stop:
                    end = min(pos + chunk, len(self.audio))
                    stream.write(self.audio[pos:end])
                    self.position_update.emit(pos / self.sr)
                    pos = end
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def stop(self):
        self._stop = True


# ── processing helpers ────────────────────────────────────────────────────────
def normalise(audio: np.ndarray) -> np.ndarray:
    peak = np.abs(audio).max()
    if peak > 0: return audio / peak * 0.9
    return audio

def noise_reduce(audio: np.ndarray, sr: int) -> np.ndarray:
    if not HAS_NR: return audio
    try:
        return nr.reduce_noise(y=audio, sr=sr, stationary=False)
    except Exception:
        return audio

def mix_music_bed(voice: np.ndarray, sr: int, music_path: str, vol_db: float) -> np.ndarray:
    if not HAS_PYDUB or not music_path or not Path(music_path).exists():
        return voice
    music = AudioSegment.from_file(music_path)
    music = music.set_frame_rate(sr).set_channels(1)
    music_arr = np.array(music.get_array_of_samples(), dtype=np.float32) / 32768.0
    # loop if shorter
    if len(music_arr) < len(voice):
        reps = (len(voice) // len(music_arr)) + 1
        music_arr = np.tile(music_arr, reps)
    music_arr = music_arr[:len(voice)]
    gain = 10 ** (vol_db / 20.0)
    return voice + music_arr * gain


# ── quick input helper ────────────────────────────────────────────────────────
def _quick_input(parent, title: str, default: str = "") -> tuple:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(DARK_STYLE)
    lay = QVBoxLayout(dlg)
    edit = QLineEdit(default)
    lay.addWidget(edit)
    btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    btn.accepted.connect(dlg.accept)
    btn.rejected.connect(dlg.reject)
    lay.addWidget(btn)
    ok = dlg.exec() == QDialog.DialogCode.Accepted
    return edit.text(), ok


# ── export dialog ─────────────────────────────────────────────────────────────
class ExportDialog(QDialog):
    def __init__(self, default_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Audio")
        self.setStyleSheet(DARK_STYLE)
        self.resize(420, 220)
        lay = QFormLayout(self)

        self.path_edit = QLineEdit(default_path)
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse)
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        rl.addWidget(self.path_edit); rl.addWidget(btn_browse)
        lay.addRow("Save as:", row)

        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["mp3", "wav", "flac"])
        self.fmt_combo.currentTextChanged.connect(self._update_ext)
        lay.addRow("Format:", self.fmt_combo)

        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["128k", "192k", "320k"])
        self.bitrate_combo.setCurrentText("192k")
        lay.addRow("Bitrate (MP3):", self.bitrate_combo)

        self.nr_check   = QCheckBox("Noise reduction")
        self.norm_check = QCheckBox("Normalise levels")
        self.norm_check.setChecked(True)
        lay.addRow(self.nr_check)
        lay.addRow(self.norm_check)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export As", self.path_edit.text())
        if path: self.path_edit.setText(path)

    def _update_ext(self, fmt: str):
        p = Path(self.path_edit.text())
        self.path_edit.setText(str(p.with_suffix(f".{fmt}")))

    def get_options(self) -> dict:
        return {
            "path":       self.path_edit.text(),
            "format":     self.fmt_combo.currentText(),
            "bitrate":    self.bitrate_combo.currentText(),
            "nr":         self.nr_check.isChecked(),
            "normalise":  self.norm_check.isChecked(),
        }


# ── main window ───────────────────────────────────────────────────────────────
class RedVerseRecorder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()

        self.audio: Optional[np.ndarray] = None
        self.sr     = SAMPLE_RATE
        self._rec_worker:  Optional[RecordWorker]  = None
        self._play_worker: Optional[PlaybackWorker] = None
        self._live_chunks: list[np.ndarray] = []
        self._recording = False
        self._paused_rec = False

        self._init_ui()
        self.setStyleSheet(DARK_STYLE)
        self._refresh_devices()

        # keyboard shortcuts
        QShortcut(QKeySequence("Space"), self, self._toggle_playback)
        QShortcut(QKeySequence("R"),     self, self._toggle_record)
        QShortcut(QKeySequence("Delete"),self, self._chop_region)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 820)

        tabs = QTabWidget()
        tabs.addTab(self._build_studio_tab(),      "🎙 Studio")
        tabs.addTab(self._build_teleprompter_tab(),"📜 Teleprompter")
        tabs.addTab(self._build_markers_tab(),     "🚩 Markers")
        tabs.addTab(self._build_settings_tab(),    "⚙️ Settings")
        self.setCentralWidget(tabs)

        sb = self.statusBar()
        self._status_time = QLabel("00:00.000")
        self._status_time.setStyleSheet(f"color:{ACCENT};font-family:Monospace;font-size:13px;font-weight:bold;")
        self._status_mode = QLabel("IDLE")
        self._status_mode.setStyleSheet(f"color:{MUTED};font-size:11px;")
        sb.addPermanentWidget(self._status_time)
        sb.addWidget(self._status_mode)

    # ── studio tab ────────────────────────────────────────────────────────────
    def _build_studio_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)

        # device row
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Input:"))
        self.dev_combo = QComboBox(); self.dev_combo.setMinimumWidth(280)
        btn_refresh = QPushButton("↻"); btn_refresh.setFixedWidth(32)
        btn_refresh.clicked.connect(self._refresh_devices)
        dev_row.addWidget(self.dev_combo)
        dev_row.addWidget(btn_refresh)
        dev_row.addStretch()
        lay.addLayout(dev_row)

        # waveform
        wf_grp = QGroupBox("Waveform")
        wf_lay = QVBoxLayout(wf_grp)
        self.waveform = WaveformWidget()
        self.waveform.region_changed.connect(self._on_region_changed)
        self.waveform.marker_added.connect(self._on_marker_added)
        wf_lay.addWidget(self.waveform)

        # region info bar
        self.region_label = QLabel("No region selected  |  Drag on waveform to select  |  Dbl-click to add marker")
        self.region_label.setStyleSheet(f"color:{MUTED};font-size:11px;")
        wf_lay.addWidget(self.region_label)
        lay.addWidget(wf_grp, stretch=2)

        # transport
        transport = QGroupBox("Transport")
        tr_lay = QHBoxLayout(transport)

        self.btn_rec = QPushButton("● REC")
        self.btn_rec.setObjectName("rec_btn")
        self.btn_rec.setCheckable(True)
        self.btn_rec.setFixedWidth(100)
        self.btn_rec.clicked.connect(self._toggle_record)

        self.btn_pause_rec = QPushButton("⏸ Pause")
        self.btn_pause_rec.setEnabled(False)
        self.btn_pause_rec.setFixedWidth(90)
        self.btn_pause_rec.clicked.connect(self._pause_rec)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setFixedWidth(90)
        self.btn_play.clicked.connect(self._toggle_playback)

        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setFixedWidth(90)
        self.btn_stop.clicked.connect(self._stop_all)

        tr_lay.addWidget(self.btn_rec)
        tr_lay.addWidget(self.btn_pause_rec)
        tr_lay.addSpacing(16)
        tr_lay.addWidget(self.btn_play)
        tr_lay.addWidget(self.btn_stop)
        tr_lay.addSpacing(16)

        # level meter
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedWidth(120)
        self.level_bar.setFixedHeight(18)
        tr_lay.addWidget(QLabel("Level:"))
        tr_lay.addWidget(self.level_bar)
        tr_lay.addStretch()
        lay.addWidget(transport)

        # edit toolbar
        edit_grp = QGroupBox("Edit")
        edit_lay = QHBoxLayout(edit_grp)

        self.btn_chop    = QPushButton("✂ Chop Region")
        self.btn_chop.setToolTip("Delete selected region (Del)")
        self.btn_chop.clicked.connect(self._chop_region)

        self.btn_replace = QPushButton("🔁 Record Replace")
        self.btn_replace.setToolTip("Re-record selected region")
        self.btn_replace.clicked.connect(self._replace_region)

        self.btn_trim    = QPushButton("⇤ Trim to Region")
        self.btn_trim.setToolTip("Keep only selected region")
        self.btn_trim.clicked.connect(self._trim_to_region)

        self.btn_undo    = QPushButton("↩ Undo")
        self.btn_undo.clicked.connect(self._undo)

        self.btn_load    = QPushButton("📂 Load Audio")
        self.btn_load.clicked.connect(self._load_audio)

        self.btn_export  = QPushButton("💾 Export")
        self.btn_export.setStyleSheet(f"background:{ACCENT};font-weight:bold;")
        self.btn_export.clicked.connect(self._export)

        for btn in [self.btn_chop, self.btn_replace, self.btn_trim,
                    self.btn_undo, self.btn_load, self.btn_export]:
            edit_lay.addWidget(btn)
        edit_lay.addStretch()
        lay.addWidget(edit_grp)

        self._undo_stack: list[np.ndarray] = []
        return w

    # ── teleprompter tab ──────────────────────────────────────────────────────
    def _build_teleprompter_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        btn_load_txt = QPushButton("📂 Load Text")
        btn_load_txt.clicked.connect(self._load_teleprompter)
        self.tp_size_spin = QSpinBox()
        self.tp_size_spin.setRange(10, 48)
        self.tp_size_spin.setValue(self.cfg.get("teleprompter_size", 16))
        self.tp_size_spin.valueChanged.connect(self._update_tp_font)
        ctrl.addWidget(btn_load_txt)
        ctrl.addWidget(QLabel("Font size:"))
        ctrl.addWidget(self.tp_size_spin)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.teleprompter = QTextEdit()
        self.teleprompter.setPlaceholderText(
            "Paste story text here or load a file…\n\n"
            "This panel stays visible while you record in the Studio tab."
        )
        self._update_tp_font(self.tp_size_spin.value())
        lay.addWidget(self.teleprompter, stretch=1)
        return w

    # ── markers tab ──────────────────────────────────────────────────────────
    def _build_markers_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Double-click the waveform to add markers. Click a marker to jump to it."))

        self.marker_list = QListWidget()
        self.marker_list.itemDoubleClicked.connect(self._jump_to_marker)
        lay.addWidget(self.marker_list)

        btn_row = QHBoxLayout()
        btn_del_mk = QPushButton("🗑 Delete Selected Marker")
        btn_del_mk.clicked.connect(self._delete_marker)
        btn_clear_mk = QPushButton("🗑 Clear All Markers")
        btn_clear_mk.clicked.connect(self._clear_markers)
        btn_row.addWidget(btn_del_mk)
        btn_row.addWidget(btn_clear_mk)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        return w

    # ── settings tab ─────────────────────────────────────────────────────────
    def _build_settings_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        grp_out = QGroupBox("Output")
        out_lay = QFormLayout(grp_out)
        self.out_dir_edit = QLineEdit(self.cfg.get("output_dir",""))
        btn_od = QPushButton("…"); btn_od.setFixedWidth(32)
        btn_od.clicked.connect(self._browse_out_dir)
        od_row = QWidget(); odl = QHBoxLayout(od_row); odl.setContentsMargins(0,0,0,0)
        odl.addWidget(self.out_dir_edit); odl.addWidget(btn_od)
        out_lay.addRow("Output folder:", od_row)
        lay.addWidget(grp_out)

        grp_music = QGroupBox("Music Bed (optional)")
        ml = QFormLayout(grp_music)
        self.music_path_edit = QLineEdit(self.cfg.get("music_bed_path",""))
        btn_mp = QPushButton("…"); btn_mp.setFixedWidth(32)
        btn_mp.clicked.connect(self._browse_music)
        mp_row = QWidget(); mpl = QHBoxLayout(mp_row); mpl.setContentsMargins(0,0,0,0)
        mpl.addWidget(self.music_path_edit); mpl.addWidget(btn_mp)
        ml.addRow("Music file:", mp_row)
        self.music_vol_spin = QDoubleSpinBox()
        self.music_vol_spin.setRange(-60, 0)
        self.music_vol_spin.setValue(self.cfg.get("music_bed_volume",-18))
        self.music_vol_spin.setSuffix(" dB")
        ml.addRow("Music volume:", self.music_vol_spin)
        lay.addWidget(grp_music)

        btn_save = QPushButton("💾 Save Settings")
        btn_save.setStyleSheet(f"background:{ACCENT};font-weight:bold;")
        btn_save.clicked.connect(self._save_settings)
        lay.addWidget(btn_save)
        lay.addStretch()
        return w

    # ── devices ───────────────────────────────────────────────────────────────
    def _refresh_devices(self):
        self.dev_combo.clear()
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    self.dev_combo.addItem(f"{i}: {d['name']}", i)
        except Exception as e:
            self.statusBar().showMessage(f"Audio device error: {e}")

    # ── recording ─────────────────────────────────────────────────────────────
    def _toggle_record(self):
        if not self._recording:
            self._start_record()
        else:
            self._stop_record()

    def _start_record(self):
        dev_idx = self.dev_combo.currentData()
        self._rec_worker = RecordWorker(device=dev_idx)
        self._rec_worker.chunk_ready.connect(self._on_chunk)
        self._rec_worker.stopped.connect(self._on_rec_stopped)
        self._live_chunks = []
        self._recording   = True
        self._paused_rec  = False
        self._rec_worker.start()
        self.btn_rec.setText("■ STOP REC")
        self.btn_rec.setChecked(True)
        self.btn_pause_rec.setEnabled(True)
        self._status_mode.setText("● RECORDING")
        self._status_mode.setStyleSheet(f"color:{ACCENT};font-weight:bold;")

    def _stop_record(self):
        if self._rec_worker:
            self.audio = self._rec_worker.get_audio()
            self._rec_worker.stop()
        self._recording  = False
        self._paused_rec = False
        self.btn_rec.setText("● REC")
        self.btn_rec.setChecked(False)
        self.btn_pause_rec.setEnabled(False)
        self.btn_pause_rec.setText("⏸ Pause")
        self._status_mode.setText("IDLE")
        self._status_mode.setStyleSheet(f"color:{MUTED};")
        if self.audio is not None and len(self.audio) > 0:
            self.waveform.set_audio(self.audio, self.sr)
            dur = len(self.audio) / self.sr
            self.statusBar().showMessage(f"Recorded {dur:.2f}s")

    def _pause_rec(self):
        if not self._rec_worker: return
        if not self._paused_rec:
            self._rec_worker.pause()
            self._paused_rec = True
            self.btn_pause_rec.setText("▶ Resume")
            self._status_mode.setText("⏸ PAUSED")
        else:
            self._rec_worker.resume()
            self._paused_rec = False
            self.btn_pause_rec.setText("⏸ Pause")
            self._status_mode.setText("● RECORDING")

    def _on_chunk(self, chunk: np.ndarray):
        self._live_chunks.append(chunk)
        # live waveform update
        if len(self._live_chunks) % 8 == 0:
            combined = np.concatenate(self._live_chunks)
            self.waveform.set_audio(combined, self.sr)
        # level meter
        rms = float(np.sqrt(np.mean(chunk**2)))
        self.level_bar.setValue(min(100, int(rms * 400)))

    def _on_rec_stopped(self):
        pass

    # ── playback ──────────────────────────────────────────────────────────────
    def _toggle_playback(self):
        if self._play_worker and self._play_worker.isRunning():
            self._play_worker.stop()
            self.btn_play.setText("▶ Play")
            return
        if self.audio is None or len(self.audio) == 0:
            return
        start = self.waveform.playhead
        self._play_worker = PlaybackWorker(self.audio, self.sr, start)
        self._play_worker.position_update.connect(self.waveform.set_playhead)
        self._play_worker.position_update.connect(self._update_timecode)
        self._play_worker.finished.connect(self._on_play_finished)
        self._play_worker.error.connect(lambda msg: self.statusBar().showMessage(f"Playback error: {msg}"))
        self._play_worker.start()
        self.btn_play.setText("⏸ Pause")
        self._status_mode.setText("▶ PLAYING")

    def _on_play_finished(self):
        self.btn_play.setText("▶ Play")
        self._status_mode.setText("IDLE")
        self._status_mode.setStyleSheet(f"color:{MUTED};")

    def _stop_all(self):
        if self._play_worker: self._play_worker.stop()
        if self._recording:   self._stop_record()
        self.btn_play.setText("▶ Play")

    def _update_timecode(self, sec: float):
        m = int(sec // 60)
        s = sec % 60
        self._status_time.setText(f"{m:02d}:{s:06.3f}")

    # ── edit ops ──────────────────────────────────────────────────────────────
    def _push_undo(self):
        if self.audio is not None:
            self._undo_stack.append(self.audio.copy())
            if len(self._undo_stack) > 20: self._undo_stack.pop(0)

    def _undo(self):
        if self._undo_stack:
            self.audio = self._undo_stack.pop()
            self.waveform.set_audio(self.audio, self.sr)
            self.statusBar().showMessage("Undo ✓")

    def _chop_region(self):
        region = self.waveform.get_region()
        if region is None or self.audio is None:
            return
        self._push_undo()
        s, e = int(region[0] * self.sr), int(region[1] * self.sr)
        self.audio = np.concatenate([self.audio[:s], self.audio[e:]])
        self.waveform.set_audio(self.audio, self.sr)
        self.waveform.clear_region()
        self.statusBar().showMessage(f"Chopped {region[1]-region[0]:.2f}s")

    def _trim_to_region(self):
        region = self.waveform.get_region()
        if region is None or self.audio is None:
            return
        self._push_undo()
        s, e = int(region[0] * self.sr), int(region[1] * self.sr)
        self.audio = self.audio[s:e]
        self.waveform.set_audio(self.audio, self.sr)
        self.waveform.clear_region()
        self.statusBar().showMessage(f"Trimmed to {region[1]-region[0]:.2f}s")

    def _replace_region(self):
        region = self.waveform.get_region()
        if region is None or self.audio is None:
            QMessageBox.information(self, "Replace", "Select a region first.")
            return
        s_samp = int(region[0] * self.sr)
        e_samp = int(region[1] * self.sr)
        dur    = region[1] - region[0]
        self.statusBar().showMessage(f"Recording replacement for {dur:.2f}s… press ■ STOP REC when done")
        self._push_undo()

        dev_idx = self.dev_combo.currentData()
        tmp_worker = RecordWorker(device=dev_idx)
        tmp_worker.start()

        def _after():
            new_seg = tmp_worker.get_audio()
            tmp_worker.stop()
            # pad or trim to region length
            if len(new_seg) < e_samp - s_samp:
                new_seg = np.pad(new_seg, (0, (e_samp - s_samp) - len(new_seg)))
            else:
                new_seg = new_seg[:e_samp - s_samp]
            self.audio = np.concatenate([self.audio[:s_samp], new_seg, self.audio[e_samp:]])
            self.waveform.set_audio(self.audio, self.sr)
            self.waveform.clear_region()
            self.statusBar().showMessage("Replace complete ✓")

        QTimer.singleShot(int(dur * 1000) + 500, _after)

    # ── markers ───────────────────────────────────────────────────────────────
    def _on_marker_added(self, pos: float, label: str):
        self.marker_list.addItem(QListWidgetItem(f"[{pos:.2f}s] {label}"))

    def _jump_to_marker(self, item: QListWidgetItem):
        row = self.marker_list.row(item)
        if row < len(self.waveform.markers):
            pos = self.waveform.markers[row]["pos_s"]
            self.waveform.set_playhead(pos)

    def _delete_marker(self):
        row = self.marker_list.currentRow()
        if row >= 0:
            self.waveform.remove_marker_at(row)
            self.marker_list.takeItem(row)

    def _clear_markers(self):
        self.waveform.markers.clear()
        self.marker_list.clear()
        self.waveform.update()

    # ── region info ───────────────────────────────────────────────────────────
    def _on_region_changed(self, s: float, e: float):
        self.region_label.setText(f"Region: {s:.3f}s → {e:.3f}s  ({e-s:.3f}s selected)")

    # ── teleprompter ──────────────────────────────────────────────────────────
    def _load_teleprompter(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Text", "", "Text files (*.txt *.md);;All (*)")
        if path:
            self.teleprompter.setPlainText(Path(path).read_text(encoding="utf-8"))

    def _update_tp_font(self, size: int):
        self.teleprompter.setFont(QFont("Georgia", size))

    # ── load audio ────────────────────────────────────────────────────────────
    def _load_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Audio", "", "Audio (*.wav *.mp3 *.flac);;All (*)")
        if not path: return
        try:
            if HAS_PYDUB:
                seg = AudioSegment.from_file(path).set_frame_rate(SAMPLE_RATE).set_channels(1)
                arr = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
                self.audio = arr
                self.sr    = SAMPLE_RATE
            else:
                sr, data = wavfile.read(path)
                self.audio = data.astype(np.float32) / 32768.0
                self.sr    = sr
            self.waveform.set_audio(self.audio, self.sr)
            self.statusBar().showMessage(f"Loaded {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    # ── export ────────────────────────────────────────────────────────────────
    def _export(self):
        if self.audio is None or len(self.audio) == 0:
            QMessageBox.warning(self, "Nothing to export", "Record or load audio first.")
            return
        out_dir  = self.cfg.get("output_dir", str(Path.home()))
        default  = str(Path(out_dir) / "voiceover.mp3")
        dlg      = ExportDialog(default, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        opts     = dlg.get_options()

        audio = self.audio.copy()

        if opts["nr"]:
            self.statusBar().showMessage("Applying noise reduction…")
            audio = noise_reduce(audio, self.sr)

        if opts["normalise"]:
            audio = normalise(audio)

        music = self.music_path_edit.text().strip() if hasattr(self, "music_path_edit") else ""
        if music:
            audio = mix_music_bed(audio, self.sr, music, self.music_vol_spin.value())

        Path(opts["path"]).parent.mkdir(parents=True, exist_ok=True)
        fmt = opts["format"]

        try:
            if fmt == "wav":
                out_int = (audio * 32767).astype(np.int16)
                wavfile.write(opts["path"], self.sr, out_int)
            elif HAS_PYDUB:
                out_int = (audio * 32767).astype(np.int16)
                seg = AudioSegment(
                    out_int.tobytes(),
                    frame_rate=self.sr,
                    sample_width=2,
                    channels=1,
                )
                kw = {"bitrate": opts["bitrate"]} if fmt == "mp3" else {}
                seg.export(opts["path"], format=fmt, **kw)
            else:
                QMessageBox.warning(self, "Export", "pydub required for MP3/FLAC export. Saving as WAV.")
                p = Path(opts["path"]).with_suffix(".wav")
                wavfile.write(str(p), self.sr, (audio * 32767).astype(np.int16))

            self.statusBar().showMessage(f"✅ Exported: {opts['path']}")
            QMessageBox.information(self, "Exported!", f"Saved to:\n{opts['path']}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ── settings ──────────────────────────────────────────────────────────────
    def _save_settings(self):
        self.cfg["output_dir"]       = self.out_dir_edit.text().strip()
        self.cfg["music_bed_path"]   = self.music_path_edit.text().strip()
        self.cfg["music_bed_volume"] = self.music_vol_spin.value()
        self.cfg["teleprompter_size"]= self.tp_size_spin.value()
        save_config(self.cfg)
        self.statusBar().showMessage("Settings saved ✓", 3000)

    def _browse_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Output Folder", self.out_dir_edit.text())
        if d: self.out_dir_edit.setText(d)

    def _browse_music(self):
        p, _ = QFileDialog.getOpenFileName(self, "Music Bed", "", "Audio (*.mp3 *.wav *.flac *.ogg);;All (*)")
        if p: self.music_path_edit.setText(p)

    def closeEvent(self, e):
        self._stop_all()
        super().closeEvent(e)


# ── entry ─────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = RedVerseRecorder()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
