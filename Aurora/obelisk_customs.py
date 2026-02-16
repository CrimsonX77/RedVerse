"""
🏛️ OBELISK LAYER - Crimson Collective Customs Checkpoint
═══════════════════════════════════════════════════════════

The first gate. The validator. The judge.

Only cards bearing the true Crimson Collective seal may pass.
Frauds are deleted without mercy. No confirmation. No second chances.

Valid cards receive the Mark of Passage and unlock the Account Realm.

Python 3.10+ | PyQt6
"""

import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QFileDialog, QMessageBox, QTextEdit,
    QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

# Import steganography module
try:
    from mutable_steganography import MutableCardSteganography
    STEG_AVAILABLE = True
except ImportError:
    STEG_AVAILABLE = False
    print("❌ FATAL: mutable_steganography module not available")
    print("The Obelisk cannot function without it.")


class ObeliskValidator:
    """
    The Obelisk's validation logic
    
    Checks for:
    1. Valid Aurora magic header
    2. Crimson Collective seal presence
    3. Sigil authenticity
    4. Timeline integrity
    5. Authenticity markers
    """
    
    def __init__(self):
        self.steg = MutableCardSteganography() if STEG_AVAILABLE else None
    
    def validate_soulcard(self, card_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Validate a soul card at the Obelisk gates
        
        Args:
            card_path: Path to card image
            
        Returns:
            Tuple of (is_valid, reason, card_data)
            - is_valid: True if card passes all checks
            - reason: Why it passed or failed
            - card_data: Extracted data if valid, None if invalid
        """
        if not self.steg:
            return False, "🚫 Obelisk offline - steganography unavailable", None
        
        # Step 1: Extract data
        try:
            card_data = self.steg.extract_data(card_path)
        except Exception as e:
            return False, f"🚫 CORRUPTED: Cannot read card data - {str(e)}", None
        
        # Step 2: Check for Crimson Collective seal
        if 'crimson_collective' not in card_data:
            return False, "🚫 UNAUTHORIZED: No Crimson Collective seal found", None
        
        crimson_seal = card_data['crimson_collective']
        
        # Step 3: Validate sigil presence
        if 'sigil' not in crimson_seal or not crimson_seal['sigil']:
            return False, "🚫 FRAUDULENT: Missing sigil", None
        
        # Step 4: Validate seal structure
        required_fields = ['sigil', 'seal', 'covenant', 'authority', 'generation']
        missing = [f for f in required_fields if f not in crimson_seal]
        if missing:
            return False, f"🚫 INCOMPLETE SEAL: Missing {', '.join(missing)}", None
        
        # Step 5: Check authority
        if crimson_seal.get('authority') != 'Aurora Archive - Crimson Artisan Guild':
            return False, "🚫 INVALID AUTHORITY: Not issued by Crimson Artisan Guild", None
        
        # Step 6: Validate generation epoch
        valid_generations = [
            'Second Era of Digital Arcana',
            'First Era of Digital Arcana',
            'Third Era of Digital Arcana'
        ]
        if crimson_seal.get('generation') not in valid_generations:
            return False, f"🚫 UNKNOWN GENERATION: {crimson_seal.get('generation')}", None
        
        # Step 7: Check authenticity markers
        if 'authenticity' in card_data:
            auth = card_data['authenticity']
            
            if not auth.get('genuine', False):
                return False, "🚫 MARKED FAKE: authenticity.genuine = false", None
            
            if auth.get('tamper_seal') != 'INTACT':
                return False, f"🚫 TAMPERED: tamper_seal = {auth.get('tamper_seal')}", None
            
            # Cross-verify sigil with verification_hash
            if 'verification_hash' in auth:
                if auth['verification_hash'] != crimson_seal['sigil']:
                    return False, "🚫 SIGIL MISMATCH: verification_hash doesn't match sigil", None
        
        # Step 8: Validate timeline
        if 'timeline' in card_data:
            timeline = card_data['timeline']
            
            if 'created' not in timeline or 'exported' not in timeline:
                return False, "🚫 INCOMPLETE TIMELINE: Missing timestamps", None
        
        # Step 9: All checks passed!
        sigil = crimson_seal['sigil']
        seal_text = crimson_seal['seal']
        
        return True, f"✅ VALIDATED: Sigil {sigil[:8]}... | {seal_text}", card_data
    
    def append_validation_mark(self, card_path: str, card_data: Dict) -> bool:
        """
        Append the Obelisk's validation mark to the card
        
        This mark proves the card has passed customs and can unlock the Account Realm
        
        Args:
            card_path: Path to card image
            card_data: Existing card data
            
        Returns:
            True if mark successfully appended
        """
        if not self.steg:
            return False
        
        try:
            # Generate validation mark using new format
            validation_sigil = hashlib.sha256(
                (card_data['crimson_collective']['sigil'] + datetime.now().isoformat()).encode()
            ).hexdigest()[:16]
            
            validation_mark = {
                'obelisk_verification': {
                    'passed': True,
                    'verification_sigil': validation_sigil,
                    'timestamp': datetime.now().isoformat(),
                    'gate': 'GATE_1_CUSTOMS',
                    'status': 'CLEARED',
                    'validator': 'Obelisk Customs Checkpoint v1.0',
                    'access_level': 'account_realm'
                }
            }
            
            # Merge with existing data
            enhanced_data = {**card_data, **validation_mark}
            
            # Re-embed with validation mark
            self.steg.embed_data(card_path, enhanced_data, force_overwrite=True)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to append validation mark: {e}")
            return False


class ObeliskMainWindow(QMainWindow):
    """
    🏛️ THE OBELISK - Crimson Collective Customs
    
    The first gate. The validator. The gatekeeper.
    """
    
    # Signal emitted when valid card passes customs
    card_validated = pyqtSignal(str, dict)  # card_path, card_data
    
    def __init__(self):
        super().__init__()
        self.validator = ObeliskValidator()
        self.current_card_path = None
        self.current_card_data = None
        self.is_shutting_down = False
        self.active_workers = []
        self.active_dialogs = []
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("🏛️ OBELISK - Crimson Collective Customs")
        self.setMinimumSize(800, 600)
        
        # Dark crimson theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0a0a0a;
                color: #dc2626;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7f1d1d, stop:1 #991b1b);
                color: white;
                border: 2px solid #dc2626;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #991b1b, stop:1 #b91c1c);
                border: 2px solid #ef4444;
            }
            QPushButton:disabled {
                background-color: rgba(100, 100, 100, 0.3);
                color: rgba(255, 255, 255, 0.3);
                border: 2px solid rgba(220, 38, 38, 0.3);
            }
            QLabel {
                color: #dc2626;
            }
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.8);
                border: 2px solid #7f1d1d;
                border-radius: 8px;
                padding: 12px;
                color: #fca5a5;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Add spacer
        layout.addSpacing(10)
        
        # Card scan area
        scan_frame = self.create_scan_area()
        layout.addWidget(scan_frame)
        
        # Add spacer
        layout.addSpacing(10)
        
        # Validation log
        log_label = QLabel("📜 Validation Log")
        log_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #dc2626;")
        layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(180)
        self.log_display.setText("⏳ Awaiting soul card submission...\n")
        layout.addWidget(self.log_display)
        
        # Add spacer
        layout.addSpacing(10)
        
        # Action buttons
        action_layout = self.create_action_buttons()
        layout.addLayout(action_layout)
        
        # Add stretch to push status to bottom
        layout.addStretch()
        
        # Status bar
        self.status_label = QLabel("🏛️ Obelisk ready. Submit card for validation.")
        self.status_label.setStyleSheet("font-size: 13px; color: #fca5a5; padding: 10px; background-color: rgba(127, 29, 29, 0.2); border-radius: 6px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def create_header(self):
        """Create dramatic header"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a0000, stop:1 #0a0a0a);
                border: 2px solid #7f1d1d;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(header_frame)
        
        title = QLabel("🏛️ THE OBELISK")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #dc2626;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Crimson Collective Customs Checkpoint")
        subtitle.setStyleSheet("font-size: 16px; color: #fca5a5; font-style: italic;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        divider = QLabel("═" * 50)
        divider.setStyleSheet("color: #7f1d1d;")
        divider.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(divider)
        
        warning = QLabel("⚠️  Only authentic Crimson Collective soul cards may pass  ⚠️")
        warning.setStyleSheet("font-size: 14px; color: #fbbf24; font-weight: bold;")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        
        return header_frame
    
    def create_scan_area(self):
        """Create card scanning area"""
        scan_frame = QFrame()
        scan_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(127, 29, 29, 0.2);
                border: 3px dashed #7f1d1d;
                border-radius: 12px;
                padding: 30px;
            }
        """)
        
        layout = QVBoxLayout(scan_frame)
        layout.setSpacing(15)
        
        # Scan icon
        icon_label = QLabel("🔍")
        icon_label.setStyleSheet("font-size: 64px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Add spacer
        layout.addSpacing(10)
        
        # Instructions
        instructions = QLabel("Present your soul card for inspection")
        instructions.setStyleSheet("font-size: 16px; color: #fca5a5; font-weight: bold;")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)
        
        # Add spacer
        layout.addSpacing(15)
        
        # Browse button
        browse_btn = QPushButton("📁 Select Soul Card")
        browse_btn.clicked.connect(self.browse_card)
        browse_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 16px 32px;
                border: 3px solid #dc2626;
                min-width: 250px;
            }
        """)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add spacer
        layout.addSpacing(10)
        
        # Current card label
        self.card_label = QLabel("No card selected")
        self.card_label.setStyleSheet("font-size: 12px; color: #7f1d1d; padding: 8px; background-color: rgba(0, 0, 0, 0.3); border-radius: 4px;")
        self.card_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.card_label)
        
        return scan_frame
    
    def create_action_buttons(self):
        """Create action button row"""
        layout = QHBoxLayout()
        layout.setSpacing(20)
        
        # Add stretch before buttons
        layout.addStretch()
        
        # Validate button
        self.validate_btn = QPushButton("⚔️ VALIDATE CARD")
        self.validate_btn.clicked.connect(self.validate_card)
        self.validate_btn.setEnabled(False)
        self.validate_btn.setMinimumHeight(70)
        self.validate_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 20px 40px;
                border: 4px solid #dc2626;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #450a0a, stop:1 #7f1d1d);
                min-width: 250px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7f1d1d, stop:1 #991b1b);
                border: 4px solid #ef4444;
            }
        """)
        layout.addWidget(self.validate_btn)
        
        # Enter Account Realm button (disabled until validation)
        self.enter_btn = QPushButton("🚪 Enter Account Realm")
        self.enter_btn.clicked.connect(self.enter_account_realm)
        self.enter_btn.setEnabled(False)
        self.enter_btn.setMinimumHeight(70)
        self.enter_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 16px 32px;
                border: 3px solid #10b981;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #064e3b, stop:1 #047857);
                min-width: 250px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #047857, stop:1 #059669);
                border: 3px solid #34d399;
            }
            QPushButton:enabled {
                animation: pulse 2s infinite;
            }
        """)
        layout.addWidget(self.enter_btn)
        
        # Add stretch after buttons
        layout.addStretch()
        
        return layout
    
    def browse_card(self):
        """Open file dialog to select card"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Soul Card for Validation",
            str(Path.home() / "Desktop"),
            "Image Files (*.png *.jpg *.jpeg);;All Files (*.*)"
        )
        
        if file_path:
            self.current_card_path = file_path
            self.card_label.setText(f"📄 {Path(file_path).name}")
            self.validate_btn.setEnabled(True)
            self.enter_btn.setEnabled(False)  # Reset until validation
            
            self.log(f"📁 Card loaded: {Path(file_path).name}")
            self.status_label.setText("🏛️ Card loaded. Ready for validation.")
    
    def validate_card(self):
        """Validate the current card at the Obelisk"""
        if not self.current_card_path:
            return
        
        self.log("\n" + "═" * 60)
        self.log("⚔️ COMMENCING VALIDATION PROTOCOL...")
        self.log("═" * 60)
        
        self.status_label.setText("🔍 Scanning card...")
        QApplication.processEvents()  # Update UI
        
        # Run validation
        is_valid, reason, card_data = self.validator.validate_soulcard(self.current_card_path)
        
        if is_valid:
            # CARD PASSED! 🎉
            self.log(f"\n✅ {reason}")
            self.log(f"\n🔐 Sigil: {card_data['crimson_collective']['sigil']}")
            self.log(f"📜 Seal: {card_data['crimson_collective']['seal']}")
            self.log(f"⚡ Authority: {card_data['crimson_collective']['authority']}")
            self.log(f"🌟 Generation: {card_data['crimson_collective']['generation']}")
            
            if 'timeline' in card_data:
                self.log(f"\n⏰ Timeline:")
                self.log(f"  • Created: {card_data['timeline'].get('created', 'Unknown')}")
                self.log(f"  • Exported: {card_data['timeline'].get('exported', 'Unknown')}")
            
            self.log("\n✨ Appending Obelisk validation mark...")
            
            # Append validation mark
            if self.validator.append_validation_mark(self.current_card_path, card_data):
                self.log("✅ Validation mark appended successfully!")
                self.log("\n🚪 GATE 1 CLEARED - Access to Account Realm GRANTED")
                
                self.status_label.setText("✅ VALIDATED - Card may pass!")
                self.current_card_data = card_data
                
                # Enable entry to Account Realm
                self.enter_btn.setEnabled(True)
                self.validate_btn.setEnabled(False)
                
                # Success dialog
                QMessageBox.information(
                    self,
                    "✅ Validation Successful",
                    f"🏛️ The Obelisk has validated your soul card!\n\n"
                    f"Sigil: {card_data['crimson_collective']['sigil']}\n"
                    f"Seal: {card_data['crimson_collective']['seal'][:50]}...\n\n"
                    f"✨ Validation mark appended.\n"
                    f"🚪 You may now enter the Account Realm."
                )
            else:
                self.log("❌ FAILED to append validation mark")
                self.status_label.setText("⚠️ Validation succeeded but mark failed")
        
        else:
            # CARD FAILED! 💀 But we're merciful now
            self.log(f"\n❌ {reason}")
            self.log("\n💀 JUDGMENT: FRAUDULENT CARD DETECTED")
            
            # Snarky messages instead of deletion
            snarky_messages = [
                "🙄 Nice try, but the Obelisk isn't fooled that easily.",
                "🤨 Did you really think that would work?",
                "😒 The Crimson Collective demands AUTHENTICITY, not... this.",
                "🤦 This seal is more fake than a politician's smile.",
                "🎭 10/10 for effort, 0/10 for authenticity.",
                "🚫 The Obelisk has seen better forgeries from children.",
                "💩 This card has about as much legitimacy as a three-dollar bill.",
                "🎪 Welcome to the Circus of Failed Validations.",
                "🤡 This seal wouldn't fool a blind goblin.",
                "⚰️ Your card's authenticity: deceased on arrival."
            ]
            
            import random
            snarky_msg = random.choice(snarky_messages)
            
            self.log(f"\n{snarky_msg}")
            self.log("\n🏛️ The Obelisk is MERCIFUL today - your card survives.")
            self.log("But it shall NOT pass. Fix your seal and return.")
            
            self.status_label.setText("❌ FRAUDULENT CARD - Validation Failed")
            
            # Reset UI but DON'T delete the file
            self.current_card_path = None
            self.current_card_data = None
            self.card_label.setText("No card selected")
            self.validate_btn.setEnabled(False)
            self.enter_btn.setEnabled(False)
            
            self.status_label.setText("🏛️ Validation failed. Card preserved for debugging.")
            
            # Error dialog with snarky message
            QMessageBox.critical(
                self,
                "❌ Validation Failed",
                f"🏛️ The Obelisk has judged your card FRAUDULENT.\n\n"
                f"Reason: {reason}\n\n"
                f"{snarky_msg}\n\n"
                f"💾 Your card has been SPARED from deletion.\n"
                f"Fix the seal and try again.\n\n"
                f"Only authentic Crimson Collective cards may pass."
            )
    
    def enter_account_realm(self):
        """Enter the Account Realm (Gate 2) - Launch Archive Sanctum"""
        if not self.current_card_path or not self.current_card_data:
            return
        
        self.log("\n" + "═" * 60)
        self.log("🚪 ENTERING ACCOUNT REALM...")
        self.log("═" * 60)
        
        # Emit signal for validated card
        self.card_validated.emit(self.current_card_path, self.current_card_data)
        
        # Launch Archive Sanctum with validated card
        try:
            import subprocess
            import sys
            
            self.log("🏛️ Launching Archive Sanctum...")
            
            # Launch archive_sanctum.py with card path and member data
            subprocess.Popen([
                sys.executable,
                "archive_sanctum.py",
                "--card", self.current_card_path,
                "--validated"
            ])
            
            self.log("✅ Archive Sanctum launched successfully!")
            self.status_label.setText("🚪 Entering Archive Sanctum...")
            
            # Close Obelisk after launching Sanctum
            QTimer.singleShot(500, self.close)
            
        except Exception as e:
            self.log(f"❌ Failed to launch Archive Sanctum: {e}")
            QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch Archive Sanctum:\n{e}"
            )
    
    def cleanup_workers(self):
        """Stop all active background workers"""
        for worker in self.active_workers[:]:
            if worker and worker.isRunning():
                worker.terminate()
                worker.wait(1000)  # Wait up to 1 second
        self.active_workers.clear()
    
    def cleanup_dialogs(self):
        """Close all active dialogs"""
        for dialog in self.active_dialogs[:]:
            if dialog and dialog.isVisible():
                dialog.close()
        self.active_dialogs.clear()
    
    def cleanup_resources(self):
        """Gracefully clean up all resources"""
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        
        self.log("\n🌙 Closing Obelisk Customs...")
        self.status_label.setText("🌙 Shutting down...")
        
        # Stop workers
        self.cleanup_workers()
        
        # Close dialogs
        self.cleanup_dialogs()
        
        # Small delay for cleanup
        QTimer.singleShot(500, self.close)
    
    def closeEvent(self, event):
        """Override close event to ensure cleanup"""
        if not self.is_shutting_down:
            self.cleanup_resources()
            event.ignore()
            QTimer.singleShot(600, self.close)
        else:
            event.accept()
    
    def log(self, message: str):
        """Add message to validation log"""
        self.log_display.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    """Obelisk entry point"""
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Create and show Obelisk
    obelisk = ObeliskMainWindow()
    obelisk.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
