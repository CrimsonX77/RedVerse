"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  REDVOX — Transcription Dock v0.1.0                                        ║
║  "Hear what they said. Read what they meant. Share what matters."           ║
║                                                                             ║
║  A desktop tool for transcribing MP3 audio (NotebookLM podcasts, voice     ║
║  notes, conversations) into text for sharing with AI collaborators.         ║
║                                                                             ║
║  Built for Crimson by Vera Lux | Redverse Tooling                          ║
║                                                                             ║
║  Dependencies:                                                              ║
║    Required:  PyQt6, faster-whisper                                         ║
║    Optional:  pydub (for MP3→WAV conversion fallback)                       ║
║               ffmpeg (system-level, for audio processing)                   ║
║                                                                             ║
║  Install:                                                                   ║
║    pip install PyQt6 faster-whisper pydub                                   ║
║    # Also ensure ffmpeg is installed on your system                         ║
║    # Linux:  sudo apt install ffmpeg                                        ║
║    # macOS:  brew install ffmpeg                                            ║
║    # Windows: download from ffmpeg.org and add to PATH                     ║
║                                                                             ║
║  Usage:                                                                     ║
║    python redvox.py                                                         ║
║    python redvox.py --model small   (specify whisper model size)            ║
║    python redvox.py --output ~/transcripts  (default export directory)      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import json
import argparse
import signal
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QProgressBar,
    QComboBox, QStatusBar, QFrame, QSplitter, QMessageBox,
    QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize,
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QAction, QKeySequence,
    QTextCursor,
)


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RedVox] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("redvox")


# ─── Lazy Imports for Transcription Backend ───────────────────────────────────

_WHISPER_AVAILABLE = False
_WHISPER_ERROR = ""

