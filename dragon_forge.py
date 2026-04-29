#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  DRAGON FORGE — Media Converter                                  ║
║  Convert images, audio, and video between formats                ║
║  Part of the Dragon Tools ecosystem                              ║
║  Requires: PyQt6, Pillow, ffmpeg (system)                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QFrame, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
    QCheckBox, QSlider, QSpinBox, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QDragEnterEvent, QDropEvent, QPixmap

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

IMAGE_FORMATS = {
    'PNG': {'ext': '.png', 'desc': 'Portable Network Graphics'},
    'JPEG': {'ext': '.jpg', 'desc': 'Joint Photographic Experts Group'},
    'WebP': {'ext': '.webp', 'desc': 'Web Picture Format'},
    'BMP': {'ext': '.bmp', 'desc': 'Bitmap'},
    'TIFF': {'ext': '.tiff', 'desc': 'Tagged Image File Format'},
    'GIF': {'ext': '.gif', 'desc': 'Graphics Interchange Format'},
    'ICO': {'ext': '.ico', 'desc': 'Icon Format'},
}

AUDIO_FORMATS = {
    'MP3': {'ext': '.mp3', 'desc': 'MPEG Audio Layer III'},
    'WAV': {'ext': '.wav', 'desc': 'Waveform Audio'},
    'FLAC': {'ext': '.flac', 'desc': 'Free Lossless Audio Codec'},
    'AAC': {'ext': '.aac', 'desc': 'Advanced Audio Coding'},
    'OGG': {'ext': '.ogg', 'desc': 'Ogg Vorbis'},
    'AIFF': {'ext': '.aiff', 'desc': 'Audio Interchange File Format'},
    'WMA': {'ext': '.wma', 'desc': 'Windows Media Audio'},
    'OPUS': {'ext': '.opus', 'desc': 'Opus Interactive Audio'},
}

VIDEO_FORMATS = {
    'MP4': {'ext': '.mp4', 'desc': 'MPEG-4 Part 14'},
    'MKV': {'ext': '.mkv', 'desc': 'Matroska Video'},
    'WebM': {'ext': '.webm', 'desc': 'Web Media'},
    'AVI': {'ext': '.avi', 'desc': 'Audio Video Interleave'},
    'MOV': {'ext': '.mov', 'desc': 'QuickTime Movie'},
    'FLV': {'ext': '.flv', 'desc': 'Flash Video'},
    'WMV': {'ext': '.wmv', 'desc': 'Windows Media Video'},
    'GIF': {'ext': '.gif', 'desc': 'Animated GIF'},
}

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.gif', '.ico', '.svg'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.aiff', '.aif', '.wma', '.opus', '.m4a'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}

# ═══════════════════════════════════════════════════════════════
# STYLESHEET
# ═══════════════════════════════════════════════════════════════

