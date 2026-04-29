#!/usr/bin/env python3
"""
RedVerse Narrator
-----------------
Story-to-speech tool for the RedVerse Canon.
Parses prose for character dialogue, assigns voices per character,
renders with edge-tts / pyttsx3 / GPT-SoVITS, exports combined MP3.
"""

import sys
import os
import json
import asyncio
import tempfile
import threading
import re
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QComboBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QProgressBar, QSpinBox, QGroupBox, QScrollArea, QSplitter, QCheckBox,
    QDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette

# ── optional imports ──────────────────────────────────────────────────────────
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── constants ─────────────────────────────────────────────────────────────────
APP_NAME    = "RedVerse Narrator"
CONFIG_PATH = Path.home() / ".config" / "redverse_narrator" / "config.json"
SERVICE_ID  = "redverse_narrator"

DEFAULT_EDGE_VOICES = [
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
    "en-US-AriaNeural",
    "en-US-DavisNeural",
    "en-US-AmberNeural",
    "en-US-TonyNeural",
]

DARK_STYLE = """
QMainWindow, QWidget { background-color: #1a1a2e; color: #e0e0e0; }
QTabWidget::pane { border: 1px solid #444; background: #1a1a2e; }
QTabBar::tab { background: #16213e; color: #aaa; padding: 8px 16px; border-radius: 4px 4px 0 0; }
QTabBar::tab:selected { background: #0f3460; color: #e94560; }
QTextEdit, QLineEdit { background: #16213e; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; padding: 4px; }
QPushButton { background: #0f3460; color: #e0e0e0; border: none; border-radius: 4px; padding: 8px 16px; }
QPushButton:hover { background: #e94560; }
QPushButton:disabled { background: #333; color: #666; }
QComboBox { background: #16213e; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; padding: 4px; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: #16213e; color: #e0e0e0; selection-background-color: #0f3460; }
QTableWidget { background: #16213e; color: #e0e0e0; gridline-color: #333; border: 1px solid #444; }
QTableWidget::item:selected { background: #0f3460; }
QHeaderView::section { background: #0f3460; color: #e0e0e0; padding: 6px; border: none; }
QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 8px; }
QGroupBox::title { color: #e94560; subcontrol-origin: margin; left: 8px; }
QProgressBar { background: #16213e; border: 1px solid #444; border-radius: 4px; text-align: center; color: #e0e0e0; }
QProgressBar::chunk { background: #e94560; border-radius: 4px; }
QScrollBar:vertical { background: #16213e; width: 8px; }
QScrollBar::handle:vertical { background: #444; border-radius: 4px; }
QCheckBox { color: #e0e0e0; }
QLabel { color: #e0e0e0; }
QSpinBox { background: #16213e; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; padding: 4px; }
"""

# ── config ────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {
        "characters": [
            {"name": "Narrator", "voice_engine": "edge-tts", "voice": "en-GB-RyanNeural", "speed": 0},
            {"name": "Callum",   "voice_engine": "edge-tts", "voice": "en-US-DavisNeural", "speed": 0},
        ],
        "default_engine": "edge-tts",
        "ollama_model": "qwen2.5:3b",
        "ollama_url": "http://localhost:11434",
        "gptsovits_url": "http://localhost:9880",
        "external_api": "claude",
        "output_dir": str(Path.home() / "Music" / "RedVerse"),
        "silence_ms": 400,
    }

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

def get_api_key(service: str) -> str:
    if HAS_KEYRING:
        return keyring.get_password(SERVICE_ID, service) or ""
    return ""

def set_api_key(service: str, key: str):
    if HAS_KEYRING and key.strip():
        keyring.set_password(SERVICE_ID, service, key.strip())

# ── speaker detection ─────────────────────────────────────────────────────────
PARSE_PROMPT = """You are a literary dialogue parser. Given prose text, split it into segments.
Each segment has a "speaker" (character name or "Narrator") and "text" (what gets spoken aloud).

Rules:
- Narration, description, action = speaker "Narrator"
- Quoted speech = speaker is whoever is speaking
- If speaker is implied by context (e.g. previous attribution) use that name
- Split at natural speaking boundaries
- Return ONLY valid JSON array, no markdown, no explanation

Known characters: {characters}

Example output:
[
  {{"speaker": "Narrator", "text": "The storm had no name."}},
  {{"speaker": "Callum", "text": "I don't want this."}},
  {{"speaker": "Narrator", "text": "He said quietly, his voice barely above a whisper."}}
]

Text to parse:
{text}"""

