#!/usr/bin/env python3
"""
Clean Edge-TTS Speaker Module
Modular TTS interface for Aetherion Realms
PyQt6 | Python 3.10+ | Edge-TTS

Author: Crimson / Built with Vera
"""

import sys
import os
import asyncio
import tempfile
import json
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


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_VOICE = "en-GB-SoniaNeural"
CONFIG_FILE = Path.home() / ".aetherion_tts_config.json"

CHUNK_SIZES = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]

# Voice cache - populated on startup
VOICE_CACHE = []


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
            "chunk_size": 200
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
    
    def __init__(self, text: str, voice: str, rate: int, volume: int, pitch: int, chunk_size: int):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
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
        """Generate audio for a single chunk"""
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_file.close()
        
        try:
            # Format rate, volume, pitch for Edge-TTS
            rate_str = f"{self.rate:+d}%"
            volume_str = f"{self.volume:+d}%"
            pitch_str = f"{self.pitch:+d}Hz"
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def generate():
                communicate = edge_tts.Communicate(
                    text, 
                    self.voice,
                    rate=rate_str,
                    volume=volume_str,
                    pitch=pitch_str
                )
                await communicate.save(temp_file.name)
            
            loop.run_until_complete(generate())
            loop.close()
            
            # Verify file was created
            if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 100:
                return temp_file.name
            else:
                raise Exception("Audio file generation failed")
                
        except Exception as e:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise e
    
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
    
    def __init__(self, text: str, voice: str, rate: int, volume: int, pitch: int, output_path: str):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
        self.output_path = output_path
    
    def run(self):
        try:
            self.status.emit("Generating audio file...")
            
            rate_str = f"{self.rate:+d}%"
            volume_str = f"{self.volume:+d}%"
            pitch_str = f"{self.pitch:+d}Hz"
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def generate():
                communicate = edge_tts.Communicate(
                    self.text,
                    self.voice,
                    rate=rate_str,
                    volume=volume_str,
                    pitch=pitch_str
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
    
    def __init__(self):
        super().__init__()
        self.config = ConfigManager.load()
        self.tts_thread = None
        self.save_thread = None
        self.voices = []
        
        self._init_ui()
        self._load_voices()
        self._apply_config()
    
    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Aetherion TTS Speaker")
        self.setMinimumSize(600, 700)
        
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
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        gen_layout.addWidget(self.play_btn)
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
        
        controls_layout.addSpacing(20)
        
        # Pitch
        controls_layout.addWidget(QLabel("Pitch (Hz):"))
        self.pitch_spin = QSpinBox()
        self.pitch_spin.setRange(-50, 50)
        self.pitch_spin.setValue(0)
        self.pitch_spin.setSuffix("Hz")
        controls_layout.addWidget(self.pitch_spin)
        
        controls_layout.addStretch()
        
        # Reset button
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_controls)
        controls_layout.addWidget(self.reset_btn)
        
        layout.addWidget(controls_group)
        
        # === STATUS BAR ===
        self.statusBar().showMessage("Ready")
    
    def _load_voices(self):
        """Load available voices from Edge-TTS"""
        self.statusBar().showMessage("Loading voices...")
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
        self.pitch_spin.setValue(self.config.get("pitch", 0))
        
        chunk_size = self.config.get("chunk_size", 200)
        index = self.chunk_combo.findData(chunk_size)
        if index >= 0:
            self.chunk_combo.setCurrentIndex(index)
    
    def _save_config(self):
        """Save current configuration"""
        self.config = {
            "voice": self.voice_combo.currentData() or DEFAULT_VOICE,
            "rate": self.rate_spin.value(),
            "volume": self.volume_spin.value(),
            "pitch": self.pitch_spin.value(),
            "chunk_size": self.chunk_combo.currentData() or 200
        }
        ConfigManager.save(self.config)
    
    def _get_formatted_text(self) -> str:
        """Get text with formatting options applied"""
        text = self.text_edit.toPlainText()
        
        if self.strip_newlines_cb.isChecked():
            text = text.replace('\n', ' ').replace('\r', ' ')
        
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
        self.progress_bar.setValue(0)
        
        self.tts_thread = TTSThread(
            text=text,
            voice=voice,
            rate=self.rate_spin.value(),
            volume=self.volume_spin.value(),
            pitch=self.pitch_spin.value(),
            chunk_size=self.chunk_combo.currentData() or 200
        )
        
        self.tts_thread.progress.connect(self.progress_bar.setValue)
        self.tts_thread.status.connect(self.statusBar().showMessage)
        self.tts_thread.finished.connect(self._on_play_finished)
        self.tts_thread.error.connect(self._on_play_error)
        self.tts_thread.start()
    
    def _on_stop(self):
        """Stop TTS playback"""
        if self.tts_thread:
            self.tts_thread.stop()
            self.tts_thread.wait()
        self._on_play_finished()
    
    def _on_play_finished(self):
        """Handle playback completion"""
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Ready")
    
    def _on_play_error(self, error: str):
        """Handle playback error"""
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
        text = self._get_formatted_text()
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
            
            self.save_thread = SaveThread(
                text=text,
                voice=voice,
                rate=self.rate_spin.value(),
                volume=self.volume_spin.value(),
                pitch=self.pitch_spin.value(),
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
        self.pitch_spin.setValue(0)
        self.chunk_combo.setCurrentText("200")
        
        # Reset to default voice
        for i in range(self.voice_combo.count()):
            if self.voice_combo.itemData(i) == DEFAULT_VOICE:
                self.voice_combo.setCurrentIndex(i)
                break
    
    def closeEvent(self, event):
        """Handle window close"""
        self._save_config()
        
        if self.tts_thread and self.tts_thread.isRunning():
            self.tts_thread.stop()
            self.tts_thread.wait()
        
        if self.save_thread and self.save_thread.isRunning():
            self.save_thread.wait()
        
        event.accept()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = EdgeTTSApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