STYLESHEET = """
QMainWindow {
    background: #0a0a0c;
}

QWidget#centralWidget {
    background: #0a0a0c;
}

QLabel {
    color: #e8e0d8;
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
}

QLabel#titleLabel {
    color: #c41230;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 3px;
}

QLabel#subtitleLabel {
    color: #6b7280;
    font-size: 11px;
    letter-spacing: 2px;
}

QLabel#sectionLabel {
    color: #d4a846;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 4px 0;
}

QLabel#fileInfoLabel {
    color: #9b8e82;
    font-size: 11px;
    padding: 2px 0;
}

QLabel#statusLabel {
    color: #b8c0cc;
    font-size: 11px;
    padding: 6px 12px;
    background: rgba(196, 18, 48, 0.05);
    border-left: 2px solid #c41230;
}

QPushButton {
    background: transparent;
    color: #b8c0cc;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 10px 24px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    min-height: 20px;
}

QPushButton:hover {
    border-color: rgba(196, 18, 48, 0.5);
    color: #e8e0d8;
    background: rgba(196, 18, 48, 0.08);
}

QPushButton:pressed {
    background: rgba(196, 18, 48, 0.15);
}

QPushButton#convertButton {
    background: rgba(196, 18, 48, 0.15);
    border: 1px solid rgba(196, 18, 48, 0.4);
    color: #c41230;
    font-size: 13px;
    letter-spacing: 2px;
    padding: 12px 36px;
    min-height: 24px;
}

QPushButton#convertButton:hover {
    background: rgba(196, 18, 48, 0.25);
    border-color: #c41230;
    color: #ff1a3d;
}

QPushButton#convertButton:disabled {
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.05);
    color: #4a4a4a;
}

QComboBox {
    background: #14101280;
    color: #e8e0d8;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 8px 12px;
    font-size: 12px;
    min-height: 20px;
    selection-background-color: rgba(196, 18, 48, 0.3);
}

QComboBox:hover {
    border-color: rgba(196, 18, 48, 0.3);
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6b7280;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: #1a1418;
    color: #e8e0d8;
    border: 1px solid rgba(196, 18, 48, 0.2);
    selection-background-color: rgba(196, 18, 48, 0.2);
    outline: none;
}

QProgressBar {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    height: 6px;
    text-align: center;
    font-size: 0px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #8b0a20, stop:1 #c41230);
}

QFrame#dropZone {
    background: rgba(196, 18, 48, 0.03);
    border: 1px dashed rgba(196, 18, 48, 0.2);
    border-radius: 4px;
    min-height: 120px;
}

QFrame#dropZone:hover {
    border-color: rgba(196, 18, 48, 0.5);
    background: rgba(196, 18, 48, 0.06);
}

QFrame#separator {
    background: rgba(255,255,255,0.04);
    max-height: 1px;
}

QGroupBox {
    background: transparent;
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 2px;
    margin-top: 16px;
    padding-top: 20px;
    font-size: 11px;
    color: #d4a846;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #d4a846;
    font-weight: bold;
    letter-spacing: 1px;
}

QCheckBox {
    color: #9b8e82;
    font-size: 11px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(255,255,255,0.15);
    background: transparent;
}

QCheckBox::indicator:checked {
    background: rgba(196, 18, 48, 0.5);
    border-color: #c41230;
}

QCheckBox:hover {
    color: #e8e0d8;
}

QSlider::groove:horizontal {
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 12px;
    height: 12px;
    margin: -4px 0;
    background: #c41230;
    border-radius: 6px;
}

QSlider::sub-page:horizontal {
    background: rgba(196, 18, 48, 0.4);
    border-radius: 2px;
}

QSpinBox {
    background: #14101280;
    color: #e8e0d8;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 4px 8px;
    font-size: 11px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
}

QScrollBar::handle:vertical {
    background: rgba(196, 18, 48, 0.3);
    min-height: 30px;
    border-radius: 3px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


# ═══════════════════════════════════════════════════════════════
# CONVERSION WORKER THREAD
# ═══════════════════════════════════════════════════════════════

class ConversionWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, input_path: str, output_path: str, media_type: str,
                 quality: int = 85, extra_args: list = None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.media_type = media_type
        self.quality = quality
        self.extra_args = extra_args or []

    def run(self):
        try:
            if self.media_type == 'image':
                self._convert_image()
            elif self.media_type in ('audio', 'video'):
                self._convert_ffmpeg()
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

    def _convert_image(self):
        from PIL import Image
        self.status.emit("Loading image...")
        self.progress.emit(20)

        img = Image.open(self.input_path)

        # Handle RGBA -> RGB for formats that don't support alpha
        out_ext = Path(self.output_path).suffix.lower()
        if out_ext in ('.jpg', '.jpeg', '.bmp', '.ico') and img.mode == 'RGBA':
            self.status.emit("Converting color space...")
            bg = Image.new('RGB', img.size, (0, 0, 0))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif out_ext in ('.jpg', '.jpeg', '.bmp') and img.mode != 'RGB':
            img = img.convert('RGB')

        self.progress.emit(60)
        self.status.emit("Saving...")

        save_kwargs = {}
        if out_ext in ('.jpg', '.jpeg'):
            save_kwargs['quality'] = self.quality
            save_kwargs['optimize'] = True
        elif out_ext == '.webp':
            save_kwargs['quality'] = self.quality
        elif out_ext == '.png':
            save_kwargs['optimize'] = True

        img.save(self.output_path, **save_kwargs)
        self.progress.emit(100)
        self.status.emit("Done!")

    def _convert_ffmpeg(self):
        self.status.emit("Preparing conversion...")
        self.progress.emit(10)

        cmd = ['ffmpeg', '-y', '-i', self.input_path]

        out_ext = Path(self.output_path).suffix.lower()

        # Audio quality mapping
        if self.media_type == 'audio':
            if out_ext == '.mp3':
                # Map quality 0-100 to bitrate 64-320
                bitrate = int(64 + (self.quality / 100) * 256)
                cmd.extend(['-b:a', f'{bitrate}k'])
            elif out_ext == '.flac':
                cmd.extend(['-compression_level', '8'])
            elif out_ext == '.ogg':
                q = int(self.quality / 10)
                cmd.extend(['-q:a', str(q)])
            elif out_ext == '.aac':
                bitrate = int(64 + (self.quality / 100) * 192)
                cmd.extend(['-b:a', f'{bitrate}k'])
            elif out_ext == '.opus':
                bitrate = int(32 + (self.quality / 100) * 224)
                cmd.extend(['-b:a', f'{bitrate}k'])

        # Video quality mapping
        elif self.media_type == 'video':
            if out_ext == '.gif':
                cmd.extend([
                    '-vf', 'fps=15,scale=480:-1:flags=lanczos',
                    '-loop', '0'
                ])
            elif out_ext in ('.mp4', '.mov'):
                crf = int(51 - (self.quality / 100) * 41)  # CRF 51 (worst) to 10 (best)
                cmd.extend(['-c:v', 'libx264', '-crf', str(crf), '-preset', 'medium'])
                if out_ext == '.mp4':
                    cmd.extend(['-movflags', '+faststart'])
            elif out_ext == '.webm':
                crf = int(63 - (self.quality / 100) * 53)
                cmd.extend(['-c:v', 'libvpx-vp9', '-crf', str(crf), '-b:v', '0'])
            elif out_ext == '.mkv':
                crf = int(51 - (self.quality / 100) * 41)
                cmd.extend(['-c:v', 'libx264', '-crf', str(crf)])

        cmd.extend(self.extra_args)
        cmd.append(self.output_path)

        self.progress.emit(30)
        self.status.emit("Converting...")

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, stderr = process.communicate()

        if process.returncode != 0:
            raise Exception(f"FFmpeg error: {stderr.decode()[-500:]}")

        self.progress.emit(100)
        self.status.emit("Done!")


# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════

class DragonForge(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dragon Forge — Media Converter")
        self.setMinimumSize(520, 680)
        self.resize(560, 740)
        self.setAcceptDrops(True)

        self.input_path: Optional[str] = None
        self.media_type: Optional[str] = None
        self.worker: Optional[ConversionWorker] = None

        self._setup_ui()
        self._update_state()

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # ─── Header ───
        title = QLabel("DRAGON FORGE")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("MEDIA CONVERTER")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ─── Drop Zone ───
        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("dropZone")
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.drop_label = QLabel("Drop file here or click Browse")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("color: #6b7280; font-size: 13px;")
        drop_layout.addWidget(self.drop_label)

        self.drop_hint = QLabel("Images • Audio • Video")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet("color: #4a4a4a; font-size: 10px; letter-spacing: 2px;")
        drop_layout.addWidget(self.drop_hint)

        layout.addWidget(self.drop_zone)

        # ─── Browse Button ───
        browse_btn = QPushButton("BROWSE FILES")
        browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(browse_btn)

        # ─── File Info ───
        self.file_info = QLabel("")
        self.file_info.setObjectName("fileInfoLabel")
        self.file_info.setWordWrap(True)
        layout.addWidget(self.file_info)

        # ─── Separator ───
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ─── Output Format ───
        fmt_label = QLabel("OUTPUT FORMAT")
        fmt_label.setObjectName("sectionLabel")
        layout.addWidget(fmt_label)

        self.format_combo = QComboBox()
        self.format_combo.setPlaceholderText("Select a file first...")
        self.format_combo.currentTextChanged.connect(self._update_state)
        layout.addWidget(self.format_combo)

        # ─── Quality Settings ───
        self.quality_group = QGroupBox("QUALITY")
        q_layout = QHBoxLayout(self.quality_group)

        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(85)
        self.quality_slider.setTickInterval(10)
        self.quality_slider.valueChanged.connect(self._quality_changed)
        q_layout.addWidget(self.quality_slider)

        self.quality_label = QLabel("85%")
        self.quality_label.setFixedWidth(40)
        self.quality_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.quality_label.setStyleSheet("color: #d4a846; font-family: monospace; font-size: 12px;")
        q_layout.addWidget(self.quality_label)

        layout.addWidget(self.quality_group)

        # ─── Output Location ───
        out_layout = QHBoxLayout()
        self.same_dir_check = QCheckBox("Save alongside original")
        self.same_dir_check.setChecked(True)
        out_layout.addWidget(self.same_dir_check)
        out_layout.addStretch()
        layout.addLayout(out_layout)

        layout.addSpacing(4)

        # ─── Convert Button ───
        self.convert_btn = QPushButton("⚔  CONVERT")
        self.convert_btn.setObjectName("convertButton")
        self.convert_btn.clicked.connect(self._start_conversion)
        layout.addWidget(self.convert_btn)

        # ─── Progress ───
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ─── Status ───
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # ─── Footer ───
        footer = QLabel("Dragon Tools  ✦  Built for the Forge")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #2a2a2a; font-size: 9px; letter-spacing: 2px;")
        layout.addWidget(footer)

    # ─── File Detection ───
    def _detect_media_type(self, filepath: str) -> Optional[str]:
        ext = Path(filepath).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            return 'image'
        elif ext in AUDIO_EXTENSIONS:
            return 'audio'
        elif ext in VIDEO_EXTENSIONS:
            return 'video'
        return None

    def _set_input_file(self, filepath: str):
        self.input_path = filepath
        self.media_type = self._detect_media_type(filepath)

        if not self.media_type:
            self.file_info.setText(f"⚠ Unsupported format: {Path(filepath).suffix}")
            self.file_info.setStyleSheet("color: #c41230; font-size: 11px;")
            self.format_combo.clear()
            self._update_state()
            return

        # Update file info
        size = os.path.getsize(filepath)
        size_str = self._format_size(size)
        name = Path(filepath).name
        self.file_info.setText(f"✦ {name}  ({size_str})  [{self.media_type.upper()}]")
        self.file_info.setStyleSheet("color: #b8c0cc; font-size: 11px;")

        # Update drop zone
        self.drop_label.setText(name)
        self.drop_label.setStyleSheet("color: #e8e0d8; font-size: 12px; font-weight: bold;")
        self.drop_hint.setText(f"{self.media_type.upper()} • {Path(filepath).suffix.upper()}")

        # Populate format options
        self.format_combo.clear()
        current_ext = Path(filepath).suffix.lower()

        if self.media_type == 'image':
            formats = IMAGE_FORMATS
        elif self.media_type == 'audio':
            formats = AUDIO_FORMATS
        else:
            formats = VIDEO_FORMATS

        for name, info in formats.items():
            if info['ext'] != current_ext and info['ext'] != current_ext.replace('.jpeg', '.jpg'):
                self.format_combo.addItem(f"{name}  ({info['ext']})", info['ext'])

        self._update_state()

    def _browse_file(self):
        all_exts = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        filter_str = "Media Files (" + " ".join(f"*{e}" for e in sorted(all_exts)) + ")"
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Media File", "", filter_str)
        if filepath:
            self._set_input_file(filepath)

    # ─── Drag & Drop ───
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.setStyleSheet(
                "QFrame#dropZone { border-color: rgba(196, 18, 48, 0.6); "
                "background: rgba(196, 18, 48, 0.1); }"
            )

    def dragLeaveEvent(self, event):
        self.drop_zone.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.drop_zone.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if filepath:
                self._set_input_file(filepath)

    # ─── Conversion ───
    def _start_conversion(self):
        if not self.input_path or self.format_combo.currentIndex() < 0:
            return

        out_ext = self.format_combo.currentData()
        input_path = Path(self.input_path)

        if self.same_dir_check.isChecked():
            output_path = input_path.parent / f"{input_path.stem}{out_ext}"
        else:
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Save As",
                str(input_path.parent / f"{input_path.stem}{out_ext}"),
                f"*{out_ext}"
            )
            if not output_path:
                return
            output_path = Path(output_path)

        # Handle name collision
        if output_path.exists():
            counter = 1
            while output_path.exists():
                output_path = input_path.parent / f"{input_path.stem}_{counter}{out_ext}"
                counter += 1

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = ConversionWorker(
            str(self.input_path),
            str(output_path),
            self.media_type,
            quality=self.quality_slider.value()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(lambda s: self.status_label.setText(s))
        self.worker.finished.connect(self._conversion_done)
        self.worker.start()

    def _conversion_done(self, success: bool, result: str):
        self.convert_btn.setEnabled(True)
        if success:
            size = os.path.getsize(result)
            name = Path(result).name
            self.status_label.setText(f"✦ Saved: {name} ({self._format_size(size)})")
            self.status_label.setStyleSheet(
                "color: #2ecc71; font-size: 11px; padding: 6px 12px; "
                "background: rgba(46, 204, 113, 0.05); border-left: 2px solid #2ecc71;"
            )
        else:
            self.status_label.setText(f"✖ Error: {result[:150]}")
            self.status_label.setStyleSheet(
                "color: #c41230; font-size: 11px; padding: 6px 12px; "
                "background: rgba(196, 18, 48, 0.05); border-left: 2px solid #c41230;"
            )

    # ─── Helpers ───
    def _quality_changed(self, value: int):
        self.quality_label.setText(f"{value}%")

    def _update_state(self):
        has_input = self.input_path is not None and self.media_type is not None
        has_format = self.format_combo.currentIndex() >= 0
        self.convert_btn.setEnabled(has_input and has_format)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    # Dark palette fallback
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(10, 10, 12))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(232, 224, 216))
    palette.setColor(QPalette.ColorRole.Base, QColor(20, 16, 18))
    palette.setColor(QPalette.ColorRole.Text, QColor(232, 224, 216))
    palette.setColor(QPalette.ColorRole.Button, QColor(20, 16, 18))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(184, 192, 204))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(196, 18, 48))
    app.setPalette(palette)

    window = DragonForge()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
