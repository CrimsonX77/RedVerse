import os
import sys
import threading
import queue
import traceback
from enum import Enum
from typing import Optional, Callable, List
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                              QComboBox, QMessageBox, QGroupBox, QListWidget,
                              QListWidgetItem, QSplitter, QCheckBox, QScrollArea)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QClipboard, QIcon, QPixmap


class AppState(Enum):
    """Deterministic application states"""
    READY = "Ready"
    LISTENING = "Listening"
    STOPPED = "Stopped"
    TRANSCRIBING = "Transcribing"
    ERROR = "Error"


class BackendType(Enum):
    """Available speech recognition backends"""
    AUTO = "Auto"
    GOOGLE = "Google Cloud"
    WHISPER = "OpenAI Whisper"
    LOCAL = "Local Offline"


class AudioSignals(QObject):
    """Thread-safe signals for audio processing"""
    status_update = pyqtSignal(str, str)  # (status_text, color)
    transcription_ready = pyqtSignal(str)  # transcribed_text
    error_occurred = pyqtSignal(str)  # error_message


class ClipboardManager(QObject):
    """Isolated clipboard management system"""
    clipboard_changed = pyqtSignal(str)  # New clipboard content
    
    def __init__(self):
        super().__init__()
        self.clipboard = QApplication.clipboard()
        self.history: List[str] = []
        self.favorites: List[str] = []
        self.max_history = 20
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)
    
    def _on_clipboard_changed(self):
        """Monitor system clipboard changes"""
        try:
            text = self.clipboard.text()
            if text and text.strip() and (not self.history or text != self.history[0]):
                self.history.insert(0, text)
                if len(self.history) > self.max_history:
                    self.history = self.history[:self.max_history]
                self.clipboard_changed.emit(text)
        except Exception as e:
            print(f"[CLIPBOARD] Monitor error: {e}")
    
    def copy_to_clipboard(self, text: str):
        """Copy text to clipboard and add to history"""
        if not text or not text.strip():
            return
        self.clipboard.setText(text)
        # History will be updated by dataChanged signal
    
    def add_to_favorites(self, text: str):
        """Add item to favorites"""
        if text and text not in self.favorites:
            self.favorites.insert(0, text)
    
    def remove_from_favorites(self, text: str):
        """Remove item from favorites"""
        if text in self.favorites:
            self.favorites.remove(text)
    
    def clear_history(self):
        """Clear clipboard history"""
        self.history = []
    
    def get_history(self, limit: int = 10) -> List[str]:
        """Get clipboard history up to limit"""
        return self.history[:limit]
    
    def get_favorites(self) -> List[str]:
        """Get all favorites"""
        return self.favorites.copy()


class SpeechBackend:
    """Base class for speech recognition backends"""
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = False
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
    
    @staticmethod
    def check_dependencies(packages: List[str]) -> tuple[bool, List[str]]:
        """Check if required packages are installed"""
        missing = []
        for package in packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        return (len(missing) == 0, missing)
    
    def initialize(self):
        """Lazy initialization - called only when first needed"""
        raise NotImplementedError
    
    def start_listening(self, callback: Callable):
        """Start capturing audio"""
        raise NotImplementedError
    
    def stop_listening(self):
        """Stop all listening threads"""
        self.stop_event.set()
    
    def transcribe(self) -> str:
        """Transcribe collected audio"""
        raise NotImplementedError
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_event.set()
        self.initialized = False