def detect_speakers_ollama(text: str, characters: list, model: str, base_url: str) -> list:
    prompt = PARSE_PROMPT.format(
        characters=", ".join(characters),
        text=text[:6000]
    )
    try:
        client = ollama.Client(host=base_url)
        response = client.generate(model=model, prompt=prompt)
        raw = response.get("response", "")
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")

def detect_speakers_claude(text: str, characters: list, api_key: str) -> list:
    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")
    prompt = PARSE_PROMPT.format(
        characters=", ".join(characters),
        text=text[:6000]
    )
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"]
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)

def detect_speakers_openai(text: str, characters: list, api_key: str) -> list:
    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")
    prompt = PARSE_PROMPT.format(
        characters=", ".join(characters),
        text=text[:6000]
    )
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else parsed.get("segments", [])

# ── TTS rendering ─────────────────────────────────────────────────────────────
async def render_edge_tts(text: str, voice: str, speed: int, out_path: str):
    rate = f"+{speed}%" if speed >= 0 else f"{speed}%"
    comm = edge_tts.Communicate(text, voice, rate=rate)
    await comm.save(out_path)

def render_pyttsx3(text: str, out_path: str):
    engine = pyttsx3.init()
    engine.save_to_file(text, out_path)
    engine.runAndWait()

def render_gptsovits(text: str, voice: str, base_url: str, out_path: str):
    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")
    resp = requests.post(
        f"{base_url.rstrip('/')}/tts",
        json={"text": text, "speaker": voice},
        timeout=60,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)

def render_segment(text: str, char_config: dict, cfg: dict, tmp_dir: str, idx: int) -> str:
    engine  = char_config.get("voice_engine", "edge-tts")
    voice   = char_config.get("voice", "en-GB-RyanNeural")
    speed   = char_config.get("speed", 0)
    out_path = os.path.join(tmp_dir, f"seg_{idx:04d}.mp3")

    if engine == "edge-tts" and HAS_EDGE_TTS:
        asyncio.run(render_edge_tts(text, voice, speed, out_path))
    elif engine == "gptsovits":
        render_gptsovits(text, voice, cfg.get("gptsovits_url", "http://localhost:9880"), out_path)
    elif HAS_PYTTSX3:
        render_pyttsx3(text, out_path)
    else:
        raise RuntimeError("No TTS engine available")
    return out_path

