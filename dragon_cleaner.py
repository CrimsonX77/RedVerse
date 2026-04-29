#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════╗
║     DRAGON CLEANER  //  RedVerse Toolkit     ║
║     Intelligent Disk Cleanup  v1.0           ║
╚══════════════════════════════════════════════╝
PyQt6 GUI — LLM-powered aggressive cleanup
pip install PyQt6 anthropic
"""

import os
import sys
import hashlib
import json
import shutil
import fnmatch
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import anthropic

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QSplitter, QTextEdit, QCheckBox, QLineEdit, QFileDialog,
    QGroupBox, QTabWidget, QHeaderView, QMessageBox, QStatusBar,
    QFrame, QScrollArea, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QBrush, QPalette, QFontDatabase

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

SYSTEM_PROTECTED = {
    "/proc", "/sys", "/dev", "/run", "/boot",
    "/usr/bin", "/usr/sbin", "/usr/lib", "/usr/lib64",
    "/bin", "/sbin", "/lib", "/lib64",
    "/etc", "/var/lib/dpkg", "/var/lib/apt",
    "/snap/core", "/snap/snapd",
}

JUNK_PATTERNS = [
    "*.tmp", "*.temp", "~$*", "*.bak", "*.old", "*.orig",
    "thumbs.db", ".ds_store", "desktop.ini", "*.log",
    "*.cache", "*.swp", "*.swo", "core.*", "*.pid",
    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache",
    "node_modules", ".npm", ".cache",
]

LARGE_FILE_MB = 100  # Flag files above this size

DARK_STYLE = """
QMainWindow, QWidget, QDialog {
    background-color: #0d0d0f;
    color: #e0e0e0;
}
QTabWidget::pane {
    border: 1px solid #2a2a35;
    background: #0d0d0f;
}
QTabBar::tab {
    background: #1a1a22;
    color: #888;
    padding: 8px 18px;
    border: 1px solid #2a2a35;
    border-bottom: none;
    font-family: 'Courier New';
    font-size: 11px;
    letter-spacing: 1px;
}
QTabBar::tab:selected {
    background: #0d0d0f;
    color: #cc3333;
    border-top: 2px solid #cc3333;
}
QPushButton {
    background-color: #1a1a22;
    color: #cc3333;
    border: 1px solid #cc3333;
    padding: 8px 18px;
    font-family: 'Courier New';
    font-size: 11px;
    letter-spacing: 1px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #cc3333;
    color: #fff;
}
QPushButton:disabled {
    color: #444;
    border-color: #333;
}
QPushButton#danger {
    border-color: #ff2222;
    color: #ff2222;
}
QPushButton#danger:hover {
    background-color: #ff2222;
    color: #000;
}
QPushButton#safe {
    border-color: #33cc77;
    color: #33cc77;
}
QPushButton#safe:hover {
    background-color: #33cc77;
    color: #000;
}
QLineEdit {
    background: #111118;
    color: #e0e0e0;
    border: 1px solid #2a2a35;
    padding: 6px 10px;
    font-family: 'Courier New';
    font-size: 11px;
}
QProgressBar {
    background: #111118;
    border: 1px solid #2a2a35;
    height: 14px;
    text-align: center;
    font-size: 10px;
    color: #888;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #cc3333, stop:1 #ff6633);
}
QTreeWidget {
    background: #0d0d0f;
    color: #e0e0e0;
    border: 1px solid #2a2a35;
    font-family: 'Courier New';
    font-size: 10px;
    alternate-background-color: #111118;
}
QTreeWidget::item:selected {
    background: #1e1e2e;
    color: #cc3333;
}
QHeaderView::section {
    background: #1a1a22;
    color: #cc3333;
    border: 1px solid #2a2a35;
    padding: 4px 8px;
    font-family: 'Courier New';
    font-size: 10px;
    letter-spacing: 1px;
}
QTextEdit {
    background: #080810;
    color: #33cc77;
    border: 1px solid #2a2a35;
    font-family: 'Courier New';
    font-size: 10px;
    line-height: 1.5;
}
QGroupBox {
    color: #cc3333;
    border: 1px solid #2a2a35;
    margin-top: 10px;
    padding-top: 8px;
    font-family: 'Courier New';
    font-size: 10px;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLabel {
    color: #aaaaaa;
    font-family: 'Courier New';
    font-size: 10px;
}
QLabel#heading {
    color: #cc3333;
    font-size: 20px;
    letter-spacing: 3px;
    font-weight: bold;
}
QLabel#stat {
    color: #33cc77;
    font-size: 11px;
}
QCheckBox {
    color: #aaa;
    font-family: 'Courier New';
    font-size: 10px;
}
QCheckBox::indicator:checked {
    background: #cc3333;
    border: 1px solid #cc3333;
}
QStatusBar {
    background: #0a0a10;
    color: #555;
    border-top: 1px solid #2a2a35;
    font-family: 'Courier New';
    font-size: 10px;
}
QScrollBar:vertical {
    background: #0d0d0f;
    width: 8px;
}
QScrollBar::handle:vertical {
    background: #2a2a35;
    min-height: 20px;
}
"""

# ─── SCANNER THREAD ───────────────────────────────────────────────────────────

class ScannerThread(QThread):
    progress = pyqtSignal(str, int, int)   # current_path, files_scanned, total_estimate
    file_found = pyqtSignal(str, int)       # path, size_bytes
    finished = pyqtSignal(dict)             # results dict
    error = pyqtSignal(str)

    def __init__(self, root_path: str, skip_system: bool = True):
        super().__init__()
        self.root_path = root_path
        self.skip_system = skip_system
        self._stop = False

    def stop(self):
        self._stop = True

    def _is_protected(self, path: str) -> bool:
        for p in SYSTEM_PROTECTED:
            if path.startswith(p):
                return True
        return False

    def _hash_file(self, path: str, chunk_size: int = 65536) -> str | None:
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except (PermissionError, OSError, IOError):
            return None

    def _is_junk(self, path: str) -> bool:
        name = os.path.basename(path).lower()
        for pattern in JUNK_PATTERNS:
            if fnmatch.fnmatch(name, pattern.lower()):
                return True
        return False

    def run(self):
        results = {
            "duplicates": defaultdict(list),   # hash -> [paths]
            "large_files": [],                  # (path, size)
            "junk_files": [],                   # path
            "total_size": 0,
            "total_files": 0,
            "errors": 0,
            "scan_root": self.root_path,
        }

        hash_map = defaultdict(list)
        count = 0

        try:
            for dirpath, dirnames, filenames in os.walk(self.root_path):
                if self._stop:
                    break

                if self.skip_system and self._is_protected(dirpath):
                    dirnames.clear()
                    continue

                # Skip hidden system dirs
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith('.') or d in {'.config', '.local'}
                    and not self._is_protected(os.path.join(dirpath, d))
                ]

                for fname in filenames:
                    if self._stop:
                        break

                    fpath = os.path.join(dirpath, fname)

                    try:
                        stat = os.stat(fpath)
                        fsize = stat.st_size
                    except (PermissionError, OSError):
                        results["errors"] += 1
                        continue

                    # Skip symlinks and empty files
                    if os.path.islink(fpath) or fsize == 0:
                        continue

                    count += 1
                    results["total_files"] += 1
                    results["total_size"] += fsize

                    self.progress.emit(fpath, count, 0)
                    self.file_found.emit(fpath, fsize)

                    # Hash it
                    file_hash = self._hash_file(fpath)
                    if file_hash:
                        hash_map[file_hash].append((fpath, fsize))

                    # Large file?
                    if fsize > LARGE_FILE_MB * 1024 * 1024:
                        results["large_files"].append((fpath, fsize))

                    # Junk file?
                    if self._is_junk(fpath):
                        results["junk_files"].append(fpath)

        except Exception as e:
            self.error.emit(str(e))
            return

        # Extract actual duplicates (hash seen more than once)
        for h, paths in hash_map.items():
            if len(paths) > 1:
                results["duplicates"][h] = paths

        # Sort large files descending
        results["large_files"].sort(key=lambda x: x[1], reverse=True)

        self.finished.emit(dict(results))


# ─── LLM ANALYSIS THREAD ──────────────────────────────────────────────────────

class LLMAnalysisThread(QThread):
    chunk = pyqtSignal(str)
    done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, results: dict, api_key: str):
        super().__init__()
        self.results = results
        self.api_key = api_key

    def _format_summary(self) -> str:
        r = self.results
        dup_count = sum(len(v) for v in r["duplicates"].values())
        dup_groups = len(r["duplicates"])
        dup_waste = sum(
            min(sz for _, sz in paths) * (len(paths) - 1)
            for paths in r["duplicates"].values()
        )
        large_count = len(r["large_files"])
        junk_count = len(r["junk_files"])
        total_gb = r["total_size"] / 1e9

        lines = [
            f"SYSTEM SCAN RESULTS — {r['scan_root']}",
            f"Total files scanned: {r['total_files']:,}",
            f"Total size: {total_gb:.2f} GB",
            "",
            f"DUPLICATES: {dup_groups} groups ({dup_count} files, ~{dup_waste/1e9:.2f} GB recoverable)",
        ]

        # Top 20 duplicate groups
        sorted_dups = sorted(
            r["duplicates"].items(),
            key=lambda x: min(sz for _, sz in x[1]) * (len(x[1]) - 1),
            reverse=True
        )[:20]

        for h, paths in sorted_dups:
            waste = min(sz for _, sz in paths) * (len(paths) - 1)
            lines.append(f"  [{len(paths)} copies, ~{waste/1e6:.1f} MB waste]:")
            for p, s in paths:
                lines.append(f"    {p}  ({s/1e6:.1f} MB)")

        lines.append("")
        lines.append(f"LARGE FILES (top 30, >{LARGE_FILE_MB}MB):")
        for p, s in r["large_files"][:30]:
            lines.append(f"  {s/1e9:.2f} GB  {p}")

        lines.append("")
        lines.append(f"JUNK/TEMP FILES ({junk_count} total, sample):")
        for p in r["junk_files"][:50]:
            lines.append(f"  {p}")

        return "\n".join(lines)

    def run(self):
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            summary = self._format_summary()

            prompt = f"""You are an aggressive disk cleanup analyst. Analyze this disk scan report and provide clear, actionable recommendations.

