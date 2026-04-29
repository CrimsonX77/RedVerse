#!/usr/bin/env python3
"""
Consciousness Control Center - Unified GUI for entire consciousness system
Combines: RevolverCore, ConsciousnessBridge, LLM Management, Game Connection
Author: Crimson Valentine
Date: January 12, 2026
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QGroupBox, QScrollArea,
    QMessageBox, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QTabWidget, QComboBox, QSpinBox, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from revocore import RevolverCore
from consciousness_bridge import ConsciousnessBridge


# =============================================================================
# SYSTEM STATUS THREAD
# =============================================================================

class SystemStatusWorker(QThread):
    """Monitor system component status"""
    status_updated = pyqtSignal(dict)  # component_name: status
    
    def __init__(self, bridge: Optional[ConsciousnessBridge] = None):
        super().__init__()
        self.bridge = bridge
        self.running = True
    
    def run(self):
        """Check component status periodically"""
        while self.running:
            status = {}
            
            if self.bridge:
                status['bridge'] = str(self.bridge.state.value)
                status['llm'] = 'enabled' if self.bridge.llm_enabled else 'disabled'
                status['game'] = 'connected' if self.bridge.game_controller and self.bridge.game_controller.connected else 'disconnected'
                status['soul'] = self.bridge.active_soul.persona_name if self.bridge.active_soul else 'None'
            else:
                status['bridge'] = 'offline'
                status['llm'] = 'unknown'
                status['game'] = 'unknown'
                status['soul'] = 'None'
            
            self.status_updated.emit(status)
            self.msleep(2000)  # Update every 2 seconds
    
    def stop(self):
        self.running = False


# =============================================================================
# LLM CONFIGURATION DIALOG
# =============================================================================

class LLMConfigDialog(QDialog):
    """Dialog for LLM configuration"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("LLM Configuration")
        self.setMinimumSize(600, 500)
        
        self.config = {
            'provider': 'ollama',
            'model': 'CrimsonDragonX7/Whore:latest',
            'api_key': '',
            'api_endpoint': '',
            'temperature': 1.0,
            'max_tokens': 350
        }
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("◆ LLM CONFIGURATION ◆")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFD700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Provider selection
        provider_group = QGroupBox("◆ Provider")
        provider_layout = QVBoxLayout(provider_group)
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(['ollama', 'openai', 'anthropic', 'github', 'azure'])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        
        layout.addWidget(provider_group)
        
        # Model selection
        model_group = QGroupBox("◆ Model")
        model_layout = QVBoxLayout(model_group)
        
        model_input_layout = QHBoxLayout()
        model_input_layout.addWidget(QLabel("Model:"))
        self.model_input = QLineEdit("CrimsonDragonX7/Whore:latest")
        model_input_layout.addWidget(self.model_input)
        model_layout.addLayout(model_input_layout)
        
        # Common models quick select
        quick_models = QHBoxLayout()
        quick_models.addWidget(QLabel("Quick:"))
        
        for model in ['CrimsonDragonX7/Whore:latest', 'CrimsonDragonX7/Rable:latest', 'CrimsonDragonX7/Serah:latest', 'CrimsonDragonX7/Sablexx:latest', 'CrimsonDragonX7/Sable:latest', 'CrimsonDragonX7/Navi:latest']:
            btn = QPushButton(model)
            btn.clicked.connect(lambda checked, m=model: self.model_input.setText(m))
            quick_models.addWidget(btn)
        
        model_layout.addLayout(quick_models)
        layout.addWidget(model_group)
        
        # API Configuration
        api_group = QGroupBox("◆ API Configuration")
        api_layout = QVBoxLayout(api_group)
        
        # API Key
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Optional - for OpenAI/Anthropic")
        key_layout.addWidget(self.api_key_input)
        api_layout.addLayout(key_layout)
        
        # API Endpoint
        endpoint_layout = QHBoxLayout()
        endpoint_layout.addWidget(QLabel("Endpoint:"))
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText("Optional - custom endpoint URL")
        endpoint_layout.addWidget(self.endpoint_input)
        api_layout.addLayout(endpoint_layout)
        
        layout.addWidget(api_group)
        
        # Generation parameters
        params_group = QGroupBox("◆ Generation Parameters")
        params_layout = QVBoxLayout(params_group)
        
        # Temperature
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        self.temp_spin = QSpinBox()
        self.temp_spin.setMinimum(0)
        self.temp_spin.setMaximum(20)
        self.temp_spin.setValue(7)
        self.temp_spin.setSuffix(" (0.7)")
        temp_layout.addWidget(self.temp_spin)
        temp_layout.addWidget(QLabel("Creativity level"))
        params_layout.addLayout(temp_layout)
        
        # Max tokens
        tokens_layout = QHBoxLayout()
        tokens_layout.addWidget(QLabel("Max Tokens:"))
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setMinimum(10)
        self.tokens_spin.setMaximum(4000)
        self.tokens_spin.setValue(350)
        tokens_layout.addWidget(self.tokens_spin)
        tokens_layout.addWidget(QLabel("Response length"))
        params_layout.addLayout(tokens_layout)
        
        layout.addWidget(params_group)
        
        # Test connection button
        test_btn = QPushButton("🔌 Test Connection")
        test_btn.clicked.connect(self._test_connection)
        layout.addWidget(test_btn)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_config)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _on_provider_changed(self, provider: str):
        """Update UI based on provider"""
        # Show/hide API key based on provider
        needs_key = provider in ['openai', 'anthropic', 'github', 'azure']
        self.api_key_input.setEnabled(needs_key)
        
        # Update model suggestions
        if provider == 'ollama':
            self.model_input.setText('llama2')
        elif provider == 'openai':
            self.model_input.setText('gpt-4')
        elif provider == 'anthropic':
            self.model_input.setText('claude-3-opus-20240229')
    
    def _test_connection(self):
        """Test LLM connection"""
        from PyQt6.QtWidgets import QProgressDialog
        
        # Get current config
        provider = self.provider_combo.currentText()
        model = self.model_input.text()
        api_key = self.api_key_input.text()
        endpoint = self.endpoint_input.text()
        temp = self.temp_spin.value() / 10.0
        max_tokens = self.tokens_spin.value()
        
        # Show progress
        progress = QProgressDialog("Testing LLM connection...", None, 0, 0, self)
        progress.setWindowTitle("Testing Connection")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Import based on provider
            if provider == 'ollama':
                try:
                    import ollama
                    # Test with simple message
                    response = ollama.chat(
                        model=model,
                        messages=[{'role': 'user', 'content': 'Say hello in 5 words or less'}],
                        options={
                            'temperature': temp,
                            'num_predict': min(max_tokens, 50)
                        }
                    )
                    result_text = response['message']['content']
                    progress.close()
                    QMessageBox.information(
                        self,
                        "✓ Connection Successful",
                        f"Provider: {provider}\nModel: {model}\n\nResponse:\n{result_text}"
                    )
                except ImportError:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "✗ Missing Package",
                        "Ollama package not installed.\n\nInstall with:\npip install ollama"
                    )
                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "✗ Connection Failed",
                        f"Error: {str(e)}\n\nMake sure:\n1. Ollama is running\n2. Model '{model}' is pulled\n   (ollama pull {model})"
                    )
            
            elif provider == 'openai':
                try:
                    import openai
                    if not api_key:
                        progress.close()
                        QMessageBox.warning(self, "Missing API Key", "OpenAI requires an API key.")
                        return
                    
                    client = openai.OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{'role': 'user', 'content': 'Say hello in 5 words or less'}],
                        temperature=temp,
                        max_tokens=min(max_tokens, 50)
                    )
                    result_text = response.choices[0].message.content
                    progress.close()
                    QMessageBox.information(
                        self,
                        "✓ Connection Successful",
                        f"Provider: {provider}\nModel: {model}\n\nResponse:\n{result_text}"
                    )
                except ImportError:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "✗ Missing Package",
                        "OpenAI package not installed.\n\nInstall with:\npip install openai"
                    )
                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "✗ Connection Failed",
                        f"Error: {str(e)}\n\nCheck:\n1. API key is valid\n2. Model name is correct\n3. You have API credits"
                    )
            
            elif provider == 'anthropic':
                try:
                    import anthropic
                    if not api_key:
                        progress.close()
                        QMessageBox.warning(self, "Missing API Key", "Anthropic requires an API key.")
                        return
                    
                    client = anthropic.Anthropic(api_key=api_key)
                    response = client.messages.create(
                        model=model,
                        max_tokens=min(max_tokens, 50),
                        temperature=temp,
                        messages=[{'role': 'user', 'content': 'Say hello in 5 words or less'}]
                    )
                    result_text = response.content[0].text
                    progress.close()
                    QMessageBox.information(
                        self,
                        "✓ Connection Successful",
                        f"Provider: {provider}\nModel: {model}\n\nResponse:\n{result_text}"
                    )
                except ImportError:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "✗ Missing Package",
                        "Anthropic package not installed.\n\nInstall with:\npip install anthropic"
                    )
                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "✗ Connection Failed",
                        f"Error: {str(e)}\n\nCheck:\n1. API key is valid\n2. Model name is correct"
                    )
            
            elif provider in ['github', 'azure']:
                progress.close()
                QMessageBox.information(
                    self,
                    "Provider Not Implemented",
                    f"{provider.title()} testing not yet implemented.\n\nConfiguration will be saved, but testing requires implementation."
                )
            
            else:
                progress.close()
                QMessageBox.warning(self, "Unknown Provider", f"Provider '{provider}' not recognized.")
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "✗ Test Failed", f"Unexpected error:\n{str(e)}")
    
    def _save_config(self):
        """Save configuration"""
        self.config['provider'] = self.provider_combo.currentText()
        self.config['model'] = self.model_input.text()
        self.config['api_key'] = self.api_key_input.text()
        self.config['api_endpoint'] = self.endpoint_input.text()
        self.config['temperature'] = self.temp_spin.value() / 10.0
        self.config['max_tokens'] = self.tokens_spin.value()
        self.accept()
    
    def get_config(self) -> dict:
        return self.config