# ── worker thread ─────────────────────────────────────────────────────────────
class NarratorWorker(QThread):
    progress    = pyqtSignal(int, str)
    finished    = pyqtSignal(str)
    error       = pyqtSignal(str)

    def __init__(self, text: str, cfg: dict, output_path: str):
        super().__init__()
        self.text        = text
        self.cfg         = cfg
        self.output_path = output_path

    def run(self):
        try:
            cfg  = self.cfg
            char_names = [c["name"] for c in cfg["characters"]]
            char_map   = {c["name"]: c for c in cfg["characters"]}
            narrator   = char_map.get("Narrator", cfg["characters"][0])

            # ── 1. detect speakers ──────────────────────────────────────────
            self.progress.emit(5, "Detecting speakers…")
            segments = None
            errors   = []

            # try ollama first
            if HAS_OLLAMA:
                try:
                    segments = detect_speakers_ollama(
                        self.text, char_names,
                        cfg.get("ollama_model", "qwen2.5:3b"),
                        cfg.get("ollama_url", "http://localhost:11434"),
                    )
                except Exception as e:
                    errors.append(f"Ollama: {e}")

            # fallback: external API
            if segments is None:
                api = cfg.get("external_api", "claude")
                key = get_api_key(api)
                if key:
                    try:
                        if api == "claude":
                            segments = detect_speakers_claude(self.text, char_names, key)
                        elif api == "openai":
                            segments = detect_speakers_openai(self.text, char_names, key)
                    except Exception as e:
                        errors.append(f"{api}: {e}")

            # last resort: entire text as narrator
            if segments is None:
                self.progress.emit(10, f"Speaker detection failed ({'; '.join(errors)}), using Narrator voice…")
                segments = [{"speaker": "Narrator", "text": self.text}]

            self.progress.emit(20, f"Detected {len(segments)} segments. Rendering audio…")

            # ── 2. render each segment ──────────────────────────────────────
            tmp_dir = tempfile.mkdtemp(prefix="redverse_")
            audio_files = []
            silence_ms  = cfg.get("silence_ms", 400)

            for i, seg in enumerate(segments):
                pct  = 20 + int(70 * i / max(len(segments), 1))
                name = seg.get("speaker", "Narrator")
                char = char_map.get(name, narrator)
                self.progress.emit(pct, f"Rendering [{name}]: {seg['text'][:50]}…")
                path = render_segment(seg["text"], char, cfg, tmp_dir, i)
                audio_files.append(path)

            # ── 3. combine ──────────────────────────────────────────────────
            self.progress.emit(92, "Combining audio…")
            if not HAS_PYDUB:
                raise RuntimeError("pydub not installed — cannot combine segments")

            silence = AudioSegment.silent(duration=silence_ms)
            combined = AudioSegment.empty()
            for path in audio_files:
                seg_audio = AudioSegment.from_file(path)
                combined += seg_audio + silence

            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            combined.export(self.output_path, format="mp3", bitrate="192k")

            # cleanup tmp
            for f in audio_files:
                try: os.remove(f)
                except: pass
            try: os.rmdir(tmp_dir)
            except: pass

            self.progress.emit(100, "Done!")
            self.finished.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