Be AGGRESSIVE. Err on the side of deletion. The user wants space back.

For each category:
1. DUPLICATES — which copies to DELETE (keep the one in the most logical/primary location, delete the rest). List exact paths.
2. LARGE FILES — flag anything suspicious, unused-looking, or redundant. Suggest deletion or archival.
3. JUNK FILES — confirm all are safe to delete.
4. ADDITIONAL PATTERNS — point out any directories or file types that look like cache, build artifacts, old exports, etc. that could be bulk-removed.

Format your response with clear sections and ✓ KEEP / ✗ DELETE markers.
End with a TOTAL ESTIMATED RECOVERABLE SPACE summary.

SCAN REPORT:
{summary}
"""
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    self.chunk.emit(text)

            self.done.emit()

        except Exception as e:
            self.error.emit(str(e))


# ─── MAIN WINDOW ──────────────────────────────────────────────────────────────

class DragonCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scan_results = None
        self.scanner = None
        self.llm_thread = None
        self._files_scanned = 0
        self._total_size = 0
        self.setWindowTitle("DRAGON CLEANER  //  RedVerse Toolkit")
        self.resize(1280, 860)
        self.setStyleSheet(DARK_STYLE)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 8)
        root_layout.setSpacing(8)

        # ── HEADER ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("⚔  DRAGON CLEANER")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()
        sub = QLabel("INTELLIGENT DISK CLEANUP  //  REDVERSE TOOLKIT")
        sub.setStyleSheet("color: #444; font-family: Courier New; font-size: 10px; letter-spacing: 2px;")
        header.addWidget(sub)
        root_layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a35;")
        root_layout.addWidget(sep)

        # ── SCAN CONFIG ───────────────────────────────────────────────────────
        cfg_group = QGroupBox("// SCAN CONFIGURATION")
        cfg_layout = QHBoxLayout(cfg_group)

        self.path_input = QLineEdit("/")
        self.path_input.setPlaceholderText("Root path to scan...")
        cfg_layout.addWidget(QLabel("ROOT:"), 0)
        cfg_layout.addWidget(self.path_input, 3)

        browse_btn = QPushButton("BROWSE")
        browse_btn.clicked.connect(self._browse_path)
        cfg_layout.addWidget(browse_btn)

        self.skip_sys_cb = QCheckBox("Skip system paths")
        self.skip_sys_cb.setChecked(True)
        cfg_layout.addWidget(self.skip_sys_cb)

        cfg_layout.addSpacing(10)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Anthropic API key (for LLM analysis)...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        # Try to load from env
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if env_key:
            self.api_key_input.setText(env_key)
        cfg_layout.addWidget(QLabel("API KEY:"), 0)
        cfg_layout.addWidget(self.api_key_input, 2)

        root_layout.addWidget(cfg_group)

        # ── ACTION BAR ────────────────────────────────────────────────────────
        action_bar = QHBoxLayout()

        self.scan_btn = QPushButton("▶  START SCAN")
        self.scan_btn.setObjectName("safe")
        self.scan_btn.clicked.connect(self._start_scan)
        action_bar.addWidget(self.scan_btn)

        self.stop_btn = QPushButton("■  STOP")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_scan)
        action_bar.addWidget(self.stop_btn)

        self.llm_btn = QPushButton("🧠  LLM ANALYSIS")
        self.llm_btn.setEnabled(False)
        self.llm_btn.clicked.connect(self._run_llm)
        action_bar.addWidget(self.llm_btn)

        action_bar.addStretch()

        self.stat_files = QLabel("FILES: —")
        self.stat_files.setObjectName("stat")
        self.stat_size = QLabel("SIZE: —")
        self.stat_size.setObjectName("stat")
        self.stat_dups = QLabel("DUPS: —")
        self.stat_dups.setObjectName("stat")
        self.stat_recov = QLabel("RECOVERABLE: —")
        self.stat_recov.setObjectName("stat")
        self.stat_recov.setStyleSheet("color: #ff6633; font-family: Courier New; font-size: 11px;")

        for w in [self.stat_files, self.stat_size, self.stat_dups, self.stat_recov]:
            action_bar.addWidget(w)
            action_bar.addSpacing(16)

        self.delete_sel_btn = QPushButton("✗  DELETE SELECTED")
        self.delete_sel_btn.setObjectName("danger")
        self.delete_sel_btn.setEnabled(False)
        self.delete_sel_btn.clicked.connect(self._delete_selected)
        action_bar.addWidget(self.delete_sel_btn)

        root_layout.addLayout(action_bar)

        # ── PROGRESS ──────────────────────────────────────────────────────────
        prog_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        prog_layout.addWidget(self.progress_bar)

        self.current_file_label = QLabel("")
        self.current_file_label.setStyleSheet(
            "color: #444; font-family: Courier New; font-size: 9px;"
        )
        prog_layout.addWidget(self.current_file_label)
        root_layout.addLayout(prog_layout)

        # ── MAIN SPLITTER ─────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: results tabs
        self.tabs = QTabWidget()

        # Duplicates tab
        self.dup_tree = QTreeWidget()
        self.dup_tree.setHeaderLabels(["FILE / PATH", "SIZE", "HASH"])
        self.dup_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.dup_tree.header().resizeSection(1, 90)
        self.dup_tree.header().resizeSection(2, 120)
        self.dup_tree.setAlternatingRowColors(True)
        self.dup_tree.itemChanged.connect(self._on_item_changed)
        self.tabs.addTab(self.dup_tree, "DUPLICATES")

        # Large files tab
        self.large_tree = QTreeWidget()
        self.large_tree.setHeaderLabels(["PATH", "SIZE (GB)"])
        self.large_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.large_tree.header().resizeSection(1, 100)
        self.large_tree.setAlternatingRowColors(True)
        self.large_tree.itemChanged.connect(self._on_item_changed)
        self.tabs.addTab(self.large_tree, "LARGE FILES")

        # Junk tab
        self.junk_tree = QTreeWidget()
        self.junk_tree.setHeaderLabels(["PATH", "TYPE"])
        self.junk_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.junk_tree.header().resizeSection(1, 100)
        self.junk_tree.setAlternatingRowColors(True)
        self.junk_tree.itemChanged.connect(self._on_item_changed)
        self.tabs.addTab(self.junk_tree, "JUNK FILES")

        splitter.addWidget(self.tabs)

        # Right: LLM output
        llm_panel = QWidget()
        llm_layout = QVBoxLayout(llm_panel)
        llm_layout.setContentsMargins(0, 0, 0, 0)
        llm_label = QLabel("// LLM ANALYSIS OUTPUT")
        llm_label.setStyleSheet(
            "color: #cc3333; font-family: Courier New; font-size: 10px; "
            "letter-spacing: 1px; padding: 4px;"
        )
        llm_layout.addWidget(llm_label)
        self.llm_output = QTextEdit()
        self.llm_output.setReadOnly(True)
        self.llm_output.setPlaceholderText(
            "// LLM analysis will stream here after scan completes...\n"
            "// Click [LLM ANALYSIS] to begin."
        )
        llm_layout.addWidget(self.llm_output)

        # Quick-action buttons below LLM panel
        quick_bar = QHBoxLayout()
        sel_dups_btn = QPushButton("SELECT ALL DUPS")
        sel_dups_btn.clicked.connect(self._select_all_dups)
        sel_junk_btn = QPushButton("SELECT ALL JUNK")
        sel_junk_btn.clicked.connect(self._select_all_junk)
        clear_sel_btn = QPushButton("CLEAR SELECTION")
        clear_sel_btn.clicked.connect(self._clear_selection)
        for b in [sel_dups_btn, sel_junk_btn, clear_sel_btn]:
            quick_bar.addWidget(b)
        llm_layout.addLayout(quick_bar)

        splitter.addWidget(llm_panel)
        splitter.setSizes([780, 460])

        root_layout.addWidget(splitter)

        # ── STATUS BAR ────────────────────────────────────────────────────────
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("READY — Dragon Cleaner v1.0  //  RedVerse Toolkit")

    # ─── UI HELPERS ───────────────────────────────────────────────────────────

    def _browse_path(self):
        d = QFileDialog.getExistingDirectory(self, "Select root directory", "/home")
        if d:
            self.path_input.setText(d)

    def _fmt_size(self, b: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"

    def _on_item_changed(self, item, col):
        # propagate check to children
        if item.childCount() > 0:
            state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, state)
        self._update_delete_btn()

    def _update_delete_btn(self):
        checked = self._collect_checked_paths()
        self.delete_sel_btn.setEnabled(len(checked) > 0)
        if checked:
            self.status.showMessage(f"{len(checked)} files selected for deletion")

    def _collect_checked_paths(self) -> list[str]:
        paths = []
        for tree in [self.dup_tree, self.large_tree, self.junk_tree]:
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                group = root.child(i)
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child.checkState(0) == Qt.CheckState.Checked:
                        p = child.data(0, Qt.ItemDataRole.UserRole)
                        if p:
                            paths.append(p)
                # also direct items (large/junk)
                if group.checkState(0) == Qt.CheckState.Checked:
                    p = group.data(0, Qt.ItemDataRole.UserRole)
                    if p:
                        paths.append(p)
        return list(set(paths))

    # ─── SCANNING ─────────────────────────────────────────────────────────────

    def _start_scan(self):
        self.dup_tree.clear()
        self.large_tree.clear()
        self.junk_tree.clear()
        self.llm_output.clear()
        self._files_scanned = 0
        self._total_size = 0
        self.scan_results = None
        self.delete_sel_btn.setEnabled(False)
        self.llm_btn.setEnabled(False)

        root = self.path_input.text().strip() or "/"
        if not os.path.exists(root):
            QMessageBox.warning(self, "Invalid Path", f"Path does not exist: {root}")
            return

        self.scanner = ScannerThread(root, self.skip_sys_cb.isChecked())
        self.scanner.progress.connect(self._on_progress)
        self.scanner.finished.connect(self._on_scan_done)
        self.scanner.error.connect(lambda e: self.status.showMessage(f"ERROR: {e}"))

        self.progress_bar.setVisible(True)
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status.showMessage("SCANNING...")
        self.scanner.start()

    def _stop_scan(self):
        if self.scanner:
            self.scanner.stop()
        self.stop_btn.setEnabled(False)
        self.scan_btn.setEnabled(True)
        self.status.showMessage("SCAN STOPPED")

    def _on_progress(self, path: str, count: int, _):
        self._files_scanned = count
        # Only update label every 50 files for performance
        if count % 50 == 0:
            self.current_file_label.setText(f"  {path}")
            self.stat_files.setText(f"FILES: {count:,}")

    def _on_scan_done(self, results: dict):
        self.scan_results = results
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.current_file_label.setText("")

        dup_groups = len(results["duplicates"])
        dup_files = sum(len(v) for v in results["duplicates"].values())
        recoverable = sum(
            min(sz for _, sz in paths) * (len(paths) - 1)
            for paths in results["duplicates"].values()
        )

        self.stat_files.setText(f"FILES: {results['total_files']:,}")
        self.stat_size.setText(f"SIZE: {self._fmt_size(results['total_size'])}")
        self.stat_dups.setText(f"DUPS: {dup_groups} groups")
        self.stat_recov.setText(f"RECOVERABLE: {self._fmt_size(recoverable)}")

        self._populate_duplicates(results)
        self._populate_large(results)
        self._populate_junk(results)

        self.llm_btn.setEnabled(True)
        self.status.showMessage(
            f"SCAN COMPLETE — {results['total_files']:,} files | "
            f"{dup_groups} dup groups | "
            f"~{self._fmt_size(recoverable)} recoverable"
        )

    def _populate_duplicates(self, r: dict):
        self.dup_tree.blockSignals(True)
        sorted_dups = sorted(
            r["duplicates"].items(),
            key=lambda x: min(sz for _, sz in x[1]) * (len(x[1]) - 1),
            reverse=True
        )
        for h, paths in sorted_dups:
            waste = min(sz for _, sz in paths) * (len(paths) - 1)
            group = QTreeWidgetItem([
                f"[{len(paths)} copies  •  {self._fmt_size(waste)} wasted]",
                self._fmt_size(paths[0][1]),
                h[:12] + "…"
            ])
            group.setForeground(0, QBrush(QColor("#cc3333")))
            group.setCheckState(0, Qt.CheckState.Unchecked)
            group.setExpanded(True)

            # Sort: keep first (most "home-like" path), flag rest
            sorted_paths = sorted(paths, key=lambda x: (
                0 if "/home/" in x[0] else
                1 if "/root/" in x[0] else
                2
            ))

            for i, (p, s) in enumerate(sorted_paths):
                child = QTreeWidgetItem([p, self._fmt_size(s), ""])
                child.setData(0, Qt.ItemDataRole.UserRole, p)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                if i > 0:  # auto-suggest deleting copies
                    child.setForeground(0, QBrush(QColor("#888888")))
                else:
                    child.setForeground(0, QBrush(QColor("#33cc77")))
                    child.setText(0, p + "  [KEEP]")
                group.addChild(child)

            self.dup_tree.addTopLevelItem(group)
        self.dup_tree.blockSignals(False)

    def _populate_large(self, r: dict):
        self.large_tree.blockSignals(True)
        # Group by extension
        ext_group = QTreeWidgetItem(["LARGE FILES"])
        ext_group.setForeground(0, QBrush(QColor("#ff6633")))

        for p, s in r["large_files"][:500]:
            item = QTreeWidgetItem([p, f"{s/1e9:.3f} GB"])
            item.setData(0, Qt.ItemDataRole.UserRole, p)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            ext_group.addChild(item)

        ext_group.setExpanded(False)
        self.large_tree.addTopLevelItem(ext_group)
        self.large_tree.blockSignals(False)

    def _populate_junk(self, r: dict):
        self.junk_tree.blockSignals(True)
        for p in r["junk_files"][:2000]:
            ext = Path(p).suffix.upper() or "MISC"
            item = QTreeWidgetItem([p, ext])
            item.setData(0, Qt.ItemDataRole.UserRole, p)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            self.junk_tree.addTopLevelItem(item)
        self.junk_tree.blockSignals(False)

    # ─── SELECTION HELPERS ────────────────────────────────────────────────────

    def _select_all_dups(self):
        """Select all duplicate COPIES (not the kept file)."""
        self.dup_tree.blockSignals(True)
        root = self.dup_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            for j in range(1, group.childCount()):  # skip index 0 (keep)
                group.child(j).setCheckState(0, Qt.CheckState.Checked)
        self.dup_tree.blockSignals(False)
        self._update_delete_btn()

    def _select_all_junk(self):
        self.junk_tree.blockSignals(True)
        root = self.junk_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, Qt.CheckState.Checked)
        self.junk_tree.blockSignals(False)
        self._update_delete_btn()

    def _clear_selection(self):
        for tree in [self.dup_tree, self.large_tree, self.junk_tree]:
            tree.blockSignals(True)
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                g = root.child(i)
                g.setCheckState(0, Qt.CheckState.Unchecked)
                for j in range(g.childCount()):
                    g.child(j).setCheckState(0, Qt.CheckState.Unchecked)
            tree.blockSignals(False)
        self._update_delete_btn()

    # ─── DELETION ─────────────────────────────────────────────────────────────

    def _delete_selected(self):
        paths = self._collect_checked_paths()
        if not paths:
            return

        total_size = 0
        valid_paths = []
        for p in paths:
            if os.path.isfile(p):
                try:
                    total_size += os.path.getsize(p)
                    valid_paths.append(p)
                except OSError:
                    pass

        reply = QMessageBox.question(
            self,
            "CONFIRM DELETION",
            f"⚠  PERMANENTLY DELETE {len(valid_paths)} files?\n\n"
            f"Total space freed: {self._fmt_size(total_size)}\n\n"
            f"This action CANNOT be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        errors = 0
        freed = 0
        for p in valid_paths:
            try:
                sz = os.path.getsize(p)
                os.remove(p)
                freed += sz
                deleted += 1
            except OSError as e:
                errors += 1
                self.llm_output.append(f"[ERROR] {p}: {e}")

        QMessageBox.information(
            self,
            "DELETION COMPLETE",
            f"✓  Deleted {deleted} files\n"
            f"✗  Errors: {errors}\n"
            f"💾  Space freed: {self._fmt_size(freed)}"
        )
        self.status.showMessage(
            f"DELETED {deleted} files — {self._fmt_size(freed)} freed"
        )

    # ─── LLM ANALYSIS ─────────────────────────────────────────────────────────

    def _run_llm(self):
        if not self.scan_results:
            return
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(
                self, "No API Key",
                "Please enter your Anthropic API key to use LLM analysis."
            )
            return

        self.llm_output.clear()
        self.llm_output.append("// INITIALIZING LLM ANALYSIS...\n")
        self.llm_btn.setEnabled(False)
        self.tabs.setCurrentIndex(0)

        self.llm_thread = LLMAnalysisThread(self.scan_results, api_key)
        self.llm_thread.chunk.connect(self._on_llm_chunk)
        self.llm_thread.done.connect(self._on_llm_done)
        self.llm_thread.error.connect(self._on_llm_error)
        self.llm_thread.start()

    def _on_llm_chunk(self, text: str):
        self.llm_output.moveCursor(self.llm_output.textCursor().MoveOperation.End)
        self.llm_output.insertPlainText(text)
        self.llm_output.moveCursor(self.llm_output.textCursor().MoveOperation.End)

    def _on_llm_done(self):
        self.llm_btn.setEnabled(True)
        self.status.showMessage("LLM ANALYSIS COMPLETE")

    def _on_llm_error(self, err: str):
        self.llm_output.append(f"\n[LLM ERROR]: {err}")
        self.llm_btn.setEnabled(True)


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dragon Cleaner")

    # Dark palette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#0d0d0f"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#111118"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#0d0d0f"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#1a1a22"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#cc3333"))
    app.setPalette(pal)

    win = DragonCleaner()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
