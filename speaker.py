#!/usr/bin/env python3
"""
Clean Edge-TTS Speaker Module
Modular TTS interface for Aetherion Realms
PyQt6 | Python 3.10+ | Edge-TTS

Author: Crimson / Built with Vera
"""

import argparse
import sys
import os
import asyncio
import tempfile
import json
import socket
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QTextEdit, QLabel, QComboBox, 
    QSpinBox, QFileDialog, QMessageBox, QProgressBar, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

import edge_tts
import pygame
import pyttsx3
from foundations.crimson_theme import apply_crimson_theme


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_VOICE = "en-GB-SoniaNeural"
CONFIG_FILE = Path.home() / ".aetherion_tts_config.json"

CHUNK_SIZES = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]

# TTS Mode constants
TTS_MODE_ONLINE = "online"  # Edge-TTS (requires internet)
TTS_MODE_OFFLINE = "offline"  # pyttsx3 (local system voices)

# Voice cache - populated on startup
VOICE_CACHE = []
OFFLINE_VOICES = []  # System voices for offline mode


# =============================================================================
# CONFIGURATION MANAGER
# =============================================================================

class ConfigManager:
    """Handles loading/saving of TTS configuration"""
    
    @staticmethod
    def load() -> dict:
        """Load configuration from file"""
        defaults = {
            "voice": DEFAULT_VOICE,
            "rate": 0,
            "volume": 0,
            "pitch": 0,
            "chunk_size": 200,
            "strip_symbols": True,
            "tts_mode": TTS_MODE_ONLINE,
            "offline_voice": None  # Will auto-detect first available
        }
        
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except Exception as e:
                print(f"Config load error: {e}")
        
        return defaults
    
    @staticmethod
    def save(config: dict):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Config save error: {e}")


# =============================================================================
# VOICE CACHE MANAGER
# =============================================================================

