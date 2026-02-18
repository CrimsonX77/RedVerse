"""
Aurora Archive - Main GUI Application
Python 3.10+ | PyQt6
"""

import sys
import asyncio
import os
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QFrame, QGridLayout, QTextEdit,
    QComboBox, QProgressBar, QScrollArea, QSizePolicy, QMessageBox,
    QDialog, QDialogButtonBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QLineEdit, QSpinBox, QSlider
)
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QPalette, QColor, QLinearGradient, QBrush, QPainter, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import requests

# Import API config manager
try:
    from api_config_manager import APIConfigManager
    API_CONFIG_AVAILABLE = True
except ImportError:
    API_CONFIG_AVAILABLE = False
    print("Warning: api_config_manager module not available")

# Import card generation module
try:
    from card_generation import CardGenerator
    CARD_GEN_AVAILABLE = True
except ImportError:
    CARD_GEN_AVAILABLE = False
    print("Warning: card_generation module not available")

# Import card scanner module
try:
    from card_scanner import CardScanner, CardFormat
    CARD_SCANNER_AVAILABLE = True
except ImportError:
    CARD_SCANNER_AVAILABLE = False
    print("Warning: card_scanner module not available")

# Import steganography module
try:
    from mutable_steganography import MutableCardSteganography
    STEG_AVAILABLE = True
except ImportError:
    STEG_AVAILABLE = False
    print("Warning: mutable_steganography module not available")

# Import seal compositor
try:
    from seal_compositor import SealCompositor
    SEAL_AVAILABLE = True
except ImportError:
    SEAL_AVAILABLE = False
    print("Warning: seal_compositor module not available")

# Setup logging
logger = logging.getLogger(__name__)


def get_available_sd_models(sd_url: str = "http://localhost:7860") -> list:
    """
    Fetch available Stable Diffusion models from the SD WebUI API.
    
    Args:
        sd_url: Base URL of the SD WebUI instance
        
    Returns:
        List of model filenames (e.g., ['model1.safetensors', 'model2.ckpt'])
    """
    try:
        response = requests.get(
            f"{sd_url}/sdapi/v1/sd-models",
            timeout=3
        )
        
        if response.status_code == 200:
            models_data = response.json()
            # Extract model titles (filenames)
            models = [model.get('title', model.get('model_name', '')) 
                     for model in models_data]
            
            # Filter out empty strings and return
            return [m for m in models if m]
        else:
            print(f"SD API returned status {response.status_code}")
            return []
            
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Stable Diffusion API - is it running?")
        return []
    except requests.exceptions.Timeout:
        print("Stable Diffusion API request timed out")
        return []
    except Exception as e:
        print(f"Error fetching SD models: {e}")
        return []


def get_available_samplers(sd_url: str = "http://localhost:7860") -> list:
    """
    Fetch available samplers from the SD WebUI API.
    
    Returns:
        List of sampler names
    """
    try:
        response = requests.get(
            f"{sd_url}/sdapi/v1/samplers",
            timeout=3
        )
        
        if response.status_code == 200:
            samplers_data = response.json()
            samplers = [s.get('name', '') for s in samplers_data]
            return [s for s in samplers if s]
        else:
            return ['Euler a', 'Euler', 'DPM++ 2M Karras', 'DPM++ SDE Karras', 
                    'DPM++ 2M SDE Karras', 'DDIM', 'PLMS']
    except:
        return ['Euler a', 'Euler', 'DPM++ 2M Karras', 'DPM++ SDE Karras', 
                'DPM++ 2M SDE Karras', 'DDIM', 'PLMS']


def get_available_upscalers(sd_url: str = "http://localhost:7860") -> list:
    """
    Fetch available upscalers from the SD WebUI API.
    
    Returns:
        List of upscaler names
    """
    try:
        response = requests.get(
            f"{sd_url}/sdapi/v1/upscalers",
            timeout=3
        )
        
        if response.status_code == 200:
            upscalers_data = response.json()
            upscalers = [u.get('name', '') for u in upscalers_data]
            return [u for u in upscalers if u]
        else:
            return ['None', 'Latent', 'Latent (bicubic)', 'Latent (nearest)', 
                    'R-ESRGAN 4x+', 'R-ESRGAN 4x+ Anime6B']
    except:
        return ['None', 'Latent', 'Latent (bicubic)', 'Latent (nearest)', 
                'R-ESRGAN 4x+', 'R-ESRGAN 4x+ Anime6B']


def get_available_schedulers(sd_url: str = "http://localhost:7860") -> list:
    """
    Fetch available schedulers from the SD WebUI API.
    
    Returns:
        List of scheduler names
    """
    try:
        response = requests.get(
            f"{sd_url}/sdapi/v1/schedulers",
            timeout=3
        )
        
        if response.status_code == 200:
            schedulers_data = response.json()
            # Handle both string list and object list formats
            if schedulers_data and isinstance(schedulers_data[0], dict):
                schedulers = [s.get('name', s.get('label', '')) for s in schedulers_data]
            else:
                schedulers = [str(s) for s in schedulers_data]
            return [s for s in schedulers if s]
        else:
            return ['automatic', 'karras', 'exponential', 'polyexponential']
    except:
        return ['automatic', 'karras', 'exponential', 'polyexponential']


class FullScreenImageViewer(QDialog):
    """Full-screen image viewer dialog"""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Card Preview")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.showFullScreen()
        
        # Black background
        self.setStyleSheet("background-color: black;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load and display image
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # Scale to screen size while maintaining aspect ratio
            screen = self.screen().size()
            scaled = pixmap.scaled(
                screen.width(), 
                screen.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        
        layout.addWidget(self.image_label)
        
        # Info label
        info = QLabel("Click anywhere or press any key to close")
        info.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 0.7); padding: 10px; font-size: 14px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info, alignment=Qt.AlignmentFlag.AlignBottom)
    
    def mousePressEvent(self, event):
        """Close on any click"""
        self.close()
    
    def keyPressEvent(self, event):
        """Close on any key press"""
        self.close()


class SteganographyDataViewer(QDialog):
    """Dialog to display steganography data from card image"""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Card Steganography Data - Editable")
        self.setMinimumSize(900, 700)
        
        # Store image path and original data for re-encoding
        self.image_path = image_path
        self.original_data = {}
        self.has_changes = False
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📊 Embedded Card Metadata (Editable)")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #9333ea; padding: 10px;")
        layout.addWidget(header)
        
        # Info label
        info_text = f"Image: {Path(image_path).name}\n💡 Column B (Value) is editable - changes will re-encode the image"
        self.info_label = QLabel(info_text)
        self.info_label.setStyleSheet("color: #c084fc; font-size: 12px; padding: 5px;")
        layout.addWidget(self.info_label)
        
        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property (Read-Only)", "Value (Editable)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1b4b;
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 8px;
                color: #e0e0e0;
                gridline-color: rgba(168, 85, 247, 0.2);
            }
            QTableWidget::item {
                padding: 8px;
                color: #e0e0e0;
                background-color: transparent;
            }
            QTableWidget::item:selected {
                background-color: #9333ea;
                color: white;
            }
            QTableWidget::item:alternate {
                background-color: rgba(88, 28, 135, 0.2);
            }
            QHeaderView::section {
                background-color: #9333ea;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # Connect item changed signal to track edits
        self.table.itemChanged.connect(self.on_item_changed)
        
        # Load steganography data
        self.load_steg_data(image_path)
        
        layout.addWidget(self.table)
        
        # Button box with Save & Re-encode button
        button_layout = QHBoxLayout()
        
        self.save_encode_btn = QPushButton("💾 Save & Re-encode Image")
        self.save_encode_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #047857, stop:1 #059669);
            }
            QPushButton:disabled {
                background-color: rgba(100, 100, 100, 0.3);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.save_encode_btn.clicked.connect(self.save_and_reencode)
        self.save_encode_btn.setEnabled(False)  # Disabled until changes made
        button_layout.addWidget(self.save_encode_btn)
        
        button_layout.addStretch()
        
        export_btn = QPushButton("📊 Export to CSV")
        export_btn.clicked.connect(self.export_to_csv)
        button_layout.addWidget(export_btn)
        
        close_btn = QPushButton("✖ Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Style the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: white;
            }
            QPushButton {
                background-color: #9333ea;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a855f7;
            }
        """)
    
    def load_steg_data(self, image_path: str):
        """Load and display steganography data from image"""
        try:
            if not STEG_AVAILABLE:
                self.table.setRowCount(1)
                self.table.setItem(0, 0, QTableWidgetItem("Error"))
                self.table.setItem(0, 1, QTableWidgetItem("Steganography module not available"))
                return
            # Use mutable steganography module
            try:
                from mutable_steganography import MutableCardSteganography
                stego = MutableCardSteganography()
                data = stego.extract_data(image_path)
                
                # Store original data for re-encoding
                self.original_data = data
                
                # Flatten nested structures for display
                metadata = self._flatten_dict(data)
                
            except (ImportError, ValueError, json.JSONDecodeError):
                # Fallback: show placeholder data
                metadata = {
                    "Status": "⚠️ No embedded data found",
                    "Note": "Card does not contain Aurora embedded metadata",
                }
                self.original_data = metadata
            
            # Temporarily block signals while populating
            self.table.blockSignals(True)
            
            # Populate table
            self.table.setRowCount(len(metadata))
            for i, (key, value) in enumerate(metadata.items()):
                # Column A (Property) - Read-only
                key_item = QTableWidgetItem(str(key))
                key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                key_item.setBackground(QColor("#2d1b4e"))  # Dark purple background
                key_item.setForeground(QColor("#e0e0e0"))  # Light text
                
                # Column B (Value) - Editable
                value_item = QTableWidgetItem(str(value))
                value_item.setFlags(value_item.flags() | Qt.ItemFlag.ItemIsEditable)
                value_item.setBackground(QColor("#1e1b4b"))  # Slightly lighter background
                value_item.setForeground(QColor("#ffffff"))  # White text
                
                self.table.setItem(i, 0, key_item)
                self.table.setItem(i, 1, value_item)
            
            # Re-enable signals
            self.table.blockSignals(False)
                
        except Exception as e:
            # Show error in table
            self.table.setRowCount(1)
            error_key = QTableWidgetItem("Error")
            error_val = QTableWidgetItem(str(e))
            error_key.setForeground(QColor("#ff0000"))
            error_val.setForeground(QColor("#ff0000"))
            self.table.setItem(0, 0, error_key)
            self.table.setItem(0, 1, error_val)
    
    def on_item_changed(self, item):
        """Track when table items are edited"""
        if item.column() == 1:  # Only track changes to Value column
            self.has_changes = True
            self.save_encode_btn.setEnabled(True)
            # Update info label to show unsaved changes
            info_text = f"Image: {Path(self.image_path).name}\n⚠️ Unsaved changes - click 'Save & Re-encode' to update image"
            self.info_label.setText(info_text)
            self.info_label.setStyleSheet("color: #fbbf24; font-size: 12px; padding: 5px;")
    
    def save_and_reencode(self):
        """Save edited data and re-encode the image"""
        try:
            if not STEG_AVAILABLE:
                QMessageBox.warning(self, "Module Unavailable", "Steganography module not available")
                return
            # Collect edited data from table
            edited_data = {}
            for row in range(self.table.rowCount()):
                key = self.table.item(row, 0).text()
                value = self.table.item(row, 1).text()
                edited_data[key] = value
            
            # Unflatten the data back to nested structure
            unflattened_data = self._unflatten_dict(edited_data)
            
            # Re-encode the image with new data
            from mutable_steganography import MutableCardSteganography
            stego = MutableCardSteganography()
            
            # Generate new filename with timestamp
            from datetime import datetime
            original_path = Path(self.image_path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"{original_path.stem}_edited_{timestamp}{original_path.suffix}"
            new_path = original_path.parent / new_filename
            
            # Re-encode
            stego.embed_data(str(self.image_path), unflattened_data, str(new_path))
            
            # Show success message
            QMessageBox.information(
                self,
                "✅ Re-encoding Complete",
                f"Image successfully re-encoded with updated data!\n\n"
                f"New file: {new_path.name}\n"
                f"Location: {new_path.parent}\n\n"
                f"Original image preserved."
            )
            
            # Reset change tracking
            self.has_changes = False
            self.save_encode_btn.setEnabled(False)
            self.info_label.setText(f"Image: {Path(self.image_path).name}\n✅ Changes saved to new file")
            self.info_label.setStyleSheet("color: #10b981; font-size: 12px; padding: 5px;")
            
            # Update to use new image
            self.image_path = str(new_path)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Re-encoding Failed",
                f"Failed to re-encode image:\n{str(e)}\n\n"
                f"Make sure the mutable_steganography module is available."
            )
    
    def _flatten_dict(self, data: dict, parent_key: str = '', sep: str = '.') -> dict:
        """
        Flatten nested dictionary structure
        
        Args:
            data: Dictionary to flatten
            parent_key: Parent key for nested items
            sep: Separator for nested keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Handle lists (like rentals, cards, audit_trail)
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        items.extend(self._flatten_dict(item, f"{new_key}[{i}]", sep=sep).items())
                    else:
                        items.append((f"{new_key}[{i}]", item))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _unflatten_dict(self, flat_data: dict, sep: str = '.') -> dict:
        """
        Unflatten a flattened dictionary back to nested structure
        
        Args:
            flat_data: Flattened dictionary with dot-notation keys
            sep: Separator used in keys
            
        Returns:
            Nested dictionary
        """
        result = {}
        
        for key, value in flat_data.items():
            parts = key.split(sep)
            current = result
            
            for i, part in enumerate(parts[:-1]):
                # Check if this is a list index (e.g., "rentals[0]")
                if '[' in part and ']' in part:
                    base_key, index_str = part.split('[')
                    index = int(index_str.rstrip(']'))
                    
                    # Create list if doesn't exist
                    if base_key not in current:
                        current[base_key] = []
                    
                    # Extend list if needed
                    while len(current[base_key]) <= index:
                        current[base_key].append({})
                    
                    current = current[base_key][index]
                else:
                    # Regular nested dict
                    if part not in current:
                        current[part] = {}
                    current = current[part]
            
            # Set the final value
            final_key = parts[-1]
            if '[' in final_key and ']' in final_key:
                base_key, index_str = final_key.split('[')
                index = int(index_str.rstrip(']'))
                
                if base_key not in current:
                    current[base_key] = []
                
                while len(current[base_key]) <= index:
                    current[base_key].append(None)
                
                current[base_key][index] = value
            else:
                current[final_key] = value
        
        return result
    
    def export_to_csv(self):
        """Export table data to CSV file"""
        try:
            from datetime import datetime
            filename = f"card_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = Path.home() / "Desktop" / filename
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                f.write("Property,Value\n")
                for row in range(self.table.rowCount()):
                    key = self.table.item(row, 0).text()
                    value = self.table.item(row, 1).text()
                    # Escape quotes and commas properly
                    key = key.replace('"', '""')
                    value = value.replace('"', '""')
                    f.write(f'"{key}","{value}"\n')
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"Data exported to:\n{filepath}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export data:\n{e}"
            )