# ── character row dialog ──────────────────────────────────────────────────────
class CharacterDialog(QDialog):
    def __init__(self, char: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Character Voice")
        self.setStyleSheet(DARK_STYLE)
        self.resize(420, 280)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit(char["name"] if char else "")
        layout.addRow("Name:", self.name_edit)

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["edge-tts", "pyttsx3", "gptsovits"])
        if char:
            idx = self.engine_combo.findText(char.get("voice_engine", "edge-tts"))
            if idx >= 0: self.engine_combo.setCurrentIndex(idx)
        layout.addRow("Engine:", self.engine_combo)

        self.voice_edit = QLineEdit(char.get("voice", "en-GB-RyanNeural") if char else "en-GB-RyanNeural")
        layout.addRow("Voice / Speaker ID:", self.voice_edit)

        # quick-fill edge-tts presets
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— edge-tts presets —")
        self.preset_combo.addItems(DEFAULT_EDGE_VOICES)
        self.preset_combo.currentTextChanged.connect(self._fill_preset)
        layout.addRow("Quick fill:", self.preset_combo)

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(-50, 50)
        self.speed_spin.setValue(char.get("speed", 0) if char else 0)
        self.speed_spin.setSuffix("%")
        layout.addRow("Speed offset:", self.speed_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _fill_preset(self, val):
        if val and not val.startswith("—"):
            self.voice_edit.setText(val)

    def get_character(self) -> dict:
        return {
            "name":         self.name_edit.text().strip(),
            "voice_engine": self.engine_combo.currentText(),
            "voice":        self.voice_edit.text().strip(),
            "speed":        self.speed_spin.value(),
        }


# ── main window ───────────────────────────────────────────────────────────────
class RedVerseNarrator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg    = load_config()
        self.worker = None
        self._init_ui()
        self.setStyleSheet(DARK_STYLE)

    # ── UI build ──────────────────────────────────────────────────────────────
    def _init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 780)

        tabs = QTabWidget()
        tabs.addTab(self._build_narrator_tab(), "📖 Narrator")
        tabs.addTab(self._build_characters_tab(), "🎭 Characters")
        tabs.addTab(self._build_settings_tab(), "⚙️ Settings")
        tabs.addTab(self._build_preview_tab(), "👁 Segment Preview")

        self.setCentralWidget(tabs)
        self.statusBar().showMessage("Ready")

    # ── narrator tab ──────────────────────────────────────────────────────────
    def _build_narrator_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        # toolbar
        toolbar = QHBoxLayout()
        btn_load = QPushButton("📂 Load Text File")
        btn_load.clicked.connect(self._load_file)
        self.btn_parse = QPushButton("🔍 Parse Speakers")
        self.btn_parse.clicked.connect(self._parse_only)
        self.btn_render = QPushButton("🎙 Render MP3")
        self.btn_render.clicked.connect(self._render)
        self.btn_render.setStyleSheet("background:#e94560;font-weight:bold;")
        toolbar.addWidget(btn_load)
        toolbar.addWidget(self.btn_parse)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_render)
        lay.addLayout(toolbar)

        # text input
        grp_text = QGroupBox("Story Text")
        grp_lay  = QVBoxLayout(grp_text)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Paste or load story text here…")
        self.text_edit.setFont(QFont("Monospace", 10))
        grp_lay.addWidget(self.text_edit)
        lay.addWidget(grp_text, stretch=2)

        # output
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output file:"))
        self.out_path_edit = QLineEdit(
            str(Path(self.cfg.get("output_dir", str(Path.home()))) / "story.mp3")
        )
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self.out_path_edit, stretch=1)
        out_row.addWidget(btn_browse)
        lay.addLayout(out_row)

        # progress
        self.progress_bar   = QProgressBar()
        self.progress_label = QLabel("Ready")
        self.progress_label.setStyleSheet("color:#aaa;font-size:11px;")
        lay.addWidget(self.progress_bar)
        lay.addWidget(self.progress_label)

        return w

    # ── characters tab ────────────────────────────────────────────────────────
    def _build_characters_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)

        info = QLabel("Define characters and assign voices. 'Narrator' is used for all non-dialogue text.")
        info.setStyleSheet("color:#aaa;font-size:11px;")
        lay.addWidget(info)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕ Add Character")
        btn_add.clicked.connect(self._add_character)
        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self._edit_character)
        btn_del = QPushButton("🗑 Delete Selected")
        btn_del.clicked.connect(self._delete_character)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.char_table = QTableWidget(0, 4)
        self.char_table.setHorizontalHeaderLabels(["Name", "Engine", "Voice / Speaker ID", "Speed"])
        self.char_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.char_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.char_table.doubleClicked.connect(self._edit_character)
        lay.addWidget(self.char_table)

        self._refresh_char_table()
        return w

    # ── settings tab ─────────────────────────────────────────────────────────
    def _build_settings_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        # speaker detection
        grp_det = QGroupBox("Speaker Detection")
        det_lay = QFormLayout(grp_det)

        self.ollama_model_edit = QLineEdit(self.cfg.get("ollama_model", "qwen2.5:3b"))
        det_lay.addRow("Ollama model:", self.ollama_model_edit)
        self.ollama_url_edit = QLineEdit(self.cfg.get("ollama_url", "http://localhost:11434"))
        det_lay.addRow("Ollama URL:", self.ollama_url_edit)

        self.ext_api_combo = QComboBox()
        self.ext_api_combo.addItems(["claude", "openai"])
        idx = self.ext_api_combo.findText(self.cfg.get("external_api", "claude"))
        if idx >= 0: self.ext_api_combo.setCurrentIndex(idx)
        det_lay.addRow("Fallback API:", self.ext_api_combo)

        self.claude_key_edit = QLineEdit(get_api_key("claude"))
        self.claude_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.claude_key_edit.setPlaceholderText("sk-ant-…")
        det_lay.addRow("Claude API key:", self.claude_key_edit)

        self.openai_key_edit = QLineEdit(get_api_key("openai"))
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText("sk-…")
        det_lay.addRow("OpenAI API key:", self.openai_key_edit)
        lay.addWidget(grp_det)

        # GPT-SoVITS
        grp_gpt = QGroupBox("GPT-SoVITS (optional local server)")
        gpt_lay = QFormLayout(grp_gpt)
        self.gptsovits_url_edit = QLineEdit(self.cfg.get("gptsovits_url", "http://localhost:9880"))
        gpt_lay.addRow("Server URL:", self.gptsovits_url_edit)
        lay.addWidget(grp_gpt)

        # output
        grp_out = QGroupBox("Output")
        out_lay = QFormLayout(grp_out)
        self.out_dir_edit = QLineEdit(self.cfg.get("output_dir", str(Path.home() / "Music" / "RedVerse")))
        btn_out_dir = QPushButton("…")
        btn_out_dir.setFixedWidth(32)
        btn_out_dir.clicked.connect(self._browse_output_dir)
        out_row_w = QWidget()
        out_row_l = QHBoxLayout(out_row_w)
        out_row_l.setContentsMargins(0,0,0,0)
        out_row_l.addWidget(self.out_dir_edit)
        out_row_l.addWidget(btn_out_dir)
        out_lay.addRow("Output folder:", out_row_w)

        self.silence_spin = QSpinBox()
        self.silence_spin.setRange(0, 2000)
        self.silence_spin.setValue(self.cfg.get("silence_ms", 400))
        self.silence_spin.setSuffix(" ms")
        out_lay.addRow("Silence between segments:", self.silence_spin)
        lay.addWidget(grp_out)

        btn_save = QPushButton("💾 Save Settings")
        btn_save.clicked.connect(self._save_settings)
        btn_save.setStyleSheet("background:#e94560;font-weight:bold;")
        lay.addWidget(btn_save)
        lay.addStretch()
        return w

    # ── preview tab ───────────────────────────────────────────────────────────
    def _build_preview_tab(self):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Parsed segments (after running 'Parse Speakers'):"))
        self.preview_table = QTableWidget(0, 2)
        self.preview_table.setHorizontalHeaderLabels(["Speaker", "Text"])
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.preview_table)
        return w

    # ── character management ──────────────────────────────────────────────────
    def _refresh_char_table(self):
        self.char_table.setRowCount(0)
        for c in self.cfg["characters"]:
            row = self.char_table.rowCount()
            self.char_table.insertRow(row)
            self.char_table.setItem(row, 0, QTableWidgetItem(c["name"]))
            self.char_table.setItem(row, 1, QTableWidgetItem(c.get("voice_engine","edge-tts")))
            self.char_table.setItem(row, 2, QTableWidgetItem(c.get("voice","")))
            self.char_table.setItem(row, 3, QTableWidgetItem(f"{c.get('speed',0)}%"))

    def _add_character(self):
        dlg = CharacterDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cfg["characters"].append(dlg.get_character())
            self._refresh_char_table()
            save_config(self.cfg)

    def _edit_character(self):
        rows = self.char_table.selectedItems()
        if not rows: return
        row = self.char_table.currentRow()
        dlg = CharacterDialog(self.cfg["characters"][row], parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cfg["characters"][row] = dlg.get_character()
            self._refresh_char_table()
            save_config(self.cfg)

    def _delete_character(self):
        row = self.char_table.currentRow()
        if row < 0: return
        name = self.cfg["characters"][row]["name"]
        if name == "Narrator":
            QMessageBox.warning(self, "Cannot delete", "The Narrator character is required.")
            return
        self.cfg["characters"].pop(row)
        self._refresh_char_table()
        save_config(self.cfg)

    # ── file / path helpers ───────────────────────────────────────────────────
    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Text File", "", "Text files (*.txt *.md);;All files (*)")
        if path:
            self.text_edit.setPlainText(Path(path).read_text(encoding="utf-8"))

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save MP3 As", self.out_path_edit.text(), "MP3 files (*.mp3)")
        if path:
            self.out_path_edit.setText(path)

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.out_dir_edit.text())
        if d:
            self.out_dir_edit.setText(d)

    # ── settings save ─────────────────────────────────────────────────────────
    def _save_settings(self):
        self.cfg["ollama_model"]   = self.ollama_model_edit.text().strip()
        self.cfg["ollama_url"]     = self.ollama_url_edit.text().strip()
        self.cfg["external_api"]   = self.ext_api_combo.currentText()
        self.cfg["gptsovits_url"]  = self.gptsovits_url_edit.text().strip()
        self.cfg["output_dir"]     = self.out_dir_edit.text().strip()
        self.cfg["silence_ms"]     = self.silence_spin.value()
        set_api_key("claude",  self.claude_key_edit.text().strip())
        set_api_key("openai",  self.openai_key_edit.text().strip())
        save_config(self.cfg)
        self.statusBar().showMessage("Settings saved ✓", 3000)

    # ── parse only ────────────────────────────────────────────────────────────
    def _parse_only(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "No text", "Please paste or load story text first.")
            return
        self.btn_parse.setEnabled(False)
        self.btn_render.setEnabled(False)
        self.progress_label.setText("Parsing speakers…")
        self.progress_bar.setValue(5)

        cfg = self._current_cfg()
        char_names = [c["name"] for c in cfg["characters"]]

        def _do():
            try:
                segs = None
                if HAS_OLLAMA:
                    try:
                        segs = detect_speakers_ollama(text, char_names,
                            cfg.get("ollama_model","qwen2.5:3b"),
                            cfg.get("ollama_url","http://localhost:11434"))
                    except: pass
                if segs is None:
                    api = cfg.get("external_api","claude")
                    key = get_api_key(api)
                    if key:
                        if api=="claude": segs = detect_speakers_claude(text, char_names, key)
                        else: segs = detect_speakers_openai(text, char_names, key)
                if segs is None:
                    segs = [{"speaker":"Narrator","text":text}]
                return segs
            except Exception as e:
                return e

        def _thread():
            result = _do()
            # update UI from main thread via timer
            QTimer.singleShot(0, lambda: self._parse_done(result))

        threading.Thread(target=_thread, daemon=True).start()

    def _parse_done(self, result):
        self.btn_parse.setEnabled(True)
        self.btn_render.setEnabled(True)
        if isinstance(result, Exception):
            self.progress_label.setText(f"Parse error: {result}")
            self.progress_bar.setValue(0)
            return
        self.preview_table.setRowCount(0)
        for seg in result:
            row = self.preview_table.rowCount()
            self.preview_table.insertRow(row)
            self.preview_table.setItem(row, 0, QTableWidgetItem(seg.get("speaker","?")))
            self.preview_table.setItem(row, 1, QTableWidgetItem(seg.get("text","")))
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"Parsed {len(result)} segments — check 'Segment Preview' tab")

    # ── render ────────────────────────────────────────────────────────────────
    def _current_cfg(self) -> dict:
        cfg = dict(self.cfg)
        cfg["ollama_model"]  = self.ollama_model_edit.text().strip() if hasattr(self,"ollama_model_edit") else cfg.get("ollama_model","qwen2.5:3b")
        cfg["ollama_url"]    = self.ollama_url_edit.text().strip()   if hasattr(self,"ollama_url_edit")   else cfg.get("ollama_url","http://localhost:11434")
        cfg["external_api"]  = self.ext_api_combo.currentText()      if hasattr(self,"ext_api_combo")     else cfg.get("external_api","claude")
        cfg["gptsovits_url"] = self.gptsovits_url_edit.text().strip() if hasattr(self,"gptsovits_url_edit") else cfg.get("gptsovits_url","http://localhost:9880")
        cfg["silence_ms"]    = self.silence_spin.value()             if hasattr(self,"silence_spin")      else cfg.get("silence_ms",400)
        return cfg

    def _render(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "No text", "Please paste or load story text first.")
            return
        out = self.out_path_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "No output path", "Please set an output file path.")
            return

        self.btn_render.setEnabled(False)
        self.btn_parse.setEnabled(False)
        self.progress_bar.setValue(0)

        self.worker = NarratorWorker(text, self._current_cfg(), out)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(msg)
        self.statusBar().showMessage(msg)

    def _on_finished(self, path: str):
        self.btn_render.setEnabled(True)
        self.btn_parse.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"✅ Saved: {path}")
        self.statusBar().showMessage(f"Saved: {path}", 5000)
        QMessageBox.information(self, "Done!", f"MP3 saved to:\n{path}")

    def _on_error(self, msg: str):
        self.btn_render.setEnabled(True)
        self.btn_parse.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"❌ Error: {msg}")
        QMessageBox.critical(self, "Error", msg)


# ── entry point ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = RedVerseNarrator()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