class LocalSpeechBackend(SpeechBackend):
    """Offline speech recognition using speech_recognition library"""
    
    def __init__(self):
        super().__init__("Local Offline")
        self.recognizer = None
        self.microphone = None
        self.audio_data = None
        self.listening_thread = None
    
    def initialize(self):
        if self.initialized:
            return
        
        # Check dependencies first
        has_deps, missing = self.check_dependencies(['speech_recognition', 'pyaudio'])
        if not has_deps:
            raise RuntimeError(f"Missing packages: {', '.join(missing)}. Install with: pip install SpeechRecognition pyaudio")
        
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise
            print(f"[{self.name}] Adjusting for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            self.initialized = True
            print(f"[{self.name}] Initialized successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize {self.name}: {str(e)}")
    
    def start_listening(self, callback: Callable):
        self.stop_event.clear()
        self.audio_data = None
        
        def listen_worker():
            try:
                import speech_recognition as sr
                with self.microphone as source:
                    print(f"[{self.name}] Listening...")
                    callback("Listening", "#FFC107")
                    
                    # Listen with timeout awareness
                    while not self.stop_event.is_set():
                        try:
                            audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=30)
                            if not self.stop_event.is_set():
                                self.audio_data = audio
                                print(f"[{self.name}] Audio captured")
                                break
                        except sr.WaitTimeoutError:
                            continue
                        except Exception as e:
                            if not self.stop_event.is_set():
                                print(f"[{self.name}] Listen error: {e}")
                                callback("Error", "#f44336")
                            break
                    
                    print(f"[{self.name}] Listening stopped")
            except Exception as e:
                print(f"[{self.name}] Fatal listening error: {e}")
                traceback.print_exc()
        
        self.listening_thread = threading.Thread(target=listen_worker, daemon=True)
        self.listening_thread.start()
    
    def stop_listening(self):
        print(f"[{self.name}] Stop signal received")
        super().stop_listening()
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=3)
    
    def transcribe(self) -> str:
        if not self.audio_data:
            raise RuntimeError("No audio data captured")
        
        import speech_recognition as sr
        try:
            print(f"[{self.name}] Transcribing...")
            text = self.recognizer.recognize_google(self.audio_data)
            print(f"[{self.name}] Transcription complete")
            return text
        except sr.UnknownValueError:
            raise RuntimeError("Could not understand audio")
        except sr.RequestError as e:
            raise RuntimeError(f"Recognition service error: {e}")
    
    def cleanup(self):
        super().cleanup()
        self.audio_data = None


class GoogleCloudBackend(SpeechBackend):
    """Google Cloud Speech-to-Text backend"""
    
    def __init__(self):
        super().__init__("Google Cloud")
        self.client = None
        self.stream = None
        self.audio_buffer = []
        self.listening_thread = None
    
    def initialize(self):
        if self.initialized:
            return
        
        # Check dependencies first
        has_deps, missing = self.check_dependencies(['google.cloud.speech', 'pyaudio'])
        if not has_deps:
            pkg_names = []
            if 'google.cloud.speech' in missing:
                pkg_names.append('google-cloud-speech')
            if 'pyaudio' in missing:
                pkg_names.append('pyaudio')
            raise RuntimeError(f"Missing packages: {', '.join(pkg_names)}. Install with: pip install {' '.join(pkg_names)}")
        
        try:
            from google.cloud import speech
            import pyaudio
            
            # Auto-detect service account credentials from project directory
            if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                creds_file = Path(__file__).parent / 'scribe-486923-ffbe3bcd944a.json'
                if creds_file.exists():
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_file)
                    print(f"[{self.name}] Auto-set credentials from {creds_file.name}")
                else:
                    raise RuntimeError(
                        "Google Cloud credentials not found. Place scribe-486923-ffbe3bcd944a.json "
                        "in the project directory or set GOOGLE_APPLICATION_CREDENTIALS env var."
                    )
            
            self.client = speech.SpeechClient()
            self.initialized = True
            print(f"[{self.name}] Initialized successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize {self.name}: {str(e)}")
    
    def start_listening(self, callback: Callable):
        self.stop_event.clear()
        self.audio_buffer = []
        
        def listen_worker():
            try:
                import pyaudio
                
                RATE = 16000
                CHUNK = 1024
                
                audio_interface = pyaudio.PyAudio()
                stream = audio_interface.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                
                print(f"[{self.name}] Listening...")
                callback("Listening", "#FFC107")
                
                while not self.stop_event.is_set():
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        self.audio_buffer.append(data)
                    except Exception as e:
                        if not self.stop_event.is_set():
                            print(f"[{self.name}] Stream read error: {e}")
                        break
                
                stream.stop_stream()
                stream.close()
                audio_interface.terminate()
                print(f"[{self.name}] Listening stopped, captured {len(self.audio_buffer)} chunks")
                
            except Exception as e:
                print(f"[{self.name}] Fatal listening error: {e}")
                traceback.print_exc()
        
        self.listening_thread = threading.Thread(target=listen_worker, daemon=True)
        self.listening_thread.start()
    
    def stop_listening(self):
        print(f"[{self.name}] Stop signal received")
        super().stop_listening()
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=3)
    
    def transcribe(self) -> str:
        if not self.audio_buffer:
            raise RuntimeError("No audio data captured")
        
        from google.cloud import speech
        
        try:
            print(f"[{self.name}] Transcribing...")
            audio_content = b''.join(self.audio_buffer)
            
            audio = speech.RecognitionAudio(content=audio_content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
            )
            
            response = self.client.recognize(config=config, audio=audio)
            
            if not response.results:
                raise RuntimeError("No transcription results")
            
            text = ' '.join([result.alternatives[0].transcript 
                           for result in response.results])
            print(f"[{self.name}] Transcription complete")
            return text
            
        except Exception as e:
            raise RuntimeError(f"Google Cloud transcription error: {str(e)}")
    
    def cleanup(self):
        super().cleanup()
        self.audio_buffer = []


