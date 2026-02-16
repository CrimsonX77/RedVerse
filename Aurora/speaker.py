import sys
import os
import json
import asyncio
import threading
import tempfile
import wave
import pyaudio
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QTextEdit, QSlider, QLabel, 
                             QComboBox, QFileDialog, QMessageBox, QProgressBar,
                             QSplitter, QGroupBox, QSpinBox, QTabWidget, QLineEdit,
                             QCheckBox, QTextBrowser, QSpacerItem, QSizePolicy,
                             QScrollArea, QFrame, QDoubleSpinBox, QInputDialog)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QIcon
import speech_recognition as sr

# Handle docx import with fallback
try:
    from docx import Document
    DOCX_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    print(f"Warning: python-docx not available: {e}")
    DOCX_AVAILABLE = False
    Document = None

import time
import pygame
import edge_tts
import subprocess
import numpy as np
import soundfile as sf
import librosa
from scipy import signal

class EdgeTTSThread(QThread):
    """Thread for Edge-TTS text-to-speech"""
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, text, voice, rate, volume, pitch=0, chunk_size=200, effects=None):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
        self.chunk_size = chunk_size
        self.effects = effects or {}
        self.is_running = True
        self.audio_files = []
        
    def run(self):
        try:
            # Split text into manageable chunks
            chunks = self.split_text_into_chunks(self.text, self.chunk_size)
            total_chunks = len(chunks)
            
            print(f"🎵 Starting TTS generation: {total_chunks} chunks")
            
            # Initialize pygame mixer for audio playback with higher quality settings
            try:
                pygame.mixer.quit()  # Ensure previous mixer is closed
                # Use higher quality audio settings
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
                print("✅ Pygame mixer initialized (44.1kHz)")
            except Exception as e:
                print(f"⚠️ High quality mixer init failed: {e}")
                # Fallback to safer settings if there's an error
                try:
                    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=2048)
                    print("✅ Pygame mixer initialized (22.05kHz)")
                except Exception as e2:
                    print(f"⚠️ Standard mixer init failed: {e2}")
                    # Last resort fallback
                    pygame.mixer.init()
                    print("✅ Pygame mixer initialized (default settings)")
            
            for i, chunk in enumerate(chunks):
                if not self.is_running:
                    break
                    
                if chunk.strip():
                    # Generate audio for this chunk
                    audio_file = self.generate_audio_chunk(chunk, i)
                    if audio_file and self.is_running:  # Check again after generation
                        self.audio_files.append(audio_file)
                        # Play the audio chunk
                        self.play_audio_file(audio_file)
                    
                # Update progress
                progress_percent = int((i + 1) / total_chunks * 100)
                self.progress.emit(progress_percent)
                
                # Check if we should stop after each chunk
                if not self.is_running:
                    break
                
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Stop any playing audio
            try:
                pygame.mixer.music.stop()
            except:
                pass
                
            # Cleanup temp files
            for file in self.audio_files:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except:
                    pass
    
    def split_text_into_chunks(self, text, max_length):
        """Split text into chunks for processing"""
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
    
    def generate_audio_chunk(self, text, chunk_index):
        """Generate audio for a text chunk using Edge-TTS"""
        try:
            print(f"🎙️ Generating chunk {chunk_index}: {text[:50]}...")
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_file.close()
            
            # Adjust rate for Edge-TTS (it uses percentage format)
            rate_str = f"{self.rate-100:+d}%"  # Convert 50-200 to -50% to +100%
            
            # Run Edge-TTS in asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def generate():
                communicate = edge_tts.Communicate(text, self.voice, rate=rate_str)
                await communicate.save(temp_file.name)
            
            loop.run_until_complete(generate())
            loop.close()
            
            print(f"✅ Audio file generated: {temp_file.name} ({os.path.getsize(temp_file.name)} bytes)")
            
            # Check if we need to apply effects
            apply_effects = False
            
            # Check pitch first
            if self.pitch != 0:
                apply_effects = True
                
            # Check if any other effect is active with a significant value
            if not apply_effects and self.effects:
                for effect_name, effect_value in self.effects.items():
                    # Skip checking eq settings if they're all near zero
                    if effect_name.startswith('eq_') and abs(effect_value) < 0.5:
                        continue
                    # For other effects, consider any non-zero value
                    elif effect_value != 0:
                        if isinstance(effect_value, (int, float)) and abs(effect_value) > 0.01:
                            apply_effects = True
                            break
            
            # Only apply effects if needed
            if apply_effects:
                processed_file = self.apply_audio_effects(temp_file.name)
                # Clean up original file
                try:
                    os.remove(temp_file.name)
                except:
                    pass
                return processed_file
            
            return temp_file.name
                
        except Exception as e:
            self.error.emit(f"Error generating audio: {str(e)}")
            return None
    
    def apply_audio_effects(self, input_file):
        """Apply comprehensive audio effects to the generated speech"""
        try:
            # Load audio
            audio, sr = librosa.load(input_file, sr=None)
            
            # Track if any effects are actually applied
            effects_applied = False
            
            # Apply pitch shifting
            if self.pitch != 0:
                audio = librosa.effects.pitch_shift(audio, sr=sr, n_steps=self.pitch)
                effects_applied = True
            
            # Apply formant shifting (simulate different voice characteristics)
            if 'formant' in self.effects and self.effects['formant'] != 0:
                audio = self.shift_formants(audio, sr, self.effects['formant'])
                effects_applied = True
            
            # Apply tremolo (amplitude modulation)
            if 'tremolo' in self.effects and self.effects['tremolo'] > 0.01:  # Using threshold to avoid near-zero values
                audio = self.add_tremolo(audio, sr, self.effects['tremolo'])
                effects_applied = True
            
            # Apply vibrato (frequency modulation)
            if 'vibrato' in self.effects and self.effects['vibrato'] > 0.01:
                audio = self.add_vibrato(audio, sr, self.effects['vibrato'])
                effects_applied = True
            
            # Apply reverb effect
            if 'reverb' in self.effects and self.effects['reverb'] > 0.01:
                audio = self.add_reverb(audio, sr, self.effects['reverb'])
                effects_applied = True
            
            # Apply echo effect
            if 'echo' in self.effects and self.effects['echo'] > 0.01:
                audio = self.add_echo(audio, sr, self.effects['echo'])
                effects_applied = True
            
            # Apply chorus effect
            if 'chorus' in self.effects and self.effects['chorus'] > 0.01:
                audio = self.add_chorus(audio, sr, self.effects['chorus'])
                effects_applied = True
            
            # Apply flanger effect
            if 'flanger' in self.effects and self.effects['flanger'] > 0.01:
                audio = self.add_flanger(audio, sr, self.effects['flanger'])
                effects_applied = True
            
            # Apply distortion
            if 'distortion' in self.effects and self.effects['distortion'] > 0.01:
                audio = self.add_distortion(audio, self.effects['distortion'])
                effects_applied = True
            
            # Apply robot voice effect
            if 'robot' in self.effects and self.effects['robot'] > 0.01:
                audio = self.add_robot_effect(audio, sr, self.effects['robot'])
                effects_applied = True
            
            # Apply noise gate
            if 'noise_gate' in self.effects and self.effects['noise_gate'] > 0:
                audio = self.apply_noise_gate(audio, self.effects['noise_gate'])
                effects_applied = True
            
            # Apply EQ
            if any(abs(self.effects.get(k, 0)) > 0.5 for k in ['eq_low', 'eq_mid', 'eq_high']):
                audio = self.apply_eq(audio, sr, self.effects)
                effects_applied = True
            
            # Apply compression
            if 'compression' in self.effects and self.effects['compression'] > 0.01:
                audio = self.apply_compression(audio, self.effects['compression'])
                effects_applied = True
            
            # If no effects were applied, just return the original file
            if not effects_applied:
                return input_file
            
            # Normalize to prevent clipping
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio)) * 0.95
            
            # Create new temporary file for processed audio
            output_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_file.close()
            
            # Save processed audio
            sf.write(output_file.name, audio, sr)
            
            return output_file.name
            
        except Exception as e:
            self.error.emit(f"Error applying effects: {str(e)}")
            return input_file
    
    def shift_formants(self, audio, sr, factor):
        """Shift formants by modifying spectral envelope"""
        try:
            # Use STFT for frequency domain manipulation
            stft = librosa.stft(audio, n_fft=2048, hop_length=512)
            magnitude = np.abs(stft)
            phase = np.angle(stft)
            
            # Simple formant shifting by frequency scaling
            freq_bins, time_bins = magnitude.shape
            shifted_magnitude = np.zeros_like(magnitude)
            
            shift_factor = 1.0 + (factor * 0.05)  # Scale factor
            
            for t in range(time_bins):
                for f in range(freq_bins):
                    shifted_f = int(f * shift_factor)
                    if 0 <= shifted_f < freq_bins:
                        shifted_magnitude[f, t] = magnitude[shifted_f, t]
            
            # Reconstruct audio
            stft_processed = shifted_magnitude * np.exp(1j * phase)
            audio_processed = librosa.istft(stft_processed)
            
            return audio_processed
        except:
            return audio
    
    def add_tremolo(self, audio, sr, amount):
        """Add tremolo (amplitude modulation) effect"""
        tremolo_freq = 5.0  # Hz
        tremolo_depth = amount / 100.0
        t = np.arange(len(audio)) / sr
        tremolo = 1 + tremolo_depth * np.sin(2 * np.pi * tremolo_freq * t)
        return audio * tremolo
    
    def add_vibrato(self, audio, sr, amount):
        """Add vibrato (frequency modulation) effect"""
        vibrato_freq = 6.0  # Hz
        vibrato_depth = amount / 100.0 * 2.0  # semitones
        t = np.arange(len(audio)) / sr
        
        # Create time-varying pitch shift
        vibrato_shift = vibrato_depth * np.sin(2 * np.pi * vibrato_freq * t)
        
        # Simple implementation using interpolation
        indices = np.arange(len(audio)) + vibrato_shift * 10
        indices = np.clip(indices, 0, len(audio) - 1)
        
        return np.interp(np.arange(len(audio)), indices, audio)
    
    def add_reverb(self, audio, sr, amount):
        """Add reverb effect"""
        # Create impulse response for reverb
        reverb_length = int(sr * 0.5)  # 0.5 second reverb
        impulse = np.random.normal(0, 1, reverb_length)
        impulse *= np.exp(-np.arange(reverb_length) / (sr * 0.1))  # Exponential decay
        
        # Convolve with impulse response
        reverb_audio = signal.convolve(audio, impulse, mode='same')
        
        # Mix with original
        return audio * (1 - amount) + reverb_audio * amount * 0.3
    
    def add_echo(self, audio, sr, amount):
        """Add echo effect"""
        delay_samples = int(sr * 0.2)  # 200ms delay
        if delay_samples < len(audio):
            echo_audio = np.copy(audio)
            echo_audio[delay_samples:] += audio[:-delay_samples] * amount * 0.5
            return echo_audio
        return audio
    
    def add_chorus(self, audio, sr, amount):
        """Add chorus effect"""
        delays = [int(sr * d) for d in [0.01, 0.02, 0.03]]  # Multiple short delays
        chorus_audio = np.copy(audio)
        
        for delay in delays:
            if delay < len(audio):
                delayed = np.zeros_like(audio)
                delayed[delay:] = audio[:-delay]
                chorus_audio += delayed * amount * 0.3
        
        return chorus_audio
    
    def add_flanger(self, audio, sr, amount):
        """Add flanger effect"""
        delay_samples = int(sr * 0.005)  # 5ms base delay
        lfo_freq = 0.5  # Low frequency oscillator
        t = np.arange(len(audio)) / sr
        
        # Variable delay line
        delay_variation = delay_samples * (1 + amount/100.0 * np.sin(2 * np.pi * lfo_freq * t))
        
        flanger_audio = np.copy(audio)
        for i in range(len(audio)):
            delay = int(delay_variation[i])
            if i >= delay:
                flanger_audio[i] += audio[i - delay] * amount * 0.01
        
        return flanger_audio
    
    def add_distortion(self, audio, amount):
        """Add distortion effect"""
        # Only apply distortion if amount is significant
        if amount < 0.01:
            return audio
            
        # Use a more controlled distortion algorithm
        gain = 1 + amount * 0.03  # Reduced multiplier to minimize fuzzing
        distorted = np.tanh(audio * gain) / gain
        
        # Mix with a heavier bias toward the clean signal
        mix_ratio = amount/100.0
        if mix_ratio > 0.5:  # Cap the mix ratio to avoid too much distortion
            mix_ratio = 0.5
            
        return audio * (1 - mix_ratio) + distorted * mix_ratio
    
    def add_robot_effect(self, audio, sr, amount):
        """Add robot/vocoder effect"""
        # Simple ring modulation for robot effect
        carrier_freq = 30.0  # Hz
        t = np.arange(len(audio)) / sr
        carrier = np.sin(2 * np.pi * carrier_freq * t)
        
        robot_audio = audio * (1 + amount/100.0 * carrier)
        return robot_audio
    
    def apply_noise_gate(self, audio, threshold):
        """Apply noise gate to reduce background noise"""
        threshold_linear = threshold / 100.0 * 0.1
        gate = np.where(np.abs(audio) > threshold_linear, 1.0, 0.1)
        return audio * gate
    
    def apply_eq(self, audio, sr, settings):
        """Apply 3-band equalizer"""
        # Define frequency bands
        low_freq = 300
        high_freq = 3000
        
        # Get EQ gains (default to 0 if not specified)
        low_gain = settings.get('eq_low', 0) / 10.0
        mid_gain = settings.get('eq_mid', 0) / 10.0
        high_gain = settings.get('eq_high', 0) / 10.0
        
        # Apply simple EQ using frequency domain filtering
        stft = librosa.stft(audio)
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Create gain curve
        gains = np.ones(len(freqs))
        
        # Low frequencies
        low_mask = freqs < low_freq
        gains[low_mask] *= (1 + low_gain)
        
        # High frequencies  
        high_mask = freqs > high_freq
        gains[high_mask] *= (1 + high_gain)
        
        # Mid frequencies
        mid_mask = (freqs >= low_freq) & (freqs <= high_freq)
        gains[mid_mask] *= (1 + mid_gain)
        
        # Apply gains
        stft_processed = stft * gains[:, np.newaxis]
        audio_eq = librosa.istft(stft_processed)
        
        return audio_eq
    
    def apply_compression(self, audio, amount):
        """Apply dynamic range compression"""
        threshold = 0.5
        ratio = 1 + amount * 0.01
        
        # Simple compression
        compressed = np.copy(audio)
        over_threshold = np.abs(audio) > threshold
        compressed[over_threshold] = np.sign(audio[over_threshold]) * (
            threshold + (np.abs(audio[over_threshold]) - threshold) / ratio
        )
        
        return compressed

    def apply_pitch_shift(self, input_file):
        """Apply pitch shifting to audio file (legacy method)"""
        try:
            # Load audio
            audio, sr = librosa.load(input_file, sr=None)
            
            # Apply pitch shifting
            audio_shifted = librosa.effects.pitch_shift(audio, sr=sr, n_steps=self.pitch)
            
            # Create new temporary file for processed audio
            output_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_file.close()
            
            # Save processed audio
            sf.write(output_file.name, audio_shifted, sr)
            
            return output_file.name
            
        except Exception as e:
            self.error.emit(f"Error applying pitch shift: {str(e)}")
            return input_file
    
    def play_audio_file(self, file_path):
        """Play audio file with volume control"""
        try:
            # Verify file exists
            if not os.path.exists(file_path):
                self.error.emit(f"Audio file not found: {file_path}")
                return
            
            print(f"🔊 Playing audio: {file_path}")
            
            # Load and play audio
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.set_volume(self.volume / 100.0)
            pygame.mixer.music.play()
            
            print(f"🎵 Playback started (volume: {self.volume}%)")
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy() and self.is_running:
                pygame.time.wait(100)
            
            print("✅ Playback finished")
                
        except Exception as e:
            print(f"❌ Playback error: {e}")
            self.error.emit(f"Error playing audio: {str(e)}")
    
    def stop(self):
        """Stop audio generation and playback"""
        self.is_running = False
        try:
            # Stop any playing audio
            pygame.mixer.music.stop()
            # Force unload to release any file handles
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Stop cleanup error: {e}")

