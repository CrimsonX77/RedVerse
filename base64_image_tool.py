"""
Base64 Image Tool — Encode & Decode
A standalone PyQt6 desktop application.
"""

import sys
import os
import base64
import hashlib
import re
import traceback
from io import BytesIO
from pathlib import Path

# ── Dependency pre-check ────────────────────────────────────────────────────
MISSING = []
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QTextEdit, QLabel, QFileDialog, QStatusBar,
        QSplitter, QFrame, QMessageBox, QProgressBar, QTabWidget,
        QCheckBox, QScrollArea, QSizePolicy, QGroupBox, QLineEdit,
        QDialog, QDialogButtonBox
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMimeData
    from PyQt6.QtGui import QPixmap, QImage, QColor, QPalette, QFont, QDragEnterEvent, QDropEvent, QClipboard
except ImportError:
    MISSING.append("PyQt6")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    MISSING.append("Pillow")

# ── Stylesheet ───────────────────────────────────────────────────────────────
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #2d2d4e;
    background-color: #16213e;
    border-radius: 6px;
}
QTabBar::tab {
    background: #0f3460;
    color: #a0a0c0;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #e94560;
    color: white;
}
QTabBar::tab:hover:!selected {
    background: #1a4a80;
    color: white;
}
QGroupBox {
    border: 1px solid #2d2d4e;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #a0c4ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QTextEdit, QLineEdit {
    background-color: #0d1b2a;
    border: 1px solid #2d2d4e;
    border-radius: 6px;
    color: #c8d8e8;
    padding: 6px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    selection-background-color: #e94560;
}
QTextEdit:focus, QLineEdit:focus {
    border: 1px solid #e94560;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #1a4a80;
}
QPushButton:pressed {
    background-color: #e94560;
}
QPushButton#danger {
    background-color: #5a1a2a;
    color: #ff8888;
}
QPushButton#danger:hover {
    background-color: #e94560;
    color: white;
}
QPushButton#success {
    background-color: #1a5a2a;
    color: #88ff88;
}
QPushButton#success:hover {
    background-color: #2a8a3a;
    color: white;
}
QPushButton#accent {
    background-color: #e94560;
    color: white;
}
QPushButton#accent:hover {
    background-color: #ff6080;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444466;
}
QStatusBar {
    background-color: #0f3460;
    color: #a0c4ff;
    border-top: 1px solid #2d2d4e;
}
QLabel#preview_placeholder {
    color: #444466;
    font-size: 14px;
    border: 2px dashed #2d2d4e;
    border-radius: 8px;
    padding: 40px;
}
QLabel#section_title {
    color: #e94560;
    font-size: 14px;
    font-weight: bold;
}
QLabel#info_label {
    color: #a0c4ff;
    font-size: 11px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QFrame#sandbox_frame {
    border: 2px solid #e94560;
    border-radius: 8px;
    background-color: #1a0d1a;
    padding: 8px;
}
QCheckBox {
    color: #a0c4ff;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #2d2d4e;
    background: #0d1b2a;
}
QCheckBox::indicator:checked {
    background: #e94560;
    border: 1px solid #e94560;
}
"""

LIGHT_STYLE = """
QMainWindow, QWidget {
    background-color: #f5f5f5;
    color: #1a1a2e;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #ccccdd;
    background-color: #ffffff;
    border-radius: 6px;
}
QTabBar::tab {
    background: #dde4f0;
    color: #333355;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #0f3460;
    color: white;
}
QTabBar::tab:hover:!selected {
    background: #bbc8e0;
}
QGroupBox {
    border: 1px solid #ccccdd;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #0f3460;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QTextEdit, QLineEdit {
    background-color: #ffffff;
    border: 1px solid #aaaacc;
    border-radius: 6px;
    color: #1a1a2e;
    padding: 6px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    selection-background-color: #0f3460;
    selection-color: white;
}
QTextEdit:focus, QLineEdit:focus {
    border: 1px solid #0f3460;
}
QPushButton {
    background-color: #0f3460;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #1a4a80;
}
QPushButton:pressed {
    background-color: #e94560;
}
QPushButton#danger {
    background-color: #e94560;
    color: white;
}
QPushButton#danger:hover {
    background-color: #ff6080;
}
QPushButton#success {
    background-color: #2a8a3a;
    color: white;
}
QPushButton#success:hover {
    background-color: #3aaa4a;
}
QPushButton#accent {
    background-color: #e94560;
    color: white;
}
QPushButton#accent:hover {
    background-color: #ff6080;
}
QPushButton:disabled {
    background-color: #ccccdd;
    color: #888888;
}
QStatusBar {
    background-color: #dde4f0;
    color: #333355;
    border-top: 1px solid #ccccdd;
}
QLabel#preview_placeholder {
    color: #aaaacc;
    font-size: 14px;
    border: 2px dashed #ccccdd;
    border-radius: 8px;
    padding: 40px;
}
QLabel#section_title {
    color: #e94560;
    font-size: 14px;
    font-weight: bold;
}
QLabel#info_label {
    color: #555588;
    font-size: 11px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QFrame#sandbox_frame {
    border: 2px solid #e94560;
    border-radius: 8px;
    background-color: #fff5f8;
    padding: 8px;
}
QCheckBox {
    color: #333355;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #aaaacc;
    background: white;
}
QCheckBox::indicator:checked {
    background: #0f3460;
    border: 1px solid #0f3460;
}
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def extract_base64_from_text(text: str) -> str | None:
    """Strip data URI prefix if present, then validate base64 payload."""
    text = text.strip()
    # Handle data URI like: data:image/png;base64,XXXX
    if text.startswith("data:"):
        match = re.search(r"base64,(.+)", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    # Remove whitespace
    text = re.sub(r"\s+", "", text)
    # Quick validity check
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", text):
        return None
    return text

def validate_base64(b64: str) -> tuple[bool, str]:
    """Returns (valid, message)."""
    try:
        data = base64.b64decode(b64, validate=True)
        return True, f"Valid base64 — {len(data):,} bytes decoded"
    except Exception as e:
        return False, f"Invalid base64: {e}"

def decode_base64_to_pixmap(b64: str) -> tuple[QPixmap | None, str, dict]:
    """Decode base64 string to QPixmap. Returns (pixmap, error_msg, metadata)."""
    try:
        data = base64.b64decode(b64, validate=True)
        image = QImage()
        ok = image.loadFromData(data)
        if not ok:
            return None, "Could not interpret data as an image format.", {}
        pixmap = QPixmap.fromImage(image)
        md5 = hashlib.md5(data).hexdigest()
        meta = {
            "size_bytes": len(data),
            "width": image.width(),
            "height": image.height(),
            "format": image.format().name if hasattr(image.format(), 'name') else str(image.format()),
            "md5": md5,
        }
        return pixmap, "", meta
    except Exception as e:
        return None, str(e), {}

def encode_image_to_base64(path: str) -> tuple[str | None, str, dict]:
    """Encode image file to base64. Returns (b64_string, error_msg, metadata)."""
    try:
        p = Path(path)
        if not p.exists():
            return None, "File not found.", {}
        with open(p, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("ascii")
        md5 = hashlib.md5(data).hexdigest()
        # Try to get image dimensions
        w, h = 0, 0
        img = QImage(path)
        if not img.isNull():
            w, h = img.width(), img.height()
        meta = {
            "filename": p.name,
            "size_bytes": len(data),
            "b64_length": len(b64),
            "width": w,
            "height": h,
            "md5": md5,
        }
        return b64, "", meta
    except Exception as e:
        return None, str(e), {}

def format_bytes(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

# ── Sandbox Confirm Dialog ────────────────────────────────────────────────────

class SandboxDialog(QDialog):
    def __init__(self, pixmap: QPixmap, meta: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠ Sandbox Confirmation")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        warn = QLabel("🛡 Review the image below before rendering it fully. Confirm to proceed.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #e94560; font-weight: bold;")
        layout.addWidget(warn)

        frame = QFrame()
        frame.setObjectName("sandbox_frame")
        fl = QVBoxLayout(frame)

        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scaled = pixmap.scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        preview_label.setPixmap(scaled)
        fl.addWidget(preview_label)

        info_lines = [
            f"Dimensions: {meta.get('width', '?')} × {meta.get('height', '?')} px",
            f"Decoded size: {format_bytes(meta.get('size_bytes', 0))}",
            f"MD5: {meta.get('md5', 'N/A')}",
        ]
        info_label = QLabel("\n".join(info_lines))
        info_label.setObjectName("info_label")
        fl.addWidget(info_label)
        layout.addWidget(frame)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("✓ Confirm & Render")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("✕ Discard")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

# ── Decode Tab ────────────────────────────────────────────────────────────────

class DecodeTab(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._pending_pixmap = None
        self._pending_meta = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Input group
        input_group = QGroupBox("Base64 Input")
        ig_layout = QVBoxLayout(input_group)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText(
            "Paste your Base64 string here — or use 'Auto-Paste' to grab from clipboard…"
        )
        self.input_box.setMinimumHeight(120)
        self.input_box.setMaximumHeight(180)
        ig_layout.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        self.btn_auto_paste = QPushButton("📋 Auto-Paste")
        self.btn_auto_paste.setToolTip("Search clipboard for Base64 string and paste it here")
        self.btn_auto_paste.clicked.connect(self.auto_paste)

        self.btn_clear = QPushButton("🗑 Clear")
        self.btn_clear.setObjectName("danger")
        self.btn_clear.clicked.connect(self.clear_input)

        self.btn_decode = QPushButton("🔓 Decode")
        self.btn_decode.setObjectName("accent")
        self.btn_decode.clicked.connect(self.do_decode)

        self.sandbox_check = QCheckBox("Sandbox mode (confirm before render)")
        self.sandbox_check.setChecked(True)

        btn_row.addWidget(self.btn_auto_paste)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(self.sandbox_check)
        btn_row.addWidget(self.btn_decode)
        ig_layout.addLayout(btn_row)
        layout.addWidget(input_group)

        # ── Preview group
        preview_group = QGroupBox("Image Preview")
        pg_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("No image decoded yet.\n\nPaste a Base64 string above and click Decode.")
        self.preview_label.setObjectName("preview_placeholder")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(200)
        pg_layout.addWidget(self.preview_label)

        self.meta_label = QLabel("")
        self.meta_label.setObjectName("info_label")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pg_layout.addWidget(self.meta_label)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 Save Image…")
        self.btn_save.setObjectName("success")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_image)

        self.btn_copy_img = QPushButton("📋 Copy to Clipboard")
        self.btn_copy_img.setEnabled(False)
        self.btn_copy_img.clicked.connect(self.copy_image)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.refresh)

        save_row.addWidget(self.btn_save)
        save_row.addWidget(self.btn_copy_img)
        save_row.addStretch()
        save_row.addWidget(self.btn_refresh)
        pg_layout.addLayout(save_row)
        layout.addWidget(preview_group, 1)

    def auto_paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            self.status_message.emit("⚠ Clipboard is empty.")
            return
        extracted = extract_base64_from_text(text)
        if extracted:
            self.input_box.setPlainText(extracted)
            self.status_message.emit(f"✓ Clipboard base64 pasted — {len(extracted):,} chars.")
        else:
            self.status_message.emit("⚠ No valid Base64 string found in clipboard.")

    def clear_input(self):
        self.input_box.clear()
        self._pending_pixmap = None
        self._pending_meta = {}
        self.preview_label.setText("No image decoded yet.\n\nPaste a Base64 string above and click Decode.")
        self.preview_label.setObjectName("preview_placeholder")
        self.meta_label.setText("")
        self.btn_save.setEnabled(False)
        self.btn_copy_img.setEnabled(False)
        self.status_message.emit("Cleared.")

    def refresh(self):
        if self.input_box.toPlainText().strip():
            self.do_decode()
        else:
            self.status_message.emit("Nothing to refresh — paste a Base64 string first.")

    def do_decode(self):
        raw = self.input_box.toPlainText().strip()
        if not raw:
            self.status_message.emit("⚠ Input is empty.")
            return

        b64 = extract_base64_from_text(raw)
        if not b64:
            self.status_message.emit("✕ Could not find valid Base64 data in input.")
            return

        valid, msg = validate_base64(b64)
        if not valid:
            self.status_message.emit(f"✕ Validation failed: {msg}")
            return

        pixmap, err, meta = decode_base64_to_pixmap(b64)
        if err:
            self.status_message.emit(f"✕ Decode error: {err}")
            return

        if self.sandbox_check.isChecked():
            dlg = SandboxDialog(pixmap, meta, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.status_message.emit("Decode cancelled by sandbox check.")
                return

        self._pending_pixmap = pixmap
        self._pending_meta = meta
        self._show_preview(pixmap, meta)

    def _show_preview(self, pixmap: QPixmap, meta: dict):
        max_w = max(self.preview_label.width() - 20, 400)
        max_h = 320
        scaled = pixmap.scaled(max_w, max_h,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setObjectName("")
        self.meta_label.setText(
            f"  {meta.get('width')}×{meta.get('height')} px  |  "
            f"{format_bytes(meta.get('size_bytes', 0))}  |  "
            f"MD5: {meta.get('md5', 'N/A')[:16]}…"
        )
        self.btn_save.setEnabled(True)
        self.btn_copy_img.setEnabled(True)
        self.status_message.emit(
            f"✓ Decoded {meta.get('width')}×{meta.get('height')} px "
            f"({format_bytes(meta.get('size_bytes', 0))})"
        )

    def save_image(self):
        if not self._pending_pixmap:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", str(Path.home()),
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;BMP Image (*.bmp);;All Files (*)"
        )
        if path:
            ok = self._pending_pixmap.save(path)
            if ok:
                self.status_message.emit(f"✓ Saved to {path}")
            else:
                self.status_message.emit(f"✕ Failed to save to {path}")

    def copy_image(self):
        if not self._pending_pixmap:
            return
        QApplication.clipboard().setPixmap(self._pending_pixmap)
        self.status_message.emit("✓ Image copied to clipboard.")


# ── Encode Tab ────────────────────────────────────────────────────────────────

class EncodeTab(QWidget):
    status_message = pyqtSignal(str)

    SUPPORTED = "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp *.ico);; All Files (*)"

    def __init__(self):
        super().__init__()
        self._b64_result = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Drop zone group
        drop_group = QGroupBox("Image Input — Drag & Drop or Browse")
        dg_layout = QVBoxLayout(drop_group)

        self.drop_label = QLabel("📂  Drag & drop an image here, or click Browse…")
        self.drop_label.setObjectName("preview_placeholder")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(140)
        dg_layout.addWidget(self.drop_label)

        self.image_info_label = QLabel("")
        self.image_info_label.setObjectName("info_label")
        self.image_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dg_layout.addWidget(self.image_info_label)

        btn_row = QHBoxLayout()
        self.btn_browse = QPushButton("📂 Browse…")
        self.btn_browse.clicked.connect(self.browse_image)
        self.btn_encode = QPushButton("🔒 Encode to Base64")
        self.btn_encode.setObjectName("accent")
        self.btn_encode.setEnabled(False)
        self.btn_encode.clicked.connect(self.do_encode)
        self.btn_clear_enc = QPushButton("🗑 Clear")
        self.btn_clear_enc.setObjectName("danger")
        self.btn_clear_enc.clicked.connect(self.clear_all)

        btn_row.addWidget(self.btn_browse)
        btn_row.addWidget(self.btn_clear_enc)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_encode)
        dg_layout.addLayout(btn_row)
        layout.addWidget(drop_group)

        # ── Output group
        output_group = QGroupBox("Base64 Output")
        og_layout = QVBoxLayout(output_group)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setPlaceholderText("Encoded Base64 string will appear here…")
        self.output_box.setMinimumHeight(120)
        og_layout.addWidget(self.output_box)

        out_btn_row = QHBoxLayout()
        self.btn_copy_b64 = QPushButton("📋 Copy to Clipboard")
        self.btn_copy_b64.setEnabled(False)
        self.btn_copy_b64.clicked.connect(self.copy_b64)

        self.btn_save_b64 = QPushButton("💾 Save to File…")
        self.btn_save_b64.setObjectName("success")
        self.btn_save_b64.setEnabled(False)
        self.btn_save_b64.clicked.connect(self.save_b64)

        self.include_header_check = QCheckBox("Include data URI header (data:image/...;base64,)")
        self.include_header_check.setChecked(False)

        out_btn_row.addWidget(self.include_header_check)
        out_btn_row.addStretch()
        out_btn_row.addWidget(self.btn_copy_b64)
        out_btn_row.addWidget(self.btn_save_b64)
        og_layout.addLayout(out_btn_row)
        layout.addWidget(output_group, 1)

        # Enable drag and drop on this widget
        self.setAcceptDrops(True)
        self._image_path = None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._load_image(path)

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", str(Path.home()), self.SUPPORTED)
        if path:
            self._load_image(path)

    def _load_image(self, path: str):
        img = QImage(path)
        if img.isNull():
            self.status_message.emit(f"✕ Could not load image: {path}")
            return
        self._image_path = path
        p = Path(path)
        px = QPixmap.fromImage(img)
        scaled = px.scaled(380, 130, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        self.drop_label.setPixmap(scaled)
        size = p.stat().st_size
        self.image_info_label.setText(
            f"{p.name}  |  {img.width()}×{img.height()} px  |  {format_bytes(size)}"
        )
        self.btn_encode.setEnabled(True)
        self.status_message.emit(f"✓ Loaded: {p.name}")

    def do_encode(self):
        if not self._image_path:
            return
        b64, err, meta = encode_image_to_base64(self._image_path)
        if err:
            self.status_message.emit(f"✕ Encode error: {err}")
            return

        if self.include_header_check.isChecked():
            ext = Path(self._image_path).suffix.lower().strip(".")
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
                    "bmp": "bmp", "webp": "webp", "ico": "x-icon", "tiff": "tiff"}.get(ext, "png")
            self._b64_result = f"data:image/{mime};base64,{b64}"
        else:
            self._b64_result = b64

        self.output_box.setPlainText(self._b64_result)
        self.btn_copy_b64.setEnabled(True)
        self.btn_save_b64.setEnabled(True)
        self.status_message.emit(
            f"✓ Encoded {meta.get('filename', '')} → {meta.get('b64_length', 0):,} chars "
            f"({format_bytes(meta.get('size_bytes', 0))})"
        )

    def copy_b64(self):
        if self._b64_result:
            QApplication.clipboard().setText(self._b64_result)
            self.status_message.emit("✓ Base64 copied to clipboard.")

    def save_b64(self):
        if not self._b64_result:
            return
        default_name = Path(self._image_path).stem + "_base64.txt" if self._image_path else "output_base64.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Base64 String", str(Path.home() / default_name),
            "Text File (*.txt);;All Files (*)"
        )
        if path:
            try:
                with open(path, "w") as f:
                    f.write(self._b64_result)
                self.status_message.emit(f"✓ Saved to {path}")
            except Exception as e:
                self.status_message.emit(f"✕ Save failed: {e}")

    def clear_all(self):
        self._image_path = None
        self._b64_result = ""
        self.drop_label.setText("📂  Drag & drop an image here, or click Browse…")
        self.image_info_label.setText("")
        self.output_box.clear()
        self.btn_encode.setEnabled(False)
        self.btn_copy_b64.setEnabled(False)
        self.btn_save_b64.setEnabled(False)
        self.status_message.emit("Cleared.")


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Base64 Image Tool")
        self.setMinimumSize(720, 640)
        self.resize(860, 720)
        self._dark_mode = True
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 6)
        main_layout.setSpacing(8)

        # ── Header bar
        header = QHBoxLayout()
        title = QLabel("🔷  Base64 Image Tool")
        title.setObjectName("section_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.theme_btn = QPushButton("☀ Light Mode")
        self.theme_btn.setFixedWidth(120)
        self.theme_btn.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_btn)

        quit_btn = QPushButton("⏻ Quit")
        quit_btn.setObjectName("danger")
        quit_btn.setFixedWidth(80)
        quit_btn.clicked.connect(self.graceful_shutdown)
        header.addWidget(quit_btn)
        main_layout.addLayout(header)

        # ── Tabs
        self.tabs = QTabWidget()
        self.decode_tab = DecodeTab()
        self.encode_tab = EncodeTab()
        self.tabs.addTab(self.decode_tab, "🔓  Decode  (Base64 → Image)")
        self.tabs.addTab(self.encode_tab, "🔒  Encode  (Image → Base64)")
        main_layout.addWidget(self.tabs, 1)

        # ── Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

        self.decode_tab.status_message.connect(self.status_bar.showMessage)
        self.encode_tab.status_message.connect(self.status_bar.showMessage)

    def _apply_theme(self):
        self.setStyleSheet(DARK_STYLE if self._dark_mode else LIGHT_STYLE)
        self.theme_btn.setText("☀ Light Mode" if self._dark_mode else "🌙 Dark Mode")

    def toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self._apply_theme()

    def graceful_shutdown(self):
        reply = QMessageBox.question(
            self, "Quit",
            "Are you sure you want to quit Base64 Image Tool?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QApplication.quit()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "Confirm Exit",
            "Close Base64 Image Tool?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


# ── Dependency check dialog ───────────────────────────────────────────────────

def show_missing_deps(missing: list[str]):
    app = QApplication.instance() or QApplication(sys.argv)
    msg = QMessageBox()
    msg.setWindowTitle("Missing Dependencies")
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText(
        f"The following required packages are missing:\n\n"
        + "\n".join(f"  • {m}" for m in missing)
        + f"\n\nInstall them with:\n  pip install {' '.join(missing)}"
    )
    msg.exec()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if "PyQt6" in MISSING:
        print("ERROR: PyQt6 is not installed. Run: pip install PyQt6")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("Base64 Image Tool")
    app.setStyle("Fusion")

    if MISSING:
        show_missing_deps(MISSING)
        # Pillow missing is non-fatal — we use QImage fallback
        if "Pillow" in MISSING:
            print("Warning: Pillow not installed. Using Qt-native image loading (most formats still work).")

    window = MainWindow()
    window.show()
    window.status_bar.showMessage("✓ Ready — Pillow available." if PIL_AVAILABLE else "⚠ Pillow not found — using Qt native image support.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