class WhisperBackend(SpeechBackend):
    """OpenAI Whisper backend (local model)"""
    
    def __init__(self):
        super().__init__("OpenAI Whisper")
        self.model = None
        self.audio_buffer = []
        self.listening_thread = None
    
    def initialize(self):
        if self.initialized:
            return
        
        # Check dependencies first
        has_deps, missing = self.check_dependencies(['whisper', 'pyaudio', 'numpy'])
        if not has_deps:
            pkg_names = []
            if 'whisper' in missing:
                pkg_names.append('openai-whisper')
            if 'pyaudio' in missing:
                pkg_names.append('pyaudio')
            if 'numpy' in missing:
                pkg_names.append('numpy')
            raise RuntimeError(f"Missing packages: {', '.join(pkg_names)}. Install with: pip install {' '.join(pkg_names)}")
        
        try:
            import whisper
            import pyaudio
            
            print(f"[{self.name}] Loading Whisper model (this may take a moment)...")
            self.model = whisper.load_model("base")
            self.initialized = True
            print(f"[{self.name}] Initialized successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize {self.name}: {str(e)}")
    
    def start_listening(self, callback: Callable):
        self.stop_event.clear()
        self.audio_buffer = []
        
        def listen_worker():
            try:
                import pyaudio
                import numpy as np
                
                RATE = 16000
                CHUNK = 1024
                
                audio_interface = pyaudio.PyAudio()
                stream = audio_interface.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                
                print(f"[{self.name}] Listening...")
                callback("Listening", "#FFC107")
                
                while not self.stop_event.is_set():
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        self.audio_buffer.append(data)
                    except Exception as e:
                        if not self.stop_event.is_set():
                            print(f"[{self.name}] Stream read error: {e}")
                        break
                
                stream.stop_stream()
                stream.close()
                audio_interface.terminate()
                print(f"[{self.name}] Listening stopped, captured {len(self.audio_buffer)} chunks")
                
            except Exception as e:
                print(f"[{self.name}] Fatal listening error: {e}")
                traceback.print_exc()
        
        self.listening_thread = threading.Thread(target=listen_worker, daemon=True)
        self.listening_thread.start()
    
    def stop_listening(self):
        print(f"[{self.name}] Stop signal received")
        super().stop_listening()
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=3)
    
    def transcribe(self) -> str:
        if not self.audio_buffer:
            raise RuntimeError("No audio data captured")
        
        import numpy as np
        
        try:
            print(f"[{self.name}] Transcribing...")
            
            # Convert audio buffer to numpy array
            audio_data = b''.join(self.audio_buffer)
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            result = self.model.transcribe(audio_np, fp16=False)
            text = result['text'].strip()
            
            print(f"[{self.name}] Transcription complete")
            return text
            
        except Exception as e:
            raise RuntimeError(f"Whisper transcription error: {str(e)}")
    
    def cleanup(self):
        super().cleanup()
        self.audio_buffer = []