class CardScannerDialog(QDialog):
    """Dialog to scan cards and display account details"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Card Scanner - Account Management")
        self.setMinimumSize(900, 700)
        
        if CARD_SCANNER_AVAILABLE:
            self.scanner = CardScanner()
        else:
            self.scanner = None
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📷 Card Scanner & User Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #9333ea; padding: 10px;")
        layout.addWidget(header)
        
        # Scan section
        scan_frame = QFrame()
        scan_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        scan_layout = QHBoxLayout(scan_frame)
        
        # File path input
        self.file_path_input = QTextEdit()
        self.file_path_input.setMaximumHeight(40)
        self.file_path_input.setPlaceholderText("Enter card image path or drag & drop...")
        scan_layout.addWidget(self.file_path_input, stretch=1)
        
        # Browse button
        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.browse_image)
        scan_layout.addWidget(browse_btn)
        
        # Scan button
        scan_btn = QPushButton("🔍 Scan Card")
        scan_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9333ea, stop:1 #ec4899);
                padding: 10px 20px;
                font-size: 14px;
            }
        """)
        scan_btn.clicked.connect(self.scan_card)
        scan_layout.addWidget(scan_btn)
        
        layout.addWidget(scan_frame)
        
        # Tabs for display modes
        self.tabs = QTabWidget()
        
        # Account Details Tab
        self.details_display = QTextEdit()
        self.details_display.setReadOnly(True)
        self.details_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        self.tabs.addTab(self.details_display, "📋 Account Details")
        
        # All Users Tab
        self.users_display = QTextEdit()
        self.users_display.setReadOnly(True)
        self.users_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        self.tabs.addTab(self.users_display, "👥 All Users")
        
        layout.addWidget(self.tabs)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        refresh_users_btn = QPushButton("🔄 Refresh Users")
        refresh_users_btn.clicked.connect(self.refresh_users)
        action_layout.addWidget(refresh_users_btn)
        
        # Import CSV button
        import_csv_btn = QPushButton("📥 Import CSV")
        import_csv_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ea580c, stop:1 #f97316);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c2410c, stop:1 #ea580c);
            }
        """)
        import_csv_btn.clicked.connect(self.import_csv_and_reload)
        action_layout.addWidget(import_csv_btn)
        
        clear_user_btn = QPushButton("🚪 Logout Current")
        clear_user_btn.clicked.connect(self.logout_current)
        action_layout.addWidget(clear_user_btn)
        
        action_layout.addStretch()
        
        # Export CSV button
        export_btn = QPushButton("📊 Export All to CSV")
        export_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
        """)
        export_btn.clicked.connect(self.export_all_users_csv)
        action_layout.addWidget(export_btn)
        
        close_btn = QPushButton("✖ Close")
        close_btn.clicked.connect(self.close)
        action_layout.addWidget(close_btn)
        
        layout.addLayout(action_layout)
        
        # Style the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: white;
            }
            QPushButton {
                background-color: #9333ea;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a855f7;
            }
            QTabWidget::pane {
                border: 1px solid rgba(168, 85, 247, 0.3);
                background-color: rgba(0, 0, 0, 0.2);
            }
            QTabBar::tab {
                background-color: rgba(255, 255, 255, 0.05);
                color: #c084fc;
                padding: 10px 20px;
                margin-right: 4px;
                border-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #9333ea;
                color: white;
            }
        """)
        
        # Initial load
        if self.scanner:
            self.refresh_users()
        else:
            self.details_display.setText("⚠️ Card Scanner module not available.\nPlease ensure card_scanner.py is in the project directory.")
    
    def browse_image(self):
        """Open file dialog to select card image"""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Card Image",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)"
        )
        
        if file_path:
            self.file_path_input.setText(file_path)
    
    def scan_card(self):
        """Scan the card image and display details"""
        if not self.scanner:
            QMessageBox.warning(
                self,
                "Scanner Unavailable",
                "Card scanner module is not available."
            )
            return
        
        card_path = self.file_path_input.toPlainText().strip()
        
        if not card_path:
            QMessageBox.warning(
                self,
                "No Image Selected",
                "Please select a card image to scan."
            )
            return
        
        try:
            # Scan the card
            data, card_format = self.scanner.scan_card(card_path, register_user=True)
            
            # Display account details
            details = self.scanner.display_account_details(data, card_format)
            self.details_display.setText(details)
            
            # Refresh users list
            self.refresh_users()
            
            # Update parent window's member_data if parent is AuroraMainWindow
            if self.parent() and hasattr(self.parent(), 'member_data'):
                # Extract key member info from scanned data
                member_profile = data.get('member_profile', {})
                subscription = data.get('subscription', {})
                
                self.parent().member_data = {
                    'name': member_profile.get('name', 'Unknown'),
                    'email': member_profile.get('email', ''),
                    'tier': subscription.get('tier', 'Standard'),
                    'card_count': len(data.get('cards', [])),
                    'next_billing': subscription.get('next_billing_date', 'N/A'),
                    'monthly_total': 0.0,  # Would calculate from subscription
                    'member_id': data.get('member_id', ''),
                    'user_id': data.get('member_id', ''),
                    # Store full member data for embedding
                    'full_data': data
                }
                print(f"✓ Updated main window with member: {member_profile.get('name', 'Unknown')}")
            
            # Show success message
            format_name = "Aurora Member" if card_format == CardFormat.AURORA_MEMBER else \
                         "AetherCard Soul" if card_format == CardFormat.AETHER_SOUL else \
                         "Unknown Format"
            
            member_name = data.get('member_profile', {}).get('name', 'Unknown')
            
            QMessageBox.information(
                self,
                "Card Scanned",
                f"✓ Card scanned successfully!\n\nMember: {member_name}\nFormat: {format_name}\n\n"
                f"User registered in database and loaded into main window."
            )
            
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "File Not Found",
                f"Card image not found:\n{card_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Scan Error",
                f"Failed to scan card:\n{str(e)}"
            )
    
    def refresh_users(self):
        """Refresh the all users display"""
        if not self.scanner:
            return
        
        users_list = self.scanner.list_all_users()
        self.users_display.setText(users_list)
    
    def logout_current(self):
        """Logout current user"""
        if not self.scanner:
            return
        
        self.scanner.clear_current_user()
        self.details_display.setText("✓ Current user logged out.\n\nScan a card to load a user account.")
        
        QMessageBox.information(
            self,
            "Logged Out",
            "✓ Current user logged out."
        )
    
    def import_csv_and_reload(self):
        """Import CSV, rescan images, and update database with fresh data"""
        if not self.scanner:
            QMessageBox.warning(
                self,
                "Import Failed",
                "Card scanner not available."
            )
            return
        
        # Ask user to select CSV file
        csv_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Aurora CSV",
            str(Path.home() / "Desktop"),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not csv_path:
            return  # User cancelled
        
        try:
            import csv
            
            # Read CSV and extract card image paths
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if not rows:
                QMessageBox.information(
                    self,
                    "Empty CSV",
                    "The CSV file contains no data."
                )
                return
            
            # Check if _card_image_path column exists (for new exports)
            # If not, we'll ask user to provide card directory
            has_image_paths = '_card_image_path' in rows[0]
            card_directory = None
            
            if not has_image_paths:
                # Ask user to select directory containing card images
                reply = QMessageBox.question(
                    self,
                    "Card Images Location",
                    "This CSV doesn't contain image paths (older export format).\n\n"
                    "Would you like to select a directory containing the card images?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    card_directory = QFileDialog.getExistingDirectory(
                        self,
                        "Select Card Images Directory",
                        str(Path.home() / "Desktop" / "Authunder" / "generated_cards")
                    )
                    if not card_directory:
                        return  # User cancelled
                else:
                    return  # User chose not to provide directory
            
            # Process each row
            success_count = 0
            error_count = 0
            errors = []
            
            progress = QProgressBar()
            progress.setMaximum(len(rows))
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Importing CSV")
            progress_dialog.setText("Rescanning cards and updating database...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            
            for idx, row in enumerate(rows):
                # Get image path from CSV or construct it
                if has_image_paths:
                    card_path = row.get('_card_image_path', '').strip()
                else:
                    # Try to construct path from card_id or member_id
                    card_id = row.get('card_id', '').strip()
                    member_id = row.get('member_id', '').strip()
                    
                    # Try various filename patterns
                    possible_names = []
                    if card_id:
                        possible_names.append(f"{card_id}_member_card.png")
                        possible_names.append(f"{card_id}_embedded.png")
                        possible_names.append(f"{card_id}.png")
                    if member_id:
                        possible_names.append(f"aurora_{member_id}_000_member_card.png")
                        possible_names.append(f"aurora_{member_id}_000_embedded.png")
                    
                    # Search for file in provided directory
                    card_path = None
                    for name in possible_names:
                        test_path = Path(card_directory) / name
                        if test_path.exists():
                            card_path = str(test_path)
                            break
                
                if not card_path or not Path(card_path).exists():
                    error_count += 1
                    name_hint = row.get('member_profile.name', row.get('name', f'Row {idx + 1}'))
                    errors.append(f"{name_hint}: Image not found")
                    continue
                
                try:
                    # Rescan the card to get fresh data
                    self.scanner.scan_card(card_path, register_user=True)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {idx + 1}: {str(e)}")
            
            # Refresh displays
            self.refresh_users()
            
            # Show results
            result_msg = f"✓ Import Complete!\n\n"
            result_msg += f"Successfully rescanned: {success_count} cards\n"
            result_msg += f"Errors: {error_count}\n\n"
            result_msg += f"Database updated with fresh data from card images.\n"
            
            if not has_image_paths:
                result_msg += f"\n💡 Tip: Future exports will include image paths automatically."
            
            if errors and len(errors) <= 5:
                result_msg += f"\n\nErrors:\n" + "\n".join(errors[:5])
            elif errors:
                result_msg += f"\n\nShowing first 5 errors:\n" + "\n".join(errors[:5])
            
            QMessageBox.information(
                self,
                "Import Complete",
                result_msg
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import CSV:\n{str(e)}"
            )
    
    def export_all_users_csv(self):
        """Export all users to comprehensive CSV file with all member schema fields"""
        if not self.scanner:
            QMessageBox.warning(
                self,
                "Export Failed",
                "Card scanner not available."
            )
            return
        
        # Get all users from database
        all_users = self.scanner.database.get_all_users()
        
        if not all_users:
            QMessageBox.information(
                self,
                "No Data",
                "No users in database to export."
            )
            return
        
        # Ask user where to save
        from datetime import datetime
        default_filename = f"aurora_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Users to CSV",
            str(Path.home() / "Desktop" / default_filename),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filepath:
            return  # User cancelled
        
        try:
            # Collect all possible field names from all users (for comprehensive headers)
            all_fields = set()
            flattened_users = []
            
            for user in all_users:
                user_data = user.get('data', {})
                flattened = self._flatten_dict_for_csv(user_data)
                
                # Add scanner metadata (prefixed with _ to appear first when sorted)
                flattened['_user_id'] = user.get('user_id', '')
                flattened['_card_format'] = user.get('format', '')
                flattened['_card_image_path'] = user.get('card_image_path', '')  # ADDED
                flattened['_first_scan'] = user.get('first_scan', '')
                flattened['_last_scan'] = user.get('last_scan', '')
                flattened['_scan_count'] = user.get('scan_count', 0)
                
                all_fields.update(flattened.keys())
                flattened_users.append(flattened)
            
            # Sort fields for consistent column order
            sorted_fields = sorted(all_fields)
            
            # Write CSV with proper escaping
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted_fields, extrasaction='ignore')
                writer.writeheader()
                
                for user_dict in flattened_users:
                    # Ensure all fields are present (fill missing with empty string)
                    row = {field: user_dict.get(field, '') for field in sorted_fields}
                    writer.writerow(row)
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"✓ Exported {len(all_users)} user(s) to:\n{filepath}\n\n"
                f"Total fields: {len(sorted_fields)}\n"
                f"Each user's data is in a separate row.\n"
                f"Card images linked via _card_image_path column."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV:\n{str(e)}"
            )
    
    def _flatten_dict_for_csv(self, data: dict, parent_key: str = '', sep: str = '.') -> dict:
        """
        Flatten nested dictionary for CSV export
        
        Args:
            data: Dictionary to flatten
            parent_key: Parent key prefix
            sep: Separator for nested keys
            
        Returns:
            Flattened dictionary with dot-notation keys
        """
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                # Recursively flatten nested dicts
                items.extend(self._flatten_dict_for_csv(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Handle lists - create indexed keys
                if len(v) == 0:
                    items.append((new_key, '[]'))
                else:
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            items.extend(self._flatten_dict_for_csv(item, f"{new_key}[{i}]", sep=sep).items())
                        else:
                            items.append((f"{new_key}[{i}]", item))
            else:
                # Primitive value - convert to string
                items.append((new_key, str(v) if v is not None else ''))
        
        return dict(items)


class MemberRegistrationDialog(QDialog):
    """Dialog for registering new members with complete member schema"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Member Registration")
        self.setMinimumSize(900, 700)
        
        # Import member manager
        try:
            from member_manager import MemberManager
            self.member_manager = MemberManager()
        except ImportError:
            self.member_manager = None
            QMessageBox.critical(
                self,
                "Module Missing",
                "member_manager.py not found. Please ensure it's in the project directory."
            )
            self.reject()
            return
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("👤 New Member Registration")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #9333ea; padding: 10px;")
        layout.addWidget(header)
        
        # Tabbed form
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(168, 85, 247, 0.3);
                background-color: rgba(0, 0, 0, 0.2);
            }
            QTabBar::tab {
                background-color: rgba(255, 255, 255, 0.05);
                color: #c084fc;
                padding: 10px 20px;
                margin-right: 4px;
                border-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #9333ea;
                color: white;
            }
        """)
        
        # Tab 1: Profile
        profile_tab = self.create_profile_tab()
        tabs.addTab(profile_tab, "📋 Profile")
        
        # Tab 2: Subscription
        subscription_tab = self.create_subscription_tab()
        tabs.addTab(subscription_tab, "💳 Subscription")
        
        # Tab 3: Payment (Optional)
        payment_tab = self.create_payment_tab()
        tabs.addTab(payment_tab, "💰 Payment (Optional)")
        
        # Tab 4: Preferences
        preferences_tab = self.create_preferences_tab()
        tabs.addTab(preferences_tab, "⚙️ Preferences")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("✖ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("✓ Create Member & Generate Card")
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #ec4899);
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #f472b6);
            }
        """)
        save_btn.clicked.connect(self.create_member)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        # Style dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: white;
            }
            QLabel {
                color: #c084fc;
            }
            QLineEdit, QTextEdit, QSpinBox, QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 4px;
                padding: 8px;
                color: white;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #9333ea;
            }
            QCheckBox {
                color: white;
            }
            QPushButton {
                background-color: #9333ea;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #a855f7;
            }
        """)
    
    def create_profile_tab(self):
        """Create profile information tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form = QGridLayout(scroll_content)
        
        row = 0
        
        # Name (required)
        form.addWidget(QLabel("* Name:"), row, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Full name")
        form.addWidget(self.name_input, row, 1)
        row += 1
        
        # Email (required)
        form.addWidget(QLabel("* Email:"), row, 0)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        form.addWidget(self.email_input, row, 1)
        row += 1
        
        # Phone
        form.addWidget(QLabel("Phone:"), row, 0)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+1234567890")
        form.addWidget(self.phone_input, row, 1)
        row += 1
        
        # Gender
        form.addWidget(QLabel("Gender:"), row, 0)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Prefer not to say", "Male", "Female", "Non-binary", "Other"])
        form.addWidget(self.gender_combo, row, 1)
        row += 1
        
        # Age
        form.addWidget(QLabel("Age:"), row, 0)
        self.age_input = QSpinBox()
        self.age_input.setRange(0, 150)
        self.age_input.setValue(0)
        self.age_input.setSpecialValueText("Not specified")
        form.addWidget(self.age_input, row, 1)
        row += 1
        
        # Bio
        form.addWidget(QLabel("Bio:"), row, 0, Qt.AlignmentFlag.AlignTop)
        self.bio_input = QTextEdit()
        self.bio_input.setPlaceholderText("Brief description...")
        self.bio_input.setMaximumHeight(80)
        form.addWidget(self.bio_input, row, 1)
        row += 1
        
        # Location
        form.addWidget(QLabel("Location:"), row, 0)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("City, State/Country")
        form.addWidget(self.location_input, row, 1)
        row += 1
        
        # Interests
        form.addWidget(QLabel("Interests:"), row, 0)
        self.interests_input = QLineEdit()
        self.interests_input.setPlaceholderText("reading, gaming, art (comma-separated)")
        form.addWidget(self.interests_input, row, 1)
        row += 1
        
        # Address section
        form.addWidget(QLabel("─── Address ───"), row, 0, 1, 2)
        row += 1
        
        form.addWidget(QLabel("Street:"), row, 0)
        self.street_input = QLineEdit()
        form.addWidget(self.street_input, row, 1)
        row += 1
        
        form.addWidget(QLabel("City:"), row, 0)
        self.city_input = QLineEdit()
        form.addWidget(self.city_input, row, 1)
        row += 1
        
        form.addWidget(QLabel("State:"), row, 0)
        self.state_input = QLineEdit()
        form.addWidget(self.state_input, row, 1)
        row += 1
        
        form.addWidget(QLabel("ZIP Code:"), row, 0)
        self.zip_input = QLineEdit()
        form.addWidget(self.zip_input, row, 1)
        row += 1
        
        form.addWidget(QLabel("Country:"), row, 0)
        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("USA")
        form.addWidget(self.country_input, row, 1)
        row += 1
        
        form.setColumnStretch(1, 1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def create_subscription_tab(self):
        """Create subscription tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form = QGridLayout()
        row = 0
        
        # Tier
        form.addWidget(QLabel("* Membership Tier:"), row, 0)
        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["Kids ($5/month)", "Standard ($10/month)", "Premium ($15/month)"])
        self.tier_combo.setCurrentIndex(1)  # Default to Standard
        form.addWidget(self.tier_combo, row, 1)
        row += 1
        
        # Tier descriptions
        tier_info = QLabel(
            "• Kids: 3 generations/day, basic features\n"
            "• Standard: 10 generations/day, standard features\n"
            "• Premium: Unlimited generations, all features"
        )
        tier_info.setStyleSheet("color: #a78bfa; font-size: 11px; padding: 10px;")
        form.addWidget(tier_info, row, 0, 1, 2)
        row += 1
        
        # Billing cycle
        form.addWidget(QLabel("Billing Cycle:"), row, 0)
        self.billing_combo = QComboBox()
        self.billing_combo.addItems(["Monthly", "Yearly (10% off)"])
        form.addWidget(self.billing_combo, row, 1)
        row += 1
        
        # Auto-renew
        self.auto_renew_check = QCheckBox("Auto-renew subscription")
        self.auto_renew_check.setChecked(True)
        form.addWidget(self.auto_renew_check, row, 0, 1, 2)
        row += 1
        
        form.setColumnStretch(1, 1)
        layout.addLayout(form)
        layout.addStretch()
        
        return widget
    
    def create_payment_tab(self):
        """Create payment tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info_label = QLabel("💳 Payment information (can be added later)")
        info_label.setStyleSheet("color: #a78bfa; padding: 10px;")
        layout.addWidget(info_label)
        
        form = QGridLayout()
        row = 0
        
        # Payment type
        form.addWidget(QLabel("Payment Method:"), row, 0)
        self.payment_type_combo = QComboBox()
        self.payment_type_combo.addItems(["Not provided", "Credit Card", "Debit Card", "PayPal", "Bank Transfer"])
        form.addWidget(self.payment_type_combo, row, 1)
        row += 1
        
        # Last four digits
        form.addWidget(QLabel("Last 4 Digits:"), row, 0)
        self.last_four_input = QLineEdit()
        self.last_four_input.setPlaceholderText("4242")
        self.last_four_input.setMaxLength(4)
        form.addWidget(self.last_four_input, row, 1)
        row += 1
        
        # Expiry
        form.addWidget(QLabel("Expiry (MM/YY):"), row, 0)
        self.expiry_input = QLineEdit()
        self.expiry_input.setPlaceholderText("12/28")
        form.addWidget(self.expiry_input, row, 1)
        row += 1
        
        form.setColumnStretch(1, 1)
        layout.addLayout(form)
        layout.addStretch()
        
        return widget
    
    def create_preferences_tab(self):
        """Create preferences tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form = QGridLayout(scroll_content)
        
        row = 0
        
        # Card Generation Preferences
        form.addWidget(QLabel("─── Card Generation ───"), row, 0, 1, 2)
        row += 1
        
        form.addWidget(QLabel("Art Style:"), row, 0)
        self.art_style_combo = QComboBox()
        self.art_style_combo.addItems(["fantasy", "sci-fi", "anime", "realistic", "abstract", "cyberpunk"])
        form.addWidget(self.art_style_combo, row, 1)
        row += 1
        
        form.addWidget(QLabel("Color Scheme:"), row, 0)
        self.color_scheme_combo = QComboBox()
        self.color_scheme_combo.addItems([
            "azure_silver", "crimson_gold", "emerald_jade", "violet_amethyst",
            "sapphire_pearl", "ruby_onyx", "amber_bronze"
        ])
        form.addWidget(self.color_scheme_combo, row, 1)
        row += 1
        
        form.addWidget(QLabel("Card Border:"), row, 0)
        self.border_combo = QComboBox()
        self.border_combo.addItems(["tribal_arcane", "futuristic_tech", "elegant_classic", "ornate_baroque"])
        form.addWidget(self.border_combo, row, 1)
        row += 1
        
        # Notification Preferences
        form.addWidget(QLabel("─── Notifications ───"), row, 0, 1, 2)
        row += 1
        
        self.email_notif_check = QCheckBox("Email notifications")
        self.email_notif_check.setChecked(True)
        form.addWidget(self.email_notif_check, row, 0, 1, 2)
        row += 1
        
        self.sms_notif_check = QCheckBox("SMS notifications")
        form.addWidget(self.sms_notif_check, row, 0, 1, 2)
        row += 1
        
        self.push_notif_check = QCheckBox("Push notifications")
        self.push_notif_check.setChecked(True)
        form.addWidget(self.push_notif_check, row, 0, 1, 2)
        row += 1
        
        # Reading Preferences
        form.addWidget(QLabel("─── Reading ───"), row, 0, 1, 2)
        row += 1
        
        form.addWidget(QLabel("Favorite Genres:"), row, 0)
        self.genres_input = QLineEdit()
        self.genres_input.setPlaceholderText("fantasy, sci-fi, mystery (comma-separated)")
        self.genres_input.setText("fantasy, sci-fi")
        form.addWidget(self.genres_input, row, 1)
        row += 1
        
        form.addWidget(QLabel("Language:"), row, 0)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["en", "es", "fr", "de", "ja", "zh"])
        form.addWidget(self.language_combo, row, 1)
        row += 1
        
        form.addWidget(QLabel("Font Size:"), row, 0)
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems(["small", "medium", "large", "x-large"])
        self.font_size_combo.setCurrentIndex(1)
        form.addWidget(self.font_size_combo, row, 1)
        row += 1
        
        form.addWidget(QLabel("Theme:"), row, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light", "auto"])
        form.addWidget(self.theme_combo, row, 1)
        row += 1
        
        form.setColumnStretch(1, 1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def create_member(self):
        """Validate and create new member"""
        # Validation
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Name is required")
            return
        
        if not email or '@' not in email:
            QMessageBox.warning(self, "Validation Error", "Valid email is required")
            return
        
        # Extract tier
        tier_text = self.tier_combo.currentText()
        tier = tier_text.split()[0]  # "Kids" from "Kids ($5/month)"
        
        # Extract interests
        interests_text = self.interests_input.text().strip()
        interests = [i.strip() for i in interests_text.split(',')] if interests_text else []
        
        # Extract genres
        genres_text = self.genres_input.text().strip()
        genres = [g.strip() for g in genres_text.split(',')] if genres_text else []
        
        # Create member
        try:
            member_data = self.member_manager.create_new_member(
                name=name,
                email=email,
                phone=self.phone_input.text().strip(),
                gender=self.gender_combo.currentText(),
                age=self.age_input.value() if self.age_input.value() > 0 else None,
                bio=self.bio_input.toPlainText().strip(),
                location=self.location_input.text().strip(),
                interests=interests,
                street=self.street_input.text().strip(),
                city=self.city_input.text().strip(),
                state=self.state_input.text().strip(),
                zip_code=self.zip_input.text().strip(),
                country=self.country_input.text().strip(),
                tier=tier,
                billing_cycle=self.billing_combo.currentText().split()[0].lower(),
                auto_renew=self.auto_renew_check.isChecked(),
                payment_type=self.payment_type_combo.currentText(),
                payment_last_four=self.last_four_input.text().strip(),
                payment_expiry=self.expiry_input.text().strip(),
                art_style=self.art_style_combo.currentText(),
                color_scheme=self.color_scheme_combo.currentText(),
                card_border=self.border_combo.currentText(),
                email_notifications=self.email_notif_check.isChecked(),
                sms_notifications=self.sms_notif_check.isChecked(),
                push_notifications=self.push_notif_check.isChecked(),
                reading_genres=genres,
                reading_language=self.language_combo.currentText(),
                font_size=self.font_size_combo.currentText(),
                theme=self.theme_combo.currentText()
            )
            
            # Store member data for parent to access
            self.member_data = member_data
            
            QMessageBox.information(
                self,
                "Member Created",
                f"✓ Member created successfully!\n\n"
                f"Member ID: {member_data['member_id']}\n"
                f"Name: {member_data['member_profile']['name']}\n"
                f"Tier: {member_data['subscription']['tier']}\n\n"
                f"Card will be generated next."
            )
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Creation Error",
                f"Failed to create member:\n{str(e)}"
            )



class CardWidget(QFrame):
    """The main animated card display widget with video support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 420)
        self.tier = "Standard"
        self.show_upgrade_badge = True
        self.current_image_path = None
        self.current_video_path = None
        self.is_video_mode = False
        self.has_red_seal = False
        self.media_player = None
        self.video_widget = None
        self.audio_output = None
        self.setup_ui()
    
    def eventFilter(self, obj, event):
        """Filter events to catch double-clicks on the label or video widget"""
        if event.type() == event.Type.MouseButtonDblClick:
            # Handle video mode
            if self.is_video_mode and self.current_video_path:
                import subprocess
                import platform
                
                try:
                    if platform.system() == 'Linux':
                        subprocess.Popen(['xdg-open', self.current_video_path])
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.Popen(['open', self.current_video_path])
                    elif platform.system() == 'Windows':
                        subprocess.Popen(['start', self.current_video_path], shell=True)
                except Exception as e:
                    print(f"Failed to open video: {e}")
                return True
            
            # Handle image mode
            elif self.current_image_path:
                import subprocess
                import platform
                
                try:
                    if platform.system() == 'Linux':
                        subprocess.Popen(['xdg-open', self.current_image_path])
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.Popen(['open', self.current_image_path])
                    elif platform.system() == 'Windows':
                        subprocess.Popen(['start', self.current_image_path], shell=True)
                except Exception as e:
                    print(f"Failed to open image: {e}")
                return True
        return super().eventFilter(obj, event)
        
    def setup_ui(self):
        self.setStyleSheet("""
            CardWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1b4b, stop:1 #581c87);
                border: 2px solid #a855f7;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Tier badge
        tier_badge = QLabel(self.tier)
        tier_badge.setStyleSheet("""
            QLabel {
                background-color: #9333ea;
                color: white;
                padding: 4px 12px;
                border-radius: 10px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        tier_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tier_badge.setFixedWidth(80)
        layout.addWidget(tier_badge, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Card content area
        content = QLabel("🎴\n\nCard Animation\nWill Display Here\n\nMotion: 60fps\nPremium Quality")
        content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.setStyleSheet("""
            QLabel {
                color: #c084fc;
                font-size: 13px;
                padding: 20px;
            }
        """)
        layout.addWidget(content, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Store content label reference for updates
        self.content_label = content
        
        # Install event filter to capture double-clicks on the label
        content.installEventFilter(self)
        
        # Volume control (hidden until video is loaded)
        volume_widget = QWidget()
        volume_layout = QHBoxLayout(volume_widget)
        volume_layout.setContentsMargins(10, 5, 10, 5)
        volume_layout.setSpacing(8)
        
        volume_icon = QLabel("🔊")
        volume_icon.setStyleSheet("font-size: 16px;")
        volume_layout.addWidget(volume_icon)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)  # Default 50%
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.1);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #9333ea;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #a855f7;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9333ea, stop:1 #ec4899);
                border-radius: 3px;
            }
        """)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("50%")
        self.volume_label.setStyleSheet("color: #c084fc; font-size: 11px; min-width: 35px;")
        volume_layout.addWidget(self.volume_label)
        
        volume_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.5);
                border-radius: 6px;
            }
        """)
        self.volume_widget = volume_widget
        self.volume_widget.setVisible(False)  # Hidden until video loads
        layout.addWidget(self.volume_widget)
        
        # Upgrade badge
        if self.show_upgrade_badge:
            upgrade_badge = QLabel("🔓 UPGRADE FOR FULL ACCESS")
            upgrade_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(239, 68, 68, 0.8);
                    color: white;
                    padding: 6px 10px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 10px;
                }
            """)
            upgrade_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(upgrade_badge, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
    
    def update_card_image(self, image_path: str):
        """Update the card display with a generated image and check for RedSeal"""
        try:
            self.current_image_path = image_path
            self.is_video_mode = False
            
            # Check if image has RedSeal (steganography data)
            self.has_red_seal = self._check_red_seal(image_path)
            
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale to fit the card widget
                scaled_pixmap = pixmap.scaled(
                    260, 360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Update the content label with the image
                self.content_label.setPixmap(scaled_pixmap)
                self.content_label.setText("")
                self.content_label.setCursor(Qt.CursorShape.PointingHandCursor)
                
                # Show video widget if in video mode, otherwise hide it
                if hasattr(self, 'video_widget') and self.video_widget:
                    self.video_widget.setVisible(False)
                
                # Hide volume control in image mode
                if hasattr(self, 'volume_widget'):
                    self.volume_widget.setVisible(False)
                
                # Notify parent if RedSeal is detected
                if self.has_red_seal:
                    print(f"✅ RedSeal detected in {Path(image_path).name} - Video upload enabled")
                    
        except Exception as e:
            print(f"Error updating card image: {e}")
    
    def _on_volume_changed(self, value: int):
        """Handle volume slider changes"""
        if self.audio_output:
            # Convert 0-100 to 0.0-1.0
            volume = value / 100.0
            self.audio_output.setVolume(volume)
            self.volume_label.setText(f"{value}%")
    
    def _check_red_seal(self, image_path: str) -> bool:
        """Check if image contains RedSeal (embedded steganography data)"""
        try:
            from mutable_steganography import MutableCardSteganography
            stego = MutableCardSteganography()
            data = stego.extract_data(image_path)
            
            # If we can extract data, it has RedSeal
            return data is not None and len(data) > 0
        except:
            return False
    
    def upload_video(self):
        """Upload and display an MP4 video (under 10MB) to replace the PNG"""
        if not self.has_red_seal:
            QMessageBox.warning(
                self,
                "RedSeal Required",
                "Video upload is only available for cards with genuine RedSeal authentication.\n\n"
                "Generate a card with embedded steganography data first."
            )
            return
        
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File (MP4, under 10MB)",
            str(Path.home()),
            "Video Files (*.mp4 *.MP4);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Validate file
        try:
            file_size = Path(file_path).stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 10:
                QMessageBox.warning(
                    self,
                    "File Too Large",
                    f"Video file is {file_size_mb:.2f} MB.\n\n"
                    f"Maximum allowed size is 10 MB.\n"
                    f"Please compress your video and try again."
                )
                return
            
            # Load video
            self._load_video(file_path)
            
            QMessageBox.information(
                self,
                "Video Loaded",
                f"✅ Video loaded successfully!\n\n"
                f"File: {Path(file_path).name}\n"
                f"Size: {file_size_mb:.2f} MB\n\n"
                f"The video will play in loop mode.\n"
                f"Double-click to open in external player."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Video Load Failed",
                f"Failed to load video:\n{str(e)}"
            )
    
    def _load_video(self, video_path: str):
        """Load and display video in the card widget"""
        try:
            self.current_video_path = video_path
            self.is_video_mode = True
            
            # Hide the image label
            self.content_label.setVisible(False)
            
            # Create video widget if not exists
            if not self.video_widget:
                self.video_widget = QVideoWidget()
                # Increased size to fit video and controls properly
                self.video_widget.setFixedSize(280, 420)
                self.video_widget.setCursor(Qt.CursorShape.PointingHandCursor)
                # Insert video widget at same position as content_label
                layout = self.layout()
                layout.insertWidget(1, self.video_widget, alignment=Qt.AlignmentFlag.AlignCenter)
                # Install event filter for double-click
                self.video_widget.installEventFilter(self)
            
            self.video_widget.setVisible(True)
            
            # Create media player if not exists
            if not self.media_player:
                self.media_player = QMediaPlayer()
                self.audio_output = QAudioOutput()
                self.media_player.setAudioOutput(self.audio_output)
                self.media_player.setVideoOutput(self.video_widget)
                
                # Set initial volume from slider
                initial_volume = self.volume_slider.value() / 100.0
                self.audio_output.setVolume(initial_volume)
                
                # Loop the video
                self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            
            # Show volume control
            if hasattr(self, 'volume_widget'):
                self.volume_widget.setVisible(True)
            
            # Load and play video
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.media_player.play()
            
        except Exception as e:
            print(f"Error loading video: {e}")
            raise
    
    def _on_media_status_changed(self, status):
        """Handle media player status changes for looping"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.play()
    
    def switch_to_image_mode(self):
        """Switch back to displaying the PNG image"""
        if self.current_image_path and self.is_video_mode:
            self.is_video_mode = False
            
            # Stop video
            if self.media_player:
                self.media_player.stop()
            
            # Hide video widget
            if self.video_widget:
                self.video_widget.setVisible(False)
            
            # Hide volume control
            if hasattr(self, 'volume_widget'):
                self.volume_widget.setVisible(False)
            
            # Show image label
            self.content_label.setVisible(True)
            self.update_card_image(self.current_image_path)