class SpeechRecognitionThread(QThread):
    """Thread for speech recognition"""
    recognized = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, language='en-US'):
        super().__init__()
        self.language = language
        self.is_listening = True
        
    def run(self):
        try:
            r = sr.Recognizer()
            mic = sr.Microphone()
            
            with mic as source:
                r.adjust_for_ambient_noise(source)
            
            while self.is_listening:
                try:
                    with mic as source:
                        audio = r.listen(source, timeout=1, phrase_time_limit=5)
                    
                    text = r.recognize_google(audio, language=self.language)
                    self.recognized.emit(text)
                    
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    self.error.emit(f"Recognition error: {e}")
                    break
                    
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        self.is_listening = False

class EdgeTTSApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tts_thread = None
        self.sr_thread = None
        self.available_voices = []
        self.load_voices()
        self.init_ui()
        
    def load_voices(self):
        """Load available Edge-TTS voices"""
        try:
            # Run async function to get voices
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            voices = loop.run_until_complete(edge_tts.list_voices())
            loop.close()
            
            # Create readable voice list - using ShortName instead of FriendlyName
            self.available_voices = []
            for voice in voices:
                name = voice['ShortName']
                self.available_voices.append(name)
                
            # Sort alphabetically
            self.available_voices.sort()
            
        except Exception as e:
            print(f"Error loading voices: {e}")
            # Fallback to common voices
            self.available_voices = [
                "en-US-AriaNeural",
                "en-US-JennyNeural",
                "en-US-GuyNeural",
                "en-GB-SoniaNeural"
            ]
        
    def init_ui(self):
        self.setWindowTitle("🎙️ VoiceForge TTS Studio")
        self.setWindowIcon(QIcon('icon.png'))  # Will use system icon if file not found
        self.setGeometry(100, 100, 1200, 800)
        
        # Apply dark theme with crimson, gold and silver accents
        self.setStyleSheet("""
            /* Main application background and text */
            QMainWindow, QWidget {
            background-color: #121212;
            color: #E0E0E0;
            }
            
            /* Tab Widget styling */
            QTabWidget::pane {
            border: 1px solid #3A3A3A;
            background-color: #1E1E1E;
            }
            
            QTabBar::tab {
            background-color: #2D2D2D;
            color: #BBBBBB;
            padding: 8px 12px;
            border: 1px solid #3A3A3A;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            min-width: 120px;
            font-weight: bold;
            transition: all 0.2s ease-in-out; /* Add smooth transition */
            }
            
            QTabBar::tab:selected {
            background-color: #CC1155;  /* Crimson when selected */
            color: #FFFFFF;
            border-bottom: none;
            }
            
            QTabBar::tab:hover:!selected {
            background-color: #3D3D3D;
            border-bottom: 2px solid #CC1155;
            padding-bottom: 10px; /* Slight enlargement effect */
            color: #D4AF37; /* Gold text on hover */
            }
            
            /* Group Boxes */
            QGroupBox {
            border: 1px solid #3A3A3A;
            border-radius: 4px;
            margin-top: 1em;
            padding-top: 8px;
            font-weight: bold;
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                          stop:0 #252525, stop:1 #1E1E1E);
            }
            
            QGroupBox::title {
            color: #D4AF37;  /* Gold for titles */
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 2px 8px;
            left: 10px;
            background-color: #CC1155;
            border-radius: 3px;
            font-weight: bold;
            }
            
            /* Sliders */
            QSlider::groove:horizontal {
            border: 1px solid #444444;
            height: 8px;
            background: #2A2A2A;
            margin: 2px 0;
            border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
            background: #C0C0C0;  /* Silver handles */
            border: 1px solid #777777;
            width: 14px;
            margin: -4px 0;
            border-radius: 7px;
            }
            
            QSlider::handle:horizontal:hover {
            background: #D4AF37;  /* Gold on hover */
            }
            
            /* Special styling for pitch slider - more prominent */
            QSlider#pitchSlider::groove:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #AA1144, stop:0.5 #2A2A2A, stop:1 #AA1144);
            height: 10px;
            }
            
            QSlider#pitchSlider::handle:horizontal {
            background: #D4AF37;  /* Gold handle */
            border: 1px solid #AA1144;
            width: 18px;
            margin: -5px 0;
            }
            
            /* ComboBox */
            QComboBox {
            background-color: #2A2A2A;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 5px;
            color: #E0E0E0;
            selection-background-color: #CC1155;  /* Crimson selection */
            }
            
            QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 15px;
            border-left: 1px solid #555555;
            }
            
            QComboBox QAbstractItemView {
            background-color: #2A2A2A;
            border: 1px solid #555555;
            selection-background-color: #CC1155;
            selection-color: #FFFFFF;
            }
            
            /* Push buttons */
            QPushButton {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 12px;
            min-width: 80px;
            }
            
            QPushButton:hover {
            background-color: #3A3A3A;
            border: 1px solid #D4AF37;  /* Gold border on hover */
            color: #D4AF37;  /* Gold text on hover */
            }
            
            QPushButton:pressed {
            background-color: #CC1155;  /* Crimson when pressed */
            color: #FFFFFF;
            border: 1px solid #D4AF37;  /* Gold border when pressed */
            }
            
            QPushButton:checked {
            background-color: #CC1155;  /* Crimson when toggled */
            color: #FFFFFF;
            border: 2px solid #FFFFFF;  /* High contrast border */
            font-weight: bold;
            }
            
            QPushButton:disabled {
            background-color: #1A1A1A;
            color: #555555;
            border: 1px solid #333333;
            }
            
            /* Play/Test buttons - special styling */
            QPushButton[text*="▶"], QPushButton[text*="🔊"] {
            background-color: #2A2A2A;
            color: #D4AF37;  /* Gold text */
            font-weight: bold;
            border: 1px solid #555555;
            }
            
            QPushButton[text*="▶"]:hover, QPushButton[text*="🔊"]:hover {
            background-color: #3A3A3A;
            border: 1px solid #CC1155;  /* Crimson border */
            }
            
            QPushButton[text*="▶"]:pressed, QPushButton[text*="🔊"]:pressed {
            background-color: #CC1155;
            color: #FFFFFF;
            }
            
            /* Stop button - special styling */
            QPushButton[text*="⏹"] {
            background-color: #2A2A2A;
            color: #C0C0C0;  /* Silver text */
            border: 1px solid #555555;
            }
            
            QPushButton[text*="⏹"]:hover {
            background-color: #3A3A3A;
            border: 1px solid #CC1155;
            }
            
            QPushButton[text*="⏹"]:pressed {
            background-color: #CC1155;
            color: #FFFFFF;
            }
            
            /* Preset-related buttons */
            QPushButton[text*="Preset"], QPushButton[text*="Reset"] {
            background-color: #2A2A2A;
            color: #D4AF37;  /* Gold text */
            border: 1px solid #555555;
            }
            
            /* Text Edit */
            QTextEdit, QTextBrowser {
            background-color: #1A1A1A;
            color: #E0E0E0;
            border: 1px solid #3A3A3A;
            border-radius: 3px;
            selection-background-color: #CC1155;
            selection-color: #FFFFFF;
            padding: 5px;
            }
            
            /* Spinbox and LineEdit */
            QSpinBox, QDoubleSpinBox, QLineEdit {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 3px;
            selection-background-color: #CC1155;
            selection-color: #FFFFFF;
            }
            
            /* Labels */
            QLabel {
            color: #E0E0E0;
            }
            
            /* Special labels (slider values) */
            QLabel[text*="dB"], QLabel[text*="%"], QLabel[text*="semitones"], 
            QLabel[text*="neutral"], QLabel[text*="brighter"], QLabel[text*="darker"] {
            color: #C0C0C0;  /* Silver for values */
            min-width: 80px;
            font-weight: bold;
            }
            
            /* Progress bar */
            QProgressBar {
            border: 1px solid #3A3A3A;
            border-radius: 3px;
            background-color: #1A1A1A;
            text-align: center;
            color: #FFFFFF;
            font-weight: bold;
            height: 20px;
            }
            
            QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #CC1155, stop:0.5 #D4AF37, stop:1 #CC1155);
            width: 20px;
            margin: 0.5px;
            border-radius: 2px;
            }
            
            /* Scroll area and scrollbars */
            QScrollArea {
            border: none;
            }
            
            QScrollBar:vertical {
            border: none;
            background-color: #2A2A2A;
            width: 12px;
            margin: 12px 0 12px 0;
            }
            
            QScrollBar::handle:vertical {
            background-color: #555555;
            min-height: 20px;
            border-radius: 4px;
            }
            
            QScrollBar::handle:vertical:hover {
            background-color: #CC1155;  /* Crimson on hover */
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
            height: 12px;
            }
            
            QScrollBar:horizontal {
            border: none;
            background-color: #2A2A2A;
            height: 12px;
            margin: 0 12px 0 12px;
            }
            
            QScrollBar::handle:horizontal {
            background-color: #555555;
            min-width: 20px;
            border-radius: 4px;
            }
            
            QScrollBar::handle:horizontal:hover {
            background-color: #CC1155;  /* Crimson on hover */
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
            width: 12px;
            }
            
            /* Checkbox */
            QCheckBox {
            spacing: 5px;
            }
            
            QCheckBox::indicator {
            width: 15px;
            height: 15px;
            }
            
            QCheckBox::indicator:unchecked {
            border: 1px solid #555555;
            background-color: #2A2A2A;
            border-radius: 3px;
            }
            
            QCheckBox::indicator:checked {
            border: 1px solid #D4AF37;  /* Gold border */
            background-color: #CC1155;  /* Crimson fill */
            border-radius: 3px;
            }
            
            /* Frame - divider line - REMOVED QFrame selectors that use frameShape */
            /* These selectors don't work reliably in stylesheets */
        """)
        
        # Set object names for special styling
        self.pitch_slider = None  # We'll set this later in setup_tts_tab
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create a title label for the application
        main_layout = QVBoxLayout()
        
        # Add a stylish title
        title_layout = QHBoxLayout()
        title_layout.addStretch()
        
        title_label = QLabel("🎙️ VoiceForge TTS Studio")
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #FFFFFF;
            padding: 5px 15px;
            border-radius: 5px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #CC1155, stop:0.5 #D4AF37, stop:1 #CC1155);
        """)
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Professional Voice Synthesis")
        subtitle_label.setStyleSheet("""
            font-size: 14px;
            font-style: italic;
            color: #C0C0C0;
            margin-left: 10px;
        """)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()
        
        main_layout.addLayout(title_layout)
        
        # Add a separator below the title
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #CC1155; min-height: 2px;")
        main_layout.addWidget(separator)
        
        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)  # More modern appearance
        
        # TTS Tab
        tts_tab = QWidget()
        self.setup_tts_tab(tts_tab)
        tab_widget.addTab(tts_tab, "🔊 Edge TTS")
        
        # Speech Recognition Tab
        sr_tab = QWidget()
        self.setup_sr_tab(sr_tab)
        tab_widget.addTab(sr_tab, "🎤 Speech Recognition")
        
        # Voice Info Tab
        info_tab = QWidget()
        self.setup_info_tab(info_tab)
        tab_widget.addTab(info_tab, "ℹ️ Voice Info")
        
        # Add a status bar
        self.statusBar().showMessage("Ready - VoiceForge TTS Studio v1.0")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #252525;
                color: #B0C4DE;
                border-top: 1px solid #3A3A3A;
                padding: 3px;
            }
        """)
        
        # Add the tab widget to the main layout
        main_layout.addWidget(tab_widget)
        central_widget.setLayout(main_layout)
        
    def setup_tts_tab(self, tab):
        """Setup Enhanced Edge-TTS tab with comprehensive voice modulation"""
        main_layout = QVBoxLayout()
        
        # Create scroll area for all controls
        scroll = QScrollArea()
        scroll_widget = QWidget()
        layout = QVBoxLayout()
        
        # File controls
        file_group = QGroupBox("File Controls")
        file_layout = QHBoxLayout()
        
        self.load_button = QPushButton("📂 Load Word Document")
        self.load_button.setObjectName("fileButton")
        self.load_button.setStyleSheet("""
            QPushButton#fileButton {
                background-color: #2D2D2D;
                color: #B0C4DE;  /* Light steel blue */
                border: 1px solid #4682B4;  /* Steel blue */
            }
            QPushButton#fileButton:hover {
                background-color: #3D3D3D;
                border: 1px solid #1E90FF;  /* Dodger blue */
                color: #ADD8E6;  /* Light blue */
            }
        """)
        self.load_button.clicked.connect(self.load_document)
        file_layout.addWidget(self.load_button)
        
        self.save_button = QPushButton("💾 Save Text")
        self.save_button.setObjectName("fileButton")  # Reuse the same styling
        self.save_button.clicked.connect(self.save_text)
        file_layout.addWidget(self.save_button)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Playback controls - MOVED TO TOP
        playback_group = QGroupBox("Playback Controls")
        playback_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Generate & Play")
        self.play_button.clicked.connect(self.play_text)
        playback_layout.addWidget(self.play_button)
        
        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_speech)
        self.stop_button.setEnabled(False)
        playback_layout.addWidget(self.stop_button)
        
        self.test_button = QPushButton("🔊 Test Voice")
        self.test_button.clicked.connect(self.test_voice)
        playback_layout.addWidget(self.test_button)
        
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("mainProgressBar")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% Complete")
        layout.addWidget(self.progress_bar)
        
        # Text area
        text_group = QGroupBox("Text Content")
        text_layout = QVBoxLayout()
        
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("mainTextEdit")
        self.text_edit.setStyleSheet("""
            QTextEdit#mainTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #CC1155;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #CC1155;
                selection-color: #FFFFFF;
            }
            QTextEdit#mainTextEdit:focus {
                border: 2px solid #D4AF37;
            }
        """)
        self.text_edit.setPlaceholderText("Enter your text here or load a Word document...")
        self.text_edit.setFont(QFont("Arial", 12))
        self.text_edit.setMaximumHeight(150)
        text_layout.addWidget(self.text_edit)
        
        text_group.setLayout(text_layout)
        layout.addWidget(text_group)
        
        # Voice Model Selection
        model_group = QGroupBox("Voice Selection")
        model_layout = QVBoxLayout()
        
        # Voice selection
        voice_select_layout = QHBoxLayout()
        voice_select_layout.addWidget(QLabel("Voice:"))
        self.voice_combo = QComboBox()
        self.voice_combo.setObjectName("voiceCombo")  # Special ID for custom styling
        self.voice_combo.setStyleSheet("""
            QComboBox#voiceCombo {
                background-color: #252525;
                border: 1px solid #CC1155;
                color: #FFFFFF;
                padding: 5px;
                font-weight: bold;
            }
            QComboBox#voiceCombo::drop-down {
                border-left: 1px solid #CC1155;
            }
        """)
        for voice_name in self.available_voices:
            self.voice_combo.addItem(voice_name, voice_name)
        # Set default to Sonia (British UK voice)
        for i, voice_name in enumerate(self.available_voices):
            if "SoniaNeural" in voice_name:
                self.voice_combo.setCurrentIndex(i)
                break
        voice_select_layout.addWidget(self.voice_combo)
        model_layout.addLayout(voice_select_layout)
        
        # Chunk size for processing
        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("Chunk Size (chars):"))
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(50, 500)
        self.chunk_size_spin.setValue(200)
        chunk_layout.addWidget(self.chunk_size_spin)
        chunk_layout.addWidget(QLabel("Smaller = more responsive, Larger = more efficient"))
        model_layout.addLayout(chunk_layout)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Basic Voice Controls
        basic_group = QGroupBox("Basic Voice Controls")
        basic_layout = QVBoxLayout()
        
        # Speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.update_speed_label)
        speed_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel("100%")
        speed_layout.addWidget(self.speed_label)
        basic_layout.addLayout(speed_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.update_volume_label)
        volume_layout.addWidget(self.volume_slider)
        self.volume_label = QLabel("80%")
        volume_layout.addWidget(self.volume_label)
        basic_layout.addLayout(volume_layout)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # Advanced Voice Modulation
        mod_group = QGroupBox("Voice Modulation")
        mod_layout = QVBoxLayout()
        
        # Pitch control
        pitch_layout = QHBoxLayout()
        pitch_layout.addWidget(QLabel("Pitch:"))
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setObjectName("pitchSlider")  # Special ID for custom styling
        self.pitch_slider.setRange(-12, 12)
        self.pitch_slider.setValue(0)
        self.pitch_slider.valueChanged.connect(self.update_pitch_label)
        pitch_layout.addWidget(self.pitch_slider)
        self.pitch_label = QLabel("0 semitones")
        self.pitch_label.setProperty("accent", "true")
        pitch_layout.addWidget(self.pitch_label)
        mod_layout.addLayout(pitch_layout)
        
        # Formant shifting
        formant_layout = QHBoxLayout()
        formant_layout.addWidget(QLabel("Formant:"))
        self.edge_formant_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_formant_slider.setRange(-12, 12)
        self.edge_formant_slider.setValue(0)
        self.edge_formant_slider.valueChanged.connect(self.update_edge_formant_label)
        formant_layout.addWidget(self.edge_formant_slider)
        self.edge_formant_label = QLabel("0 (neutral)")
        formant_layout.addWidget(self.edge_formant_label)
        mod_layout.addLayout(formant_layout)
        
        # Tremolo (amplitude modulation)
        tremolo_layout = QHBoxLayout()
        tremolo_layout.addWidget(QLabel("Tremolo:"))
        self.edge_tremolo_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_tremolo_slider.setRange(0, 100)
        self.edge_tremolo_slider.setValue(0)
        self.edge_tremolo_slider.valueChanged.connect(self.update_edge_tremolo_label)
        tremolo_layout.addWidget(self.edge_tremolo_slider)
        self.edge_tremolo_label = QLabel("0%")
        tremolo_layout.addWidget(self.edge_tremolo_label)
        mod_layout.addLayout(tremolo_layout)
        
        # Vibrato (frequency modulation)
        vibrato_layout = QHBoxLayout()
        vibrato_layout.addWidget(QLabel("Vibrato:"))
        self.edge_vibrato_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_vibrato_slider.setRange(0, 100)
        self.edge_vibrato_slider.setValue(0)
        self.edge_vibrato_slider.valueChanged.connect(self.update_edge_vibrato_label)
        vibrato_layout.addWidget(self.edge_vibrato_slider)
        self.edge_vibrato_label = QLabel("0%")
        vibrato_layout.addWidget(self.edge_vibrato_label)
        mod_layout.addLayout(vibrato_layout)
        
        mod_group.setLayout(mod_layout)
        layout.addWidget(mod_group)
        
        # Audio Effects
        effects_group = QGroupBox("Audio Effects")
        effects_layout = QVBoxLayout()
        
        # Reverb
        reverb_layout = QHBoxLayout()
        reverb_layout.addWidget(QLabel("Reverb:"))
        self.edge_reverb_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_reverb_slider.setRange(0, 100)
        self.edge_reverb_slider.setValue(0)
        self.edge_reverb_slider.valueChanged.connect(self.update_edge_reverb_label)
        reverb_layout.addWidget(self.edge_reverb_slider)
        self.edge_reverb_label = QLabel("0%")
        reverb_layout.addWidget(self.edge_reverb_label)
        effects_layout.addLayout(reverb_layout)
        
        # Echo
        echo_layout = QHBoxLayout()
        echo_layout.addWidget(QLabel("Echo:"))
        self.edge_echo_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_echo_slider.setRange(0, 100)
        self.edge_echo_slider.setValue(0)
        self.edge_echo_slider.valueChanged.connect(self.update_edge_echo_label)
        echo_layout.addWidget(self.edge_echo_slider)
        self.edge_echo_label = QLabel("0%")
        echo_layout.addWidget(self.edge_echo_label)
        effects_layout.addLayout(echo_layout)
        
        # Chorus
        chorus_layout = QHBoxLayout()
        chorus_layout.addWidget(QLabel("Chorus:"))
        self.edge_chorus_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_chorus_slider.setRange(0, 100)
        self.edge_chorus_slider.setValue(0)
        self.edge_chorus_slider.valueChanged.connect(self.update_edge_chorus_label)
        chorus_layout.addWidget(self.edge_chorus_slider)
        self.edge_chorus_label = QLabel("0%")
        chorus_layout.addWidget(self.edge_chorus_label)
        effects_layout.addLayout(chorus_layout)
        
        # Flanger
        flanger_layout = QHBoxLayout()
        flanger_layout.addWidget(QLabel("Flanger:"))
        self.edge_flanger_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_flanger_slider.setRange(0, 100)
        self.edge_flanger_slider.setValue(0)
        self.edge_flanger_slider.valueChanged.connect(self.update_edge_flanger_label)
        flanger_layout.addWidget(self.edge_flanger_slider)
        self.edge_flanger_label = QLabel("0%")
        flanger_layout.addWidget(self.edge_flanger_label)
        effects_layout.addLayout(flanger_layout)
        
        # Distortion
        distortion_layout = QHBoxLayout()
        distortion_layout.addWidget(QLabel("Distortion:"))
        self.edge_distortion_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_distortion_slider.setRange(0, 100)
        self.edge_distortion_slider.setValue(0)
        self.edge_distortion_slider.valueChanged.connect(self.update_edge_distortion_label)
        distortion_layout.addWidget(self.edge_distortion_slider)
        self.edge_distortion_label = QLabel("0%")
        distortion_layout.addWidget(self.edge_distortion_label)
        effects_layout.addLayout(distortion_layout)
        
        # Robot Voice
        robot_layout = QHBoxLayout()
        robot_layout.addWidget(QLabel("Robot Voice:"))
        self.edge_robot_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_robot_slider.setRange(0, 100)
        self.edge_robot_slider.setValue(0)
        self.edge_robot_slider.valueChanged.connect(self.update_edge_robot_label)
        robot_layout.addWidget(self.edge_robot_slider)
        self.edge_robot_label = QLabel("0%")
        robot_layout.addWidget(self.edge_robot_label)
        effects_layout.addLayout(robot_layout)
        
        effects_group.setLayout(effects_layout)
        layout.addWidget(effects_group)
        
        # Audio Processing
        processing_group = QGroupBox("Audio Processing")
        processing_layout = QVBoxLayout()
        
        # Noise Gate
        gate_layout = QHBoxLayout()
        gate_layout.addWidget(QLabel("Noise Gate:"))
        self.edge_gate_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_gate_slider.setRange(0, 100)
        self.edge_gate_slider.setValue(0)
        self.edge_gate_slider.valueChanged.connect(self.update_edge_gate_label)
        gate_layout.addWidget(self.edge_gate_slider)
        self.edge_gate_label = QLabel("0%")
        gate_layout.addWidget(self.edge_gate_label)
        processing_layout.addLayout(gate_layout)
        
        # Compression
        comp_layout = QHBoxLayout()
        comp_layout.addWidget(QLabel("Compression:"))
        self.edge_comp_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_comp_slider.setRange(0, 100)
        self.edge_comp_slider.setValue(0)
        self.edge_comp_slider.valueChanged.connect(self.update_edge_comp_label)
        comp_layout.addWidget(self.edge_comp_slider)
        self.edge_comp_label = QLabel("0%")
        comp_layout.addWidget(self.edge_comp_label)
        processing_layout.addLayout(comp_layout)
        
        processing_group.setLayout(processing_layout)
        layout.addWidget(processing_group)
        
        # Equalizer
        eq_group = QGroupBox("3-Band Equalizer")
        eq_layout = QVBoxLayout()
        
        # Low EQ
        eq_low_layout = QHBoxLayout()
        eq_low_layout.addWidget(QLabel("Low (< 300Hz):"))
        self.edge_eq_low_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_eq_low_slider.setRange(-20, 20)
        self.edge_eq_low_slider.setValue(0)
        self.edge_eq_low_slider.valueChanged.connect(self.update_edge_eq_low_label)
        eq_low_layout.addWidget(self.edge_eq_low_slider)
        self.edge_eq_low_label = QLabel("0 dB")
        eq_low_layout.addWidget(self.edge_eq_low_label)
        eq_layout.addLayout(eq_low_layout)
        
        # Mid EQ
        eq_mid_layout = QHBoxLayout()
        eq_mid_layout.addWidget(QLabel("Mid (300Hz-3kHz):"))
        self.edge_eq_mid_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_eq_mid_slider.setRange(-20, 20)
        self.edge_eq_mid_slider.setValue(0)
        self.edge_eq_mid_slider.valueChanged.connect(self.update_edge_eq_mid_label)
        eq_mid_layout.addWidget(self.edge_eq_mid_slider)
        self.edge_eq_mid_label = QLabel("0 dB")
        eq_mid_layout.addWidget(self.edge_eq_mid_label)
        eq_layout.addLayout(eq_mid_layout)
        
        # High EQ
        eq_high_layout = QHBoxLayout()
        eq_high_layout.addWidget(QLabel("High (> 3kHz):"))
        self.edge_eq_high_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_eq_high_slider.setRange(-20, 20)
        self.edge_eq_high_slider.setValue(0)
        self.edge_eq_high_slider.valueChanged.connect(self.update_edge_eq_high_label)
        eq_high_layout.addWidget(self.edge_eq_high_slider)
        self.edge_eq_high_label = QLabel("0 dB")
        eq_high_layout.addWidget(self.edge_eq_high_label)
        eq_layout.addLayout(eq_high_layout)
        
        eq_group.setLayout(eq_layout)
        layout.addWidget(eq_group)
        
        # Text Formatting Options
        format_group = QGroupBox("Text Formatting Options")
        format_layout = QVBoxLayout()
        
        # Asterisk toggle
        asterisk_layout = QHBoxLayout()
        self.asterisk_toggle = QCheckBox("Read text inside *asterisks*")
        self.asterisk_toggle.setChecked(True)  # Default to include asterisks content
        asterisk_layout.addWidget(self.asterisk_toggle)
        format_layout.addLayout(asterisk_layout)
        
        # Quotes toggle
        quotes_layout = QHBoxLayout()
        self.quotes_toggle = QCheckBox('Only read text inside "quotes"')
        self.quotes_toggle.setChecked(False)  # Default to read all text
        quotes_layout.addWidget(self.quotes_toggle)
        format_layout.addLayout(quotes_layout)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # Preset Management
        preset_group = QGroupBox("Edge-TTS Presets")
        preset_layout = QHBoxLayout()
        
        self.edge_preset_combo = QComboBox()
        self.edge_preset_combo.addItems([
            "Default",
            "Professional",
            "Radio DJ",
            "Deep Voice", 
            "Chipmunk",
            "Robot",
            "Echo Chamber",
            "Telephone",
            "Stadium",
            "Whisper",
            "Dramatic",
            "Sci-Fi"
        ])
        self.edge_preset_combo.currentTextChanged.connect(self.load_edge_preset)
        preset_layout.addWidget(QLabel("Preset:"))
        preset_layout.addWidget(self.edge_preset_combo)
        
        self.save_edge_preset_button = QPushButton("Save Preset")
        self.save_edge_preset_button.clicked.connect(self.save_edge_preset)
        preset_layout.addWidget(self.save_edge_preset_button)
        
        self.reset_edge_button = QPushButton("Reset All")
        self.reset_edge_button.clicked.connect(self.reset_edge_settings)
        preset_layout.addWidget(self.reset_edge_button)
        
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # Set up scroll area
        scroll_widget.setLayout(layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        
        main_layout.addWidget(scroll)
        tab.setLayout(main_layout)
        
    def setup_sr_tab(self, tab):
        layout = QVBoxLayout()
        
        # Recognition controls
        rec_group = QGroupBox("Speech Recognition Controls")
        rec_layout = QVBoxLayout()
        
        # Language selection
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "en-US (English - US)",
            "en-GB (English - UK)", 
            "en-AU (English - Australia)",
            "es-ES (Spanish)",
            "fr-FR (French)",
            "de-DE (German)",
            "it-IT (Italian)",
            "pt-BR (Portuguese - Brazil)"
        ])
        lang_layout.addWidget(self.language_combo)
        rec_layout.addLayout(lang_layout)
        
        # Recognition buttons
        button_layout = QHBoxLayout()
        self.start_rec_button = QPushButton("🎤 Start Listening")
        self.start_rec_button.clicked.connect(self.start_recognition)
        button_layout.addWidget(self.start_rec_button)
        
        self.stop_rec_button = QPushButton("⏹ Stop Listening")
        self.stop_rec_button.clicked.connect(self.stop_recognition)
        self.stop_rec_button.setEnabled(False)
        button_layout.addWidget(self.stop_rec_button)
        
        self.clear_button = QPushButton("🗑 Clear Text")
        self.clear_button.clicked.connect(self.clear_recognized_text)
        button_layout.addWidget(self.clear_button)
        
        rec_layout.addLayout(button_layout)
        rec_group.setLayout(rec_layout)
        layout.addWidget(rec_group)
        
        # Recognized text area
        text_group = QGroupBox("Recognized Text")
        text_layout = QVBoxLayout()
        
        self.recognized_text = QTextEdit()
        self.recognized_text.setPlainText("Recognized speech will appear here...")
        self.recognized_text.setFont(QFont("Arial", 12))
        text_layout.addWidget(self.recognized_text)
        
        text_group.setLayout(text_layout)
        layout.addWidget(text_group)
        
        # Transfer button
        transfer_layout = QHBoxLayout()
        self.transfer_button = QPushButton("➡ Transfer to TTS")
        self.transfer_button.clicked.connect(self.transfer_to_tts)
        transfer_layout.addWidget(self.transfer_button)
        layout.addLayout(transfer_layout)
        
        tab.setLayout(layout)
        
    def setup_info_tab(self, tab):
        layout = QVBoxLayout()
        
        info_group = QGroupBox("Edge-TTS Information")
        info_layout = QVBoxLayout()
        
        info_text = QTextBrowser()
        info_text.setHtml(f"""
        <h3>Enhanced Edge-TTS Features:</h3>
        <ul>
            <li><b>Zero Setup:</b> No models to download or servers to run</li>
            <li><b>High Quality:</b> Same voices as Windows 11 Narrator</li>
            <li><b>Many Languages:</b> Multiple languages available</li>
            <li><b>Multiple Voices:</b> {len(self.available_voices)} total voices</li>
            <li><b>Completely Free:</b> No API costs or limits</li>
            <li><b>Offline Capable:</b> Works without internet after voice cache</li>
            <li><b>Comprehensive Effects:</b> Full audio processing pipeline with 12+ effects</li>
            <li><b>Voice Presets:</b> 12 pre-configured voice styles</li>
        </ul>
        
        <h3>Edge-TTS Voice Effects:</h3>
        <ul>
            <li><b>Pitch Control:</b> ±12 semitones for voice character</li>
            <li><b>Formant Shifting:</b> Change vocal tract characteristics</li>
            <li><b>Tremolo:</b> Amplitude modulation for voice shake</li>
            <li><b>Vibrato:</b> Frequency modulation for musical effect</li>
            <li><b>Reverb:</b> Add spatial depth and ambience</li>
            <li><b>Echo:</b> Create delay-based effects</li>
            <li><b>Chorus:</b> Thicken voice with multiple delays</li>
            <li><b>Flanger:</b> Sweeping comb filter effect</li>
            <li><b>Distortion:</b> Add grit and character</li>
            <li><b>Robot Voice:</b> Ring modulation for synthetic sound</li>
            <li><b>Noise Gate:</b> Remove background noise</li>
            <li><b>Compression:</b> Control dynamic range</li>
            <li><b>3-Band EQ:</b> Shape frequency response (Low/Mid/High)</li>
        </ul>

        <h3>Available Voices: {len(self.available_voices)} Edge-TTS</h3>
        <p>Voice selection includes male and female voices in multiple languages.</p>
        
        <h3>Edge-TTS Voice Presets (NEW!):</h3>
        <ul>
            <li><b>Professional:</b> Clean, professional sound for business</li>
            <li><b>Radio DJ:</b> Enhanced broadcast-style voice</li>
            <li><b>Deep Voice:</b> Lower, more authoritative tone</li>
            <li><b>Chipmunk:</b> High-pitched, playful character</li>
            <li><b>Robot:</b> Mechanical, synthetic sound</li>
            <li><b>Echo Chamber:</b> Spacious, reverberant environment</li>
            <li><b>Telephone:</b> Band-limited communication sound</li>
            <li><b>Stadium:</b> Large venue announcement style</li>
            <li><b>Whisper:</b> Quiet, intimate delivery</li>
            <li><b>Dramatic:</b> Enhanced emotional impact with effects</li>
            <li><b>Sci-Fi:</b> Futuristic voice with multiple effects</li>
        </ul>
        
        <h3>Piper Voice Presets:</h3>
        <ul>
            <li><b>Radio Voice:</b> Professional broadcast sound</li>
            <li><b>Deep Voice:</b> Lower, more authoritative tone</li>
            <li><b>Chipmunk:</b> High-pitched, playful character</li>
            <li><b>Robot:</b> Mechanical, synthetic sound</li>
            <li><b>Echo Chamber:</b> Spacious, reverberant</li>
            <li><b>Telephone:</b> Band-limited communication</li>
            <li><b>Stadium:</b> Large venue announcement</li>
            <li><b>Whisper:</b> Quiet, intimate delivery</li>
            <li><b>Dramatic:</b> Enhanced emotional impact</li>
        </ul>
        
        <h3>Usage Tips:</h3>
        <ul>
            <li>Experiment with different voices to find your preference</li>
            <li>Adjust speed and volume to your liking</li>
            <li>Use punctuation for natural speech rhythm</li>
            <li>Smaller chunk sizes = more responsive playback</li>
            <li>Larger chunk sizes = more efficient processing</li>
            <li>Combine multiple effects for unique voices</li>
            <li>Use presets as starting points for customization</li>
            <li>Use the "*asterisk*" toggle to include/exclude emphasized text</li>
            <li>Use the "quotes" toggle to only read text inside quotation marks</li>
        </ul>
        
        <h3>Requirements:</h3>
        <ul>
            <li>pip install edge-tts</li>
            <li>pip install piper-tts</li>
            <li>pip install librosa</li>
            <li>pip install soundfile</li>
            <li>pip install numpy</li>
            <li>pip install scipy</li>
            <li>pip install pygame</li>
            <li>pip install PyQt5</li>
            <li>pip install SpeechRecognition</li>
            <li>pip install python-docx</li>
        </ul>
        """)
        
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        tab.setLayout(layout)
    
    def update_speed_label(self):
        self.speed_label.setText(f"{self.speed_slider.value()}%")
    
    def update_volume_label(self):
        self.volume_label.setText(f"{self.volume_slider.value()}%")
    
    def update_pitch_label(self):
        value = self.pitch_slider.value()
        self.pitch_label.setText(f"{value:+d} semitones")
    
    # Edge-TTS Effect Label Updates
    def update_edge_formant_label(self):
        value = self.edge_formant_slider.value()
        if value == 0:
            self.edge_formant_label.setText("0 (neutral)")
        elif value > 0:
            self.edge_formant_label.setText(f"+{value} (brighter)")
        else:
            self.edge_formant_label.setText(f"{value} (darker)")
    
    def update_edge_tremolo_label(self):
        self.edge_tremolo_label.setText(f"{self.edge_tremolo_slider.value()}%")
    
    def update_edge_vibrato_label(self):
        self.edge_vibrato_label.setText(f"{self.edge_vibrato_slider.value()}%")
    
    def update_edge_reverb_label(self):
        self.edge_reverb_label.setText(f"{self.edge_reverb_slider.value()}%")
    
    def update_edge_echo_label(self):
        self.edge_echo_label.setText(f"{self.edge_echo_slider.value()}%")
    
    def update_edge_chorus_label(self):
        self.edge_chorus_label.setText(f"{self.edge_chorus_slider.value()}%")
    
    def update_edge_flanger_label(self):
        self.edge_flanger_label.setText(f"{self.edge_flanger_slider.value()}%")
    
    def update_edge_distortion_label(self):
        self.edge_distortion_label.setText(f"{self.edge_distortion_slider.value()}%")
    
    def update_edge_robot_label(self):
        self.edge_robot_label.setText(f"{self.edge_robot_slider.value()}%")
    
    def update_edge_gate_label(self):
        self.edge_gate_label.setText(f"{self.edge_gate_slider.value()}%")
    
    def update_edge_comp_label(self):
        self.edge_comp_label.setText(f"{self.edge_comp_slider.value()}%")
    
    def update_edge_eq_low_label(self):
        value = self.edge_eq_low_slider.value()
        self.edge_eq_low_label.setText(f"{value:+d} dB")
    
    def update_edge_eq_mid_label(self):
        value = self.edge_eq_mid_slider.value()
        self.edge_eq_mid_label.setText(f"{value:+d} dB")
    
    def update_edge_eq_high_label(self):
        value = self.edge_eq_high_slider.value()
        self.edge_eq_high_label.setText(f"{value:+d} dB")
    
    def load_document(self):
        """Load a Word document"""
        if not DOCX_AVAILABLE:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Text Document", "", 
                "Text Files (*.txt);;All Files (*)"
            )
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Word Document", "", 
                "Word Documents (*.docx);;Text Files (*.txt);;All Files (*)"
            )
        
        if file_path:
            try:
                if file_path.endswith('.docx'):
                    if not DOCX_AVAILABLE:
                        QMessageBox.warning(self, "Error", "python-docx package is not available. Please install it with 'pip install python-docx' to load Word documents.")
                        return
                    doc = Document(file_path)
                    text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                else:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        text = file.read()
                
                self.text_edit.setPlainText(text)
                QMessageBox.information(self, "Success", "Document loaded successfully!")
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error loading document: {e}")
    
    def save_text(self):
        """Save current text to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Text", "", 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "Success", "Text saved successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error saving text: {e}")
    
    def test_voice(self):
        """Test current voice settings with a short phrase"""
        test_text = "Hello! This is a test of the Edge TTS voice synthesis. How do you like this voice?"
        self.generate_speech(test_text)
    
    def play_text(self):
        """Start text-to-speech playback"""
        text = self.text_edit.toPlainText().strip()
        
        if not text or text == "Enter your text here or load a Word document...":
            QMessageBox.warning(self, "Warning", "No text to speak!")
            return
            
        self.generate_speech(text)
    
    def generate_speech(self, text):
        """Generate speech using Edge-TTS with comprehensive effects"""
        if self.tts_thread and self.tts_thread.isRunning():
            return
        
        # Get selected voice
        voice_name = self.voice_combo.currentData()
        if not voice_name:
            QMessageBox.warning(self, "Error", "Please select a voice!")
            return
        
        # Process text based on formatting options
        text = self.process_text_formatting(text, 
                                           self.asterisk_toggle.isChecked(),
                                           self.quotes_toggle.isChecked())
        
        # Get basic settings
        rate = self.speed_slider.value()
        volume = self.volume_slider.value()
        pitch = self.pitch_slider.value()
        chunk_size = self.chunk_size_spin.value()
        
        # Get effects settings
        effects = self.get_edge_effects_settings()
        
        # Start generation
        self.tts_thread = EdgeTTSThread(text, voice_name, rate, volume, pitch, chunk_size, effects)
        self.tts_thread.finished.connect(self.on_speech_finished)
        self.tts_thread.progress.connect(self.progress_bar.setValue)
        self.tts_thread.error.connect(self.on_speech_error)
        self.tts_thread.start()
        
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
    
    def process_text_formatting(self, text, read_asterisks=True, only_quotes=False):
        """Process text based on formatting options"""
        # Handle text inside quotes if only_quotes is True
        if only_quotes:
            # Extract content inside double quotes
            import re
            quote_matches = re.findall(r'"([^"]*)"', text)
            if quote_matches:
                # Join all quoted sections with a pause between them
                return ". ".join(quote_matches)
            else:
                # If no quotes found, return original text to avoid silent output
                return text
                
        # Handle text inside asterisks if read_asterisks is False
        if not read_asterisks:
            # Remove content inside asterisks
            import re
            text = re.sub(r'\*[^*]*\*', '', text)
            
        return text
    
    def get_edge_effects_settings(self):
        """Get current Edge-TTS effects settings as dictionary"""
        # Helper function to avoid very small values that might cause artifacts
        def clean_value(value, threshold=1.0):
            return value if abs(value) >= threshold else 0
            
        # For slider values divided by 100, use a smaller threshold
        def clean_small_value(value, threshold=1.0):
            scaled = value / 100.0
            return scaled if abs(value) >= threshold else 0
        
        return {
            'formant': clean_value(self.edge_formant_slider.value()),
            'tremolo': clean_small_value(self.edge_tremolo_slider.value()),
            'vibrato': clean_small_value(self.edge_vibrato_slider.value()),
            'reverb': clean_small_value(self.edge_reverb_slider.value()),
            'echo': clean_small_value(self.edge_echo_slider.value()),
            'chorus': clean_small_value(self.edge_chorus_slider.value()),
            'flanger': clean_small_value(self.edge_flanger_slider.value()),
            'distortion': clean_small_value(self.edge_distortion_slider.value()),
            'robot': clean_small_value(self.edge_robot_slider.value()),
            'noise_gate': clean_value(self.edge_gate_slider.value()),
            'compression': clean_small_value(self.edge_comp_slider.value()),
            'eq_low': clean_value(self.edge_eq_low_slider.value()),
            'eq_mid': clean_value(self.edge_eq_mid_slider.value()),
            'eq_high': clean_value(self.edge_eq_high_slider.value()),
        }
    
    def load_edge_preset(self, preset_name):
        """Load an Edge-TTS voice preset"""
        presets = {
            "Default": {
                'speed': 100, 'volume': 80, 'pitch': 0, 'formant': 0,
                'tremolo': 0, 'vibrato': 0, 'reverb': 0, 'echo': 0, 
                'chorus': 0, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 0, 'compression': 0, 
                'eq_low': 0, 'eq_mid': 0, 'eq_high': 0
            },
            "Professional": {
                'speed': 95, 'volume': 85, 'pitch': 0, 'formant': 1,
                'tremolo': 0, 'vibrato': 0, 'reverb': 5, 'echo': 0, 
                'chorus': 0, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 15, 'compression': 25,
                'eq_low': -2, 'eq_mid': 3, 'eq_high': 2
            },
            "Radio DJ": {
                'speed': 90, 'volume': 95, 'pitch': -1, 'formant': 2,
                'tremolo': 0, 'vibrato': 0, 'reverb': 10, 'echo': 5, 
                'chorus': 0, 'flanger': 0, 'distortion': 5, 'robot': 0,
                'noise_gate': 20, 'compression': 40,
                'eq_low': -3, 'eq_mid': 5, 'eq_high': 3
            },
            "Deep Voice": {
                'speed': 80, 'volume': 90, 'pitch': -8, 'formant': -5,
                'tremolo': 0, 'vibrato': 0, 'reverb': 15, 'echo': 0, 
                'chorus': 0, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 10, 'compression': 30,
                'eq_low': 8, 'eq_mid': -2, 'eq_high': -5
            },
            "Chipmunk": {
                'speed': 140, 'volume': 70, 'pitch': 12, 'formant': 8,
                'tremolo': 0, 'vibrato': 0, 'reverb': 0, 'echo': 0, 
                'chorus': 15, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 0, 'compression': 0,
                'eq_low': -10, 'eq_mid': 5, 'eq_high': 10
            },
            "Robot": {
                'speed': 75, 'volume': 85, 'pitch': -3, 'formant': 0,
                'tremolo': 0, 'vibrato': 0, 'reverb': 5, 'echo': 10, 
                'chorus': 0, 'flanger': 0, 'distortion': 20, 'robot': 60,
                'noise_gate': 30, 'compression': 50,
                'eq_low': -5, 'eq_mid': 0, 'eq_high': 5
            },
            "Echo Chamber": {
                'speed': 85, 'volume': 80, 'pitch': 0, 'formant': 0,
                'tremolo': 0, 'vibrato': 0, 'reverb': 70, 'echo': 60, 
                'chorus': 10, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 5, 'compression': 15,
                'eq_low': 2, 'eq_mid': -3, 'eq_high': 0
            },
            "Telephone": {
                'speed': 100, 'volume': 90, 'pitch': 0, 'formant': 0,
                'tremolo': 0, 'vibrato': 0, 'reverb': 0, 'echo': 0, 
                'chorus': 0, 'flanger': 0, 'distortion': 15, 'robot': 0,
                'noise_gate': 40, 'compression': 60,
                'eq_low': -15, 'eq_mid': 8, 'eq_high': -10
            },
            "Stadium": {
                'speed': 90, 'volume': 100, 'pitch': 1, 'formant': 1,
                'tremolo': 0, 'vibrato': 0, 'reverb': 80, 'echo': 40, 
                'chorus': 5, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 0, 'compression': 25,
                'eq_low': 3, 'eq_mid': 2, 'eq_high': 5
            },
            "Whisper": {
                'speed': 60, 'volume': 50, 'pitch': -2, 'formant': -1,
                'tremolo': 0, 'vibrato': 0, 'reverb': 20, 'echo': 0, 
                'chorus': 0, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 60, 'compression': 80,
                'eq_low': -5, 'eq_mid': -8, 'eq_high': -3
            },
            "Dramatic": {
                'speed': 80, 'volume': 95, 'pitch': -2, 'formant': 1,
                'tremolo': 5, 'vibrato': 0, 'reverb': 40, 'echo': 15, 
                'chorus': 0, 'flanger': 0, 'distortion': 0, 'robot': 0,
                'noise_gate': 10, 'compression': 45,
                'eq_low': 5, 'eq_mid': 3, 'eq_high': 2
            },
            "Sci-Fi": {
                'speed': 85, 'volume': 85, 'pitch': -1, 'formant': 3,
                'tremolo': 0, 'vibrato': 10, 'reverb': 30, 'echo': 20, 
                'chorus': 15, 'flanger': 25, 'distortion': 10, 'robot': 30,
                'noise_gate': 20, 'compression': 35,
                'eq_low': -3, 'eq_mid': 2, 'eq_high': 8
            }
        }
        
        if preset_name in presets:
            settings = presets[preset_name]
            self.apply_edge_settings(settings)
    
    def apply_edge_settings(self, settings):
        """Apply settings to all Edge-TTS controls"""
        self.speed_slider.setValue(settings['speed'])
        self.volume_slider.setValue(settings['volume'])
        self.pitch_slider.setValue(settings['pitch'])
        self.edge_formant_slider.setValue(settings['formant'])
        self.edge_tremolo_slider.setValue(int(settings['tremolo']))
        self.edge_vibrato_slider.setValue(int(settings['vibrato']))
        self.edge_reverb_slider.setValue(int(settings['reverb']))
        self.edge_echo_slider.setValue(int(settings['echo']))
        self.edge_chorus_slider.setValue(int(settings['chorus']))
        self.edge_flanger_slider.setValue(int(settings['flanger']))
        self.edge_distortion_slider.setValue(int(settings['distortion']))
        self.edge_robot_slider.setValue(int(settings['robot']))
        self.edge_gate_slider.setValue(settings['noise_gate'])
        self.edge_comp_slider.setValue(int(settings['compression']))
        self.edge_eq_low_slider.setValue(settings['eq_low'])
        self.edge_eq_mid_slider.setValue(settings['eq_mid'])
        self.edge_eq_high_slider.setValue(settings['eq_high'])
    
    def save_edge_preset(self):
        """Save current Edge-TTS settings as a custom preset"""
        name, ok = QInputDialog.getText(self, "Save Edge-TTS Preset", "Enter preset name:")
        if ok and name:
            # Here you could save to a file or database
            QMessageBox.information(self, "Preset Saved", f"Edge-TTS preset '{name}' saved successfully!")
    
    def reset_edge_settings(self):
        """Reset all Edge-TTS settings to default"""
        self.load_edge_preset("Default")
    
    def stop_speech(self):
        """Stop text-to-speech playback"""
        if self.tts_thread and self.tts_thread.isRunning():
            self.tts_thread.stop()
            # Wait up to 3 seconds for thread to finish
            if not self.tts_thread.wait(3000):
                # Force terminate if it doesn't stop
                self.tts_thread.terminate()
                self.tts_thread.wait(1000)
        self.on_speech_finished()
    
    def on_speech_finished(self):
        """Handle speech completion"""
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def on_speech_error(self, error_msg):
        """Handle speech errors"""
        QMessageBox.warning(self, "TTS Error", f"Error during speech generation: {error_msg}")
        self.on_speech_finished()
    
    # Speech Recognition methods
    def start_recognition(self):
        if self.sr_thread and self.sr_thread.isRunning():
            return
            
        language_text = self.language_combo.currentText()
        language_code = language_text.split(' ')[0]
        
        self.sr_thread = SpeechRecognitionThread(language_code)
        self.sr_thread.recognized.connect(self.on_text_recognized)
        self.sr_thread.error.connect(self.on_recognition_error)
        self.sr_thread.start()
        
        self.start_rec_button.setEnabled(False)
        self.stop_rec_button.setEnabled(True)
    
    def stop_recognition(self):
        if self.sr_thread:
            self.sr_thread.stop()
            self.sr_thread.wait()
        
        self.start_rec_button.setEnabled(True)
        self.stop_rec_button.setEnabled(False)
    
    def on_text_recognized(self, text):
        current_text = self.recognized_text.toPlainText()
        if current_text == "Recognized speech will appear here...":
            self.recognized_text.setPlainText(text)
        else:
            self.recognized_text.setPlainText(current_text + " " + text)
    
    def on_recognition_error(self, error_msg):
        QMessageBox.warning(self, "Recognition Error", f"Error during recognition: {error_msg}")
        self.stop_recognition()
    
    def clear_recognized_text(self):
        self.recognized_text.setPlainText("Recognized speech will appear here...")
    
    def transfer_to_tts(self):
        text = self.recognized_text.toPlainText()
        if text and text != "Recognized speech will appear here...":
            self.text_edit.setPlainText(text)
            QMessageBox.information(self, "Success", "Text transferred to TTS tab!")
    
    # Piper TTS methods
    def closeEvent(self, event):
        """Clean up threads on close"""
        if self.tts_thread:
            self.tts_thread.stop()
            self.tts_thread.wait()
        if self.sr_thread:
            self.sr_thread.stop()
            self.sr_thread.wait()
        event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Create and show the main window
    window = EdgeTTSApp()
    window.show()
    
    # Start the event loop
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