try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError as e:
    _WHISPER_ERROR = (
        "faster-whisper not installed.\n"
        "Install with: pip install faster-whisper\n"
        "Also requires ffmpeg on your system."
    )
    logger.warning(_WHISPER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Whisper model sizes: tiny, base, small, medium, large-v3
# Smaller = faster but less accurate. 'small' is a good balance.
DEFAULT_MODEL_SIZE = "small"
DEFAULT_OUTPUT_DIR = str(Path.home() / "RedVox_Transcripts")

# Supported audio formats
SUPPORTED_FORMATS = "Audio Files (*.mp3 *.wav *.m4a *.ogg *.flac *.webm *.mp4);;All Files (*)"


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPTION WORKER (runs in separate thread)
# ═══════════════════════════════════════════════════════════════════════════════

class TranscriptionWorker(QThread):
    """
    Background worker that handles audio transcription.
    Emits progress updates and the final transcript.
    """

    # Signals
    progress = pyqtSignal(int, str)           # (percentage, status_message)
    segment_ready = pyqtSignal(str, float, float)  # (text, start_time, end_time)
    finished = pyqtSignal(str)                 # full_transcript
    error = pyqtSignal(str)                    # error_message

    def __init__(
        self,
        file_path: str,
        model_size: str = DEFAULT_MODEL_SIZE,
        language: Optional[str] = None,
    ):
        super().__init__()
        self.file_path = file_path
        self.model_size = model_size
        self.language = language
        self._is_cancelled = False

    def cancel(self):
        """Request cancellation of the transcription."""
        self._is_cancelled = True

    def run(self):
        """Execute transcription in background thread."""
        try:
            if not _WHISPER_AVAILABLE:
                self.error.emit(_WHISPER_ERROR)
                return

            # ─── Load model ───────────────────────────────────────
            self.progress.emit(5, f"Loading Whisper model ({self.model_size})...")
            logger.info(f"Loading model: {self.model_size}")

            model = WhisperModel(
                self.model_size,
                device="cpu",          # Change to "cuda" if you have GPU
                compute_type="int8",   # Fastest for CPU
            )

            if self._is_cancelled:
                return

            # ─── Transcribe ───────────────────────────────────────
            self.progress.emit(15, "Transcribing audio... (this may take a moment)")
            logger.info(f"Transcribing: {self.file_path}")

            segments, info = model.transcribe(
                self.file_path,
                language=self.language,
                beam_size=5,
                vad_filter=True,       # Voice Activity Detection — skips silence
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
            )

            # ─── Process segments ─────────────────────────────────
            total_duration = info.duration or 1.0
            full_lines = []
            processed_duration = 0.0

            self.progress.emit(20, f"Processing audio ({total_duration:.0f}s detected)...")

            for segment in segments:
                if self._is_cancelled:
                    self.progress.emit(0, "Cancelled.")
                    return

                text = segment.text.strip()
                if text:
                    # Emit segment for real-time display
                    self.segment_ready.emit(text, segment.start, segment.end)
                    full_lines.append(text)

                # Update progress
                processed_duration = segment.end
                pct = min(95, int(20 + (processed_duration / total_duration) * 75))
                self.progress.emit(
                    pct,
                    f"Transcribing... {processed_duration:.0f}s / {total_duration:.0f}s"
                )

            # ─── Complete ─────────────────────────────────────────
            full_transcript = "\n\n".join(full_lines)
            self.progress.emit(100, "Transcription complete!")
            logger.info(
                f"Transcription complete: {len(full_lines)} segments, "
                f"{len(full_transcript)} characters"
            )
            self.finished.emit(full_transcript)

        except FileNotFoundError:
            self.error.emit(
                f"File not found: {self.file_path}\n"
                "Make sure the file exists and the path is correct."
            )
        except Exception as e:
            logger.exception("Transcription failed")
            self.error.emit(f"Transcription failed:\n{str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# STYLES — THE CRIMSON AESTHETIC
# ═══════════════════════════════════════════════════════════════════════════════

CRIMSON_STYLESHEET = """
/* ─── Global ──────────────────────────────────────────────────── */
QMainWindow {
    background-color: #0d0d0d;
}

QWidget {
    color: #e0d6cc;
    font-family: 'Segoe UI', 'Crimson Pro', sans-serif;
    font-size: 13px;
}

/* ─── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background-color: #1a1215;
    color: #d4a0a0;
    border: 1px solid #3d1c1c;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #2d1a1e;
    border-color: #8b3a3a;
    color: #f0c0c0;
}

QPushButton:pressed {
    background-color: #3d1c1c;
}

QPushButton:disabled {
    background-color: #111111;
    color: #555555;
    border-color: #222222;
}

QPushButton#btn_primary {
    background-color: #4a1a1a;
    border-color: #8b3a3a;
    color: #f0d0d0;
    font-size: 14px;
}

QPushButton#btn_primary:hover {
    background-color: #6b2a2a;
    border-color: #b05050;
}

QPushButton#btn_danger {
    background-color: #1a0a0a;
    border-color: #5a2020;
    color: #c07070;
}

QPushButton#btn_danger:hover {
    background-color: #3a1515;
}

/* ─── Text Areas ──────────────────────────────────────────────── */
QTextEdit {
    background-color: #0f0a0a;
    color: #d8cfc5;
    border: 1px solid #2a1515;
    border-radius: 6px;
    padding: 10px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    selection-background-color: #4a1a1a;
    selection-color: #f0d0d0;
}

QTextEdit:focus {
    border-color: #6b2a2a;
}

/* ─── Labels ──────────────────────────────────────────────────── */
QLabel {
    color: #b0a090;
    font-size: 12px;
}

QLabel#title {
    color: #c07070;
    font-size: 20px;
    font-weight: 700;
    font-family: 'Cinzel', 'Georgia', serif;
    padding: 4px 0;
}

QLabel#subtitle {
    color: #8a7060;
    font-size: 11px;
    font-style: italic;
}

QLabel#file_label {
    color: #a08070;
    font-size: 12px;
    padding: 4px 8px;
    background-color: #150e0e;
    border: 1px solid #2a1515;
    border-radius: 4px;
}

/* ─── ComboBox ────────────────────────────────────────────────── */
QComboBox {
    background-color: #1a1215;
    color: #d4a0a0;
    border: 1px solid #3d1c1c;
    border-radius: 4px;
    padding: 5px 10px;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #6b2a2a;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1a1215;
    color: #d4a0a0;
    border: 1px solid #3d1c1c;
    selection-background-color: #3d1c1c;
}

/* ─── Progress Bar ────────────────────────────────────────────── */
QProgressBar {
    background-color: #150e0e;
    border: 1px solid #2a1515;
    border-radius: 4px;
    height: 12px;
    text-align: center;
    color: #a08070;
    font-size: 10px;
}

QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a1a1a,
        stop:0.5 #8b3a3a,
        stop:1 #6b2a2a
    );
    border-radius: 3px;
}

/* ─── Status Bar ──────────────────────────────────────────────── */
QStatusBar {
    background-color: #0a0808;
    color: #6a5a50;
    border-top: 1px solid #1a1010;
    font-size: 11px;
    padding: 2px 8px;
}

/* ─── Group Box ───────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #2a1515;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
    color: #8a6060;
}

QGroupBox::title {
    subcontrol-origin: margin;
    padding: 0 8px;
    color: #a07070;
}

/* ─── Frames / Separators ─────────────────────────────────────── */
QFrame#separator {
    background-color: #2a1515;
    max-height: 1px;
}

/* ─── Scrollbar ───────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #0d0d0d;
    width: 10px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #3d1c1c;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5a2a2a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class RedVoxWindow(QMainWindow):
    """
    RedVox — Transcription Dock

    Main application window with file selection, transcription controls,
    transcript display, and export functionality.
    """

    def __init__(self, default_model: str = DEFAULT_MODEL_SIZE,
                 default_output: str = DEFAULT_OUTPUT_DIR):
        super().__init__()

        self.default_output_dir = default_output
        self.current_file: Optional[str] = None
        self.current_transcript: Optional[str] = None
        self.worker: Optional[TranscriptionWorker] = None
        self._is_shutting_down = False

        self._setup_window()
        self._build_ui(default_model)
        self._connect_signals()
        self._setup_shortcuts()
        self._update_button_states()

        # Ensure output directory exists
        Path(self.default_output_dir).mkdir(parents=True, exist_ok=True)

        self.statusBar().showMessage("Ready — Load an audio file to begin")
        logger.info("RedVox initialized")

    # ═══════════════════════════════════════════════════════════════
    # WINDOW SETUP
    # ═══════════════════════════════════════════════════════════════

    def _setup_window(self):
        """Configure the main window properties."""
        self.setWindowTitle("🩸 RedVox — Transcription Dock")
        self.setMinimumSize(720, 600)
        self.resize(900, 700)
        self.setStyleSheet(CRIMSON_STYLESHEET)

    def _build_ui(self, default_model: str):
        """Construct the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)

        # ─── Header ──────────────────────────────────────────────
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        title = QLabel("RedVox")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        header_layout.addWidget(title)

        subtitle = QLabel("Transcription Dock — Hear what they said. Share what matters.")
        subtitle.setObjectName("subtitle")
        header_layout.addWidget(subtitle)

        layout.addLayout(header_layout)

        # ─── Separator ───────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ─── Controls Row ────────────────────────────────────────
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        # File select button
        self.btn_load = QPushButton("📂  Load Audio")
        self.btn_load.setObjectName("btn_primary")
        self.btn_load.setToolTip("Select an MP3, WAV, or other audio file")
        controls_layout.addWidget(self.btn_load)

        # File label
        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setObjectName("file_label")
        self.lbl_file.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        controls_layout.addWidget(self.lbl_file)

        # Model selector
        model_label = QLabel("Model:")
        controls_layout.addWidget(model_label)

        self.cmb_model = QComboBox()
        self.cmb_model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.cmb_model.setCurrentText(default_model)
        self.cmb_model.setToolTip(
            "Whisper model size.\n"
            "tiny/base = fast, less accurate\n"
            "small = good balance (recommended)\n"
            "medium/large = slow, most accurate"
        )
        controls_layout.addWidget(self.cmb_model)

        layout.addLayout(controls_layout)

        # ─── Action Buttons Row ──────────────────────────────────
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.btn_transcribe = QPushButton("🎙  Transcribe")
        self.btn_transcribe.setObjectName("btn_primary")
        self.btn_transcribe.setToolTip("Start transcription (Ctrl+T)")
        actions_layout.addWidget(self.btn_transcribe)

        self.btn_cancel = QPushButton("✕  Cancel")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setToolTip("Cancel current transcription")
        self.btn_cancel.setVisible(False)
        actions_layout.addWidget(self.btn_cancel)

        actions_layout.addStretch()

        self.btn_refresh = QPushButton("⟳  Refresh")
        self.btn_refresh.setToolTip("Clear transcript and reset (Ctrl+R)")
        actions_layout.addWidget(self.btn_refresh)

        layout.addLayout(actions_layout)

        # ─── Progress Bar ────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        # ─── Transcript Display ──────────────────────────────────
        transcript_label = QLabel("TRANSCRIPT")
        transcript_label.setStyleSheet(
            "color: #6b4040; font-size: 11px; font-weight: 700; "
            "letter-spacing: 3px; padding-top: 4px;"
        )
        layout.addWidget(transcript_label)

        self.txt_transcript = QTextEdit()
        self.txt_transcript.setPlaceholderText(
            "Transcribed text will appear here...\n\n"
            "Load an audio file and click Transcribe to begin."
        )
        self.txt_transcript.setReadOnly(True)
        self.txt_transcript.setMinimumHeight(200)
        layout.addWidget(self.txt_transcript, stretch=1)

        # ─── Export Row ──────────────────────────────────────────
        export_layout = QHBoxLayout()
        export_layout.setSpacing(10)

        self.btn_export = QPushButton("💾  Export to File")
        self.btn_export.setToolTip("Save transcript as .txt file (Ctrl+S)")
        export_layout.addWidget(self.btn_export)

        self.btn_export_to = QPushButton("📁  Export to Directory...")
        self.btn_export_to.setToolTip("Choose a specific directory to save to")
        export_layout.addWidget(self.btn_export_to)

        self.btn_copy = QPushButton("📋  Copy to Clipboard")
        self.btn_copy.setToolTip("Copy transcript to clipboard (Ctrl+C when unfocused)")
        export_layout.addWidget(self.btn_copy)

        export_layout.addStretch()

        # Word/char count
        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("color: #5a4a40; font-size: 11px;")
        export_layout.addWidget(self.lbl_stats)

        layout.addLayout(export_layout)

        # ─── Status Bar ──────────────────────────────────────────
        self.setStatusBar(QStatusBar())

    # ═══════════════════════════════════════════════════════════════
    # SIGNALS & SHORTCUTS
    # ═══════════════════════════════════════════════════════════════

    def _connect_signals(self):
        """Wire up all button signals."""
        self.btn_load.clicked.connect(self._on_load_file)
        self.btn_transcribe.clicked.connect(self._on_transcribe)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_refresh.clicked.connect(self._on_refresh)
        self.btn_export.clicked.connect(self._on_export_default)
        self.btn_export_to.clicked.connect(self._on_export_to_directory)
        self.btn_copy.clicked.connect(self._on_copy_clipboard)

    def _setup_shortcuts(self):
        """Register keyboard shortcuts."""
        # Ctrl+O — Open file
        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_load_file)
        self.addAction(open_action)

        # Ctrl+T — Transcribe
        transcribe_action = QAction("Transcribe", self)
        transcribe_action.setShortcut(QKeySequence("Ctrl+T"))
        transcribe_action.triggered.connect(self._on_transcribe)
        self.addAction(transcribe_action)

        # Ctrl+R — Refresh
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(self._on_refresh)
        self.addAction(refresh_action)

        # Ctrl+S — Save/Export
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._on_export_default)
        self.addAction(save_action)

        # Ctrl+Q — Quit
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def _update_button_states(self):
        """Enable/disable buttons based on current state."""
        has_file = self.current_file is not None
        has_transcript = bool(self.current_transcript)
        is_working = self.worker is not None and self.worker.isRunning()

        self.btn_transcribe.setEnabled(has_file and not is_working)
        self.btn_load.setEnabled(not is_working)
        self.btn_cancel.setVisible(is_working)
        self.btn_export.setEnabled(has_transcript and not is_working)
        self.btn_export_to.setEnabled(has_transcript and not is_working)
        self.btn_copy.setEnabled(has_transcript and not is_working)
        self.cmb_model.setEnabled(not is_working)
        self.btn_refresh.setEnabled(not is_working)

    # ═══════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def _on_load_file(self):
        """Open file dialog to select an audio file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            str(Path.home()),
            SUPPORTED_FORMATS,
        )

        if file_path:
            self.current_file = file_path
            filename = Path(file_path).name
            size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            self.lbl_file.setText(f"{filename}  ({size_mb:.1f} MB)")
            self.statusBar().showMessage(f"Loaded: {filename}")
            logger.info(f"File loaded: {file_path}")
            self._update_button_states()

    def _on_transcribe(self):
        """Start the transcription process."""
        if not self.current_file:
            self.statusBar().showMessage("No file loaded — click Load Audio first")
            return

        if not _WHISPER_AVAILABLE:
            QMessageBox.warning(
                self,
                "Missing Dependency",
                "faster-whisper is not installed.\n\n"
                "Install with:\n"
                "  pip install faster-whisper\n\n"
                "You also need ffmpeg installed on your system.",
            )
            return

        # Clear previous transcript
        self.txt_transcript.clear()
        self.current_transcript = None
        self.lbl_stats.setText("")

        # Show progress
        self.progress.setVisible(True)
        self.progress.setValue(0)

        # Start worker
        model_size = self.cmb_model.currentText()
        self.worker = TranscriptionWorker(
            file_path=self.current_file,
            model_size=model_size,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.segment_ready.connect(self._on_segment)
        self.worker.finished.connect(self._on_transcription_complete)
        self.worker.error.connect(self._on_transcription_error)
        self.worker.start()

        self.statusBar().showMessage(f"Transcribing with {model_size} model...")
        self._update_button_states()
        logger.info(f"Transcription started: model={model_size}")

    def _on_cancel(self):
        """Cancel the current transcription."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.statusBar().showMessage("Cancelling...")
            logger.info("Transcription cancelled by user")

    def _on_refresh(self):
        """Reset the application state."""
        # Cancel any running work
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)

        self.current_file = None
        self.current_transcript = None
        self.txt_transcript.clear()
        self.lbl_file.setText("No file loaded")
        self.lbl_stats.setText("")
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self._update_button_states()

        self.statusBar().showMessage("Refreshed — Ready for new audio")
        logger.info("Application refreshed")

    def _on_export_default(self):
        """Export transcript to the default output directory."""
        if not self.current_transcript:
            self.statusBar().showMessage("Nothing to export")
            return

        self._export_to_directory(self.default_output_dir)

    def _on_export_to_directory(self):
        """Let user pick an export directory."""
        if not self.current_transcript:
            self.statusBar().showMessage("Nothing to export")
            return

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Export Directory",
            self.default_output_dir,
        )

        if directory:
            self._export_to_directory(directory)

    def _export_to_directory(self, directory: str):
        """Save the transcript to a specific directory."""
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)

        # Generate filename from source audio name + timestamp
        source_name = Path(self.current_file).stem if self.current_file else "transcript"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source_name}_{timestamp}.txt"
        file_path = dir_path / filename

        try:
            # Write transcript with metadata header
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# RedVox Transcription\n")
                f.write(f"# Source: {self.current_file}\n")
                f.write(f"# Date: {datetime.now().isoformat()}\n")
                f.write(f"# Model: {self.cmb_model.currentText()}\n")
                f.write(f"# ─────────────────────────────────────\n\n")
                f.write(self.current_transcript)

            self.statusBar().showMessage(f"Exported to: {file_path}")
            logger.info(f"Transcript exported: {file_path}")

            # Brief visual confirmation
            self.btn_export.setText("✓  Exported!")
            QTimer.singleShot(2000, lambda: self.btn_export.setText("💾  Export to File"))

        except Exception as e:
            QMessageBox.critical(
                self, "Export Failed", f"Could not save file:\n{str(e)}"
            )
            logger.error(f"Export failed: {e}")

    def _on_copy_clipboard(self):
        """Copy transcript to system clipboard."""
        if not self.current_transcript:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(self.current_transcript)
        self.statusBar().showMessage("Transcript copied to clipboard")

        # Brief visual confirmation
        self.btn_copy.setText("✓  Copied!")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋  Copy to Clipboard"))

    # ═══════════════════════════════════════════════════════════════
    # WORKER CALLBACKS
    # ═══════════════════════════════════════════════════════════════

    def _on_progress(self, percentage: int, message: str):
        """Update progress bar from worker."""
        self.progress.setValue(percentage)
        self.progress.setFormat(f"{percentage}% — {message}")
        self.statusBar().showMessage(message)

    def _on_segment(self, text: str, start: float, end: float):
        """Display a segment as it's transcribed (real-time streaming)."""
        # Format timestamp
        start_str = self._format_timestamp(start)
        end_str = self._format_timestamp(end)

        # Append to display with subtle timestamp
        cursor = self.txt_transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Add spacing between segments
        if cursor.position() > 0:
            cursor.insertText("\n\n")

        cursor.insertText(text)
        self.txt_transcript.setTextCursor(cursor)
        self.txt_transcript.ensureCursorVisible()

    def _on_transcription_complete(self, full_transcript: str):
        """Handle completed transcription."""
        self.current_transcript = full_transcript
        self.progress.setVisible(False)
        self._update_button_states()

        # Update stats
        words = len(full_transcript.split())
        chars = len(full_transcript)
        self.lbl_stats.setText(f"{words:,} words  ·  {chars:,} chars")

        self.statusBar().showMessage(
            f"Transcription complete — {words:,} words extracted"
        )

    def _on_transcription_error(self, error_msg: str):
        """Handle transcription errors."""
        self.progress.setVisible(False)
        self._update_button_states()
        self.statusBar().showMessage("Transcription failed")

        QMessageBox.critical(self, "Transcription Error", error_msg)
        logger.error(f"Transcription error: {error_msg}")

    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds into MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    # ═══════════════════════════════════════════════════════════════
    # GRACEFUL SHUTDOWN
    # ═══════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        """
        Graceful shutdown — ensures background threads are properly
        terminated before the application exits.
        """
        if self._is_shutting_down:
            event.accept()
            return

        self._is_shutting_down = True
        logger.info("Shutdown requested")

        # Cancel any running transcription
        if self.worker and self.worker.isRunning():
            logger.info("Waiting for transcription worker to finish...")
            self.statusBar().showMessage("Shutting down... waiting for worker")
            self.worker.cancel()

            # Give the worker a few seconds to finish gracefully
            if not self.worker.wait(5000):
                logger.warning("Worker did not finish in time — forcing termination")
                self.worker.terminate()
                self.worker.wait(2000)

        logger.info("RedVox shutdown complete")
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Launch the RedVox Transcription Dock."""
    parser = argparse.ArgumentParser(
        description="RedVox — Transcription Dock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python redvox.py                          # Launch with defaults\n"
            "  python redvox.py --model small             # Use 'small' whisper model\n"
            "  python redvox.py --output ~/my_transcripts # Custom export directory\n"
        ),
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL_SIZE,
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help=f"Whisper model size (default: {DEFAULT_MODEL_SIZE})",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Default export directory (default: {DEFAULT_OUTPUT_DIR})",
    )

    args = parser.parse_args()

    # ─── Setup signal handling for clean Ctrl+C ───────────────────
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # ─── Launch ───────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("RedVox")
    app.setOrganizationName("Redverse")

    window = RedVoxWindow(
        default_model=args.model,
        default_output=args.output,
    )
    window.show()

    logger.info("RedVox is live")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