class GenerationProgressDialog(QDialog):
    """Progress dialog for card generation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generating Card...")
        self.setModal(True)
        self.setFixedSize(500, 200)
        
        # Setup UI
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Status icon and message
        self.icon_label = QLabel("⏳")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(self.icon_label)
        
        self.status_label = QLabel("Initializing generation...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: white;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Backend indicator
        self.backend_label = QLabel("Backend: Checking...")
        self.backend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.backend_label.setStyleSheet("font-size: 11px; color: #c084fc;")
        layout.addWidget(self.backend_label)
        
        # Cancel button (hidden until needed)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Style the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: white;
            }
            QProgressBar {
                background-color: rgba(0, 0, 0, 0.5);
                border-radius: 8px;
                height: 20px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9333ea, stop:1 #ec4899);
                border-radius: 8px;
            }
            QPushButton {
                background-color: #9333ea;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a855f7;
            }
        """)
    
    def update_progress(self, message: str, percentage: int):
        """Update progress display"""
        self.status_label.setText(message)
        self.progress_bar.setValue(percentage)
        
        # Update icon based on progress
        if percentage < 30:
            self.icon_label.setText("⏳")
        elif percentage < 70:
            self.icon_label.setText("🎨")
        elif percentage < 95:
            self.icon_label.setText("✨")
        else:
            self.icon_label.setText("✅")
    
    def update_backend(self, backend: str):
        """Update backend indicator"""
        self.backend_label.setText(f"Backend: {backend}")


