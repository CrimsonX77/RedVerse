#!/usr/bin/env python3
"""
The Scrying Glass of Eternal Sight - A mystical window into the realm of visions and whispers
Behold the ancient art of visual divination with ethereal sound channeling
"""

import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QSlider, QGroupBox, QComboBox)
from PyQt6.QtMultimedia import (QMediaDevices, QCamera, QMediaCaptureSession, 
                                QAudioInput, QAudioOutput, QMediaPlayer)
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QImage

# Try to import advanced night vision packages
try:
    import numpy as np
    import cv2
    ADVANCED_NIGHT_VISION = True
    print("🌙 Advanced night vision capabilities loaded!")
except ImportError:
    ADVANCED_NIGHT_VISION = False
    print("⚠️  Basic night vision mode - install opencv-python and numpy for advanced features")
    print("🔮 Run 'python install_night_vision.py' to upgrade to full night vision")

class NightVisionProcessor(QThread):
    """Background thread for processing camera frames with night vision"""
    frameProcessed = pyqtSignal(QImage)
    
    def __init__(self):
        super().__init__()
        self.vision_mode = "🌙 Normal Vision"
        self.intensity = 5
        self.running = False
        self.camera_index = 0
        
    def set_vision_mode(self, mode):
        self.vision_mode = mode
        
    def set_intensity(self, intensity):
        self.intensity = intensity
        
    def set_camera_index(self, index):
        self.camera_index = index
        
    def start_processing(self):
        self.running = True
        self.start()
        
    def stop_processing(self):
        self.running = False
        self.wait()
        
    def run(self):
        """Main processing loop for night vision"""
        if not ADVANCED_NIGHT_VISION:
            return
            
        # Open camera with OpenCV
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print(f"❌ Could not open camera {self.camera_index}")
            return
            
        print(f"🎥 Night vision processor started for camera {self.camera_index}")
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
                
            # Apply night vision processing
            if self.vision_mode != "🌙 Normal Vision":
                processed_frame = self.apply_night_vision_processing(frame)
            else:
                processed_frame = frame
                
            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to QImage
            height, width, channel = rgb_frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Emit the processed frame
            self.frameProcessed.emit(q_image)
            
            # Control frame rate
            self.msleep(33)  # ~30 FPS
            
        cap.release()
        print("🔚 Night vision processor stopped")
    
    def apply_night_vision_processing(self, frame):
        """Apply night vision effects to OpenCV frame"""
        intensity_factor = self.intensity / 10.0
        
        if self.vision_mode == "🔮 Mystical Green":
            # Classic night vision green
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Apply histogram equalization for better contrast
            equalized = cv2.equalizeHist(gray)
            # Create green night vision effect
            green_night = np.zeros_like(frame)
            green_night[:, :, 1] = equalized * intensity_factor  # Green channel
            green_night[:, :, 0] = equalized * 0.1  # Slight blue
            return green_night.astype(np.uint8)
            
        elif self.vision_mode == "🌡️ Thermal Sight":
            # Thermal imaging effect
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Apply thermal colormap
            thermal = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
            # Apply intensity
            return (thermal * intensity_factor).astype(np.uint8)
            
        elif self.vision_mode == "⚡ Enhanced Low-Light":
            # Enhance brightness and contrast
            enhanced = cv2.convertScaleAbs(frame, alpha=1.0 + intensity_factor, beta=50)
            # Apply gamma correction
            gamma = 0.5 + intensity_factor * 0.5
            gamma_corrected = np.power(enhanced / 255.0, gamma) * 255
            return gamma_corrected.astype(np.uint8)
            
        elif self.vision_mode == "🎭 Edge Detection":
            # Edge detection with color
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            # Create colored edge image
            edge_colored = np.zeros_like(frame)
            edge_colored[:, :, 0] = edges * intensity_factor  # Blue edges
            edge_colored[:, :, 1] = edges * intensity_factor  # Green edges  
            edge_colored[:, :, 2] = edges * intensity_factor  # Red edges
            # Blend with original
            blended = cv2.addWeighted(frame, 0.3, edge_colored, 0.7, 0)
            return blended.astype(np.uint8)
            
        elif self.vision_mode == "👻 Spectral Vision":
            # Inverted colors with purple tint
            inverted = 255 - frame
            # Apply purple tint
            purple_tinted = inverted.copy()
            purple_tinted[:, :, 2] = np.clip(purple_tinted[:, :, 2] * 1.2, 0, 255)  # More red
            purple_tinted[:, :, 0] = np.clip(purple_tinted[:, :, 0] * 1.3, 0, 255)  # More blue
            return (purple_tinted * intensity_factor).astype(np.uint8)
            
        return frame