class VoiceCacheThread(QThread):
    """Thread for fetching available voices"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def fetch_voices():
                voices = await edge_tts.list_voices()
                return voices
            
            voices = loop.run_until_complete(fetch_voices())
            loop.close()
            
            self.finished.emit(voices)
            
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# TTS GENERATION THREAD
# =============================================================================

class TTSThread(QThread):
    """Thread for generating and playing TTS audio"""
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, text: str, voice: str, rate: int, volume: int, chunk_size: int):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.chunk_size = chunk_size
        self.is_running = True
        self.audio_files = []
    
    def stop(self):
        """Stop the TTS thread"""
        self.is_running = False
        try:
            pygame.mixer.music.stop()
        except:
            pass
    
    def run(self):
        try:
            chunks = self._split_text(self.text, self.chunk_size)
            total_chunks = len(chunks)
            
            if total_chunks == 0:
                self.error.emit("No text to speak")
                return
            
            # Initialize pygame mixer
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            except:
                pygame.mixer.init()
            
            for i, chunk in enumerate(chunks):
                if not self.is_running:
                    break
                
                if chunk.strip():
                    self.status.emit(f"Generating chunk {i+1}/{total_chunks}...")
                    
                    audio_file = self._generate_chunk(chunk)
                    if audio_file:
                        self.audio_files.append(audio_file)
                        self._play_audio(audio_file)
                
                progress_percent = int((i + 1) / total_chunks * 100)
                self.progress.emit(progress_percent)
            
            self.status.emit("Complete")
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._cleanup()
    
    def _split_text(self, text: str, max_length: int) -> list:
        """Split text into chunks by sentence boundaries"""
        sentences = text.replace('\n', ' ').split('.')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk + sentence) < max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _generate_chunk(self, text: str) -> str:
        """Generate audio for a single chunk using Edge-TTS"""
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_file.close()
        
        rate_str = f"{self.rate:+d}%"
        volume_str = f"{self.volume:+d}%"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def generate():
            communicate = edge_tts.Communicate(
                text, 
                self.voice,
                rate=rate_str,
                volume=volume_str
            )
            await communicate.save(temp_file.name)
        
        try:
            loop.run_until_complete(generate())
        finally:
            loop.close()
        
        return temp_file.name
    
    def _play_audio(self, audio_file: str):
        """Play an audio file"""
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy() and self.is_running:
                pygame.time.Clock().tick(10)
                
        except Exception as e:
            print(f"Playback error: {e}")
    
    def _cleanup(self):
        """Clean up temporary audio files"""
        for file in self.audio_files:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except:
                pass


# =============================================================================
# OFFLINE TTS THREAD (pyttsx3)
# =============================================================================

class OfflineTTSThread(QThread):
    """Thread for generating and playing TTS audio using pyttsx3 (offline)"""
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, text: str, voice: str, rate: int, volume: int, chunk_size: int):
        super().__init__()
        self.text = text
        self.voice = voice  # Will be voice ID for pyttsx3
        self.rate = rate
        self.volume = volume
        self.chunk_size = chunk_size
        self.is_running = True
        self.audio_files = []
    
    def stop(self):
        """Stop the TTS thread"""
        self.is_running = False
        try:
            pygame.mixer.music.stop()
        except:
            pass
    
    def run(self):
        try:
            chunks = self._split_text(self.text, self.chunk_size)
            total_chunks = len(chunks)
            
            if total_chunks == 0:
                self.error.emit("No text to speak")
                return
            
            # Initialize pygame mixer
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            except:
                pygame.mixer.init()
            
            for i, chunk in enumerate(chunks):
                if not self.is_running:
                    break
                
                if chunk.strip():
                    self.status.emit(f"Generating chunk {i+1}/{total_chunks} (Offline)...")
                    
                    audio_file = self._generate_chunk(chunk)
                    if audio_file:
                        self.audio_files.append(audio_file)
                        self._play_audio(audio_file)
                
                progress_percent = int((i + 1) / total_chunks * 100)
                self.progress.emit(progress_percent)
            
            self.status.emit("Complete (Offline)")
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(f"Offline TTS error: {str(e)}")
        finally:
            self._cleanup()
    
    def _split_text(self, text: str, max_length: int) -> list:
        """Split text into chunks by sentence boundaries"""
        sentences = text.replace('\n', ' ').split('.')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk + sentence) < max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _generate_chunk(self, text: str) -> str:
        """Generate audio for a single chunk using pyttsx3"""
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()
        
        try:
            engine = pyttsx3.init()
            
            # Set voice if specified
            if self.voice:
                engine.setProperty('voice', self.voice)
            
            # Set rate (pyttsx3 uses words per minute, default ~200)
            # Convert our percentage to WPM adjustment
            base_rate = engine.getProperty('rate')
            adjusted_rate = int(base_rate * (1 + self.rate / 100))
            engine.setProperty('rate', adjusted_rate)
            
            # Set volume (0.0 to 1.0)
            base_volume = 1.0
            adjusted_volume = max(0.0, min(1.0, base_volume * (1 + self.volume / 100)))
            engine.setProperty('volume', adjusted_volume)
            
            # Save to file
            engine.save_to_file(text, temp_file.name)
            engine.runAndWait()
            engine.stop()
            
            return temp_file.name
            
        except Exception as e:
            print(f"Offline TTS generation error: {e}")
            return None
    
    def _play_audio(self, audio_file: str):
        """Play an audio file"""
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy() and self.is_running:
                pygame.time.Clock().tick(10)
                
        except Exception as e:
            print(f"Playback error: {e}")
    
    def _cleanup(self):
        """Clean up temporary audio files"""
        for file in self.audio_files:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except:
                pass


# =============================================================================
# SAVE THREAD
# =============================================================================

class SaveThread(QThread):
    """Thread for saving TTS to file"""
    finished = pyqtSignal(str)
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, text: str, voice: str, rate: int, volume: int, output_path: str):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.output_path = output_path
    
    def run(self):
        try:
            self.status.emit("Generating audio file...")
            
            rate_str = f"{self.rate:+d}%"
            volume_str = f"{self.volume:+d}%"
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def generate():
                communicate = edge_tts.Communicate(
                    self.text,
                    self.voice,
                    rate=rate_str,
                    volume=volume_str
                )
                await communicate.save(self.output_path)
            
            loop.run_until_complete(generate())
            loop.close()
            
            self.progress.emit(100)
            self.status.emit("Saved successfully")
            self.finished.emit(self.output_path)
            
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class EdgeTTSApp(QMainWindow):
    """Main TTS Application Window"""
    
    def __init__(self, socket_port=None):
        super().__init__()
        self.config = ConfigManager.load()
        self.tts_thread = None
        self.save_thread = None
        self.voices = []
        self.socket_port = socket_port
        self.socket_server = None
        
        # Pause/Resume state
        self.is_paused = False
        self.paused_audio_file = None
        self.paused_position = 0.0
        
        # Initialize offline TTS engine and detect voices
        self._init_offline_voices()
        
        self._init_ui()
        self._load_voices()
        self._apply_config()
        
        # Start socket server if port provided
        if self.socket_port:
            self._start_socket_server()
    
    def set_text_and_play(self, text: str):
        """Set text and automatically play (for external calls)"""
        # Append to existing text rather than replacing
        current_text = self.text_edit.toPlainText()
        if current_text.strip():
            # Add separator if there's existing text
            self.text_edit.setPlainText(current_text + "\n\n" + text)
        else:
            self.text_edit.setPlainText(text)
        # Trigger play immediately
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self._on_play)
    
    def _start_socket_server(self):
        """Start socket server to receive text from ai_copilot"""
        def server_thread():
            try:
                self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket_server.bind(('localhost', self.socket_port))
                self.socket_server.listen(5)  # Increased backlog
                print(f"Socket server listening on port {self.socket_port}")
                
                while True:
                    try:
                        conn, addr = self.socket_server.accept()
                        data = conn.recv(8192).decode('utf-8')  # Increased buffer size
                        if data:
                            print(f"Received text: {data[:50]}...")
                            # Use Qt signal to safely update UI from thread
                            from PyQt6.QtCore import QMetaObject, Qt
                            QMetaObject.invokeMethod(
                                self,
                                "set_text_and_play",
                                Qt.ConnectionType.QueuedConnection,
                                argparse.Namespace(text=data).__dict__['text'] if hasattr(argparse.Namespace(text=data), 'text') else data
                            )
                        conn.close()
                    except Exception as e:
                        print(f"Socket connection error: {e}")
                        # Continue accepting connections
            except Exception as e:
                print(f"Socket server error: {e}")
        
        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()
    
    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Aetherion TTS Speaker")
        self.setMinimumSize(50, 50)
        
        # Set initial size
        self.resize(600, 700)
        
        # Apply Crimson theme
        apply_crimson_theme(self)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        
        # === GENERATION CONTROLS ===
        gen_group = QGroupBox("Generation Controls")
        gen_layout = QHBoxLayout(gen_group)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._on_play)
        self.play_btn.setMinimumHeight(40)
        
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(40)
        
        self.pause_resume_btn = QPushButton("⏸ Pause")
        self.pause_resume_btn.clicked.connect(self._on_pause_resume)
        self.pause_resume_btn.setEnabled(False)
        self.pause_resume_btn.setMinimumHeight(40)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        gen_layout.addWidget(self.play_btn)
        gen_layout.addWidget(self.pause_resume_btn)
        gen_layout.addWidget(self.stop_btn)
        gen_layout.addWidget(self.progress_bar, stretch=1)
        
        layout.addWidget(gen_group)
        
        # === TEXT FORMATTING OPTIONS ===
        format_group = QGroupBox("Text Formatting")
        format_layout = QHBoxLayout(format_group)
        
        format_layout.addWidget(QLabel("Chunk Size:"))
        self.chunk_combo = QComboBox()
        for size in CHUNK_SIZES:
            self.chunk_combo.addItem(str(size), size)
        self.chunk_combo.setCurrentText("200")
        format_layout.addWidget(self.chunk_combo)
        
        self.strip_newlines_cb = QCheckBox("Strip Newlines")
        self.strip_newlines_cb.setChecked(True)
        format_layout.addWidget(self.strip_newlines_cb)
        
        self.strip_extra_spaces_cb = QCheckBox("Collapse Spaces")
        self.strip_extra_spaces_cb.setChecked(True)
        format_layout.addWidget(self.strip_extra_spaces_cb)
        
        self.strip_symbols_cb = QCheckBox("Strip Symbols (*#_~`|)")
        self.strip_symbols_cb.setChecked(True)
        format_layout.addWidget(self.strip_symbols_cb)
        
        format_layout.addStretch()
        layout.addWidget(format_group)
        
        # === FILE CONTROLS ===
        file_group = QGroupBox("File Controls")
        file_layout = QHBoxLayout(file_group)
        
        self.load_btn = QPushButton("Load Text File")
        self.load_btn.clicked.connect(self._on_load_file)
        
        self.save_audio_btn = QPushButton("Save Audio")
        self.save_audio_btn.clicked.connect(self._on_save_audio)
        
        self.clear_btn = QPushButton("Clear Text")
        self.clear_btn.clicked.connect(self._on_clear_text)
        
        file_layout.addWidget(self.load_btn)
        file_layout.addWidget(self.save_audio_btn)
        file_layout.addWidget(self.clear_btn)
        file_layout.addStretch()
        
        layout.addWidget(file_group)
        
        # === TEXT CONTENT ===
        text_group = QGroupBox("Text Content")
        text_layout = QVBoxLayout(text_group)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Enter text to speak...")
        self.text_edit.setFont(QFont("Consolas", 11))
        self.text_edit.setMinimumHeight(200)
        
        text_layout.addWidget(self.text_edit)
        
        # Character count
        self.char_count_label = QLabel("Characters: 0")
        self.text_edit.textChanged.connect(self._update_char_count)
        text_layout.addWidget(self.char_count_label)
        
        layout.addWidget(text_group, stretch=1)
        
        # === TTS MODE SELECTION ===
        mode_group = QGroupBox("TTS Mode")
        mode_layout = QHBoxLayout(mode_group)
        
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🌐 Online (Edge-TTS)", TTS_MODE_ONLINE)
        self.mode_combo.addItem("💻 Offline (System)", TTS_MODE_OFFLINE)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        
        self.mode_status_label = QLabel("✓ Internet required")
        mode_layout.addWidget(self.mode_status_label)
        mode_layout.addStretch()
        
        layout.addWidget(mode_group)
        
        # === VOICE SELECTION ===
        voice_group = QGroupBox("Voice Selection")
        voice_layout = QHBoxLayout(voice_group)
        
        voice_layout.addWidget(QLabel("Voice:"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(300)
        voice_layout.addWidget(self.voice_combo, stretch=1)
        
        self.refresh_voices_btn = QPushButton("↻ Refresh")
        self.refresh_voices_btn.clicked.connect(self._load_voices)
        voice_layout.addWidget(self.refresh_voices_btn)
        
        layout.addWidget(voice_group)
        
        # === VOICE CONTROLS ===
        controls_group = QGroupBox("Voice Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # Rate
        controls_layout.addWidget(QLabel("Rate (%):"))
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(-50, 100)
        self.rate_spin.setValue(0)
        self.rate_spin.setSuffix("%")
        controls_layout.addWidget(self.rate_spin)
        
        controls_layout.addSpacing(20)
        
        # Volume
        controls_layout.addWidget(QLabel("Volume (%):"))
        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(-50, 50)
        self.volume_spin.setValue(0)
        self.volume_spin.setSuffix("%")
        controls_layout.addWidget(self.volume_spin)
        
        controls_layout.addStretch()
        
        # Reset button
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_controls)
        controls_layout.addWidget(self.reset_btn)
        
        layout.addWidget(controls_group)
        
        # === STATUS BAR ===
        self.statusBar().showMessage("Ready")
    
    def _init_offline_voices(self):
        """Initialize and detect offline system voices"""
        global OFFLINE_VOICES
        try:
            engine = pyttsx3.init()
            OFFLINE_VOICES = engine.getProperty('voices')
            engine.stop()
            print(f"Detected {len(OFFLINE_VOICES)} offline voices")
        except Exception as e:
            print(f"Offline voice detection error: {e}")
            OFFLINE_VOICES = []
    
    def _on_mode_changed(self):
        """Handle TTS mode change"""
        mode = self.mode_combo.currentData()
        
        if mode == TTS_MODE_ONLINE:
            self.mode_status_label.setText("✓ Internet required")
            self.mode_status_label.setStyleSheet("color: #4A9EFF;")
            self._load_voices()  # Reload online voices
        else:
            self.mode_status_label.setText("✓ Works offline")
            self.mode_status_label.setStyleSheet("color: #50C878;")
            self._load_offline_voices()  # Load system voices
    
    def _load_offline_voices(self):
        """Load offline system voices into combo box"""
        self.voice_combo.clear()
        
        if not OFFLINE_VOICES:
            self.voice_combo.addItem("No offline voices available", None)
            self.statusBar().showMessage("No offline voices detected")
            return
        
        current_voice = self.config.get("offline_voice")
        target_index = 0
        
        for i, voice in enumerate(OFFLINE_VOICES):
            # Create readable display name
            name = voice.name.split('.')[-1] if '.' in voice.name else voice.name
            lang_info = f" ({voice.languages[0]})" if voice.languages else ""
            display_name = f"{name}{lang_info}"
            
            self.voice_combo.addItem(display_name, voice.id)
            
            if current_voice and voice.id == current_voice:
                target_index = i
        
        self.voice_combo.setCurrentIndex(target_index)
        self.statusBar().showMessage(f"Loaded {len(OFFLINE_VOICES)} offline voices")
    
    def _load_voices(self):
        """Load available voices from Edge-TTS"""
        self.statusBar().showMessage("Loading online voices...")
        self.voice_combo.setEnabled(False)
        self.refresh_voices_btn.setEnabled(False)
        
        self.voice_thread = VoiceCacheThread()
        self.voice_thread.finished.connect(self._on_voices_loaded)
        self.voice_thread.error.connect(self._on_voices_error)
        self.voice_thread.start()
    
    def _on_voices_loaded(self, voices: list):
        """Handle voices loaded"""
        global VOICE_CACHE
        VOICE_CACHE = voices
        
        self.voice_combo.clear()
        
        # Sort voices by locale then name
        sorted_voices = sorted(voices, key=lambda v: (v['Locale'], v['ShortName']))
        
        current_voice = self.config.get("voice", DEFAULT_VOICE)
        target_index = 0
        
        for i, voice in enumerate(sorted_voices):
            display_name = f"{voice['ShortName']} ({voice['Locale']}) - {voice['Gender']}"
            self.voice_combo.addItem(display_name, voice['ShortName'])
            
            if voice['ShortName'] == current_voice:
                target_index = i
        
        self.voice_combo.setCurrentIndex(target_index)
        self.voice_combo.setEnabled(True)
        self.refresh_voices_btn.setEnabled(True)
        
        # Verify default voice exists
        voice_names = [v['ShortName'] for v in voices]
        if DEFAULT_VOICE in voice_names:
            self.statusBar().showMessage(f"Loaded {len(voices)} voices. Default: {DEFAULT_VOICE} ✓")
        else:
            self.statusBar().showMessage(f"Loaded {len(voices)} voices. Warning: {DEFAULT_VOICE} not found!")
    
    def _on_voices_error(self, error: str):
        """Handle voice loading error"""
        self.voice_combo.setEnabled(True)
        self.refresh_voices_btn.setEnabled(True)
        self.statusBar().showMessage(f"Voice loading error: {error}")
        QMessageBox.warning(self, "Voice Error", f"Failed to load voices: {error}")
    
    def _apply_config(self):
        """Apply saved configuration"""
        self.rate_spin.setValue(self.config.get("rate", 0))
        self.volume_spin.setValue(self.config.get("volume", 0))
        
        chunk_size = self.config.get("chunk_size", 200)
        index = self.chunk_combo.findData(chunk_size)
        if index >= 0:
            self.chunk_combo.setCurrentIndex(index)
        
        self.strip_symbols_cb.setChecked(self.config.get("strip_symbols", True))
        
        # Restore TTS mode
        tts_mode = self.config.get("tts_mode", TTS_MODE_ONLINE)
        mode_index = self.mode_combo.findData(tts_mode)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
    
    def _save_config(self):
        """Save current configuration"""
        current_mode = self.mode_combo.currentData()
        
        self.config = {
            "voice": self.voice_combo.currentData() or DEFAULT_VOICE,
            "rate": self.rate_spin.value(),
            "volume": self.volume_spin.value(),
            "chunk_size": self.chunk_combo.currentData() or 200,
            "strip_symbols": self.strip_symbols_cb.isChecked(),
            "tts_mode": current_mode,
            "offline_voice": self.voice_combo.currentData() if current_mode == TTS_MODE_OFFLINE else self.config.get("offline_voice")
        }
        ConfigManager.save(self.config)
    
    def _get_formatted_text(self) -> str:
        """Get text with formatting options applied"""
        text = self.text_edit.toPlainText()
        
        if self.strip_newlines_cb.isChecked():
            text = text.replace('\n', ' ').replace('\r', ' ')
        
        if self.strip_symbols_cb.isChecked():
            # Remove common markdown and verbatim punctuation
            symbols_to_remove = ['*', '#', '_', '~', '`', '|', '[', ']', '{', '}', '<', '>']
            for symbol in symbols_to_remove:
                text = text.replace(symbol, '')
        
        if self.strip_extra_spaces_cb.isChecked():
            while '  ' in text:
                text = text.replace('  ', ' ')
        
        return text.strip()
    
    def _update_char_count(self):
        """Update character count label"""
        count = len(self.text_edit.toPlainText())
        self.char_count_label.setText(f"Characters: {count}")
    
    def _on_play(self):
        """Start TTS playback"""
        text = self._get_formatted_text()
        if not text:
            QMessageBox.warning(self, "No Text", "Please enter some text to speak.")
            return
        
        voice = self.voice_combo.currentData()
        if not voice:
            QMessageBox.warning(self, "No Voice", "Please select a voice.")
            return
        
        self._save_config()
        
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_resume_btn.setEnabled(True)
        self.pause_resume_btn.setText("⏸ Pause")
        self.is_paused = False
        self.progress_bar.setValue(0)
        
        # Determine which TTS engine to use
        current_mode = self.mode_combo.currentData()
        
        if current_mode == TTS_MODE_ONLINE:
            # Use Edge-TTS (online)
            self.tts_thread = TTSThread(
                text=text,
                voice=voice,
                rate=self.rate_spin.value(),
                volume=self.volume_spin.value(),
                chunk_size=self.chunk_combo.currentData() or 200
            )
        else:
            # Use pyttsx3 (offline)
            self.tts_thread = OfflineTTSThread(
                text=text,
                voice=voice,
                rate=self.rate_spin.value(),
                volume=self.volume_spin.value(),
                chunk_size=self.chunk_combo.currentData() or 200
            )
        
        self.tts_thread.progress.connect(self.progress_bar.setValue)
        self.tts_thread.status.connect(self.statusBar().showMessage)
        self.tts_thread.finished.connect(self._on_play_finished)
        self.tts_thread.error.connect(self._on_play_error_with_fallback)
        self.tts_thread.start()
    
    def _on_stop(self):
        """Stop TTS playback"""
        if self.tts_thread:
            self.tts_thread.stop()
            self.tts_thread.wait()
        # Clean up paused state
        if self.paused_audio_file and os.path.exists(self.paused_audio_file):
            try:
                os.remove(self.paused_audio_file)
            except:
                pass
        self.paused_audio_file = None
        self.paused_position = 0.0
        self._on_play_finished()
    
    def _on_pause_resume(self):
        """Handle pause/resume button"""
        try:
            if not self.is_paused:
                # Pause current playback
                self.paused_position = pygame.mixer.music.get_pos() / 1000.0  # Convert ms to seconds
                pygame.mixer.music.pause()
                self.is_paused = True
                self.pause_resume_btn.setText("▶ Resume")
                self.statusBar().showMessage(f"Paused at {self.paused_position:.1f}s")
            else:
                # Resume playback
                pygame.mixer.music.unpause()
                self.is_paused = False
                self.pause_resume_btn.setText("⏸ Pause")
                self.statusBar().showMessage("Resumed")
        except Exception as e:
            self.statusBar().showMessage(f"Pause/Resume error: {e}")
    
    def _on_play_finished(self):
        """Handle playback completion"""
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_resume_btn.setEnabled(False)
        self.pause_resume_btn.setText("⏸ Pause")
        self.is_paused = False
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Ready")
    
    def _on_play_error_with_fallback(self, error: str):
        """Handle playback error with automatic fallback to offline mode"""
        current_mode = self.mode_combo.currentData()
        
        # If online mode failed and offline voices are available, offer fallback
        if current_mode == TTS_MODE_ONLINE and OFFLINE_VOICES:
            self._on_play_finished()
            
            reply = QMessageBox.question(
                self,
                "Online TTS Failed",
                f"Online TTS error: {error}\n\nSwitch to offline mode and retry?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Switch to offline mode
                offline_index = self.mode_combo.findData(TTS_MODE_OFFLINE)
                if offline_index >= 0:
                    self.mode_combo.setCurrentIndex(offline_index)
                    # Retry playback
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(100, self._on_play)
        else:
            self._on_play_finished()
            QMessageBox.warning(self, "TTS Error", f"Error during playback: {error}")
    
    def _on_play_error(self, error: str):
        """Handle playback error (without fallback)"""
        self._on_play_finished()
        QMessageBox.warning(self, "TTS Error", f"Error during playback: {error}")
    
    def _on_load_file(self):
        """Load text from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Text File", "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.text_edit.setPlainText(f.read())
                self.statusBar().showMessage(f"Loaded: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load file: {e}")
    
    def _on_save_audio(self):
        """Save TTS to audio file"""
        text = self._get_formatted_text()  # This now properly formats the text
        if not text:
            QMessageBox.warning(self, "No Text", "Please enter some text to save.")
            return
        
        voice = self.voice_combo.currentData()
        if not voice:
            QMessageBox.warning(self, "No Voice", "Please select a voice.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Audio File", "",
            "MP3 Files (*.mp3);;WAV Files (*.wav);;All Files (*.*)"
        )
        
        if file_path:
            self._save_config()
            
            self.play_btn.setEnabled(False)
            self.save_audio_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            
            # Pass the formatted text to SaveThread
            self.save_thread = SaveThread(
                text=text,  # Already formatted by _get_formatted_text()
                voice=voice,
                rate=self.rate_spin.value(),
                volume=self.volume_spin.value(),
                output_path=file_path
            )
            
            self.save_thread.progress.connect(self.progress_bar.setValue)
            self.save_thread.status.connect(self.statusBar().showMessage)
            self.save_thread.finished.connect(self._on_save_finished)
            self.save_thread.error.connect(self._on_save_error)
            self.save_thread.start()
    
    def _on_save_finished(self, path: str):
        """Handle save completion"""
        self.play_btn.setEnabled(True)
        self.save_audio_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        QMessageBox.information(self, "Saved", f"Audio saved to:\n{path}")
    
    def _on_save_error(self, error: str):
        """Handle save error"""
        self.play_btn.setEnabled(True)
        self.save_audio_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        QMessageBox.warning(self, "Save Error", f"Failed to save audio: {error}")
    
    def _on_clear_text(self):
        """Clear text content"""
        self.text_edit.clear()
    
    def _reset_controls(self):
        """Reset voice controls to defaults"""
        self.rate_spin.setValue(0)
        self.volume_spin.setValue(0)
        self.chunk_combo.setCurrentText("200")
        
        # Reset to default voice
        for i in range(self.voice_combo.count()):
            if self.voice_combo.itemData(i) == DEFAULT_VOICE:
                self.voice_combo.setCurrentIndex(i)
                break
    
    def resizeEvent(self, event):
        """Handle window resize"""
        super().resizeEvent(event)
    
    def closeEvent(self, event):
        """Handle window close"""
        self._save_config()
        
        if self.tts_thread and self.tts_thread.isRunning():
            self.tts_thread.stop()
            self.tts_thread.wait()
        
        if self.save_thread and self.save_thread.isRunning():
            self.save_thread.wait()
        
        # Clean up paused audio file
        if self.paused_audio_file and os.path.exists(self.paused_audio_file):
            try:
                os.remove(self.paused_audio_file)
            except:
                pass
        
        event.accept()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Application entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Edge-TTS Speaker')
    parser.add_argument('--text', type=str, help='Text to speak')
    parser.add_argument('--autoplay', action='store_true', help='Automatically play the text')
    parser.add_argument('--socket', type=int, help='Socket port for IPC')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = EdgeTTSApp(socket_port=args.socket)
    
    # If text provided, set it and optionally autoplay
    if args.text:
        if args.autoplay:
            window.set_text_and_play(args.text)
        else:
            window.text_edit.setPlainText(args.text)
    
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