# =============================================================================
# AUTO-SWITCH RULES DIALOG
# =============================================================================

class AutoSwitchDialog(QDialog):
    """Dialog for configuring auto-switch rules"""
    
    def __init__(self, parent, revolver: RevolverCore):
        super().__init__(parent)
        self.revolver = revolver
        self.rules = []
        
        self.setWindowTitle("Auto-Switch Rules")
        self.setMinimumSize(600, 400)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("◆ AUTO-SWITCH RULES ◆")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFD700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        info = QLabel("Define keywords that automatically switch to specific chambers")
        info.setStyleSheet("color: #9cdcfe; font-style: italic;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        # Rules list
        rules_group = QGroupBox("◆ Active Rules")
        rules_layout = QVBoxLayout(rules_group)
        self.rules_list = QListWidget()
        rules_layout.addWidget(self.rules_list)
        
        rules_buttons = QHBoxLayout()
        add_rule_btn = QPushButton("+ Add Rule")
        add_rule_btn.clicked.connect(self._add_rule)
        rules_buttons.addWidget(add_rule_btn)
        
        remove_rule_btn = QPushButton("- Remove Rule")
        remove_rule_btn.clicked.connect(self._remove_rule)
        rules_buttons.addWidget(remove_rule_btn)
        
        rules_layout.addLayout(rules_buttons)
        layout.addWidget(rules_group)
        
        # New rule section
        add_group = QGroupBox("◆ New Rule")
        add_layout = QVBoxLayout(add_group)
        
        keywords_layout = QHBoxLayout()
        keywords_layout.addWidget(QLabel("Keywords:"))
        self.keywords_input = QLineEdit()
        self.keywords_input.setPlaceholderText("e.g., code, debug, programming")
        keywords_layout.addWidget(self.keywords_input)
        add_layout.addLayout(keywords_layout)
        
        chamber_layout = QHBoxLayout()
        chamber_layout.addWidget(QLabel("Chamber:"))
        self.chamber_combo = QComboBox()
        
        for i in range(self.revolver.num_chambers):
            if self.revolver.chambers[i]:
                name = self.revolver.chamber_names.get(i, f"Chamber {i}")
                self.chamber_combo.addItem(f"[{i}] {name}", i)
        
        chamber_layout.addWidget(self.chamber_combo)
        add_layout.addLayout(chamber_layout)
        
        layout.addWidget(add_group)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _add_rule(self):
        keywords_text = self.keywords_input.text().strip()
        if not keywords_text:
            return
        
        chamber_num = self.chamber_combo.currentData()
        keywords = [k.strip().lower() for k in keywords_text.split(',')]
        self.rules.append((keywords, chamber_num))
        
        chamber_name = self.revolver.chamber_names.get(chamber_num, f"Chamber {chamber_num}")
        rule_text = f"{', '.join(keywords)} → [{chamber_num}] {chamber_name}"
        self.rules_list.addItem(rule_text)
        self.keywords_input.clear()
    
    def _remove_rule(self):
        current_row = self.rules_list.currentRow()
        if current_row >= 0:
            self.rules.pop(current_row)
            self.rules_list.takeItem(current_row)
    
    def get_rules(self) -> List[tuple]:
        return self.rules


# =============================================================================
# ASYNC GENERATION WORKER
# =============================================================================

class GenerationWorker(QThread):
    """Background thread for async generation"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, bridge: ConsciousnessBridge, message: str):
        super().__init__()
        self.bridge = bridge
        self.message = message
    
    def run(self):
        try:
            response = self.bridge.process_input(self.message)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# MAIN CONTROL CENTER GUI
# =============================================================================

class ConsciousnessControlCenter(QMainWindow):
    """Unified control center for entire consciousness system"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("◆ CONSCIOUSNESS CONTROL CENTER ◆")
        self.setMinimumSize(1200, 800)
        
        # Core components
        self.revolver: Optional[RevolverCore] = None
        self.bridge: Optional[ConsciousnessBridge] = None
        self.generation_worker: Optional[GenerationWorker] = None
        self.status_worker: Optional[SystemStatusWorker] = None
        self.auto_switch_rules: List[tuple] = []
        self.llm_config: Dict = {}
        
        self._apply_theme()
        self._setup_ui()
        self._initialize_system()
    
    def _apply_theme(self):
        """Apply Crimson dark theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a0a0a;
            }
            QWidget {
                background-color: #1a0a0a;
                color: #c0c0c0;
                font-family: 'Segoe UI';
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
                padding: 8px 16px;
                font-weight: bold;
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
            }
            QLabel {
                color: #c0c0c0;
            }
            QTextEdit {
                background-color: #0f0f0f;
                color: #c0c0c0;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #0f0f0f;
                color: #c0c0c0;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 6px;
            }
            QListWidget {
                background-color: #0f0f0f;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #1a1a1a;
            }
            QListWidget::item:selected {
                background-color: #8B0000;
                color: #FFD700;
            }
            QTabWidget::pane {
                border: 1px solid #2a2a2a;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: #c0c0c0;
                padding: 8px 16px;
                border: 1px solid #1a1a1a;
            }
            QTabBar::tab:selected {
                background-color: #8B0000;
                color: #FFD700;
            }
            QComboBox, QSpinBox {
                background-color: #0f0f0f;
                color: #c0c0c0;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 6px;
            }
            QProgressBar {
                background-color: #0f0f0f;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                text-align: center;
                color: #FFD700;
            }
            QProgressBar::chunk {
                background-color: #8B0000;
            }
        """)
    
    def _setup_ui(self):
        """Setup main UI"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Header with status
        header_layout = QHBoxLayout()
        
        header = QLabel("CONSCIOUSNESS CONTROL CENTER")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #FFD700; padding: 10px;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        # System status indicators
        self.status_bridge = QLabel("⚫ Bridge")
        self.status_llm = QLabel("⚫ LLM")
        self.status_game = QLabel("⚫ Game")
        
        for status_label in [self.status_bridge, self.status_llm, self.status_game]:
            status_label.setStyleSheet("padding: 5px; color: #666666;")
            header_layout.addWidget(status_label)
        
        layout.addLayout(header_layout)
        
        # Main content area - tabs
        self.tabs = QTabWidget()
        
        # Tab 1: Chambers & Chat
        self.tabs.addTab(self._create_chambers_tab(), "🔫 Chambers")
        
        # Tab 2: LLM Configuration
        self.tabs.addTab(self._create_llm_tab(), "🤖 LLM")
        
        # Tab 3: Game Connection
        self.tabs.addTab(self._create_game_tab(), "🎮 Game")
        
        # Tab 4: System Settings
        self.tabs.addTab(self._create_settings_tab(), "⚙ Settings")
        
        layout.addWidget(self.tabs)
        
        # Bottom control bar
        control_bar = self._create_control_bar()
        layout.addWidget(control_bar)
    
    def _create_chambers_tab(self) -> QWidget:
        """Create chambers and chat tab"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # Left: Chambers
        chambers_group = QGroupBox("◆ SOUL CHAMBERS")
        chambers_layout = QVBoxLayout(chambers_group)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #9cdcfe; font-style: italic;")
        chambers_layout.addWidget(self.status_label)
        
        self.chambers_list = QListWidget()
        self.chambers_list.itemDoubleClicked.connect(self._switch_chamber)
        chambers_layout.addWidget(self.chambers_list)
        
        # Chamber controls
        chamber_controls = QVBoxLayout()
        
        autoswitch_btn = QPushButton("⚙ Auto-Switch Rules")
        autoswitch_btn.clicked.connect(self._configure_autoswitch)
        chamber_controls.addWidget(autoswitch_btn)
        
        reload_btn = QPushButton("🔄 Reload Chambers")
        reload_btn.clicked.connect(self._reload_chambers)
        chamber_controls.addWidget(reload_btn)
        
        chamber_adjust = QHBoxLayout()
        chamber_adjust.addWidget(QLabel("Chambers:"))
        self.chamber_spin = QSpinBox()
        self.chamber_spin.setMinimum(6)
        self.chamber_spin.setMaximum(99)
        self.chamber_spin.setValue(6)
        chamber_adjust.addWidget(self.chamber_spin)
        chamber_controls.addLayout(chamber_adjust)
        
        chambers_layout.addLayout(chamber_controls)
        layout.addWidget(chambers_group, stretch=1)
        
        # Right: Chat
        chat_group = QGroupBox("◆ CONVERSATION")
        chat_layout = QVBoxLayout(chat_group)
        
        self.active_indicator = QLabel("Active: None")
        self.active_indicator.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.active_indicator.setStyleSheet("color: #FFD700; padding: 5px;")
        self.active_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chat_layout.addWidget(self.active_indicator)
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        chat_layout.addWidget(self.chat_history)
        
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message...")
        self.message_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.message_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        chat_layout.addLayout(input_layout)
        
        clear_btn = QPushButton("Clear Chat")
        clear_btn.clicked.connect(lambda: self.chat_history.clear())
        chat_layout.addWidget(clear_btn)
        
        layout.addWidget(chat_group, stretch=2)
        
        return widget
    
    def _create_llm_tab(self) -> QWidget:
        """Create LLM configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # LLM Status
        status_group = QGroupBox("◆ LLM STATUS")
        status_layout = QVBoxLayout(status_group)
        
        self.llm_status_label = QLabel("LLM: Not Configured")
        self.llm_status_label.setFont(QFont("Arial", 12))
        self.llm_status_label.setStyleSheet("color: #9cdcfe;")
        status_layout.addWidget(self.llm_status_label)
        
        layout.addWidget(status_group)
        
        # Quick actions
        actions_group = QGroupBox("◆ ACTIONS")
        actions_layout = QVBoxLayout(actions_group)
        
        config_btn = QPushButton("⚙ Configure LLM")
        config_btn.clicked.connect(self._open_llm_config)
        actions_layout.addWidget(config_btn)
        
        self.llm_toggle = QPushButton("🔴 Enable LLM")
        self.llm_toggle.clicked.connect(self._toggle_llm)
        actions_layout.addWidget(self.llm_toggle)
        
        test_btn = QPushButton("🔬 Test LLM")
        test_btn.clicked.connect(self._test_llm)
        actions_layout.addWidget(test_btn)
        
        layout.addWidget(actions_group)
        
        # Configuration display
        config_group = QGroupBox("◆ CURRENT CONFIGURATION")
        config_layout = QVBoxLayout(config_group)
        
        self.config_display = QTextEdit()
        self.config_display.setReadOnly(True)
        self.config_display.setMaximumHeight(200)
        config_layout.addWidget(self.config_display)
        
        layout.addWidget(config_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_game_tab(self) -> QWidget:
        """Create game connection tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Connection status
        status_group = QGroupBox("◆ GAME CONNECTION")
        status_layout = QVBoxLayout(status_group)
        
        self.game_status_label = QLabel("Game: Disconnected")
        self.game_status_label.setFont(QFont("Arial", 12))
        self.game_status_label.setStyleSheet("color: #f48771;")
        status_layout.addWidget(self.game_status_label)
        
        layout.addWidget(status_group)
        
        # Connection settings
        settings_group = QGroupBox("◆ CONNECTION SETTINGS")
        settings_layout = QVBoxLayout(settings_group)
        
        ws_layout = QHBoxLayout()
        ws_layout.addWidget(QLabel("WebSocket URL:"))
        self.ws_url_input = QLineEdit("ws://localhost:8888")
        ws_layout.addWidget(self.ws_url_input)
        settings_layout.addLayout(ws_layout)
        
        layout.addWidget(settings_group)
        
        # Actions
        actions_group = QGroupBox("◆ ACTIONS")
        actions_layout = QVBoxLayout(actions_group)
        
        self.game_connect_btn = QPushButton("🔌 Connect to Game")
        self.game_connect_btn.clicked.connect(self._connect_game)
        actions_layout.addWidget(self.game_connect_btn)
        
        self.game_disconnect_btn = QPushButton("🔌 Disconnect")
        self.game_disconnect_btn.clicked.connect(self._disconnect_game)
        self.game_disconnect_btn.setEnabled(False)
        actions_layout.addWidget(self.game_disconnect_btn)
        
        start_server_btn = QPushButton("🚀 Start Game Server")
        start_server_btn.clicked.connect(self._start_game_server)
        actions_layout.addWidget(start_server_btn)
        
        layout.addWidget(actions_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_settings_tab(self) -> QWidget:
        """Create system settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Paths
        paths_group = QGroupBox("◆ PATHS")
        paths_layout = QVBoxLayout(paths_group)
        
        souls_layout = QHBoxLayout()
        souls_layout.addWidget(QLabel("Souls Directory:"))
        self.souls_path_label = QLabel("/home/crimson/Desktop/Dev/MechPilot/ai_copilot/personas")
        self.souls_path_label.setStyleSheet("color: #9cdcfe;")
        souls_layout.addWidget(self.souls_path_label)
        paths_layout.addLayout(souls_layout)
        
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("Memory Directory:"))
        self.memory_path_label = QLabel(str(Path.home() / ".consciousness_memory"))
        self.memory_path_label.setStyleSheet("color: #9cdcfe;")
        memory_layout.addWidget(self.memory_path_label)
        paths_layout.addLayout(memory_layout)
        
        layout.addWidget(paths_group)
        
        # Memory management
        memory_group = QGroupBox("◆ MEMORY MANAGEMENT")
        memory_layout = QVBoxLayout(memory_group)
        
        save_btn = QPushButton("💾 Save Memory")
        save_btn.clicked.connect(self._save_memory)
        memory_layout.addWidget(save_btn)
        
        clear_btn = QPushButton("🗑 Clear Memory")
        clear_btn.clicked.connect(self._clear_memory)
        memory_layout.addWidget(clear_btn)
        
        layout.addWidget(memory_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_control_bar(self) -> QWidget:
        """Create bottom control bar"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        self.bridge_toggle = QPushButton("🟢 Start Bridge")
        self.bridge_toggle.clicked.connect(self._toggle_bridge)
        layout.addWidget(self.bridge_toggle)
        
        layout.addStretch()
        
        self.power_btn = QPushButton("⚡ FULL SYSTEM START")
        self.power_btn.setMinimumHeight(40)
        self.power_btn.setStyleSheet("""
            QPushButton {
                background-color: #006400;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #008000;
            }
        """)
        self.power_btn.clicked.connect(self._full_system_start)
        layout.addWidget(self.power_btn)
        
        return widget
    
    def _initialize_system(self):
        """Initialize all system components"""
        # Paths
        souls_dir = Path("/home/crimson/Desktop/Dev/MechPilot/ai_copilot/personas")
        memory_dir = Path.home() / ".consciousness_memory"
        
        # Initialize RevolverCore
        if souls_dir.exists():
            soul_files = list(souls_dir.glob("*.yaml")) + list(souls_dir.glob("*.yml"))
            num_chambers = max(6, min(len(soul_files), 99))
            
            self.revolver = RevolverCore(
                num_chambers=num_chambers,
                auto_load_directory=str(souls_dir)
            )
        else:
            self.revolver = RevolverCore(num_chambers=6)
            QMessageBox.warning(
                self,
                "Souls Not Found",
                f"Souls directory not found:\n{souls_dir}\n\nCreate it and add YAML soul files."
            )
        
        # Initialize ConsciousnessBridge
        self.bridge = ConsciousnessBridge(souls_dir, memory_dir)
        
        # Start status monitoring
        self.status_worker = SystemStatusWorker(self.bridge)
        self.status_worker.status_updated.connect(self._update_status_indicators)
        self.status_worker.start()
        
        # Update UI
        self._update_chamber_list()
        self._update_llm_status()
    
    def _update_status_indicators(self, status: dict):
        """Update system status indicators"""
        # Bridge status
        bridge_status = status.get('bridge', 'offline')
        if bridge_status == 'active':
            self.status_bridge.setText("🟢 Bridge")
            self.status_bridge.setStyleSheet("padding: 5px; color: #00FF00;")
        elif bridge_status == 'ready':
            self.status_bridge.setText("🟡 Bridge")
            self.status_bridge.setStyleSheet("padding: 5px; color: #FFD700;")
        else:
            self.status_bridge.setText("⚫ Bridge")
            self.status_bridge.setStyleSheet("padding: 5px; color: #666666;")
        
        # LLM status
        llm_status = status.get('llm', 'disabled')
        if llm_status == 'enabled':
            self.status_llm.setText("🟢 LLM")
            self.status_llm.setStyleSheet("padding: 5px; color: #00FF00;")
        else:
            self.status_llm.setText("⚫ LLM")
            self.status_llm.setStyleSheet("padding: 5px; color: #666666;")
        
        # Game status
        game_status = status.get('game', 'disconnected')
        if game_status == 'connected':
            self.status_game.setText("🟢 Game")
            self.status_game.setStyleSheet("padding: 5px; color: #00FF00;")
        else:
            self.status_game.setText("⚫ Game")
            self.status_game.setStyleSheet("padding: 5px; color: #666666;")
    
    def _update_chamber_list(self):
        """Update chamber list display"""
        self.chambers_list.clear()
        
        if not self.revolver:
            return
        
        loaded = 0
        for i in range(self.revolver.num_chambers):
            if self.revolver.chambers[i]:
                name = self.revolver.chamber_names.get(i, f"Chamber {i}")
                realizations = len(self.revolver.chambers[i].realizations)
                
                item = QListWidgetItem(f"[{i}] {name} ({realizations} realizations)")
                
                if i == self.revolver.current_chamber:
                    item.setForeground(QColor("#FFD700"))
                    item.setBackground(QColor("#8B0000"))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.chambers_list.addItem(item)
                loaded += 1
        
        self.status_label.setText(f"Loaded: {loaded}/{self.revolver.num_chambers} chambers")
        
        if loaded > 0:
            active_name = self.revolver.chamber_names.get(
                self.revolver.current_chamber,
                f"Chamber {self.revolver.current_chamber}"
            )
            self.active_indicator.setText(f"🎯 Active: [{self.revolver.current_chamber}] {active_name}")
        else:
            self.active_indicator.setText("Active: None")
    
    def _update_llm_status(self):
        """Update LLM status display"""
        if self.bridge and self.bridge.llm_enabled:
            self.llm_status_label.setText(f"LLM: ✓ {self.bridge.llm_provider} - {self.bridge.llm_model}")
            self.llm_status_label.setStyleSheet("color: #00FF00;")
            self.llm_toggle.setText("🟢 Disable LLM")
            
            config_text = f"""Provider: {self.bridge.llm_provider}
Model: {self.bridge.llm_model}
Temperature: {self.bridge.llm_temperature}
Max Tokens: {self.bridge.llm_max_tokens}
Status: Enabled"""
            self.config_display.setText(config_text)
        else:
            self.llm_status_label.setText("LLM: Disabled (Using scripted responses)")
            self.llm_status_label.setStyleSheet("color: #9cdcfe;")
            self.llm_toggle.setText("🔴 Enable LLM")
            self.config_display.setText("LLM not configured. Click 'Configure LLM' to set up.")
    
    def _switch_chamber(self, item: QListWidgetItem):
        """Switch to selected chamber"""
        chamber_num = item.data(Qt.ItemDataRole.UserRole)
        
        try:
            self.revolver.rotate_to(chamber_num)
            
            # Also update bridge if active
            if self.bridge and self.bridge.active_soul:
                soul_file = self.revolver.chamber_files.get(chamber_num)
                if soul_file:
                    filename = Path(soul_file).name
                    self.bridge.hot_swap_soul(filename)
            
            self._update_chamber_list()
            
            chamber_name = self.revolver.chamber_names.get(chamber_num, f"Chamber {chamber_num}")
            self._append_system_message(f"🔄 Switched to [{chamber_num}] {chamber_name}")
        except Exception as e:
            QMessageBox.warning(self, "Switch Failed", str(e))
    
    def _send_message(self):
        """Send message through bridge"""
        message = self.message_input.text().strip()
        if not message:
            return
        
        if not self.bridge or not self.bridge.active_soul:
            QMessageBox.warning(self, "No Active Soul", "Please ensure a soul is loaded in the bridge.")
            return
        
        # Check auto-switch rules
        self._check_autoswitch(message)
        
        self._append_user_message(message)
        self.message_input.clear()
        
        # Disable input
        self.message_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        # Generate response
        self.generation_worker = GenerationWorker(self.bridge, message)
        self.generation_worker.finished.connect(self._on_generation_finished)
        self.generation_worker.error.connect(self._on_generation_error)
        self.generation_worker.start()
    
    def _check_autoswitch(self, message: str):
        """Check auto-switch rules"""
        message_lower = message.lower()
        
        for keywords, chamber_num in self.auto_switch_rules:
            if any(keyword in message_lower for keyword in keywords):
                if self.revolver.current_chamber != chamber_num:
                    try:
                        item = self.chambers_list.findItems(f"[{chamber_num}]", Qt.MatchFlag.MatchStartsWith)[0]
                        self._switch_chamber(item)
                    except:
                        pass
    
    def _on_generation_finished(self, response: str):
        """Handle generation completion"""
        self._append_assistant_message(response)
        self.message_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.message_input.setFocus()
        self._update_chamber_list()
    
    def _on_generation_error(self, error: str):
        """Handle generation error"""
        self._append_system_message(f"❌ Error: {error}")
        self.message_input.setEnabled(True)
        self.send_btn.setEnabled(True)
    
    def _append_user_message(self, message: str):
        self.chat_history.append(f'<p style="color: #00FF00;"><b>You:</b> {message}</p>')
    
    def _append_assistant_message(self, message: str):
        chamber_name = "Unknown"
        if self.bridge and self.bridge.active_soul:
            chamber_name = self.bridge.active_soul.persona_name
        self.chat_history.append(f'<p style="color: #9cdcfe;"><b>{chamber_name}:</b> {message}</p>')
    
    def _append_system_message(self, message: str):
        self.chat_history.append(f'<p style="color: #FFD700; font-style: italic;">{message}</p>')
    
    def _configure_autoswitch(self):
        """Open auto-switch config"""
        if not self.revolver:
            return
        
        dialog = AutoSwitchDialog(self, self.revolver)
        dialog.rules = self.auto_switch_rules.copy()
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.auto_switch_rules = dialog.get_rules()
            QMessageBox.information(self, "Rules Updated", f"{len(self.auto_switch_rules)} rules active")
    
    def _reload_chambers(self):
        """Reload chambers"""
        num_chambers = self.chamber_spin.value()
        souls_dir = Path("/home/crimson/Desktop/Dev/MechPilot/ai_copilot/personas")
        
        if not souls_dir.exists():
            QMessageBox.warning(self, "Not Found", f"Souls directory not found:\n{souls_dir}")
            return
        
        self.revolver = RevolverCore(num_chambers=num_chambers, auto_load_directory=str(souls_dir))
        self._update_chamber_list()
        self._append_system_message(f"🔄 Reloaded with {num_chambers} chambers")
    
    def _open_llm_config(self):
        """Open LLM configuration dialog"""
        dialog = LLMConfigDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.llm_config = dialog.get_config()
            
            # Apply to bridge
            if self.bridge:
                success = self.bridge.enable_llm(
                    provider=self.llm_config['provider'],
                    model=self.llm_config['model'],
                    api_key=self.llm_config.get('api_key') or None,
                    api_endpoint=self.llm_config.get('api_endpoint') or None,
                    temperature=self.llm_config['temperature'],
                    max_tokens=self.llm_config['max_tokens']
                )
                
                if success:
                    QMessageBox.information(self, "Success", "LLM configured and enabled!")
                else:
                    QMessageBox.warning(self, "Failed", "Could not enable LLM. Check configuration.")
            
            self._update_llm_status()
    
    def _toggle_llm(self):
        """Toggle LLM on/off"""
        if not self.bridge:
            return
        
        if self.bridge.llm_enabled:
            self.bridge.disable_llm()
        else:
            if not self.llm_config:
                QMessageBox.warning(self, "Not Configured", "Please configure LLM first.")
                return
            
            self.bridge.enable_llm(
                provider=self.llm_config['provider'],
                model=self.llm_config['model'],
                api_key=self.llm_config.get('api_key') or None,
                api_endpoint=self.llm_config.get('api_endpoint') or None,
                temperature=self.llm_config['temperature'],
                max_tokens=self.llm_config['max_tokens']
            )
        
        self._update_llm_status()
    
    def _test_llm(self):
        """Test LLM connection"""
        if not self.bridge or not self.bridge.llm_enabled:
            QMessageBox.warning(self, "LLM Disabled", "Please enable LLM first.")
            return
        
        test_message = "Say 'Hello!' if you can hear me."
        try:
            response = self.bridge.call_llm([{'role': 'user', 'content': test_message}])
            QMessageBox.information(self, "LLM Test", f"✓ LLM responded:\n\n{response}")
        except Exception as e:
            QMessageBox.critical(self, "LLM Test Failed", f"✗ Error:\n\n{str(e)}")
    
    def _connect_game(self):
        """Connect to game server"""
        if not self.bridge:
            return
        
        url = self.ws_url_input.text().strip()
        
        try:
            # Run async connection in background
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.bridge.connect_to_game(url))
            
            self.game_status_label.setText("Game: Connected ✓")
            self.game_status_label.setStyleSheet("color: #00FF00;")
            self.game_connect_btn.setEnabled(False)
            self.game_disconnect_btn.setEnabled(True)
            
            QMessageBox.information(self, "Connected", f"Connected to game at {url}")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", str(e))
    
    def _disconnect_game(self):
        """Disconnect from game"""
        if not self.bridge:
            return
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.bridge.disconnect_from_game())
            
            self.game_status_label.setText("Game: Disconnected")
            self.game_status_label.setStyleSheet("color: #f48771;")
            self.game_connect_btn.setEnabled(True)
            self.game_disconnect_btn.setEnabled(False)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
    
    def _start_game_server(self):
        """Start game WebSocket server"""
        QMessageBox.information(
            self,
            "Start Server",
            "To start the game server, run:\n\npython v12/game_websocket_server.py\n\nThen connect using the 'Connect to Game' button."
        )
    
    def _toggle_bridge(self):
        """Toggle bridge on/off"""
        if not self.bridge:
            return
        
        if self.bridge.state.value == 'offline':
            # Load first chamber's soul into bridge
            if self.revolver and self.revolver.chambers[0]:
                soul_file = Path(self.revolver.chamber_files[0]).name
                if self.bridge.load_soul(soul_file):
                    self.bridge.start_bridge()
                    self.bridge_toggle.setText("🔴 Stop Bridge")
                    self._append_system_message("✓ Bridge started")
            else:
                QMessageBox.warning(self, "No Souls", "Load souls before starting bridge.")
        else:
            self.bridge.stop_bridge()
            self.bridge_toggle.setText("🟢 Start Bridge")
            self._append_system_message("Bridge stopped")
    
    def _full_system_start(self):
        """Start all systems"""
        # Start bridge
        if self.bridge.state.value == 'offline':
            self._toggle_bridge()
        
        # Enable LLM if configured
        if self.llm_config and not self.bridge.llm_enabled:
            self._toggle_llm()
        
        self._append_system_message("⚡ FULL SYSTEM ACTIVATED")
        QMessageBox.information(
            self,
            "System Active",
            "✓ Bridge: Active\n✓ Chambers: Loaded\n✓ Ready for operation"
        )
    
    def _save_memory(self):
        """Save memory to disk"""
        if self.bridge and self.bridge.memory:
            self.bridge.memory.save()
            QMessageBox.information(self, "Saved", "Memory saved to disk.")
    
    def _clear_memory(self):
        """Clear memory"""
        result = QMessageBox.question(
            self,
            "Clear Memory?",
            "This will delete all conversation history. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            if self.bridge and self.bridge.memory:
                self.bridge.memory.clear()
                QMessageBox.information(self, "Cleared", "Memory cleared.")
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.status_worker:
            self.status_worker.stop()
            self.status_worker.wait()
        
        if self.bridge:
            self.bridge.stop_bridge()
        
        event.accept()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Consciousness Control Center")
    
    window = ConsciousnessControlCenter()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