class NightVisionVideoWidget(QLabel):
    """Custom video widget that displays processed night vision frames"""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 480)
        self.setStyleSheet("border: 3px solid #4ecdc4; background-color: black;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("🔮 Night Vision Display")
        
    def display_frame(self, image):
        """Display a processed frame"""
        # Scale image to fit widget while maintaining aspect ratio
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled_pixmap)

class MysticVisionOrb(QWidget):
    def __init__(self):
        super().__init__()
        self.scrying_eye = None
        self.vision_conduit = None
        self.whisper_collector = None
        self.echo_projector = None
        self.silence_veil_active = False
        self.ethereal_volume = 0.7  # Default 70% mystical resonance
        
        # Night Vision Mystical Properties
        self.current_vision_mode = "🌙 Normal Vision"
        self.night_vision_power = 5
        self.vision_processor_timer = QTimer()
        self.vision_processor_timer.timeout.connect(self.process_mystical_vision)
        
        # Night Vision Processor
        self.night_vision_processor = None
        self.using_night_vision = False
        
        self.forge_enchanted_interface()
        
    def forge_enchanted_interface(self):
        primary_runes = QVBoxLayout()
        
        # Apply mystical dark theme styling
        self.apply_mystical_styling()
        
        # Ancient status proclamation
        self.oracle_proclamation = QLabel("🔮 The Mystical Scrying Orb Awaits - Invoke the Ancient Sight Ritual")
        self.oracle_proclamation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.oracle_proclamation.setObjectName("oracle_proclamation")
        ethereal_font = QFont()
        ethereal_font.setPointSize(12)
        ethereal_font.setBold(True)
        self.oracle_proclamation.setFont(ethereal_font)
        primary_runes.addWidget(self.oracle_proclamation)
        
        # The Great Vision Chamber with embedded arcane controls
        vision_sanctum = QGroupBox("⚡ Vision Portal ⚡")
        vision_sanctum.setObjectName("vision_sanctum")
        sanctum_layout = QVBoxLayout()
        
        self.crystal_vision_orb = QVideoWidget()
        self.crystal_vision_orb.setMinimumSize(640, 480)
        self.crystal_vision_orb.setObjectName("crystal_vision_orb")
        sanctum_layout.addWidget(self.crystal_vision_orb)
        
        # Night Vision Display (overlays the regular video widget)
        self.night_vision_display = NightVisionVideoWidget()
        self.night_vision_display.setObjectName("night_vision_display")
        self.night_vision_display.hide()  # Hidden by default
        sanctum_layout.addWidget(self.night_vision_display)
        
        # Ethereal sound manipulation runes (embedded in vision sanctum)
        whisper_control_runes = QHBoxLayout()
        
        # Night Vision Enchantments
        night_vision_label = QLabel("👁️ Night Vision:")
        night_vision_label.setObjectName("night_vision_label")
        whisper_control_runes.addWidget(night_vision_label)
        
        self.night_vision_mode = QComboBox()
        self.night_vision_mode.setObjectName("night_vision_mode")
        self.night_vision_mode.addItems([
            "🌙 Normal Vision",
            "🔮 Mystical Green",
            "🌡️ Thermal Sight", 
            "⚡ Enhanced Low-Light",
            "🎭 Edge Detection",
            "👻 Spectral Vision"
        ])
        self.night_vision_mode.currentTextChanged.connect(self.change_vision_mode)
        self.night_vision_mode.setEnabled(False)
        whisper_control_runes.addWidget(self.night_vision_mode)
        
        # Mystical intensity dial
        intensity_label = QLabel("🔥 Power:")
        intensity_label.setObjectName("intensity_label")
        whisper_control_runes.addWidget(intensity_label)
        
        self.night_vision_intensity = QSlider(Qt.Orientation.Horizontal)
        self.night_vision_intensity.setMinimum(1)
        self.night_vision_intensity.setMaximum(10)
        self.night_vision_intensity.setValue(5)
        self.night_vision_intensity.setMaximumWidth(100)
        self.night_vision_intensity.setObjectName("night_vision_intensity")
        self.night_vision_intensity.valueChanged.connect(self.adjust_night_vision_intensity)
        self.night_vision_intensity.setEnabled(False)
        whisper_control_runes.addWidget(self.night_vision_intensity)
        
        whisper_control_runes.addWidget(QLabel("|"))  # Separator
        
        # Silence/Sound toggle enchantment
        self.silence_enchantment = QPushButton("🔊")
        self.silence_enchantment.setMaximumWidth(50)
        self.silence_enchantment.setObjectName("silence_enchantment")
        self.silence_enchantment.clicked.connect(self.invoke_silence_veil)
        self.silence_enchantment.setEnabled(False)
        self.silence_enchantment.setToolTip("Cast Silence Veil / Dispel Silence")
        whisper_control_runes.addWidget(self.silence_enchantment)
        
        # Ethereal resonance manipulation
        resonance_label = QLabel("🎵 Echo Resonance:")
        resonance_label.setObjectName("resonance_label")
        whisper_control_runes.addWidget(resonance_label)
        
        self.ethereal_resonance_dial = QSlider(Qt.Orientation.Horizontal)
        self.ethereal_resonance_dial.setMinimum(0)
        self.ethereal_resonance_dial.setMaximum(100)
        self.ethereal_resonance_dial.setValue(int(self.ethereal_volume * 100))
        self.ethereal_resonance_dial.valueChanged.connect(self.attune_ethereal_resonance)
        self.ethereal_resonance_dial.setEnabled(False)
        self.ethereal_resonance_dial.setMaximumWidth(150)
        self.ethereal_resonance_dial.setObjectName("ethereal_resonance_dial")
        whisper_control_runes.addWidget(self.ethereal_resonance_dial)
        
        self.resonance_display = QLabel("70%")
        self.resonance_display.setMinimumWidth(40)
        self.resonance_display.setObjectName("resonance_display")
        whisper_control_runes.addWidget(self.resonance_display)
        
        whisper_control_runes.addStretch()  # Push mystical controls to the left
        
        sanctum_layout.addLayout(whisper_control_runes)
        vision_sanctum.setLayout(sanctum_layout)
        primary_runes.addWidget(vision_sanctum)
        
        # Sacred command incantations
        incantation_layout = QHBoxLayout()
        
        # Awakening ritual button
        self.awakening_ritual = QPushButton("▶ Awaken the Scrying Eye & Gather Whispers")
        self.awakening_ritual.setObjectName("awakening_ritual")
        self.awakening_ritual.clicked.connect(self.commence_mystical_sight)
        incantation_layout.addWidget(self.awakening_ritual)
        
        # Banishment ritual button
        self.banishment_ritual = QPushButton("⏹ Seal the Vision Portal")
        self.banishment_ritual.setObjectName("banishment_ritual")
        self.banishment_ritual.clicked.connect(self.cease_mystical_sight)
        self.banishment_ritual.setEnabled(False)
        incantation_layout.addWidget(self.banishment_ritual)
        
        primary_runes.addLayout(incantation_layout)
        
        self.setLayout(primary_runes)
        self.setWindowTitle("🔮 The Eternal Scrying Orb of Sight & Sound")
        self.setGeometry(100, 100, 800, 650)
        
    def apply_mystical_styling(self):
        """Apply sleek dark theme with neon accents - Badass Mystical Style"""
        mystical_stylesheet = """
            /* Main Window Dark Theme */
            QWidget {
                background-color: #0a0a0a;
                color: #00ffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }
            
            /* Oracle Proclamation - Glowing Header */
            #oracle_proclamation {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f0f23);
                color: #00ffff;
                border: 2px solid #00aacc;
                border-radius: 10px;
                padding: 15px;
                margin: 10px;
                font-weight: bold;
                text-shadow: 0 0 10px #00ffff;
            }
            
            /* Vision Portal Group Box */
            #vision_sanctum {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #1a1a2e, stop:1 #0f0f23);
                border: 2px solid #ff6b6b;
                border-radius: 15px;
                margin: 10px;
                padding: 10px;
                font-weight: bold;
                color: #ff6b6b;
            }
            
            #vision_sanctum::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 5px 15px;
                color: #ff6b6b;
                text-shadow: 0 0 8px #ff6b6b;
            }
            
            /* Video Widget Dark Border */
            #crystal_vision_orb {
                border: 3px solid #4ecdc4;
                border-radius: 8px;
                background-color: #000000;
                margin: 5px;
            }
            
            /* Main Action Buttons */
            #awakening_ritual, #banishment_ritual {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2d5a87, stop:0.5 #1e3a5f, stop:1 #0f2847);
                color: #ffffff;
                border: 2px solid #4ecdc4;
                border-radius: 8px;
                padding: 12px 20px;
                margin: 5px;
                font-weight: bold;
                font-size: 12px;
                text-shadow: 0 0 5px #4ecdc4;
            }
            
            #awakening_ritual:hover, #banishment_ritual:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4ecdc4, stop:0.5 #2d5a87, stop:1 #1e3a5f);
                border-color: #00ffff;
                text-shadow: 0 0 10px #00ffff;
            }
            
            #awakening_ritual:pressed, #banishment_ritual:pressed {
                background: #1e3a5f;
                border-color: #ff6b6b;
            }
            
            #awakening_ritual:disabled, #banishment_ritual:disabled {
                background: #2a2a2a;
                color: #666666;
                border-color: #444444;
                text-shadow: none;
            }
            
            /* Silence Button */
            #silence_enchantment {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #6a4c93, stop:1 #a8e6cf);
                color: #ffffff;
                border: 2px solid #ff6b6b;
                border-radius: 25px;
                padding: 8px;
                margin: 2px;
                font-size: 16px;
                text-shadow: 0 0 5px #ff6b6b;
            }
            
            #silence_enchantment:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #a8e6cf, stop:1 #6a4c93);
                text-shadow: 0 0 10px #ffffff;
            }
            
            #silence_enchantment:disabled {
                background: #2a2a2a;
                color: #666666;
                border-color: #444444;
                text-shadow: none;
            }
            
            /* Labels */
            #resonance_label, #resonance_display, #night_vision_label, #intensity_label {
                color: #ffd93d;
                font-weight: bold;
                margin: 5px;
                text-shadow: 0 0 5px #ffd93d;
            }
            
            #night_vision_label {
                color: #00ff00;
                text-shadow: 0 0 8px #00ff00;
            }
            
            #intensity_label {
                color: #ff6b6b;
                text-shadow: 0 0 6px #ff6b6b;
            }
            
            /* Night Vision Mode Selector */
            #night_vision_mode {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2d5a27, stop:0.5 #1e3f1e, stop:1 #0f2f0f);
                color: #00ff00;
                border: 2px solid #00cc00;
                border-radius: 6px;
                padding: 5px 10px;
                margin: 2px;
                font-weight: bold;
                text-shadow: 0 0 5px #00ff00;
                selection-background-color: #004400;
            }
            
            #night_vision_mode:hover {
                border-color: #00ff00;
                text-shadow: 0 0 10px #00ff00;
            }
            
            #night_vision_mode:disabled {
                background: #2a2a2a;
                color: #666666;
                border-color: #444444;
                text-shadow: none;
            }
            
            #night_vision_mode QAbstractItemView {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 1px solid #00cc00;
                selection-background-color: #004400;
                outline: none;
            }
            
            /* Night Vision Intensity Slider */
            #night_vision_intensity::groove:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #2a2a2a, stop:0.5 #ff6b6b, stop:1 #ff0000);
                height: 6px;
                border-radius: 3px;
                border: 1px solid #555555;
            }
            
            #night_vision_intensity::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #ffffff, stop:1 #ff6b6b);
                border: 2px solid #ff0000;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }
            
            #night_vision_intensity::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #ff0000, stop:1 #ffffff);
                border-color: #ff6b6b;
            }
            
            #night_vision_intensity::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #ff6b6b, stop:1 #ff0000);
                border-radius: 3px;
            }
            
            /* Slider Styling */
            #ethereal_resonance_dial {
                margin: 5px;
            }
            
            #ethereal_resonance_dial::groove:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #2a2a2a, stop:0.5 #4ecdc4, stop:1 #ff6b6b);
                height: 8px;
                border-radius: 4px;
                border: 1px solid #555555;
            }
            
            #ethereal_resonance_dial::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #ffffff, stop:1 #4ecdc4);
                border: 2px solid #00ffff;
                width: 18px;
                height: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }
            
            #ethereal_resonance_dial::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #00ffff, stop:1 #ffffff);
                border-color: #ff6b6b;
            }
            
            #ethereal_resonance_dial::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #4ecdc4, stop:1 #00ffff);
                border-radius: 4px;
            }
            
            #ethereal_resonance_dial::add-page:horizontal {
                background: #2a2a2a;
                border-radius: 4px;
            }
            
            /* Disabled slider */
            #ethereal_resonance_dial:disabled::groove:horizontal {
                background: #2a2a2a;
            }
            
            #ethereal_resonance_dial:disabled::handle:horizontal {
                background: #555555;
                border-color: #333333;
            }
        """
        
        self.setStyleSheet(mystical_stylesheet)
        
    def invoke_silence_veil(self):
        """Weave the ancient silence enchantment upon the ethereal whispers"""
        self.silence_veil_active = not self.silence_veil_active
        if self.echo_projector:
            if self.silence_veil_active:
                self.echo_projector.setVolume(0.0)
                self.silence_enchantment.setText("🔇")
                self.silence_enchantment.setToolTip("Dispel the Silence Veil")
            else:
                self.echo_projector.setVolume(self.ethereal_volume)
                self.silence_enchantment.setText("🔊")
                self.silence_enchantment.setToolTip("Cast Silence Veil")
    
    def attune_ethereal_resonance(self, mystical_strength):
        """Harmonize the ethereal resonance with the cosmic frequencies"""
        self.ethereal_volume = mystical_strength / 100.0
        self.resonance_display.setText(f"{mystical_strength}%")
        
        if self.echo_projector and not self.silence_veil_active:
            self.echo_projector.setVolume(self.ethereal_volume)
        
    def change_vision_mode(self, mode):
        """Transform the mystical vision to different spectral realms"""
        self.current_vision_mode = mode
        print(f"🔮 Vision mode transformed to: {mode}")
        
        if ADVANCED_NIGHT_VISION and self.using_night_vision:
            if mode == "🌙 Normal Vision":
                # Switch back to normal camera view
                self.crystal_vision_orb.show()
                self.night_vision_display.hide()
                if self.night_vision_processor:
                    self.night_vision_processor.stop_processing()
            else:
                # Switch to night vision view
                self.crystal_vision_orb.hide()
                self.night_vision_display.show()
                if self.night_vision_processor:
                    self.night_vision_processor.set_vision_mode(mode)
                    if not self.night_vision_processor.isRunning():
                        self.night_vision_processor.start_processing()
        else:
            # Fallback to basic styling effects
            if mode == "🌙 Normal Vision":
                self.vision_processor_timer.stop()
            else:
                self.vision_processor_timer.start(33)  # ~30 FPS processing
            
    def adjust_night_vision_intensity(self, intensity):
        """Amplify the mystical night vision power"""
        self.night_vision_power = intensity
        print(f"🔥 Night vision power set to: {intensity}/10")
        
        if ADVANCED_NIGHT_VISION and self.night_vision_processor:
            self.night_vision_processor.set_intensity(intensity)
        
    def process_mystical_vision(self):
        """Apply mystical night vision enhancements to the scrying vision"""
        if self.current_vision_mode == "🌙 Normal Vision":
            return
            
        if ADVANCED_NIGHT_VISION:
            # Advanced night vision with OpenCV
            self.apply_advanced_night_vision()
        else:
            # Basic night vision using Qt effects
            self.apply_basic_night_vision()
            
    def apply_basic_night_vision(self):
        """Apply basic night vision effects using Qt styling"""
        # Apply different visual filters through CSS-like effects
        mode = self.current_vision_mode
        intensity = self.night_vision_power / 10.0
        
        # This is a simplified approach using Qt stylesheet filters
        filter_style = ""
        
        if mode == "🔮 Mystical Green":
            # Green tint filter
            filter_style = f"""
                #crystal_vision_orb {{
                    border: 3px solid #00ff00;
                    background-color: rgba(0, 255, 0, {int(intensity * 20)});
                }}
            """
        elif mode == "🌡️ Thermal Sight":
            # Red/orange thermal effect
            filter_style = f"""
                #crystal_vision_orb {{
                    border: 3px solid #ff4500;
                    background-color: rgba(255, 69, 0, {int(intensity * 15)});
                }}
            """
        elif mode == "⚡ Enhanced Low-Light":
            # Bright cyan enhancement
            filter_style = f"""
                #crystal_vision_orb {{
                    border: 3px solid #00ffff;
                    background-color: rgba(0, 255, 255, {int(intensity * 10)});
                }}
            """
        elif mode == "🎭 Edge Detection":
            # High contrast white border
            filter_style = f"""
                #crystal_vision_orb {{
                    border: 3px solid #ffffff;
                    background-color: rgba(255, 255, 255, {int(intensity * 5)});
                }}
            """
        elif mode == "👻 Spectral Vision":
            # Purple mystical effect
            filter_style = f"""
                #crystal_vision_orb {{
                    border: 3px solid #9966ff;
                    background-color: rgba(153, 102, 255, {int(intensity * 12)});
                }}
            """
        
        # Apply the filter
        if filter_style:
            current_style = self.styleSheet()
            # Remove old crystal_vision_orb styling and add new
            lines = current_style.split('\n')
            new_style_lines = []
            skip_until_brace = False
            
            for line in lines:
                if '#crystal_vision_orb {' in line:
                    skip_until_brace = True
                    continue
                elif skip_until_brace and '}' in line:
                    skip_until_brace = False
                    continue
                elif not skip_until_brace:
                    new_style_lines.append(line)
            
            new_style = '\n'.join(new_style_lines) + filter_style
            self.setStyleSheet(new_style)
            
    def apply_advanced_night_vision(self):
        """Apply advanced night vision using OpenCV (when available)"""
        # This would implement real computer vision filters
        # For now, it's a placeholder that could be expanded
        print(f"🔮 Applying advanced {self.current_vision_mode} at power {self.night_vision_power}")
        
        # In a full implementation, this would:
        # 1. Capture frames from the camera
        # 2. Apply OpenCV filters (histogram equalization, color space conversion, etc.)
        # 3. Display the processed frames
        # 4. Implement real night vision algorithms
        
    def enable_night_vision_controls(self, enabled):
        """Enable or disable the mystical night vision enchantments"""
        self.night_vision_mode.setEnabled(enabled)
        self.night_vision_intensity.setEnabled(enabled)
        self.using_night_vision = enabled
        
        if enabled and ADVANCED_NIGHT_VISION:
            # Initialize night vision processor
            if not self.night_vision_processor:
                self.night_vision_processor = NightVisionProcessor()
                self.night_vision_processor.frameProcessed.connect(self.night_vision_display.display_frame)
                # Use the same camera index (assuming first camera)
                self.night_vision_processor.set_camera_index(0)
                self.night_vision_processor.set_vision_mode(self.current_vision_mode)
                self.night_vision_processor.set_intensity(self.night_vision_power)
            print("🌙 Advanced night vision enchantments activated!")
        elif enabled:
            print("🌙 Basic night vision enchantments activated!")
        else:
            print("🌞 Night vision enchantments sealed")
            self.night_vision_mode.setCurrentText("🌙 Normal Vision")
            self.vision_processor_timer.stop()
            
            # Stop night vision processor
            if self.night_vision_processor:
                self.night_vision_processor.stop_processing()
                
            # Show normal camera view
            self.crystal_vision_orb.show()
            self.night_vision_display.hide()
        
    def commence_mystical_sight(self):
        """Awaken the ancient scrying eye and channel ethereal whispers"""
        try:
            # Seek the mystical vision devices
            vision_artifacts = QMediaDevices.videoInputs()
            if not vision_artifacts:
                self.oracle_proclamation.setText("❌ No Scrying Eyes detected in the mystical realm")
                return
                
            # Bind to the first vision artifact
            primary_eye = vision_artifacts[0]
            self.oracle_proclamation.setText(f"🔮 Awakening the Scrying Eye: {primary_eye.description()}")
            
            # Forge the mystical scrying eye
            self.scrying_eye = QCamera(primary_eye)
            
            # Create the vision conduit
            self.vision_conduit = QMediaCaptureSession()
            self.vision_conduit.setCamera(self.scrying_eye)
            self.vision_conduit.setVideoOutput(self.crystal_vision_orb)
            
            # Seek whisper-gathering artifacts, prioritizing the camera's integrated whisper channel
            whisper_artifacts = QMediaDevices.audioInputs()
            camera_whisper_channel = None
            
            if whisper_artifacts:
                # First, try to find the camera's integrated microphone
                camera_name = primary_eye.description().lower()
                print(f"🔍 Seeking whisper channel for camera: '{camera_name}'")
                
                # Enhanced matching with specific priority for HD camera + HD audio
                best_match_score = 0
                best_match_device = None
                
                for i, whisper_artifact in enumerate(whisper_artifacts):
                    whisper_name = whisper_artifact.description().lower()
                    print(f"  📡 Examining whisper channel {i}: '{whisper_name}'")
                    
                    match_score = 0
                    match_reasons = []
                    
                    # HIGHEST PRIORITY: HD camera + HD audio match
                    if "hd" in camera_name and "hd" in whisper_name and ("audio" in whisper_name or "microphone" in whisper_name):
                        match_score = 100
                        match_reasons.append("HD camera + HD audio perfect match")
                    
                    # HIGH PRIORITY: Direct name inclusion
                    elif camera_name in whisper_name or whisper_name in camera_name:
                        match_score = 90
                        match_reasons.append("Direct name inclusion")
                    
                    # MEDIUM PRIORITY: Shared significant words
                    else:
                        camera_words = [w for w in camera_name.split() if len(w) > 3]
                        whisper_words = [w for w in whisper_name.split() if len(w) > 3]
                        
                        shared_words = set(camera_words) & set(whisper_words)
                        if shared_words:
                            match_score = 50 + len(shared_words) * 10
                            match_reasons.append(f"Shared words: {', '.join(shared_words)}")
                    
                    # SPECIAL CASE: Prefer later devices (often camera mics) over Blue Snowball
                    if "blue" in whisper_name and "snowball" in whisper_name:
                        match_score = max(0, match_score - 30)  # Penalty for external mic
                        match_reasons.append("External USB mic penalty")
                    elif i > 0:  # Later in the list often means integrated camera mic
                        match_score += 5
                        match_reasons.append("Later device bonus")
                    
                    print(f"    📊 Match score: {match_score} - {'; '.join(match_reasons) if match_reasons else 'No match'}")
                    
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_device = whisper_artifact
                        print(f"    ⭐ New best match!")
                
                if best_match_device and best_match_score > 0:
                    camera_whisper_channel = best_match_device
                    print(f"  ✨ Selected camera's whisper channel (score {best_match_score}): {camera_whisper_channel.description()}")
                else:
                    # Final fallback: prefer the last device (likely camera mic) over first (often external)
                    camera_whisper_channel = whisper_artifacts[-1]
                    print(f"  🎤 No good match found - using last device (often camera mic): {camera_whisper_channel.description()}")
            
            # Channel ethereal whispers if a whisper artifact was found
            if camera_whisper_channel:
                print(f"🎵 Attuning to whispers from: {camera_whisper_channel.description()}")
                
                # Forge whisper collector and echo projector
                self.whisper_collector = QAudioInput(camera_whisper_channel)
                self.echo_projector = QAudioOutput()
                
                # Set initial ethereal resonance
                self.echo_projector.setVolume(self.ethereal_volume)
                
                # Bind whispers to the vision conduit
                self.vision_conduit.setAudioInput(self.whisper_collector)
                self.vision_conduit.setAudioOutput(self.echo_projector)
                
                # Empower the mystical sound controls
                self.silence_enchantment.setEnabled(True)
                self.ethereal_resonance_dial.setEnabled(True)
                
                # Awaken the night vision enchantments
                self.enable_night_vision_controls(True)
                
                proclamation_of_success = f"✨ The Great Scrying Vision + Ethereal Whispers + Night Vision manifest: {primary_eye.description()}"
            else:
                proclamation_of_success = f"✨ The Scrying Vision + Night Vision manifests (whispers remain silent): {primary_eye.description()}"
                print("🔇 No whisper-gathering artifacts found in this realm")
                
                # Still enable night vision even without audio
                self.enable_night_vision_controls(True)
            
            # Invoke the ancient sight ritual
            self.scrying_eye.start()
            
            # Transform the sacred interface
            self.awakening_ritual.setEnabled(False)
            self.banishment_ritual.setEnabled(True)
            self.oracle_proclamation.setText(proclamation_of_success)
            
            print(f"👁️ Scrying Eye awakened: {primary_eye.description()}")
            if camera_whisper_channel:
                print(f"🎧 Ethereal whispers channeled: {camera_whisper_channel.description()}")
            
        except Exception as mystical_disturbance:
            self.oracle_proclamation.setText(f"❌ Mystical Disturbance: {mystical_disturbance}")
            print(f"⚠️ Vision/Whisper mystical disturbance: {mystical_disturbance}")
            
    def cease_mystical_sight(self):
        """Seal the vision portal and silence the ethereal whispers"""
        try:
            if self.scrying_eye:
                self.scrying_eye.stop()
                self.scrying_eye = None
                
            if self.vision_conduit:
                self.vision_conduit = None
                
            if self.whisper_collector:
                self.whisper_collector = None
                
            if self.echo_projector:
                self.echo_projector = None
                
            # Dispel all sound enchantments
            self.silence_veil_active = False
            self.silence_enchantment.setText("🔊")
            self.silence_enchantment.setToolTip("Cast Silence Veil / Dispel Silence")
            
            # Seal the mystical sound controls
            self.silence_enchantment.setEnabled(False)
            self.ethereal_resonance_dial.setEnabled(False)
            
            # Seal the night vision enchantments
            self.enable_night_vision_controls(False)
            
            # Clean up night vision processor
            if self.night_vision_processor:
                self.night_vision_processor.stop_processing()
                self.night_vision_processor = None
                
            # Restore the sacred interface
            self.awakening_ritual.setEnabled(True)
            self.banishment_ritual.setEnabled(False)
            self.oracle_proclamation.setText("🔮 The Vision Portal has been sealed, whispers fade to silence")
            
            print("🚪 The mystical sight and ethereal whispers have been banished")
            
        except Exception as banishment_failure:
            self.oracle_proclamation.setText(f"❌ Banishment Ritual Failed: {banishment_failure}")
            print(f"⚠️ Banishment ritual error: {banishment_failure}")
            
    def closeEvent(self, mystical_departure):
        """Perform final banishment when the mystical window closes"""
        self.cease_mystical_sight()
        mystical_departure.accept()