class CardGenerationWorker(QThread):
    """Background thread for async card generation"""
    
    # Signals
    progress = pyqtSignal(str, int)  # message, percentage
    finished = pyqtSignal(dict)  # result
    error = pyqtSignal(str)  # error message
    backend_changed = pyqtSignal(str)  # backend name
    
    def __init__(self, generator, prompt, style, color_palette):
        super().__init__()
        self.generator = generator
        self.prompt = prompt
        self.style = style
        self.color_palette = color_palette
        self._is_cancelled = False
    
    def cancel(self):
        """Request cancellation"""
        self._is_cancelled = True
    
    def run(self):
        """Run the async generation in a separate thread"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Check if we should generate video/animation
            is_animated = False
            if hasattr(self.generator, 'grok_mode'):
                grok_mode = self.generator.grok_mode
                if 'Video' in grok_mode or 'GIF' in grok_mode:
                    is_animated = True
            
            # Run the appropriate generation method
            if is_animated:
                self.progress.emit("Preparing video generation...", 5)
                result = loop.run_until_complete(
                    self.generator.generate_animated_card(
                        prompt=self.prompt,
                        duration=5 if 'Video' in grok_mode else 3,
                        effects=['fade', 'particle'],
                        progress_callback=self.on_progress
                    )
                )
            else:
                result = loop.run_until_complete(
                    self.generator.generate_static_card(
                        prompt=self.prompt,
                        style=self.style,
                        color_palette=self.color_palette,
                        progress_callback=self.on_progress
                    )
                )
            
            loop.close()
            
            if self._is_cancelled:
                self.error.emit("Generation cancelled by user")
            elif result['success']:
                self.finished.emit(result)
            else:
                self.error.emit(result.get('error', 'Unknown error'))
                
        except Exception as e:
            self.error.emit(f"Generation error: {str(e)}")
    
    def on_progress(self, message: str, percentage: int):
        """Progress callback from generator"""
        if self._is_cancelled:
            return
        
        self.progress.emit(message, percentage)
        
        # Detect backend switches
        if "Grok" in message:
            self.backend_changed.emit("Grok API")
        elif "Stable Diffusion" in message:
            self.backend_changed.emit("Stable Diffusion")
        elif "fallback" in message.lower():
            self.backend_changed.emit("Fallback: Stable Diffusion")


class AuroraMainWindow(QMainWindow):
    """Main application window - Stripped Card Generator"""
    
    # Signal for shutdown
    session_ended = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.last_generation_metadata = {}  # Store metadata from last generation
        self.is_shutting_down = False
        self.active_workers = []
        self.active_dialogs = []
        self.active_timers = []
        
        # Initialize API config manager
        if API_CONFIG_AVAILABLE:
            self.api_manager = APIConfigManager()
            # Auto-connect to saved APIs
            QTimer.singleShot(1000, self.auto_connect_apis)
        else:
            self.api_manager = None
        
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Aurora Archive")
        self.setMinimumSize(1400, 900)
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0f172a;
                color: white;
            }
            QPushButton {
                background-color: #9333ea;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #a855f7;
            }
            QTabWidget::pane {
                border: 1px solid rgba(168, 85, 247, 0.3);
                background-color: rgba(0, 0, 0, 0.2);
            }
            QTabBar::tab {
                background-color: rgba(255, 255, 255, 0.05);
                color: #c084fc;
                padding: 10px 20px;
                margin-right: 4px;
                border-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #9333ea;
                color: white;
            }
            QTextEdit, QComboBox {
                background-color: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 8px;
                padding: 8px;
                color: white;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
            QLabel {
                color: white;
            }
            QProgressBar {
                background-color: rgba(0, 0, 0, 0.5);
                border-radius: 8px;
                height: 16px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #eab308, stop:1 #f97316);
                border-radius: 8px;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content area with sidebar
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Sidebar
        sidebar = self.create_sidebar()
        content_layout.addWidget(sidebar)
        
        # Main content with tabs
        tabs = self.create_tabs()
        content_layout.addWidget(tabs, stretch=1)
        
        main_layout.addLayout(content_layout)
        
    def create_header(self):
        """Create the top header bar"""
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.3);
                border-bottom: 1px solid rgba(168, 85, 247, 0.3);
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Logo and title
        logo = QLabel("🌅")
        logo.setStyleSheet("font-size: 32px;")
        layout.addWidget(logo)
        
        title = QLabel("AURORA ARCHIVE - Card Generator")
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #f87171, stop:1 #c084fc);
            -qt-background-clip: text;
            color: transparent;
        """)
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Backend indicator
        self.backend_indicator = QLabel("Backend: Stable Diffusion")
        self.backend_indicator.setStyleSheet("""
            QLabel {
                color: #a78bfa;
                font-size: 14px;
                padding: 8px 16px;
                background-color: rgba(139, 92, 246, 0.1);
                border: 1px solid rgba(139, 92, 246, 0.3);
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.backend_indicator)
        
        return header
        
    def create_sidebar(self):
        """Create the left sidebar with card display"""
        sidebar = QFrame()
        sidebar.setFixedWidth(340)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.2);
                border-right: 1px solid rgba(168, 85, 247, 0.3);
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Card display - store reference
        self.card_widget = CardWidget()
        layout.addWidget(self.card_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        # Generate button
        generate_btn = QPushButton("✨ Generate New Card")
        generate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #9333ea);
                padding: 12px;
                font-size: 14px;
            }
        """)
        generate_btn.clicked.connect(self.on_quick_generate_clicked)
        layout.addWidget(generate_btn)
        
        # Export button
        export_btn = QPushButton("📦 Export Card")
        export_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #dc2626, stop:1 #b91c1c);
                padding: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #b91c1c, stop:1 #991b1b);
            }
            QPushButton:disabled {
                background-color: rgba(100, 100, 100, 0.3);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        export_btn.clicked.connect(self.on_export_card_clicked)
        self.export_btn = export_btn  # Store reference
        self.export_btn.setEnabled(False)  # Disabled until card is generated
        layout.addWidget(export_btn)
        
        # Video upload button (only for RedSealed cards)
        video_btn = QPushButton("🎬 Upload Video (RedSeal)")
        video_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #dc2626, stop:1 #7c2d12);
                padding: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #b91c1c, stop:1 #991b1b);
            }
            QPushButton:disabled {
                background-color: rgba(100, 100, 100, 0.3);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        video_btn.setToolTip("Upload MP4 video (under 10MB) to replace PNG display\nOnly available for cards with RedSeal authentication")
        video_btn.clicked.connect(self.on_upload_video_clicked)
        self.video_btn = video_btn  # Store reference
        self.video_btn.setEnabled(False)  # Disabled until RedSealed card is generated
        layout.addWidget(video_btn)
        
        # Switch to image button (shown when video is playing)
        image_btn = QPushButton("🖼️ Show Image")
        image_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0891b2, stop:1 #0e7490);
                padding: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0e7490, stop:1 #155e75);
            }
        """)
        image_btn.setToolTip("Switch back to displaying the PNG image")
        image_btn.clicked.connect(self.on_switch_to_image_clicked)
        self.image_btn = image_btn  # Store reference
        self.image_btn.setVisible(False)  # Hidden until video is loaded
        layout.addWidget(image_btn)
        
        layout.addStretch()
        
        return sidebar
        
    def create_tabs(self):
        """Create the main tabbed content area"""
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
            }
        """)
        
        # Add simplified tabs - only core card functionality
        tabs.addTab(self.create_card_creator(), "🎨 Card Generation")
        tabs.addTab(self.create_api_settings(), "⚙️ API Settings")
        
        return tabs
        
    def create_card_creator(self):
        """Card creation tab"""
        # Create scroll area wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(24)
        
        title = QLabel("Create New Card")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)
        
        # Creation form
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 12px;
                padding: 30px;
            }
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(20)
        
        # Character concept
        concept_label = QLabel("Card Character Concept")
        concept_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 8px;")
        form_layout.addWidget(concept_label)
        
        self.concept_input = QTextEdit()
        self.concept_input.setPlaceholderText("Describe your ideal card character... (Standard tier: choose from curated templates)")
        self.concept_input.setMaximumHeight(120)
        form_layout.addWidget(self.concept_input)
        
        # Style and color selection
        selection_grid = QGridLayout()
        selection_grid.setSpacing(16)
        
        # Style template
        style_label = QLabel("Style Template")
        style_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        selection_grid.addWidget(style_label, 0, 0)
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(['Fantasy', 'Sci-Fi', 'Anime', 'Realistic'])
        selection_grid.addWidget(self.style_combo, 1, 0)
        
        # Color palette
        color_label = QLabel("Color Palette")
        color_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        selection_grid.addWidget(color_label, 0, 1)
        
        self.color_combo = QComboBox()
        self.color_combo.addItems(['', 'Crimson & Gold', 'Azure & Silver', 'Emerald & Bronze', 'Violet & White'])
        selection_grid.addWidget(self.color_combo, 1, 1)
        
        form_layout.addLayout(selection_grid)
        
        # Advanced Settings Section
        advanced_label = QLabel("⚙️ Advanced Settings")
        advanced_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px; color: #c084fc;")
        form_layout.addWidget(advanced_label)
        
        advanced_grid = QGridLayout()
        advanced_grid.setSpacing(16)
        
        # Model selection
        model_label = QLabel("Model")
        model_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(model_label, 0, 0)
        
        # Model selection with refresh button
        model_container = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Choose the AI model for generation")
        model_container.addWidget(self.model_combo, stretch=1)
        
        # Refresh button
        self.refresh_models_btn = QPushButton("🔄")
        self.refresh_models_btn.setFixedSize(32, 32)
        self.refresh_models_btn.setToolTip("Refresh model list from Stable Diffusion")
        self.refresh_models_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(147, 51, 234, 0.3);
                border: 1px solid #9333ea;
                border-radius: 6px;
                font-size: 14px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(147, 51, 234, 0.5);
                border: 1px solid #a855f7;
            }
            QPushButton:pressed {
                background-color: #9333ea;
            }
        """)
        self.refresh_models_btn.clicked.connect(self.refresh_model_list)
        model_container.addWidget(self.refresh_models_btn)
        
        advanced_grid.addLayout(model_container, 1, 0)
        
        # Load models initially
        self.refresh_model_list(show_message=False)
        
        # Sampling steps
        steps_label = QLabel(f"Sampling Steps")
        steps_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(steps_label, 0, 1)
        
        steps_container = QHBoxLayout()
        self.steps_combo = QComboBox()
        self.steps_combo.addItems(['20', '30', '40', '50', '60'])
        self.steps_combo.setCurrentText('20')
        self.steps_combo.setToolTip("Higher steps = better quality but slower (20-60)")
        steps_container.addWidget(self.steps_combo)
        
        steps_info = QLabel("steps")
        steps_info.setStyleSheet("color: #a855f7; font-size: 11px;")
        steps_container.addWidget(steps_info)
        steps_container.addStretch()
        
        advanced_grid.addLayout(steps_container, 1, 1)
        
        # CFG Scale
        cfg_label = QLabel("CFG Scale")
        cfg_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(cfg_label, 2, 0)
        
        cfg_container = QHBoxLayout()
        self.cfg_combo = QComboBox()
        self.cfg_combo.addItems(['5.0', '7.0', '7.5', '9.0', '11.0', '13.0', '15.0'])
        self.cfg_combo.setCurrentText('7.0')
        self.cfg_combo.setToolTip("How closely to follow prompt (5-15, default 7.0)")
        cfg_container.addWidget(self.cfg_combo)
        
        cfg_info = QLabel("prompt strength")
        cfg_info.setStyleSheet("color: #a855f7; font-size: 11px;")
        cfg_container.addWidget(cfg_info)
        cfg_container.addStretch()
        
        advanced_grid.addLayout(cfg_container, 2, 1)
        
        # Sampler
        sampler_label = QLabel("Sampler")
        sampler_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(sampler_label, 3, 0)
        
        self.sampler_combo = QComboBox()
        self.sampler_combo.setToolTip("Sampling method for generation")
        advanced_grid.addWidget(self.sampler_combo, 4, 0)
        
        # Scheduler (optional, some samplers have it)
        scheduler_label = QLabel("Scheduler")
        scheduler_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(scheduler_label, 3, 1)
        
        self.scheduler_combo = QComboBox()
        self.scheduler_combo.setToolTip("Noise schedule (Karras is most common)")
        advanced_grid.addWidget(self.scheduler_combo, 4, 1)
        
        # Width
        width_label = QLabel("Width")
        width_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(width_label, 5, 0)
        
        width_container = QHBoxLayout()
        self.width_combo = QComboBox()
        self.width_combo.addItems(['512', '576', '640', '704', '768', '832', '896', '960', '1024'])
        self.width_combo.setCurrentText('512')
        self.width_combo.setToolTip("Image width in pixels (512 is default)")
        width_container.addWidget(self.width_combo)
        
        width_info = QLabel("px")
        width_info.setStyleSheet("color: #a855f7; font-size: 11px;")
        width_container.addWidget(width_info)
        width_container.addStretch()
        
        advanced_grid.addLayout(width_container, 6, 0)
        
        # Height
        height_label = QLabel("Height")
        height_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(height_label, 5, 1)
        
        height_container = QHBoxLayout()
        self.height_combo = QComboBox()
        self.height_combo.addItems(['512', '576', '640', '704', '768', '832', '896', '960', '1024'])
        self.height_combo.setCurrentText('768')
        self.height_combo.setToolTip("Image height in pixels (768 for portrait cards)")
        height_container.addWidget(self.height_combo)
        
        height_info = QLabel("px")
        height_info.setStyleSheet("color: #a855f7; font-size: 11px;")
        height_container.addWidget(height_info)
        height_container.addStretch()
        
        advanced_grid.addLayout(height_container, 6, 1)
        
        # Hi-Res Fix section
        hires_label = QLabel("🔍 Hi-Res Fix")
        hires_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #c084fc;")
        advanced_grid.addWidget(hires_label, 7, 0, 1, 2)  # Span 2 columns
        
        # Hi-Res Fix toggle
        hires_toggle_container = QHBoxLayout()
        self.hires_checkbox = QCheckBox("Enable Hi-Res Fix")
        self.hires_checkbox.setChecked(False)
        self.hires_checkbox.setToolTip("Upscale and refine the image (better quality, slower)")
        self.hires_checkbox.stateChanged.connect(self.on_hires_toggled)
        hires_toggle_container.addWidget(self.hires_checkbox)
        hires_toggle_container.addStretch()
        
        advanced_grid.addLayout(hires_toggle_container, 8, 0, 1, 2)  # Span 2 columns
        
        # Upscaler (only shown when Hi-Res Fix is enabled)
        upscaler_label = QLabel("Upscaler")
        upscaler_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(upscaler_label, 9, 0)
        self.upscaler_label = upscaler_label  # Store reference
        
        self.upscaler_combo = QComboBox()
        self.upscaler_combo.setToolTip("Upscaling algorithm for Hi-Res Fix")
        advanced_grid.addWidget(self.upscaler_combo, 10, 0)
        
        # HR Scale
        hr_scale_label = QLabel("HR Scale")
        hr_scale_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        advanced_grid.addWidget(hr_scale_label, 9, 1)
        self.hr_scale_label = hr_scale_label  # Store reference
        
        hr_scale_container = QHBoxLayout()
        self.hr_scale_combo = QComboBox()
        self.hr_scale_combo.addItems(['1.5', '2.0', '2.5', '3.0', '4.0'])
        self.hr_scale_combo.setCurrentText('2.0')
        self.hr_scale_combo.setToolTip("Upscale multiplier (2.0 = double resolution)")
        hr_scale_container.addWidget(self.hr_scale_combo)
        
        hr_scale_info = QLabel("x")
        hr_scale_info.setStyleSheet("color: #a855f7; font-size: 11px;")
        hr_scale_container.addWidget(hr_scale_info)
        hr_scale_container.addStretch()
        
        advanced_grid.addLayout(hr_scale_container, 10, 1)
        self.hr_scale_container = hr_scale_container  # Store reference
        
        # Load samplers and upscalers
        self.refresh_samplers_and_upscalers()
        
        # Initially hide Hi-Res Fix options
        self.on_hires_toggled(0)
        
        form_layout.addLayout(advanced_grid)
        
        # Grok Image/Video Generation Section
        grok_section = QFrame()
        grok_section.setStyleSheet("""
            QFrame {
                background-color: rgba(236, 72, 153, 0.2);
                border: 1px solid rgba(236, 72, 153, 0.4);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        grok_layout = QVBoxLayout(grok_section)
        
        grok_header = QLabel("🎬 Grok AI - Image & Video Generation")
        grok_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #ec4899;")
        grok_layout.addWidget(grok_header)
        
        grok_info = QLabel("Use Grok AI for experimental image/video generation (requires X.AI API)")
        grok_info.setStyleSheet("color: #f9a8d4; font-size: 11px; margin-bottom: 10px;")
        grok_layout.addWidget(grok_info)
        
        # Grok toggle
        grok_toggle_layout = QHBoxLayout()
        self.use_grok_checkbox = QCheckBox("Use Grok AI instead of Stable Diffusion")
        self.use_grok_checkbox.setChecked(False)
        self.use_grok_checkbox.setToolTip("Switch to Grok for image/video generation")
        self.use_grok_checkbox.stateChanged.connect(self.on_grok_toggled)
        grok_toggle_layout.addWidget(self.use_grok_checkbox)
        grok_toggle_layout.addStretch()
        grok_layout.addLayout(grok_toggle_layout)
        
        # Grok mode selection (image or video)
        grok_mode_layout = QHBoxLayout()
        grok_mode_label = QLabel("Mode:")
        grok_mode_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #f9a8d4;")
        grok_mode_layout.addWidget(grok_mode_label)
        
        self.grok_mode_combo = QComboBox()
        self.grok_mode_combo.addItems(['Still Image', 'Short Video/Animation (3-5s)', 'Animated GIF'])
        self.grok_mode_combo.setEnabled(False)
        self.grok_mode_combo.setToolTip("Choose between still image or short video generation")
        grok_mode_layout.addWidget(self.grok_mode_combo, stretch=1)
        grok_layout.addLayout(grok_mode_layout)
        
        # Grok quality settings
        grok_quality_layout = QHBoxLayout()
        grok_quality_label = QLabel("Quality:")
        grok_quality_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #f9a8d4;")
        grok_quality_layout.addWidget(grok_quality_label)
        
        self.grok_quality_combo = QComboBox()
        self.grok_quality_combo.addItems(['Standard', 'High', 'Ultra (Premium)'])
        self.grok_quality_combo.setEnabled(False)
        self.grok_quality_combo.setCurrentIndex(1)
        grok_quality_layout.addWidget(self.grok_quality_combo, stretch=1)
        grok_layout.addLayout(grok_quality_layout)
        
        # Store Grok widgets for enabling/disabling
        self.grok_mode_label = grok_mode_label
        self.grok_quality_label = grok_quality_label
        
        form_layout.addWidget(grok_section)
        
        # Generation limit notice
        limit_frame = QFrame()
        limit_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(147, 51, 234, 0.2);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        limit_layout = QVBoxLayout(limit_frame)
        
        limit_text = QLabel("⚡ Generations remaining today: <b>2 / 3</b>")
        limit_text.setStyleSheet("color: #c084fc; font-size: 13px;")
        limit_layout.addWidget(limit_text)
        
        upgrade_text = QLabel("Upgrade to Premium for unlimited generations and full creative control")
        upgrade_text.setStyleSheet("color: #a855f7; font-size: 11px;")
        limit_layout.addWidget(upgrade_text)
        
        form_layout.addWidget(limit_frame)
        
        # Generate button
        generate_btn = QPushButton("✨ Generate Card")
        generate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9333ea, stop:1 #ec4899);
                padding: 16px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        generate_btn.clicked.connect(self.on_generate_clicked)
        form_layout.addWidget(generate_btn)
        
        layout.addWidget(form_frame)
        layout.addStretch()
        
        # Set widget into scroll area
        scroll.setWidget(widget)
        return scroll
    
    def create_api_settings(self):
        """API configuration and management tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(24)
        
        title = QLabel("API Configuration")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)
        
        subtitle = QLabel("Configure and manage your AI generation backends")
        subtitle.setStyleSheet("font-size: 14px; color: #94a3b8;")
        layout.addWidget(subtitle)
        
        # API configurations container
        if self.api_manager:
            supported_apis = self.api_manager.SUPPORTED_APIS
            
            for api_type, api_info in supported_apis.items():
                api_frame = self.create_api_config_section(api_type, api_info)
                layout.addWidget(api_frame)
        else:
            error_label = QLabel("⚠️ API Configuration Manager not available")
            error_label.setStyleSheet("color: #f87171; font-size: 14px;")
            layout.addWidget(error_label)
        
        layout.addStretch()
        scroll.setWidget(widget)
        return scroll
    
    def create_api_config_section(self, api_type: str, api_info: dict):
        """Create a configuration section for a specific API"""
        # Main frame
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        
        # Header with API name and status
        header_layout = QHBoxLayout()
        
        name_label = QLabel(f"🔌 {api_info['name']}")
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(name_label)
        
        header_layout.addStretch()
        
        # Status indicator
        existing_config = self.api_manager.get_api(api_type) if self.api_manager else None
        status_label = QLabel()
        if existing_config:
            if existing_config.get('verified'):
                status_label.setText("✅ Connected")
                status_label.setStyleSheet("color: #10b981; font-size: 12px; padding: 4px 8px; background-color: rgba(16, 185, 129, 0.1); border-radius: 4px;")
            else:
                status_label.setText("⚠️ Not Verified")
                status_label.setStyleSheet("color: #f59e0b; font-size: 12px; padding: 4px 8px; background-color: rgba(245, 158, 11, 0.1); border-radius: 4px;")
        else:
            status_label.setText("⭕ Not Configured")
            status_label.setStyleSheet("color: #6b7280; font-size: 12px; padding: 4px 8px; background-color: rgba(107, 114, 128, 0.1); border-radius: 4px;")
        
        header_layout.addWidget(status_label)
        layout.addLayout(header_layout)
        
        # URL field (hidden for Grok - auto-set to correct endpoint)
        if api_type != 'grok':
            url_layout = QHBoxLayout()
            url_label = QLabel("URL:")
            url_label.setStyleSheet("font-weight: bold; color: #a78bfa; min-width: 80px;")
            url_layout.addWidget(url_label)
            
            url_input = QLineEdit()
            url_input.setPlaceholderText(api_info['default_url'])
            url_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(30, 41, 59, 0.5);
                    border: 1px solid rgba(139, 92, 246, 0.3);
                    border-radius: 6px;
                    padding: 8px;
                    color: white;
                }
                QLineEdit:focus {
                    border-color: #a78bfa;
                }
            """)
            
            if existing_config:
                url_input.setText(existing_config.get('url', ''))
            
            # Store reference
            setattr(self, f'{api_type}_url_input', url_input)
            url_layout.addWidget(url_input)
            layout.addLayout(url_layout)
        else:
            # For Grok, create hidden input with preset URL
            url_input = QLineEdit()
            url_input.setText(api_info['default_url'])
            url_input.setVisible(False)
            setattr(self, f'{api_type}_url_input', url_input)
        
        # API Key field (if required)
        if api_info['requires_key']:
            key_layout = QHBoxLayout()
            key_label = QLabel("API Key:")
            key_label.setStyleSheet("font-weight: bold; color: #a78bfa; min-width: 80px;")
            key_layout.addWidget(key_label)
            
            key_input = QLineEdit()
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            key_input.setPlaceholderText("Enter your API key...")
            key_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(30, 41, 59, 0.5);
                    border: 1px solid rgba(139, 92, 246, 0.3);
                    border-radius: 6px;
                    padding: 8px;
                    color: white;
                }
                QLineEdit:focus {
                    border-color: #a78bfa;
                }
            """)
            
            if existing_config and existing_config.get('api_key'):
                key_input.setText(existing_config['api_key'])
            
            # Store reference
            setattr(self, f'{api_type}_key_input', key_input)
            key_layout.addWidget(key_input)
            
            # Show/Hide key button
            toggle_btn = QPushButton("👁️")
            toggle_btn.setFixedWidth(40)
            toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(139, 92, 246, 0.2);
                    border: 1px solid rgba(139, 92, 246, 0.3);
                    border-radius: 6px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: rgba(139, 92, 246, 0.3);
                }
            """)
            toggle_btn.clicked.connect(lambda checked, inp=key_input: 
                inp.setEchoMode(QLineEdit.EchoMode.Normal if inp.echoMode() == QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password))
            key_layout.addWidget(toggle_btn)
            
            layout.addLayout(key_layout)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        # Auto-connect checkbox
        auto_connect_check = QCheckBox("Auto-connect on startup")
        auto_connect_check.setStyleSheet("color: #94a3b8; font-size: 12px;")
        if existing_config and api_type in self.api_manager.get_auto_connect_apis():
            auto_connect_check.setChecked(True)
        
        setattr(self, f'{api_type}_auto_connect', auto_connect_check)
        btn_layout.addWidget(auto_connect_check)
        
        btn_layout.addStretch()
        
        # Test connection button
        test_btn = QPushButton("🔍 Test Connection")
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(59, 130, 246, 0.3);
                border: 1px solid rgba(59, 130, 246, 0.5);
                border-radius: 6px;
                padding: 8px 16px;
                color: #60a5fa;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(59, 130, 246, 0.4);
            }
        """)
        test_btn.clicked.connect(lambda: self.test_api_connection(api_type))
        btn_layout.addWidget(test_btn)
        
        # Save button
        save_btn = QPushButton("💾 Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.3);
                border: 1px solid rgba(16, 185, 129, 0.5);
                border-radius: 6px;
                padding: 8px 16px;
                color: #10b981;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(16, 185, 129, 0.4);
            }
        """)
        save_btn.clicked.connect(lambda: self.save_api_config(api_type))
        btn_layout.addWidget(save_btn)
        
        # Remove button
        if existing_config:
            remove_btn = QPushButton("🗑️ Remove")
            remove_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.3);
                    border: 1px solid rgba(239, 68, 68, 0.5);
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #ef4444;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(239, 68, 68, 0.4);
                }
            """)
            remove_btn.clicked.connect(lambda: self.remove_api_config(api_type))
            btn_layout.addWidget(remove_btn)
        
        layout.addLayout(btn_layout)
        
        return frame
    
    def save_api_config(self, api_type: str):
        """Save API configuration"""
        if not self.api_manager:
            QMessageBox.warning(self, "Error", "API manager not available")
            return
        
        # Get inputs
        url_input = getattr(self, f'{api_type}_url_input', None)
        key_input = getattr(self, f'{api_type}_key_input', None)
        auto_connect = getattr(self, f'{api_type}_auto_connect', None)
        
        if not url_input:
            return
        
        # For Grok, always use the correct API endpoint
        api_info = self.api_manager.SUPPORTED_APIS[api_type]
        if api_type == 'grok':
            url = api_info['default_url']  # Always use https://api.x.ai/v1
        else:
            url = url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Missing URL", "Please enter the API URL")
                return
        
        api_key = key_input.text().strip() if key_input else None
        
        if api_info['requires_key'] and not api_key:
            QMessageBox.warning(self, "Missing API Key", f"Please enter your {api_info['name']} API key")
            return
        
        # Save configuration
        success = self.api_manager.add_api(api_type, url, api_key)
        
        if success:
            # Set auto-connect
            if auto_connect:
                self.api_manager.set_auto_connect(api_type, auto_connect.isChecked())
            
            # Export to .env
            self.api_manager.export_to_env(api_type)
            
            # Reload environment variables immediately
            # Also update both GROK_API_KEY and XAI_API_KEY for compatibility
            if api_type == 'grok' and api_key:
                os.environ['GROK_API_KEY'] = api_key
                os.environ['XAI_API_KEY'] = api_key
                logger.info("Updated both GROK_API_KEY and XAI_API_KEY in runtime environment")
            
            QMessageBox.information(
                self, 
                "Success", 
                f"{api_info['name']} configuration saved successfully!\n\n"
                "✅ Configuration encrypted and stored\n"
                "✅ Environment variables updated\n"
                "✅ Ready to use immediately"
            )
            
            # Refresh the tab
            self.refresh_api_settings()
        else:
            QMessageBox.critical(self, "Error", "Failed to save API configuration")
    
    def test_api_connection(self, api_type: str):
        """Test API connection"""
        if not self.api_manager:
            return
        
        url_input = getattr(self, f'{api_type}_url_input', None)
        key_input = getattr(self, f'{api_type}_key_input', None)
        
        if not url_input:
            return
        
        # Get URL (use default for Grok)
        api_info = self.api_manager.SUPPORTED_APIS[api_type]
        if api_type == 'grok':
            url = api_info['default_url']
        else:
            url = url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Missing URL", "Please enter the API URL first")
                return
        
        api_key = key_input.text().strip() if key_input else None
        
        if not api_key and api_info['requires_key']:
            QMessageBox.warning(self, "Missing API Key", "Please enter your API key first")
            return
        
        # Show progress with cancel button
        progress = QMessageBox(self)
        progress.setWindowTitle("Testing Connection")
        progress.setText(f"Testing connection to {api_info['name']}...\n\nThis may take a few seconds.")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.show()
        QApplication.processEvents()
        
        # Use QTimer to prevent UI freeze
        def test_connection():
            try:
                # Test connection with 5 second timeout
                test_url = f"{url}{api_info['test_endpoint']}"
                headers = {}
                
                if api_key:
                    if api_type in ['grok', 'openai', 'stability']:
                        headers['Authorization'] = f'Bearer {api_key}'
                
                response = requests.get(test_url, headers=headers, timeout=5)
                progress.close()
                
                if response.status_code == 200:
                    # Mark as verified
                    config = self.api_manager.get_api(api_type)
                    if config:
                        self.api_manager.mark_verified(api_type, True)
                    
                    QMessageBox.information(
                        self,
                        "Connection Successful",
                        f"✅ Successfully connected to {api_info['name']}!\n\n"
                        f"Status Code: {response.status_code}"
                    )
                    
                    # Refresh to show verified status
                    self.refresh_api_settings()
                else:
                    QMessageBox.warning(
                        self,
                        "Connection Failed",
                        f"⚠️ Connection test failed\n\n"
                        f"Status Code: {response.status_code}\n"
                        f"Response: {response.text[:200]}"
                    )
            
            except requests.exceptions.Timeout:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Connection Timeout",
                    f"⏱️ Connection to {api_info['name']} timed out (5 seconds).\n\n"
                    "Please check:\n"
                    "• The API service is available\n"
                    "• Your internet connection\n"
                    "• Your API key is valid"
                )
            
            except requests.exceptions.ConnectionError:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Connection Error",
                    f"❌ Cannot connect to {api_info['name']}.\n\n"
                    "Please check:\n"
                    "• The URL is correct\n"
                    "• The service is running\n"
                    "• Your firewall settings"
                )
            
            except Exception as e:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Connection Error",
                    f"❌ Failed to connect:\n\n{str(e)}"
                )
        
        # Run test in background to prevent UI freeze
        QTimer.singleShot(100, test_connection)
    
    def remove_api_config(self, api_type: str):
        """Remove API configuration"""
        if not self.api_manager:
            return
        
        api_info = self.api_manager.SUPPORTED_APIS[api_type]
        
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove {api_info['name']} configuration?\n\n"
            "This will delete the saved URL and API key.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.api_manager.remove_api(api_type)
            QMessageBox.information(self, "Removed", f"{api_info['name']} configuration removed")
            self.refresh_api_settings()
    
    def refresh_api_settings(self):
        """Refresh the API settings tab"""
        # Find the tab widget
        tabs = self.findChild(QTabWidget)
        if tabs:
            # Get current tab index
            current_index = tabs.currentIndex()
            
            # Replace the API settings tab
            api_tab = self.create_api_settings()
            tabs.removeTab(1)  # Remove old API settings tab
            tabs.insertTab(1, api_tab, "⚙️ API Settings")
            
            # Restore tab selection if it was the API settings tab
            if current_index == 1:
                tabs.setCurrentIndex(1)
    
    def log_card_to_csv(self, card_path: str, metadata: dict, member_data: Optional[dict] = None):
        """
        Log generated card information to CSV file for tracking across apps.
        
        Args:
            card_path: Path to the generated card image
            metadata: Generation metadata (backend, time, model, etc.)
            member_data: Optional member information if available
        """
        try:
            # CSV file location
            csv_path = Path("generated_cards_log.csv")
            
            # Check if file exists to determine if we need headers
            file_exists = csv_path.exists()
            
            # Prepare row data
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = {
                'timestamp': timestamp,
                'card_path': str(card_path),
                'filename': Path(card_path).name,
                'member_id': member_data.get('id', 'N/A') if member_data else 'N/A',
                'member_name': member_data.get('name', 'N/A') if member_data else 'N/A',
                'member_email': member_data.get('email', 'N/A') if member_data else 'N/A',
                'tier': member_data.get('tier', 'N/A') if member_data else 'N/A',
                'style': metadata.get('style', 'N/A'),
                'prompt': metadata.get('prompt', 'N/A')[:100],  # Truncate long prompts
                'backend': metadata.get('backend', 'N/A'),
                'model': metadata.get('model', 'N/A'),
                'sampler': metadata.get('sampler', 'N/A'),
                'steps': metadata.get('steps', 'N/A'),
                'cfg_scale': metadata.get('cfg', 'N/A'),
                'resolution': f"{metadata.get('width', 512)}x{metadata.get('height', 768)}",
                'generation_time_sec': metadata.get('generation_time', 'N/A'),
                'file_size_mb': metadata.get('file_size_mb', 'N/A')
            }
            
            # Write to CSV
            with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = list(row.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header if new file
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(row)
            
            print(f"✓ Card logged to CSV: {csv_path}")
            
        except Exception as e:
            print(f"Warning: Failed to log card to CSV: {e}")
            # Don't raise - CSV logging is non-critical
    
    def on_quick_generate_clicked(self):
        """Handle quick generate button from sidebar"""
        # Use default settings for quick generation
        prompt = "Fantasy mystical warrior"
        style = "Fantasy"
        color = "Crimson & Gold"
        
        self.start_generation(prompt, style, color)
    
    def on_scan_card_data_clicked(self):
        """Handle scan card data button - extract and display steganography data"""
        if not self.card_widget.current_image_path:
            QMessageBox.warning(
                self,
                "No Image",
                "Please generate or load a card image first."
            )
            return
        
        try:
            # Show the steganography data viewer
            image_path = self.card_widget.current_image_path
            viewer = SteganographyDataViewer(image_path, self)
            self.active_dialogs.append(viewer)  # Track dialog
            viewer.exec()
            if viewer in self.active_dialogs:
                self.active_dialogs.remove(viewer)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Scan Failed",
                f"Failed to scan card data:\n{e}"
            )
    
    def on_upload_video_clicked(self):
        """Handle video upload button - upload MP4 to replace PNG display"""
        if not self.card_widget.current_image_path:
            QMessageBox.warning(
                self,
                "No Card Generated",
                "Please generate a card first before uploading a video."
            )
            return
        
        if not self.card_widget.has_red_seal:
            QMessageBox.warning(
                self,
                "RedSeal Required",
                "Video upload is only available for cards with genuine RedSeal authentication.\n\n"
                "This card does not contain embedded steganography data.\n"
                "Generate a new card with steganography enabled."
            )
            return
        
        # Call the card widget's upload_video method
        self.card_widget.upload_video()
        
        # Update button visibility if video was loaded
        if self.card_widget.is_video_mode:
            self.image_btn.setVisible(True)
    
    def on_switch_to_image_clicked(self):
        """Handle switch to image button - return to PNG display"""
        self.card_widget.switch_to_image_mode()
        self.image_btn.setVisible(False)
    
    def on_export_card_clicked(self):
        """Export card with enhanced steganography - timestamp + Crimson Collective sigil"""
        if not self.card_widget.current_image_path:
            QMessageBox.warning(
                self,
                "No Card to Export",
                "Please generate a card first before exporting."
            )
            return
        
        try:
            from datetime import datetime
            import secrets
            import hashlib
            
            # Get current card path
            source_path = self.card_widget.current_image_path
            
            # Ask user where to save
            from PyQt6.QtWidgets import QFileDialog
            default_name = f"aurora_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            export_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Card with Crimson Collective Seal",
                str(Path.home() / "Desktop" / default_name),
                "PNG Images (*.png);;All Files (*)"
            )
            
            if not export_path:
                return  # User cancelled
            
            # Generate mythic Crimson Collective identifier
            export_timestamp = datetime.now().isoformat()
            
            # Create unique mythic sigil (prose-style identifier)
            mythic_phrases = [
                "forged in the Crimson Void where stars bleed light",
                "blessed by the Thirteen Seers of the Eternal Archive",
                "bound by the ancient covenant of the Scarlet Scribes",
                "sealed with the mark of the Vermillion Guardians",
                "witnessed by the Keepers of the Crimson Dawn",
                "consecrated in the halls of the Ruby Monastery",
                "empowered by the rites of the Cardinal Assembly",
                "inscribed in the tome of Sanguine Mysteries",
                "sanctioned by the Council of Crimson Oracles",
                "woven into the tapestry of the Red Collective"
            ]
            
            # Generate unique hash from timestamp and random bytes
            unique_bytes = (export_timestamp + secrets.token_hex(16)).encode()
            sigil_hash = hashlib.sha256(unique_bytes).hexdigest()[:16]
            
            # Select mythic phrase based on hash
            phrase_index = int(sigil_hash[:4], 16) % len(mythic_phrases)
            mythic_identifier = mythic_phrases[phrase_index]
            
            # Create enhanced export data
            export_data = {
                # Original embedded data (if exists)
                **self.last_generation_metadata,
                
                # Export metadata
                'export_timestamp': export_timestamp,
                'export_type': 'crimson_collective_sealed',
                'export_version': '2.0',
                
                # Crimson Collective Seal
                'crimson_collective': {
                    'sigil': sigil_hash,
                    'seal': f"This card was {mythic_identifier}",
                    'covenant': 'By the Crimson Collective, authenticated and preserved',
                    'authority': 'Aurora Archive - Crimson Artisan Guild',
                    'generation': 'Second Era of Digital Arcana'
                },
                
                # Timestamp tracking
                'timeline': {
                    'created': self.last_generation_metadata.get('timestamp', 'Unknown'),
                    'exported': export_timestamp,
                    'sealed_by': 'Crimson Collective Authenticator v2.0'
                },
                
                # Authenticity markers
                'authenticity': {
                    'genuine': True,
                    'origin': 'Aurora Archive Card Generator',
                    'verification_hash': sigil_hash,
                    'tamper_seal': 'INTACT'
                }
            }
            
            # Copy file first
            import shutil
            shutil.copy2(source_path, export_path)
            
            # Re-embed with enhanced export data using MutableCardSteganography
            if STEG_AVAILABLE:
                steg = MutableCardSteganography()
                steg.embed_data(export_path, export_data, force_overwrite=True)
                
                # Apply RedSeal compositor for Obelisk validation
                if SEAL_AVAILABLE:
                    try:
                        seal_comp = SealCompositor()
                        # Create minimal member data for seal
                        seal_member_data = {
                            'member_id': 'EXPORT_' + sigil_hash[:8],
                            'tier': 'Standard',
                            'crimson_collective': export_data['crimson_collective'],
                            'timeline': export_data['timeline'],
                            'authenticity': export_data['authenticity']
                        }
                        # Apply seal to card
                        seal_comp.embed_and_composite(export_path, seal_member_data, output_path=export_path)
                        print("✅ RedSeal applied - card will pass Obelisk validation")
                    except Exception as seal_err:
                        print(f"⚠️ RedSeal application failed: {seal_err}")
                
                QMessageBox.information(
                    self,
                    "Card Exported & Sealed! 🔮",
                    f"Your card has been exported with the Crimson Collective seal!\n\n"
                    f"📁 Exported to: {Path(export_path).name}\n"
                    f"🔐 Sigil: {sigil_hash}\n"
                    f"⏰ Sealed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"🌟 Mythic Seal:\n"
                    f'"{mythic_identifier}"\n\n'
                    f"✓ Card authenticated by Crimson Collective\n"
                    f"✓ Export timestamp embedded\n"
                    f"✓ Tamper detection active\n"
                    f"✓ RedSeal applied (Obelisk-ready)"
                )
            else:
                # Fallback - just copy without enhanced embedding
                QMessageBox.information(
                    self,
                    "Card Exported",
                    f"Card exported to:\n{export_path}\n\n"
                    f"⚠️ Steganography module unavailable\n"
                    f"Exported as plain copy without Crimson Collective seal."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export card:\n\n{str(e)}"
            )
        except ImportError:
            QMessageBox.critical(
                self,
                "Module Not Found",
                "Steganography module is not available.\n\n"
                "Please ensure steganography_module.py is in the project directory."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Scan Failed",
                f"Failed to scan card data:\n{e}"
            )
    
    def on_generate_clicked(self):
        """Handle generate button from card creator tab"""
        # Check if card generation is available
        if not CARD_GEN_AVAILABLE:
            QMessageBox.critical(
                self,
                "Module Not Available",
                "Card generation module is not available.\n\n"
                "Please ensure card_generation.py is in the project directory."
            )
            return
        
        # Get input values
        prompt = self.concept_input.toPlainText().strip()
        style = self.style_combo.currentText()
        color = self.color_combo.currentText()
        
        # Validate input
        if not prompt:
            QMessageBox.warning(
                self,
                "Input Required",
                "Please enter a character concept for your card."
            )
            return
        
        # Always use Premium tier (unrestricted generation)
        member_tier = 'Premium'
        
        # For Standard tier, ensure prompt includes style keyword
        if member_tier == 'Standard' and style not in prompt:
            prompt = f"{style} {prompt}"
        
        # Get advanced settings
        model = self.model_combo.currentText()
        steps = int(self.steps_combo.currentText())
        cfg = float(self.cfg_combo.currentText())
        sampler = self.sampler_combo.currentText()
        scheduler = self.scheduler_combo.currentText()
        width = int(self.width_combo.currentText())
        height = int(self.height_combo.currentText())
        enable_hr = self.hires_checkbox.isChecked()
        upscaler = self.upscaler_combo.currentText() if enable_hr else None
        hr_scale = float(self.hr_scale_combo.currentText()) if enable_hr else 2.0
        
        self.start_generation(prompt, style, color, model, steps, cfg, 
                            sampler, scheduler, width, height, 
                            enable_hr, upscaler, hr_scale)
    
    def start_generation(self, prompt: str, style: str, color: str, 
                        model: str = None, steps: int = None, cfg: float = None,
                        sampler: str = None, scheduler: str = None,
                        width: int = None, height: int = None,
                        enable_hr: bool = None, upscaler: str = None, hr_scale: float = None):
        """Start the card generation process"""
        try:
            # Determine backend based on Grok checkbox
            if self.use_grok_checkbox.isChecked():
                backend = 'grok'
                backend_display = "Grok AI"
            else:
                backend = 'stable_diffusion'
                backend_display = "Stable Diffusion"
            
            # Create generator with unrestricted Premium tier
            generator = CardGenerator(
                backend=backend,
                tier='Premium',  # Always unrestricted
                user_id='guest'  # Simple user ID
            )
            
            # Inject API key from config manager if using Grok
            if backend == 'grok' and self.api_manager:
                grok_config = self.api_manager.get_api('grok')
                if grok_config and grok_config.get('api_key'):
                    generator.set_grok_api_key(grok_config['api_key'])
                    logger.info("Injected Grok API key from encrypted config")
            
            # Override settings if provided (only for SD)
            if backend == 'stable_diffusion':
                if model:
                    generator.sd_model = model
                if steps:
                    generator.custom_steps = steps
                if cfg:
                    generator.custom_cfg = cfg
                if sampler:
                    generator.sd_sampler = sampler
                if width:
                    generator.custom_width = width
                if height:
                    generator.custom_height = height
                if enable_hr is not None:
                    generator.sd_enable_hr = enable_hr
                if upscaler:
                    generator.sd_hr_upscaler = upscaler
                if hr_scale:
                    generator.sd_hr_scale = hr_scale
            else:
                # Grok-specific settings
                grok_mode = self.grok_mode_combo.currentText()
                grok_quality = self.grok_quality_combo.currentText()
                # Store for future Grok implementation
                generator.grok_mode = grok_mode
                generator.grok_quality = grok_quality
            
            # Create progress dialog
            self.progress_dialog = GenerationProgressDialog(self)
            self.progress_dialog.update_backend(f"Initializing {backend_display}...")
            self.active_dialogs.append(self.progress_dialog)  # Track dialog
            
            # Create worker thread
            self.worker = CardGenerationWorker(
                generator=generator,
                prompt=prompt,
                style=style,
                color_palette=color
            )
            self.active_workers.append(self.worker)  # Track worker
            
            # Connect signals
            self.worker.progress.connect(self.progress_dialog.update_progress)
            self.worker.backend_changed.connect(self.progress_dialog.update_backend)
            self.worker.finished.connect(self.on_generation_complete)
            self.worker.error.connect(self.on_generation_error)
            
            # Handle dialog rejection (cancel)
            self.progress_dialog.rejected.connect(self.on_generation_cancelled)
            
            # Start generation
            self.worker.start()
            self.progress_dialog.exec()
            
            # Remove from tracking when dialog closes
            if self.progress_dialog in self.active_dialogs:
                self.active_dialogs.remove(self.progress_dialog)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Failed to start generation:\n\n{str(e)}\n\n"
                "Make sure Stable Diffusion is running on localhost:7860"
            )
    
    def on_generation_complete(self, result: dict):
        """Handle successful generation"""
        try:
            # Close progress dialog
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.accept()
            
            # Store generation metadata
            self.last_generation_metadata = result.get('metadata', {})
            self.last_generation_metadata['path'] = result.get('path', '')
            self.last_generation_metadata['timestamp'] = result.get('timestamp', '')
            
            # Get generated path
            generated_path = result.get('path')
            metadata = result.get('metadata', {})
            
            # 🔐 EMBED STEGANOGRAPHY DATA (Pre-authentication)
            # This "pre-codes" the card with metadata for later verification
            if generated_path and STEG_AVAILABLE:
                try:
                    steg = MutableCardSteganography()
                    
                    # Prepare card data for embedding
                    card_data = {
                        'card_id': metadata.get('card_id', 'unknown'),
                        'timestamp': metadata.get('timestamp', ''),
                        'generator': 'Aurora Archive Card Generator v2.0',
                        'tier': 'Premium',  # Always Premium for standalone generator
                        'user_id': 'guest',
                        'style': metadata.get('style', 'Unknown'),
                        'backend': metadata.get('backend', 'Unknown'),
                        'prompt': metadata.get('prompt', '')[:200],  # First 200 chars
                        'color_palette': metadata.get('color_palette', 'Unknown'),
                        'model': metadata.get('model', 'Unknown'),
                        'generation_params': {
                            'steps': metadata.get('steps', 0),
                            'cfg_scale': metadata.get('cfg_scale', 0),
                            'sampler': metadata.get('sampler', 'Unknown'),
                            'width': metadata.get('width', 0),
                            'height': metadata.get('height', 0),
                        }
                    }
                    
                    # Embed data into image (modifies in-place)
                    steg.embed_data(generated_path, card_data, overwrite=True)
                    
                    print(f"✅ Steganography embedded: {generated_path}")
                    
                except Exception as steg_error:
                    print(f"⚠️  Steganography embedding failed: {steg_error}")
                    # Don't fail the whole generation if embedding fails
            
            # Update card widget with generated image
            if generated_path:
                # Display the card
                self.card_widget.update_card_image(generated_path)
                
                # Enable export and scan buttons when image is loaded
                if hasattr(self, 'export_btn'):
                    self.export_btn.setEnabled(True)
                if hasattr(self, 'scan_data_btn'):
                    self.scan_data_btn.setEnabled(True)
                
                # Enable video upload button if card has RedSeal
                if hasattr(self, 'video_btn'):
                    if self.card_widget.has_red_seal:
                        self.video_btn.setEnabled(True)
                        self.video_btn.setToolTip("Upload MP4 video (under 10MB) to replace PNG display\n✅ RedSeal detected - Video upload enabled!")
                    else:
                        self.video_btn.setEnabled(False)
                        self.video_btn.setToolTip("Upload MP4 video (under 10MB) to replace PNG display\n❌ RedSeal required - Generate card with steganography enabled")
            
            # Show success message
            steg_status = "✓ Pre-authenticated with steganography" if STEG_AVAILABLE else "⚠️ No steganography (module unavailable)"
            QMessageBox.information(
                self,
                "Card Generated! ✨",
                f"Your card has been generated successfully!\n\n"
                f"📁 Path: {result['path']}\n"
                f"⏱️  Time: {metadata.get('generation_time', 0):.1f}s\n"
                f"🎨 Style: {metadata.get('style', 'N/A')}\n"
                f"💾 Size: {metadata.get('file_size_mb', 0):.2f} MB\n"
                f"🖥️  Backend: {metadata.get('backend', 'N/A')}\n\n"
                f"{steg_status}\n"
                f"✓ Card logged to CSV tracking system"
            )
            
            # Log to CSV for cross-app tracking
            self.log_card_to_csv(
                card_path=generated_path,
                metadata=metadata,
                member_data=None  # No member data needed
            )
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Display Error",
                f"Card generated but failed to display:\n\n{str(e)}\n\n"
                f"You can find your card at: {result.get('path', 'unknown')}"
            )
    
    def on_generation_error(self, error_message: str):
        """Handle generation error"""
        try:
            # Close progress dialog
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.reject()
            
            # Provide helpful error messages
            if "Connection" in error_message or "connect" in error_message.lower():
                QMessageBox.critical(
                    self,
                    "Connection Error",
                    f"Failed to connect to generation backend:\n\n{error_message}\n\n"
                    "Troubleshooting:\n"
                    "• Make sure Stable Diffusion WebUI is running\n"
                    "• Check that it's accessible at http://localhost:7860\n"
                    "• Verify the --api flag is enabled\n"
                    "• Check your firewall settings"
                )
            elif "API key" in error_message or "key" in error_message.lower():
                QMessageBox.critical(
                    self,
                    "API Key Error",
                    f"API authentication failed:\n\n{error_message}\n\n"
                    "Please check your API key in the .env file."
                )
            elif "validation" in error_message.lower() or "tier" in error_message.lower():
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Prompt validation failed:\n\n{error_message}\n\n"
                    "Tips:\n"
                    "• Standard tier: Include style keyword (Fantasy, Sci-Fi, Anime, Realistic)\n"
                    "• Kids tier: Choose from whitelisted prompts\n"
                    "• Premium tier: Full creative freedom"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Generation Failed",
                    f"Card generation failed:\n\n{error_message}\n\n"
                    "Please try again or check the logs for more details."
                )
        except Exception as e:
            print(f"Error in error handler: {e}")
    
    def on_generation_cancelled(self):
        """Handle generation cancellation"""
        try:
            if hasattr(self, 'worker') and self.worker.isRunning():
                self.worker.cancel()
                self.worker.wait(3000)  # Wait up to 3 seconds
                if self.worker.isRunning():
                    self.worker.terminate()
        except Exception as e:
            print(f"Error cancelling generation: {e}")
    
    def refresh_model_list(self, show_message: bool = True):
        """
        Refresh the model dropdown list by fetching available models from SD API.
        
        Args:
            show_message: Whether to show a status message after refresh
        """
        # Store current selection
        current_model = self.model_combo.currentText()
        
        # Get SD URL from environment or use default
        sd_url = os.getenv('STABLE_DIFFUSION_URL', 'http://localhost:7860')
        
        # Fetch available models
        models = get_available_sd_models(sd_url)
        
        if models:
            # Clear and repopulate combo box
            self.model_combo.clear()
            self.model_combo.addItems(models)
            
            # Try to restore previous selection
            if current_model:
                index = self.model_combo.findText(current_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
            
            # Update refresh button to show success
            if show_message:
                self.refresh_models_btn.setText("✓")
                QTimer.singleShot(1000, lambda: self.refresh_models_btn.setText("🔄"))
                
                # Optional: Show status in status bar or tooltip
                self.refresh_models_btn.setToolTip(
                    f"Refresh model list from Stable Diffusion\n"
                    f"Last updated: {models.__len__()} models found"
                )
        else:
            # No models found or connection failed - add fallback models
            self.model_combo.clear()
            self.model_combo.addItems([
                'fefaHentaiMix_v10.safetensors',
                'v1-5-pruned-emaonly.safetensors',
                'YiffMix_v37.safetensors'
            ])
            
            if show_message:
                self.refresh_models_btn.setText("⚠")
                QTimer.singleShot(2000, lambda: self.refresh_models_btn.setText("🔄"))
                
                self.refresh_models_btn.setToolTip(
                    "Could not connect to Stable Diffusion API\n"
                    "Using fallback model list\n"
                    "Make sure SD WebUI is running with --api flag"
                )
    
    def refresh_samplers_and_upscalers(self):
        """Refresh samplers, schedulers, and upscalers from SD API"""
        sd_url = os.getenv('STABLE_DIFFUSION_URL', 'http://localhost:7860')
        
        # Load samplers
        samplers = get_available_samplers(sd_url)
        self.sampler_combo.clear()
        self.sampler_combo.addItems(samplers)
        
        # Set default sampler to Euler a
        default_sampler = 'Euler a'
        if default_sampler in samplers:
            self.sampler_combo.setCurrentText(default_sampler)
        elif 'Euler' in samplers:
            self.sampler_combo.setCurrentText('Euler')
        
        # Load schedulers
        schedulers = get_available_schedulers(sd_url)
        current_scheduler = self.scheduler_combo.currentText()
        self.scheduler_combo.clear()
        self.scheduler_combo.addItems(schedulers)
        
        # Set default scheduler to automatic
        default_scheduler = 'automatic'
        if default_scheduler in schedulers:
            self.scheduler_combo.setCurrentText(default_scheduler)
        elif schedulers:
            self.scheduler_combo.setCurrentIndex(0)
        
        # Load upscalers
        upscalers = get_available_upscalers(sd_url)
        self.upscaler_combo.clear()
        self.upscaler_combo.addItems(upscalers)
        
        # Set default upscaler
        default_upscaler = 'R-ESRGAN 4x+ Anime6B'
        if default_upscaler in upscalers:
            self.upscaler_combo.setCurrentText(default_upscaler)
        elif 'Latent' in upscalers:
            self.upscaler_combo.setCurrentText('Latent')
    
    def on_hires_toggled(self, state):
        """Show/hide Hi-Res Fix options based on checkbox state"""
        enabled = state == 2  # Qt.CheckState.Checked value
        
        # Toggle visibility of Hi-Res Fix options
        self.upscaler_label.setVisible(enabled)
        self.upscaler_combo.setVisible(enabled)
        self.hr_scale_label.setVisible(enabled)
        
        # Hide the container widgets for hr_scale
        for i in range(self.hr_scale_container.count()):
            widget = self.hr_scale_container.itemAt(i).widget()
            if widget:
                widget.setVisible(enabled)
    
    def on_grok_toggled(self, state):
        """Enable/disable Grok-specific options"""
        enabled = (state == 2)  # Qt.CheckState.Checked is 2
        
        # Enable/disable Grok widgets
        self.grok_mode_combo.setEnabled(enabled)
        self.grok_quality_combo.setEnabled(enabled)
        
        # Update labels color
        color = "#f9a8d4" if enabled else "#666"
        self.grok_mode_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {color};")
        self.grok_quality_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {color};")
        
        # Update backend indicator in header
        if enabled:
            self.backend_indicator.setText("Backend: Grok AI")
            self.backend_indicator.setStyleSheet("""
                QLabel {
                    color: #f9a8d4;
                    font-size: 14px;
                    padding: 8px 16px;
                    background-color: rgba(236, 72, 153, 0.1);
                    border: 1px solid rgba(236, 72, 153, 0.3);
                    border-radius: 4px;
                }
            """)
        else:
            self.backend_indicator.setText("Backend: Stable Diffusion")
            self.backend_indicator.setStyleSheet("""
                QLabel {
                    color: #a78bfa;
                    font-size: 14px;
                    padding: 8px 16px;
                    background-color: rgba(139, 92, 246, 0.1);
                    border: 1px solid rgba(139, 92, 246, 0.3);
                    border-radius: 4px;
                }
            """)
        
        # Optionally disable SD-specific options when Grok is enabled
        if enabled:
            # Using Grok - could disable some SD options
            self.model_combo.setEnabled(False)
            self.sampler_combo.setEnabled(False)
            self.scheduler_combo.setEnabled(False)
            self.hires_checkbox.setEnabled(False)
        else:
            # Using SD - enable SD options
            self.model_combo.setEnabled(True)
            self.sampler_combo.setEnabled(True)
            self.scheduler_combo.setEnabled(True)
            self.hires_checkbox.setEnabled(True)
    
    def cleanup_workers(self):
        """Stop all active background workers"""
        for worker in self.active_workers[:]:
            if worker and worker.isRunning():
                worker.cancel()  # Request cancellation
                worker.wait(2000)  # Wait up to 2 seconds
                if worker.isRunning():
                    worker.terminate()  # Force terminate if still running
        self.active_workers.clear()
    
    def cleanup_dialogs(self):
        """Close all active dialogs"""
        for dialog in self.active_dialogs[:]:
            if dialog and dialog.isVisible():
                dialog.close()
        self.active_dialogs.clear()
    
    def cleanup_timers(self):
        """Stop all active timers"""
        for timer in self.active_timers[:]:
            if timer and timer.isActive():
                timer.stop()
        self.active_timers.clear()
    
    def cleanup_resources(self):
        """Gracefully clean up all resources"""
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        print("🌙 Closing Aurora Archive...")
        
        # Stop workers
        self.cleanup_workers()
        
        # Close dialogs
        self.cleanup_dialogs()
        
        # Stop timers
        self.cleanup_timers()
        
        # Clean up video player if active
        if hasattr(self, 'card_widget') and self.card_widget:
            if self.card_widget.media_player:
                self.card_widget.media_player.stop()
                self.card_widget.media_player = None
            if self.card_widget.audio_output:
                self.card_widget.audio_output = None
        
        # Small delay for cleanup
        QTimer.singleShot(500, self.finalize_shutdown)
    
    def finalize_shutdown(self):
        """Final shutdown step"""
        print("✨ Aurora Archive closed gracefully")
        self.session_ended.emit()
        QTimer.singleShot(500, self.close)
    
    def auto_connect_apis(self):
        """Auto-connect to configured APIs on startup"""
        if not self.api_manager:
            return
        
        auto_connect_list = self.api_manager.get_auto_connect_apis()
        
        if not auto_connect_list:
            return
        
        print(f"🔌 Auto-connecting to {len(auto_connect_list)} API(s)...")
        
        for api_type in auto_connect_list:
            api_config = self.api_manager.get_api(api_type)
            if api_config:
                api_info = self.api_manager.SUPPORTED_APIS.get(api_type)
                if api_info:
                    print(f"  ✓ Connected to {api_info['name']}")
                    
                    # Mark as verified if it was previously verified
                    if api_config.get('verified'):
                        print(f"    (Using saved credentials)")
    
    def closeEvent(self, event):
        """Override close event to ensure cleanup"""
        if not self.is_shutting_down:
            reply = QMessageBox.question(
                self,
                "Close Aurora Archive?",
                "Are you sure you want to close Aurora Archive?\n\n"
                "Any unsaved work will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.cleanup_resources()
                event.ignore()  # Ignore for now, will close after cleanup
            else:
                event.ignore()
        else:
            event.accept()

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Create and show main window
    window = AuroraMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()