class DictationGUI(QMainWindow):
    """Main dictation GUI application"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎙️ Dictation")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(100, 100)  # Scalable down to 100x100
        
        # State management
        self.current_state = AppState.READY
        self.current_backend: Optional[SpeechBackend] = None
        self.backends = {}
        self.signals = AudioSignals()
        
        # Clipboard manager (isolated from dictation logic)
        self.clipboard_manager = ClipboardManager()
        self.clipboard_manager.clipboard_changed.connect(self._on_clipboard_updated)
        
        # Connect signals
        self.signals.status_update.connect(self._update_status_display)
        self.signals.transcription_ready.connect(self._display_transcription)
        self.signals.error_occurred.connect(self._display_error)
        
        # Flag to prevent double-clicks
        self.operation_in_progress = False
        
        # Clipboard view state
        self.show_extended_history = False
        
        self.apply_theme()
        self.init_ui()
        self.set_state(AppState.READY)
    
    def apply_theme(self):
        """Apply Crimson/Gold/Black/Silver theme"""
        stylesheet = """
            QMainWindow {
                background-color: #1a0a0a;
            }
            
            QWidget {
                background-color: #1a0a0a;
                color: #c0c0c0;
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 13px;
            }
            
            QGroupBox {
                border: 2px solid #2a2a2a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #FFD700;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            
            QPushButton {
                background-color: #8B0000;
                color: #FFD700;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                min-height: 30px;
            }
            
            QPushButton:hover {
                background-color: #A52A2A;
                border: 1px solid #FFD700;
            }
            
            QPushButton:pressed {
                background-color: #660000;
            }
            
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #505050;
                border: 1px solid #1a1a1a;
            }
            
            QComboBox {
                background-color: #2a2a2a;
                color: #c0c0c0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
                min-width: 200px;
            }
            
            QComboBox:hover {
                border: 1px solid #FFD700;
            }
            
            QComboBox::drop-down {
                border: none;
            }
            
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #c0c0c0;
                selection-background-color: #8B0000;
                selection-color: #FFD700;
            }
            
            QTextEdit {
                background-color: #0f0f0f;
                color: #c0c0c0;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
            
            QListWidget {
                background-color: #0f0f0f;
                color: #c0c0c0;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 5px;
            }
            
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #1a1a1a;
            }
            
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
            
            QListWidget::item:selected {
                background-color: #8B0000;
                color: #FFD700;
            }
            
            QLabel {
                color: #c0c0c0;
                padding: 5px;
            }
            
            QCheckBox {
                color: #c0c0c0;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #2a2a2a;
                border-radius: 3px;
                background-color: #0f0f0f;
            }
            
            QCheckBox::indicator:checked {
                background-color: #8B0000;
                border: 1px solid #FFD700;
            }
        """
        self.setStyleSheet(stylesheet)
    
    def init_ui(self):
        """Initialize user interface with symbols and clipboard features"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create horizontal splitter for main content and clipboard
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Dictation controls
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        
        # Title with symbol
        title = QLabel("🎙️")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(32)
        title.setFont(title_font)
        title.setStyleSheet("color: #DC143C; padding: 10px;")
        left_layout.addWidget(title)
        
        # Control panel
        control_group = QGroupBox("⚙️ Controls")
        control_layout = QVBoxLayout()
        
        # Backend selector
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("🔧"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems([b.value for b in BackendType])
        self.backend_combo.setCurrentIndex(0)  # Auto
        backend_layout.addWidget(self.backend_combo)
        
        # Check backends button
        check_backends_btn = QPushButton("🔍")
        check_backends_btn.setMaximumWidth(50)
        check_backends_btn.clicked.connect(self.check_backend_availability)
        check_backends_btn.setToolTip("Check which backends are available")
        backend_layout.addWidget(check_backends_btn)
        
        backend_layout.addStretch()
        control_layout.addLayout(backend_layout)
        
        # Backend status label
        self.backend_status_label = QLabel("Click 🔍 to check backend availability")
        self.backend_status_label.setStyleSheet("color: #888888; font-size: 11px; padding: 5px;")
        self.backend_status_label.setWordWrap(True)
        control_layout.addWidget(self.backend_status_label)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ Start")
        self.start_btn.clicked.connect(self.on_start_listening)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.on_stop_listening)
        button_layout.addWidget(self.stop_btn)
        
        self.transcribe_btn = QPushButton("📝 Transcribe")
        self.transcribe_btn.clicked.connect(self.on_transcribe)
        button_layout.addWidget(self.transcribe_btn)
        
        control_layout.addLayout(button_layout)
        control_group.setLayout(control_layout)
        left_layout.addWidget(control_group)
        
        # Status indicator
        status_group = QGroupBox("📊 Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(14)
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("color: #4CAF50; padding: 15px; background-color: #0f0f0f; border-radius: 5px;")
        status_layout.addWidget(self.status_label)
        
        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)
        
        # Output area
        output_group = QGroupBox("📄 Output")
        output_layout = QVBoxLayout()
        
        self.output_text = QTextEdit()
        self.output_text.setPlaceholderText("Transcription will appear here...")
        output_layout.addWidget(self.output_text)
        
        # Output action buttons
        output_btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy")
        copy_btn.clicked.connect(self.copy_output_to_clipboard)
        copy_btn.setToolTip("Copy output to clipboard")
        output_btn_layout.addWidget(copy_btn)
        
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(lambda: self.output_text.clear())
        clear_btn.setToolTip("Clear output area")
        output_btn_layout.addWidget(clear_btn)
        
        output_layout.addLayout(output_btn_layout)
        output_group.setLayout(output_layout)
        left_layout.addWidget(output_group)
        
        # Quit button at bottom
        quit_btn = QPushButton("🚪 Quit")
        quit_btn.clicked.connect(self.shutdown_application)
        quit_btn.setToolTip("Shutdown application")
        quit_btn.setStyleSheet("background-color: #660000;")
        left_layout.addWidget(quit_btn)
        
        main_splitter.addWidget(left_widget)
        
        # Right panel: Clipboard manager
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)
        
        # Clipboard history
        history_group = QGroupBox("📎 Clipboard History")
        history_layout = QVBoxLayout()
        
        # History controls
        history_controls = QHBoxLayout()
        self.extended_history_check = QCheckBox("Show 20 items")
        self.extended_history_check.stateChanged.connect(self.toggle_history_view)
        history_controls.addWidget(self.extended_history_check)
        history_controls.addStretch()
        
        clear_history_btn = QPushButton("🗑️")
        clear_history_btn.setMaximumWidth(40)
        clear_history_btn.clicked.connect(self.clear_clipboard_history)
        clear_history_btn.setToolTip("Clear history")
        history_controls.addWidget(clear_history_btn)
        
        history_layout.addLayout(history_controls)
        
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.copy_history_item)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        history_layout.addWidget(self.history_list)
        
        # History action buttons
        history_btn_layout = QHBoxLayout()
        
        copy_history_btn = QPushButton("📋 Copy")
        copy_history_btn.clicked.connect(self.copy_selected_history)
        copy_history_btn.setToolTip("Copy selected item")
        history_btn_layout.addWidget(copy_history_btn)
        
        star_btn = QPushButton("⭐ Favorite")
        star_btn.clicked.connect(self.favorite_selected_history)
        star_btn.setToolTip("Add to favorites")
        history_btn_layout.addWidget(star_btn)
        
        history_layout.addLayout(history_btn_layout)
        history_group.setLayout(history_layout)
        right_layout.addWidget(history_group)
        
        # Favorites
        favorites_group = QGroupBox("⭐ Favorites")
        favorites_layout = QVBoxLayout()
        
        self.favorites_list = QListWidget()
        self.favorites_list.itemDoubleClicked.connect(self.copy_favorite_item)
        favorites_layout.addWidget(self.favorites_list)
        
        # Favorites action buttons
        fav_btn_layout = QHBoxLayout()
        
        copy_fav_btn = QPushButton("📋 Copy")
        copy_fav_btn.clicked.connect(self.copy_selected_favorite)
        copy_fav_btn.setToolTip("Copy selected favorite")
        fav_btn_layout.addWidget(copy_fav_btn)
        
        remove_fav_btn = QPushButton("🗑️ Remove")
        remove_fav_btn.clicked.connect(self.remove_selected_favorite)
        remove_fav_btn.setToolTip("Remove from favorites")
        fav_btn_layout.addWidget(remove_fav_btn)
        
        favorites_layout.addLayout(fav_btn_layout)
        favorites_group.setLayout(favorites_layout)
        right_layout.addWidget(favorites_group)
        
        main_splitter.addWidget(right_widget)
        
        # Set initial splitter sizes (60/40 split)
        main_splitter.setSizes([600, 400])
        
        main_layout.addWidget(main_splitter)
        
        # Initialize clipboard history display
        self.update_clipboard_display()
    
    def set_state(self, state: AppState):
        """Update application state and UI accordingly"""
        self.current_state = state
        print(f"[STATE] {state.value}")
        
        # Update status display
        color_map = {
            AppState.READY: "#4CAF50",      # Green
            AppState.LISTENING: "#FFC107",  # Yellow
            AppState.STOPPED: "#9E9E9E",    # Gray
            AppState.TRANSCRIBING: "#2196F3",  # Blue
            AppState.ERROR: "#DC143C"       # Crimson
        }
        
        self.status_label.setText(state.value)
        self.status_label.setStyleSheet(
            f"color: {color_map[state]}; padding: 15px; "
            f"background-color: #0f0f0f; border-radius: 5px; border: 2px solid {color_map[state]};"
        )
        
        # Update button states (independent of UI features)
        self.start_btn.setEnabled(state in [AppState.READY, AppState.STOPPED, AppState.ERROR])
        self.stop_btn.setEnabled(state == AppState.LISTENING)
        self.transcribe_btn.setEnabled(state == AppState.LISTENING)
        self.backend_combo.setEnabled(state in [AppState.READY, AppState.STOPPED, AppState.ERROR])
    
    def get_or_create_backend(self, backend_type: BackendType) -> Optional[SpeechBackend]:
        """Lazy-load backend only when needed"""
        if backend_type == BackendType.AUTO:
            # Try backends in priority order
            errors = []
            for bt in [BackendType.GOOGLE, BackendType.WHISPER, BackendType.LOCAL]:
                try:
                    backend = self.get_or_create_backend(bt)
                    if backend:
                        print(f"[AUTO] Selected {bt.value} backend")
                        return backend
                except Exception as e:
                    errors.append(f"{bt.value}: {str(e)}")
                    print(f"[AUTO] {bt.value} failed: {e}")
            
            # All backends failed
            error_msg = "All backends failed:\n" + "\n".join(f"  • {err}" for err in errors)
            raise RuntimeError(error_msg)
        
        if backend_type not in self.backends:
            try:
                print(f"[INIT] Initializing {backend_type.value}...")
                
                if backend_type == BackendType.GOOGLE:
                    backend = GoogleCloudBackend()
                elif backend_type == BackendType.WHISPER:
                    backend = WhisperBackend()
                elif backend_type == BackendType.LOCAL:
                    backend = LocalSpeechBackend()
                else:
                    raise RuntimeError(f"Unknown backend type: {backend_type}")
                
                # Initialize synchronously but with timeout
                init_result = {'success': False, 'error': None}
                
                def init_worker():
                    try:
                        backend.initialize()
                        init_result['success'] = True
                    except Exception as e:
                        init_result['error'] = str(e)
                        print(f"[INIT] Failed to initialize {backend_type.value}: {e}")
                        traceback.print_exc()
                
                init_thread = threading.Thread(target=init_worker, daemon=True)
                init_thread.start()
                init_thread.join(timeout=15)  # Wait up to 15 seconds
                
                if init_result['success']:
                    self.backends[backend_type] = backend
                    return backend
                elif init_result['error']:
                    raise RuntimeError(init_result['error'])
                else:
                    raise RuntimeError(f"{backend_type.value} initialization timed out after 15 seconds")
                    
            except Exception as e:
                print(f"[INIT] Failed to create {backend_type.value}: {e}")
                raise
        
        return self.backends.get(backend_type)
    
    def on_start_listening(self):
        """Handle Start Listening button"""
        if self.operation_in_progress:
            print("[GUI] Operation already in progress, ignoring click")
            return
        
        self.operation_in_progress = True
        
        try:
            # Get selected backend
            backend_name = self.backend_combo.currentText()
            backend_type = BackendType(backend_name)
            
            print(f"[GUI] Starting listening with {backend_type.value}")
            self.set_state(AppState.LISTENING)
            
            # Lazy-load backend
            backend = self.get_or_create_backend(backend_type)
            
            if not backend:
                raise RuntimeError(f"Failed to initialize {backend_type.value}. Check console for details.")
            
            self.current_backend = backend
            
            # Start listening with callback
            def status_callback(status_text, color):
                self.signals.status_update.emit(status_text, color)
            
            backend.start_listening(status_callback)
            
        except Exception as e:
            error_msg = f"Failed to start listening: {str(e)}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            self.signals.error_occurred.emit(error_msg)
        finally:
            self.operation_in_progress = False
    
    def on_stop_listening(self):
        """Handle Stop Listening button - authoritative kill switch"""
        if self.operation_in_progress:
            print("[GUI] Operation already in progress, ignoring click")
            return
        
        self.operation_in_progress = True
        
        try:
            print("[GUI] STOP - Authoritative kill switch activated")
            
            if self.current_backend:
                self.current_backend.stop_listening()
                self.current_backend = None
            
            self.set_state(AppState.STOPPED)
            
        except Exception as e:
            error_msg = f"Error during stop: {str(e)}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            self.signals.error_occurred.emit(error_msg)
        finally:
            self.operation_in_progress = False
    
    def on_transcribe(self):
        """Handle Transcribe button - stops listening first, then transcribes"""
        if self.operation_in_progress:
            print("[GUI] Operation already in progress, ignoring click")
            return
        
        self.operation_in_progress = True
        
        def transcribe_worker():
            try:
                print("[GUI] TRANSCRIBE - Stopping listening first")
                
                if not self.current_backend:
                    raise RuntimeError("No active backend")
                
                # Stop listening first
                self.current_backend.stop_listening()
                
                # Update state
                self.signals.status_update.emit("Transcribing", "#2196F3")
                
                # Transcribe
                text = self.current_backend.transcribe()
                
                # Clean up
                self.current_backend.cleanup()
                self.current_backend = None
                
                # Emit result
                self.signals.transcription_ready.emit(text)
                
                # Set to ready
                QTimer.singleShot(100, lambda: self.set_state(AppState.READY))
                
            except Exception as e:
                error_msg = f"Transcription failed: {str(e)}"
                print(f"[ERROR] {error_msg}")
                traceback.print_exc()
                
                # Clean up on error
                if self.current_backend:
                    try:
                        self.current_backend.cleanup()
                    except:
                        pass
                    self.current_backend = None
                
                self.signals.error_occurred.emit(error_msg)
            finally:
                self.operation_in_progress = False
        
        # Run in thread to avoid blocking GUI
        threading.Thread(target=transcribe_worker, daemon=True).start()
    
    def _update_status_display(self, status_text: str, color: str):
        """Update status label from signal (isolated from core logic)"""
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(
            f"color: {color}; padding: 15px; "
            f"background-color: #0f0f0f; border-radius: 5px; border: 2px solid {color};"
        )
    
    def _display_transcription(self, text: str):
        """Display transcription result"""
        print(f"[RESULT] Transcription: {text}")
        
        # Append to output with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.output_text.append(f"\n--- {timestamp} ---\n")
        self.output_text.append(text)
        self.output_text.append("\n")
    
    def _display_error(self, error_msg: str):
        """Display error message"""
        self.set_state(AppState.ERROR)
        
        QMessageBox.critical(
            self,
            "❌ Error",
            error_msg,
            QMessageBox.StandardButton.Ok
        )
    
    def check_backend_availability(self):
        """Check which backends are available and display status"""
        print("[CHECK] Checking backend availability...")
        
        status_lines = []
        
        # Check Local
        has_deps, missing = SpeechBackend.check_dependencies(['speech_recognition', 'pyaudio'])
        if has_deps:
            status_lines.append("✅ Local Offline: Available")
        else:
            status_lines.append(f"❌ Local Offline: Missing {', '.join(missing)}")
        
        # Check Google Cloud
        has_deps, missing = SpeechBackend.check_dependencies(['google.cloud.speech', 'pyaudio'])
        has_creds = bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
        local_creds = (Path(__file__).parent / 'scribe-486923-ffbe3bcd944a.json').exists()
        if has_deps and (has_creds or local_creds):
            creds_source = "env var" if has_creds else "local JSON"
            status_lines.append(f"✅ Google Cloud: Available (creds: {creds_source})")
        elif not has_deps:
            status_lines.append(f"❌ Google Cloud: Missing {', '.join(missing)}")
        elif not has_creds and not local_creds:
            status_lines.append("⚠️ Google Cloud: Missing credentials (no env var or local JSON)")
        
        # Check Whisper
        has_deps, missing = SpeechBackend.check_dependencies(['whisper', 'pyaudio', 'numpy'])
        if has_deps:
            status_lines.append("✅ OpenAI Whisper: Available")
        else:
            missing_display = []
            if 'whisper' in missing:
                missing_display.append('openai-whisper')
            if 'pyaudio' in missing:
                missing_display.append('pyaudio')
            if 'numpy' in missing:
                missing_display.append('numpy')
            status_lines.append(f"❌ OpenAI Whisper: Missing {', '.join(missing_display)}")
        
        status_text = "\n".join(status_lines)
        self.backend_status_label.setText(status_text)
        print(f"[CHECK] Results:\n{status_text}")
        
        # Show in message box too
        QMessageBox.information(
            self,
            "🔍 Backend Availability",
            status_text,
            QMessageBox.StandardButton.Ok
        )
    
    # === CLIPBOARD FEATURES (ISOLATED FROM DICTATION LOGIC) ===
    
    def copy_output_to_clipboard(self):
        """Copy transcription output to clipboard"""
        text = self.output_text.toPlainText()
        if text.strip():
            self.clipboard_manager.copy_to_clipboard(text)
            print(f"[CLIPBOARD] Copied output to clipboard ({len(text)} chars)")
    
    def _on_clipboard_updated(self, text: str):
        """Handle clipboard changes (isolated callback)"""
        self.update_clipboard_display()
    
    def update_clipboard_display(self):
        """Update clipboard history and favorites lists"""
        # Update history
        limit = 20 if self.show_extended_history else 10
        history = self.clipboard_manager.get_history(limit)
        
        self.history_list.clear()
        for item in history:
            preview = item[:100] + "..." if len(item) > 100 else item
            preview = preview.replace('\n', ' ')
            list_item = QListWidgetItem(preview)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.history_list.addItem(list_item)
        
        # Update favorites
        favorites = self.clipboard_manager.get_favorites()
        
        self.favorites_list.clear()
        for item in favorites:
            preview = item[:100] + "..." if len(item) > 100 else item
            preview = preview.replace('\n', ' ')
            list_item = QListWidgetItem(f"⭐ {preview}")
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.favorites_list.addItem(list_item)
    
    def toggle_history_view(self, state):
        """Toggle between 10 and 20 history items"""
        self.show_extended_history = (state == Qt.CheckState.Checked.value)
        self.update_clipboard_display()
    
    def copy_history_item(self, item: QListWidgetItem):
        """Copy history item on double-click"""
        text = item.data(Qt.ItemDataRole.UserRole)
        if text:
            self.clipboard_manager.copy_to_clipboard(text)
            print(f"[CLIPBOARD] Copied history item to clipboard")
    
    def copy_selected_history(self):
        """Copy selected history item"""
        current_item = self.history_list.currentItem()
        if current_item:
            self.copy_history_item(current_item)
    
    def favorite_selected_history(self):
        """Add selected history item to favorites"""
        current_item = self.history_list.currentItem()
        if current_item:
            text = current_item.data(Qt.ItemDataRole.UserRole)
            if text:
                self.clipboard_manager.add_to_favorites(text)
                self.update_clipboard_display()
                print(f"[CLIPBOARD] Added to favorites")
    
    def copy_favorite_item(self, item: QListWidgetItem):
        """Copy favorite item on double-click"""
        text = item.data(Qt.ItemDataRole.UserRole)
        if text:
            self.clipboard_manager.copy_to_clipboard(text)
            print(f"[CLIPBOARD] Copied favorite to clipboard")
    
    def copy_selected_favorite(self):
        """Copy selected favorite"""
        current_item = self.favorites_list.currentItem()
        if current_item:
            self.copy_favorite_item(current_item)
    
    def remove_selected_favorite(self):
        """Remove selected favorite"""
        current_item = self.favorites_list.currentItem()
        if current_item:
            text = current_item.data(Qt.ItemDataRole.UserRole)
            if text:
                self.clipboard_manager.remove_from_favorites(text)
                self.update_clipboard_display()
                print(f"[CLIPBOARD] Removed from favorites")
    
    def clear_clipboard_history(self):
        """Clear clipboard history"""
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Clear all clipboard history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.clipboard_manager.clear_history()
            self.update_clipboard_display()
            print(f"[CLIPBOARD] History cleared")
    
    # === SHUTDOWN (DETERMINISTIC AND BLOCKING) ===
    
    def shutdown_application(self):
        """Deterministic shutdown with cleanup blocking"""
        print("[SHUTDOWN] User initiated shutdown")
        
        reply = QMessageBox.question(
            self,
            "🚪 Quit",
            "Shutdown application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._perform_shutdown()
            QApplication.quit()
    
    def _perform_shutdown(self):
        """Perform deterministic cleanup (blocking until complete)"""
        print("[SHUTDOWN] Forcing STOP on all backends...")
        
        # Force STOP - terminate all listening threads
        if self.current_backend:
            try:
                self.current_backend.stop_listening()
                self.current_backend.cleanup()
                print("[SHUTDOWN] Active backend cleaned up")
            except Exception as e:
                print(f"[SHUTDOWN] Error cleaning active backend: {e}")
            finally:
                self.current_backend = None
        
        # Clean up all initialized backends
        for backend_type, backend in self.backends.items():
            try:
                backend.cleanup()
                print(f"[SHUTDOWN] {backend_type.value} cleaned up")
            except Exception as e:
                print(f"[SHUTDOWN] Error cleaning {backend_type.value}: {e}")
        
        self.backends.clear()
        print("[SHUTDOWN] All backends terminated")
    
    def closeEvent(self, event):
        """Clean shutdown on window close (deterministic)"""
        print("[GUI] Window close event received")
        self._perform_shutdown()
        print("[GUI] Shutdown complete")
        event.accept()


def main():
    """Entry point"""
    print("=" * 60)
    print("Personal Dictation Tool")
    print("Prioritizing: Deterministic behavior, clean shutdowns, explicit control")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    window = DictationGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