def invoke_the_ancient_vision_portal():
    mystical_application = QApplication(sys.argv)
    
    # Seek the sacred scrying eyes within the realm
    vision_artifacts = QMediaDevices.videoInputs()
    print(f"👁️ Discovered {len(vision_artifacts)} mystical scrying eye(s) in the ethereal realm")
    for i, artifact in enumerate(vision_artifacts):
        print(f"  📹 Scrying Eye {i}: {artifact.description()}")
    
    # Seek the whisper-gathering enchantments
    whisper_artifacts = QMediaDevices.audioInputs()
    print(f"🎤 Discovered {len(whisper_artifacts)} ethereal whisper channel(s)")
    for i, artifact in enumerate(whisper_artifacts):
        print(f"  🎵 Whisper Channel {i}: {artifact.description()}")
    
    if not vision_artifacts:
        print("❌ No scrying eyes detected in this realm. Please summon a vision artifact and attempt the ritual again.")
        return 1
    
    if not whisper_artifacts:
        print("⚠️  No whisper channels detected. The vision will manifest without ethereal sounds.")
    
    # Manifest the mystical vision orb
    mystical_orb = MysticVisionOrb()
    mystical_orb.show()
    
    return mystical_application.exec()

if __name__ == "__main__":
    sys.exit(invoke_the_ancient_vision_portal())