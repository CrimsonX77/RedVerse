"""
Aurora Archive - Member Manager GUI
Complete admin panel for member management

Features:
- Tab 1: Member List & Overview
- Tab 2: Register New Member
- Tab 3: Apply Steganography Mark
- Tab 4: Account Options (Upgrade/Downgrade/Delete)
- Tab 5: Detailed Account View

Python 3.10+ | PyQt6
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPixmap, QColor

# Import Aurora modules
from database_manager import get_database
from member_manager import MemberManager
from seal_compositor import SealCompositor, validate_card_seal
from mutable_steganography import MutableCardSteganography

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/member_manager_gui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MemberManagerGUI(QMainWindow):
    """
    Main Member Manager Application
    Admin-only interface for complete member management
    """
    
    def __init__(self):
        super().__init__()
        
        # Initialize managers
        self.db = get_database()
        self.member_mgr = MemberManager()
        self.seal_comp = SealCompositor()
        self.stego = MutableCardSteganography()
        
        # Current selection
        self.current_member_id = None
        
        # Setup UI
        self.setup_ui()
        self.load_members()
        
        logger.info("Member Manager GUI initialized")
    
    def setup_ui(self):
        self.setWindowTitle("🏛️ Aurora Archive - Member Manager (Admin)")
        self.setMinimumSize(1400, 900)
        
        # Apply dark theme matching Archive Sanctum
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0a0a0a;
                color: #fca5a5;
            }
            QTabWidget::pane {
                border: 2px solid #7f1d1d;
                border-radius: 8px;
                background-color: rgba(0, 0, 0, 0.8);
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a0000, stop:1 #0a0a0a);
                border: 2px solid #7f1d1d;
                border-bottom: none;
                padding: 12px 20px;
                margin-right: 2px;
                color: #fca5a5;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7f1d1d, stop:1 #991b1b);
                color: #dc2626;
            }
            QTabBar::tab:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a0000, stop:1 #1a0000);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7f1d1d, stop:1 #991b1b);
                color: white;
                border: 2px solid #dc2626;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
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
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: rgba(220, 38, 38, 0.1);
                border: 2px solid #7f1d1d;
                border-radius: 6px;
                padding: 8px;
                color: #fca5a5;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 2px solid #dc2626;
            }
            QLabel {
                color: #fca5a5;
                font-size: 13px;
            }
            QTableWidget {
                background-color: rgba(0, 0, 0, 0.8);
                border: 2px solid #7f1d1d;
                border-radius: 8px;
                gridline-color: #7f1d1d;
                color: #fca5a5;
            }
            QTableWidget::item:selected {
                background-color: rgba(220, 38, 38, 0.3);
                color: #dc2626;
            }
            QHeaderView::section {
                background-color: #1a0000;
                color: #dc2626;
                padding: 8px;
                border: 1px solid #7f1d1d;
                font-weight: bold;
            }
            QScrollBar:vertical {
                border: none;
                background: #1a0000;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #7f1d1d;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #991b1b;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        
        # Create all tabs
        self.tab1 = self.create_tab1_member_list()
        self.tab2 = self.create_tab2_register()
        self.tab3 = self.create_tab3_seal()
        self.tab4 = self.create_tab4_options()
        self.tab5 = self.create_tab5_detailed()
        
        self.tabs.addTab(self.tab1, "📋 Member List")
        self.tabs.addTab(self.tab2, "➕ Register Member")
        self.tabs.addTab(self.tab3, "🔖 Apply Seal")
        self.tabs.addTab(self.tab4, "⚙️ Account Options")
        self.tabs.addTab(self.tab5, "📊 Detailed View")
        
        layout.addWidget(self.tabs)
    
    def create_header(self):
        """Create application header"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a0000, stop:1 #0a0a0a);
                border-bottom: 3px solid #7f1d1d;
                padding: 20px;
            }
        """)
        
        layout = QHBoxLayout(frame)
        
        # Title
        title = QLabel("🏛️ AURORA ARCHIVE - Member Manager")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #dc2626;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Quick actions
        sanctum_btn = QPushButton("🌅 Launch Archive Sanctum")
        sanctum_btn.clicked.connect(self.launch_archive_sanctum)
        layout.addWidget(sanctum_btn)
        
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.clicked.connect(self.load_members)
        layout.addWidget(refresh_btn)
        
        return frame
    
    # ============================================
    # TAB 1: MEMBER LIST & OVERVIEW
    # ============================================
    
    def create_tab1_member_list(self):
        """Tab 1: Member List with basic overview"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Search:")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, email, or member ID...")
        self.search_input.textChanged.connect(self.filter_members)
        search_layout.addWidget(self.search_input)
        
        layout.addLayout(search_layout)
        
        # Members table
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(8)
        self.members_table.setHorizontalHeaderLabels([
            "Member ID", "Name", "Email", "Tier", "Status", 
            "Member Since", "Card Valid", "Actions"
        ])
        self.members_table.horizontalHeader().setStretchLastSection(True)
        self.members_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.members_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.members_table.itemSelectionChanged.connect(self.on_member_selected)
        
        layout.addWidget(self.members_table)
        
        # Stats footer
        self.stats_label = QLabel("Total Members: 0")
        self.stats_label.setStyleSheet("font-size: 14px; color: #10b981; font-weight: bold;")
        layout.addWidget(self.stats_label)
        
        return tab
    
    def filter_members(self):
        """Filter members table based on search"""
        search_text = self.search_input.text().lower()

        for row in range(self.members_table.rowCount()):
            show_row = any(
                item and search_text in item.text().lower()
                for col in range(self.members_table.columnCount() - 1)
                if (item := self.members_table.item(row, col))
            )
            self.members_table.setRowHidden(row, not show_row)
    
    def on_member_selected(self):
        """Handle member selection from table"""
        selected = self.members_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        self.current_member_id = self.members_table.item(row, 0).text()
        self.update_detailed_view()
        logger.debug(f"Selected member: {self.current_member_id}")
    
    # ============================================
    # TAB 2: REGISTER NEW MEMBER
    # ============================================
    
    def create_tab2_register(self):
        """Tab 2: Register new member"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(15)
        
        # Profile fields
        form_layout.addRow(QLabel("<b>👤 Member Profile</b>"))
        
        self.reg_name = QLineEdit()
        self.reg_name.setPlaceholderText("Full Name")
        form_layout.addRow("Name:", self.reg_name)
        
        self.reg_email = QLineEdit()
        self.reg_email.setPlaceholderText("email@example.com")
        form_layout.addRow("Email:", self.reg_email)
        
        self.reg_phone = QLineEdit()
        self.reg_phone.setPlaceholderText("+1234567890")
        form_layout.addRow("Phone:", self.reg_phone)
        
        self.reg_birthdate = QLineEdit()
        self.reg_birthdate.setPlaceholderText("YYYY-MM-DD")
        form_layout.addRow("Birthdate:", self.reg_birthdate)
        
        self.reg_gender = QComboBox()
        self.reg_gender.addItems(["Prefer not to say", "Male", "Female", "Non-binary", "Other"])
        form_layout.addRow("Gender:", self.reg_gender)
        
        # Address
        form_layout.addRow(QLabel("<b>📍 Address</b>"))
        
        self.reg_street = QLineEdit()
        form_layout.addRow("Street:", self.reg_street)
        
        self.reg_city = QLineEdit()
        form_layout.addRow("City:", self.reg_city)
        
        self.reg_state = QLineEdit()
        form_layout.addRow("State:", self.reg_state)
        
        self.reg_zip = QLineEdit()
        form_layout.addRow("ZIP:", self.reg_zip)
        
        # Subscription
        form_layout.addRow(QLabel("<b>💳 Subscription</b>"))
        
        self.reg_tier = QComboBox()
        self.reg_tier.addItems(["Standard", "Premium"])  # Kids auto-assigned if under 18
        form_layout.addRow("Tier:", self.reg_tier)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Clear Form")
        clear_btn.clicked.connect(self.clear_registration_form)
        button_layout.addWidget(clear_btn)
        
        register_btn = QPushButton("✅ Register Member")
        register_btn.clicked.connect(self.register_new_member)
        button_layout.addWidget(register_btn)
        
        form_layout.addRow(button_layout)
        
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        return tab
    
    def clear_registration_form(self):
        """Clear registration form"""
        self.reg_name.clear()
        self.reg_email.clear()
        self.reg_phone.clear()
        self.reg_birthdate.clear()
        self.reg_street.clear()
        self.reg_city.clear()
        self.reg_state.clear()
        self.reg_zip.clear()
    
    def register_new_member(self):
        """Register a new member"""
        try:
            # Validate required fields
            if not self.reg_name.text() or not self.reg_email.text():
                QMessageBox.warning(self, "Validation Error", "Name and Email are required!")
                return

            # Create member
            member_data = self.member_mgr.create_new_member(
                name=self.reg_name.text(),
                email=self.reg_email.text(),
                phone=self.reg_phone.text(),
                gender=self.reg_gender.currentText(),
                birthdate=self.reg_birthdate.text() if self.reg_birthdate.text() else None,
                street=self.reg_street.text(),
                city=self.reg_city.text(),
                state=self.reg_state.text(),
                zip_code=self.reg_zip.text(),
                tier=self.reg_tier.currentText()
            )

            # Save to database
            if not self.db.add_member(member_data):
                QMessageBox.critical(self, "Error", "Failed to save member to database!")
                return

            # Auto-generate generic card
            generic_card_path = self._generate_generic_card(member_data)

            success_msg = (
                f"✅ Member registered successfully!\n\n"
                f"Member ID: {member_data['member_id']}\n"
                f"Name: {member_data['member_profile']['name']}\n"
                f"Tier: {member_data['subscription']['tier']}\n\n"
            )

            if generic_card_path:
                success_msg += "Generic card generated and auto-verified!\nCard can be customized later in Archive Sanctum."
            else:
                success_msg += "Note: Generic card generation failed. Please use 'Apply Seal' tab."

            QMessageBox.information(self, "Success", success_msg)
            self.clear_registration_form()
            self.load_members()

        except Exception as e:
            logger.error(f"Registration error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Registration failed:\n{str(e)}")
    
    # ============================================
    # TAB 3: APPLY SEAL
    # ============================================
    
    def create_tab3_seal(self):
        """Tab 3: Apply steganography seal to card"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Instructions
        instructions = QLabel(
            "🔖 Apply Steganography Seal\n\n"
            "This process:\n"
            "1. Loads the member's card image or video (MP4 up to 10MB)\n"
            "2. Embeds account data into RedSeal.png (100x100)\n"
            "3. Composites the embedded seal onto bottom-left corner\n"
            "4. Saves the sealed card (archives old version)"
        )
        instructions.setStyleSheet("font-size: 13px; color: #fbbf24; padding: 15px; background-color: rgba(251, 191, 36, 0.1); border-radius: 8px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Member selection
        member_layout = QHBoxLayout()
        member_layout.addWidget(QLabel("Select Member:"))
        
        self.seal_member_combo = QComboBox()
        member_layout.addWidget(self.seal_member_combo)
        
        load_members_btn = QPushButton("🔄 Refresh Members")
        load_members_btn.clicked.connect(self.populate_seal_members)
        member_layout.addWidget(load_members_btn)
        
        layout.addLayout(member_layout)
        
        # Card selection
        card_layout = QHBoxLayout()
        card_layout.addWidget(QLabel("Card Image:"))
        
        self.seal_card_path = QLineEdit()
        self.seal_card_path.setPlaceholderText("Path to card image (512x768 PNG)")
        card_layout.addWidget(self.seal_card_path)
        
        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.browse_card_image)
        card_layout.addWidget(browse_btn)
        
        layout.addLayout(card_layout)
        
        # Preview
        preview_group = QFrame()
        preview_group.setStyleSheet("QFrame { border: 2px solid #7f1d1d; border-radius: 8px; padding: 15px; }")
        preview_layout = QVBoxLayout(preview_group)
        
        self.seal_preview_label = QLabel("Card Preview")
        self.seal_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seal_preview_label.setMinimumHeight(400)
        self.seal_preview_label.setStyleSheet("background-color: rgba(0, 0, 0, 0.5); border-radius: 4px;")
        preview_layout.addWidget(self.seal_preview_label)
        
        layout.addWidget(preview_group)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        validate_btn = QPushButton("🔍 Test Obelisk Validation")
        validate_btn.clicked.connect(self.test_obelisk_validation)
        action_layout.addWidget(validate_btn)
        
        apply_seal_btn = QPushButton("🔖 Apply Seal to Card")
        apply_seal_btn.clicked.connect(self.apply_seal_to_card)
        apply_seal_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #065f46, stop:1 #047857);
                border: 2px solid #10b981;
                font-size: 14px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #047857, stop:1 #059669);
                border: 2px solid #34d399;
            }
        """)
        action_layout.addWidget(apply_seal_btn)
        
        layout.addLayout(action_layout)
        
        return tab
    
    def populate_seal_members(self):
        """Populate member dropdown in seal tab"""
        self.seal_member_combo.clear()

        for member in self.db.get_all_members():
            name = member.get('member_profile', {}).get('name', 'Unknown')
            member_id = member.get('member_id', 'N/A')
            self.seal_member_combo.addItem(f"{name} ({member_id})", member_id)
    
    def browse_card_image(self):
        """Browse for card image or video"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Card Image or Video (MP4 under 10MB)",
            "",
            "Media Files (*.png *.mp4);;PNG Files (*.png);;MP4 Videos (*.mp4);;All Files (*)"
        )

        if not file_path:
            return

        # Validate MP4 size
        if file_path.lower().endswith('.mp4'):
            file_size = Path(file_path).stat().st_size / (1024 * 1024)
            if file_size > 10:
                QMessageBox.warning(
                    self,
                    "File Too Large",
                    f"Video file is {file_size:.2f} MB.\n\nMaximum allowed size is 10 MB."
                )
                return

        self.seal_card_path.setText(file_path)
        self.preview_card_image(file_path)
    
    def preview_card_image(self, path: str):
        """Preview card image or video"""
        try:
            if path.lower().endswith('.mp4'):
                self.seal_preview_label.clear()
                self.seal_preview_label.setText(
                    f"🎬 Video Selected\n\n{Path(path).name}\n\n"
                    f"Video will be processed with steganography\nwhen 'Apply Seal' is clicked."
                )
                self.seal_preview_label.setStyleSheet(
                    "QLabel { background-color: rgba(0, 0, 0, 0.7); "
                    "border-radius: 4px; color: #10b981; "
                    "font-size: 14px; font-weight: bold; }"
                )
            else:
                pixmap = QPixmap(path)
                scaled = pixmap.scaled(400, 600, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                self.seal_preview_label.setPixmap(scaled)
                self.seal_preview_label.setStyleSheet("background-color: rgba(0, 0, 0, 0.5); border-radius: 4px;")
        except Exception as e:
            logger.error(f"Preview error: {e}")
    
    def apply_seal_to_card(self):
        """Apply seal to selected card"""
        try:
            member_id = self.seal_member_combo.currentData()
            if not member_id:
                QMessageBox.warning(self, "Error", "Please select a member!")
                return

            card_path = self.seal_card_path.text()
            if not card_path or not Path(card_path).exists():
                QMessageBox.warning(self, "Error", "Please select a valid card image!")
                return

            member_data = self.db.get_member(member_id)
            if not member_data:
                QMessageBox.critical(self, "Error", "Member not found in database!")
                return

            # Apply seal
            result_path = self.seal_comp.embed_and_composite(card_path, member_data, None)

            if not result_path:
                QMessageBox.critical(self, "Error", "Failed to apply seal to card!")
                return

            saved_path = self.db.save_member_card(member_id, result_path)

            if saved_path:
                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ Seal applied successfully!\n\n"
                    f"Card saved to: {saved_path}\n\n"
                    f"The card is now ready for Obelisk validation."
                )
                self.preview_card_image(saved_path)
                self.load_members()
            else:
                QMessageBox.warning(self, "Warning", "Seal applied but failed to save to database!")

        except Exception as e:
            logger.error(f"Seal application error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Seal application failed:\n{str(e)}")
    
    def test_obelisk_validation(self):
        """Test if card passes Obelisk validation"""
        card_path = self.seal_card_path.text()
        if not card_path or not Path(card_path).exists():
            QMessageBox.warning(self, "Error", "Please select a card image first!")
            return

        is_valid = validate_card_seal(card_path)

        if is_valid:
            QMessageBox.information(
                self,
                "Validation Passed",
                "✅ Card has valid seal!\n\nThis card should pass Obelisk customs validation."
            )
        else:
            QMessageBox.warning(
                self,
                "Validation Failed",
                "❌ Invalid or missing seal!\n\n"
                "This card will NOT pass Obelisk customs.\nPlease apply seal first."
            )
    
    # ============================================
    # TAB 4: ACCOUNT OPTIONS
    # ============================================
    
    def create_tab4_options(self):
        """Tab 4: Account options (upgrade/downgrade/delete)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Member selection
        member_layout = QHBoxLayout()
        member_layout.addWidget(QLabel("Select Member:"))
        
        self.options_member_combo = QComboBox()
        member_layout.addWidget(self.options_member_combo)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.populate_options_members)
        member_layout.addWidget(refresh_btn)
        
        layout.addLayout(member_layout)
        
        # Current info display
        self.options_info = QLabel("Select a member to view account options")
        self.options_info.setStyleSheet("padding: 15px; background-color: rgba(220, 38, 38, 0.1); border-radius: 8px;")
        self.options_info.setWordWrap(True)
        layout.addWidget(self.options_info)
        
        # Action buttons grid
        actions_group = QFrame()
        actions_group.setStyleSheet("QFrame { border: 2px solid #7f1d1d; border-radius: 8px; padding: 20px; }")
        actions_layout = QGridLayout(actions_group)
        actions_layout.setSpacing(15)
        
        # Upgrade button
        self.upgrade_btn = QPushButton("⬆️ Upgrade Tier")
        self.upgrade_btn.clicked.connect(self.upgrade_member_tier)
        self.upgrade_btn.setMinimumHeight(60)
        actions_layout.addWidget(self.upgrade_btn, 0, 0)
        
        # Downgrade button
        self.downgrade_btn = QPushButton("⬇️ Downgrade Tier")
        self.downgrade_btn.clicked.connect(self.downgrade_member_tier)
        self.downgrade_btn.setMinimumHeight(60)
        actions_layout.addWidget(self.downgrade_btn, 0, 1)
        
        # View in Sanctum button
        sanctum_btn = QPushButton("🌅 View in Archive Sanctum")
        sanctum_btn.clicked.connect(self.view_member_in_sanctum)
        sanctum_btn.setMinimumHeight(60)
        sanctum_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e3a8a, stop:1 #1e40af);
                border: 2px solid #3b82f6;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e40af, stop:1 #2563eb);
                border: 2px solid #60a5fa;
            }
        """)
        actions_layout.addWidget(sanctum_btn, 1, 0, 1, 2)
        
        # Delete button
        delete_btn = QPushButton("🗑️ Delete Account")
        delete_btn.clicked.connect(self.delete_member_account)
        delete_btn.setMinimumHeight(60)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7f1d1d, stop:1 #991b1b);
                border: 2px solid #dc2626;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #991b1b, stop:1 #b91c1c);
                border: 2px solid #ef4444;
            }
        """)
        actions_layout.addWidget(delete_btn, 2, 0, 1, 2)
        
        layout.addWidget(actions_group)
        layout.addStretch()
        
        # Connect member selection change
        self.options_member_combo.currentIndexChanged.connect(self.update_options_info)
        
        return tab
    
    def populate_options_members(self):
        """Populate member dropdown in options tab"""
        self.options_member_combo.clear()

        for member in self.db.get_all_members():
            name = member.get('member_profile', {}).get('name', 'Unknown')
            member_id = member.get('member_id', 'N/A')
            self.options_member_combo.addItem(f"{name} ({member_id})", member_id)
    
    def update_options_info(self):
        """Update info display when member selected"""
        member_id = self.options_member_combo.currentData()
        if not member_id:
            return

        member = self.db.get_member(member_id)
        if not member:
            return

        name = member.get('member_profile', {}).get('name', 'Unknown')
        tier = member.get('subscription', {}).get('tier', 'N/A')
        status = member.get('subscription', {}).get('status', 'N/A')

        self.options_info.setText(
            f"<b>Member:</b> {name}<br>"
            f"<b>Current Tier:</b> {tier}<br>"
            f"<b>Status:</b> {status}<br><br>"
            f"Select an action below"
        )
    
    def upgrade_member_tier(self):
        """Upgrade member tier (admin direct upgrade)"""
        member_id = self.options_member_combo.currentData()
        if not member_id:
            QMessageBox.warning(self, "Error", "Please select a member!")
            return

        member = self.db.get_member(member_id)
        current_tier = member.get('subscription', {}).get('tier', 'Standard')

        # Determine available upgrades
        tier_order = ["Kids", "Standard", "Premium"]
        available_tiers = [t for t in tier_order if tier_order.index(t) > tier_order.index(current_tier)]

        if not available_tiers:
            QMessageBox.information(self, "Info", "Member is already at highest tier (Premium)!")
            return

        # Show tier selection dialog
        target_tier, ok = QInputDialog.getItem(
            self,
            "Select Target Tier",
            f"Current Tier: {current_tier}\n\nUpgrade to:",
            available_tiers,
            0,
            False
        )

        if not ok or not target_tier:
            return

        # Confirm upgrade
        reply = QMessageBox.question(
            self,
            "Confirm Upgrade",
            f"Upgrade from {current_tier} to {target_tier}?\n\n"
            f"This will take effect immediately.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Update member tier directly
            self.db.update_member(member_id, {
                'subscription': {
                    'tier': target_tier,
                    'status': 'active'
                }
            })

            QMessageBox.information(
                self,
                "Success",
                f"✅ Member upgraded to {target_tier}!"
            )

            self.load_members()
            self.update_options_info()
    
    def downgrade_member_tier(self):
        """Downgrade member tier (admin direct downgrade)"""
        member_id = self.options_member_combo.currentData()
        if not member_id:
            QMessageBox.warning(self, "Error", "Please select a member!")
            return

        member = self.db.get_member(member_id)
        current_tier = member.get('subscription', {}).get('tier', 'Standard')

        # Determine target tier
        tier_order = ["Kids", "Standard", "Premium"]
        current_index = tier_order.index(current_tier) if current_tier in tier_order else 1

        if current_index <= 0:
            QMessageBox.information(self, "Info", "Cannot downgrade below Kids tier!")
            return

        target_tier = tier_order[current_index - 1]

        # Confirm downgrade
        reply = QMessageBox.question(
            self,
            "Confirm Downgrade",
            f"Downgrade from {current_tier} to {target_tier}?\n\n"
            f"This will take effect immediately.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.db.update_member(member_id, {
                'subscription': {
                    'tier': target_tier,
                    'status': 'active'
                }
            })

            QMessageBox.information(self, "Success", f"✅ Member downgraded to {target_tier}!")
            self.load_members()
            self.update_options_info()
    
    def view_member_in_sanctum(self):
        """Open Archive Sanctum with selected member's data"""
        member_id = self.options_member_combo.currentData()
        if not member_id:
            QMessageBox.warning(self, "Error", "Please select a member!")
            return

        self._launch_sanctum(member_id)

    def _launch_sanctum(self, member_id: str):
        """Launch Archive Sanctum for specified member"""
        try:
            member = self.db.get_member(member_id)
            if not member:
                QMessageBox.critical(self, "Error", "Member not found!")
                return

            card_path = self.db.get_member_card_path(member_id)

            if not card_path or not Path(card_path).exists():
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Member has no valid card!\n\n"
                    "Please generate and seal a card first in 'Apply Seal' tab."
                )
                return

            # Launch Archive Sanctum as separate process
            import subprocess

            subprocess.Popen([
                sys.executable,
                "archive_sanctum.py",
                "--card", str(card_path),
                "--member", member_id
            ])

            logger.info(f"Launched Archive Sanctum for member: {member_id}")

        except Exception as e:
            logger.error(f"Error launching Archive Sanctum: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to launch Archive Sanctum:\n{str(e)}")
    
    def delete_member_account(self):
        """Delete member account"""
        member_id = self.options_member_combo.currentData()
        if not member_id:
            QMessageBox.warning(self, "Error", "Please select a member!")
            return

        member = self.db.get_member(member_id)
        name = member.get('member_profile', {}).get('name', 'Unknown')

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"⚠️ DELETE ACCOUNT?\n\n"
            f"Member: {name}\n"
            f"ID: {member_id}\n\n"
            f"This action CANNOT be undone!\n"
            f"All data will be archived.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.db.delete_member(member_id):
            QMessageBox.information(
                self,
                "Deleted",
                f"✅ Account deleted and archived.\n\nMember: {name}"
            )
            self.load_members()
            self.populate_options_members()
        else:
            QMessageBox.critical(self, "Error", "Failed to delete member!")
    
    # ============================================
    # TAB 5: DETAILED VIEW
    # ============================================
    
    def create_tab5_detailed(self):
        """Tab 5: Detailed account view"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        self.detailed_content = QWidget()
        self.detailed_layout = QVBoxLayout(self.detailed_content)
        
        # Placeholder
        placeholder = QLabel("Select a member from the Member List tab to view details")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("font-size: 16px; color: #9ca3af; padding: 40px;")
        self.detailed_layout.addWidget(placeholder)
        
        scroll.setWidget(self.detailed_content)
        layout.addWidget(scroll)
        
        return tab
    
    def update_detailed_view(self):
        """Update detailed view with selected member data"""
        if not self.current_member_id:
            return
        
        member = self.db.get_member(self.current_member_id)
        if not member:
            return
        
        # Clear existing content
        while self.detailed_layout.count():
            item = self.detailed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Title
        title = QLabel(f"<h2>📊 {member.get('member_profile', {}).get('name', 'Unknown')}</h2>")
        title.setStyleSheet("color: #dc2626; font-size: 24px;")
        self.detailed_layout.addWidget(title)
        
        # Member ID and Status
        id_status = QLabel(
            f"<b>Member ID:</b> {member.get('member_id', 'N/A')}<br>"
            f"<b>Status:</b> {member.get('subscription', {}).get('status', 'N/A')}<br>"
            f"<b>Tier:</b> {member.get('subscription', {}).get('tier', 'N/A')}<br>"
            f"<b>Member Since:</b> {member.get('created_at', 'N/A')[:10]}"
        )
        id_status.setStyleSheet("padding: 15px; background-color: rgba(220, 38, 38, 0.1); border-radius: 8px;")
        self.detailed_layout.addWidget(id_status)
        
        # Contact Info
        contact_group = QGroupBox("📧 Contact Information")
        contact_layout = QVBoxLayout()
        contact_info = QLabel(
            f"<b>Email:</b> {member.get('member_profile', {}).get('email', 'N/A')}<br>"
            f"<b>Phone:</b> {member.get('member_profile', {}).get('phone', 'N/A')}<br>"
            f"<b>Address:</b> {member.get('member_profile', {}).get('address', {}).get('street', 'N/A')}, "
            f"{member.get('member_profile', {}).get('address', {}).get('city', 'N/A')}, "
            f"{member.get('member_profile', {}).get('address', {}).get('state', 'N/A')} "
            f"{member.get('member_profile', {}).get('address', {}).get('zip', 'N/A')}"
        )
        contact_layout.addWidget(contact_info)
        contact_group.setLayout(contact_layout)
        self.detailed_layout.addWidget(contact_group)
        
        # Card Info
        card_group = QGroupBox("🎴 Card Information")
        card_layout = QVBoxLayout()
        card_valid = member.get('card_data', {}).get('valid', False)
        card_path = self.db.get_member_card_path(self.current_member_id)
        
        card_info = QLabel(
            f"<b>Card Valid:</b> {'✅ Yes' if card_valid else '❌ No'}<br>"
            f"<b>Card Path:</b> {card_path if card_path else 'No card on file'}"
        )
        card_layout.addWidget(card_info)
        
        # Card preview
        if card_path and Path(card_path).exists():
            card_preview = QLabel()
            card_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(card_path)
            scaled = pixmap.scaled(256, 384, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            card_preview.setPixmap(scaled)
            card_layout.addWidget(card_preview)
        
        card_group.setLayout(card_layout)
        self.detailed_layout.addWidget(card_group)
        
        # Rentals placeholder
        rentals_group = QGroupBox("📚 Current Rentals")
        rentals_layout = QVBoxLayout()
        rentals_info = QLabel("No active rentals (Books system pending)")
        rentals_layout.addWidget(rentals_info)
        rentals_group.setLayout(rentals_layout)
        self.detailed_layout.addWidget(rentals_group)
        
        self.detailed_layout.addStretch()
    
    # ============================================
    # UTILITY METHODS
    # ============================================
    
    def load_members(self):
        """Load all members into table"""
        try:
            members = self.db.get_all_members()
            
            self.members_table.setRowCount(len(members))
            
            for row, member in enumerate(members):
                # Member ID
                self.members_table.setItem(row, 0, QTableWidgetItem(member.get('member_id', 'N/A')))
                
                # Name
                name = member.get('member_profile', {}).get('name', 'Unknown')
                self.members_table.setItem(row, 1, QTableWidgetItem(name))
                
                # Email
                email = member.get('member_profile', {}).get('email', 'N/A')
                self.members_table.setItem(row, 2, QTableWidgetItem(email))
                
                # Tier
                tier = member.get('subscription', {}).get('tier', 'N/A')
                self.members_table.setItem(row, 3, QTableWidgetItem(tier))
                
                # Status
                status = member.get('subscription', {}).get('status', 'N/A')
                self.members_table.setItem(row, 4, QTableWidgetItem(status))
                
                # Member since
                created = member.get('created_at', 'N/A')[:10] if member.get('created_at') else 'N/A'
                self.members_table.setItem(row, 5, QTableWidgetItem(created))
                
                # Card valid
                card_valid = "✅ Yes" if member.get('card_data', {}).get('valid', False) else "❌ No"
                self.members_table.setItem(row, 6, QTableWidgetItem(card_valid))
            
            # Update stats
            self.stats_label.setText(f"Total Members: {len(members)}")
            
            # Refresh combo boxes
            self.populate_seal_members()
            self.populate_options_members()
            
            logger.info(f"Loaded {len(members)} members")

        except Exception as e:
            logger.error(f"Error loading members: {e}", exc_info=True)

    def launch_archive_sanctum(self):
        """Launch Archive Sanctum or login page"""
        if self.current_member_id:
            # Open Archive Sanctum directly with member data
            self._launch_sanctum(self.current_member_id)
        else:
            # Open Obelisk Customs login page
            try:
                import subprocess
                subprocess.Popen([sys.executable, "obelisk_customs.py"])
                logger.info("Launched Obelisk Customs login page")
            except Exception as e:
                logger.error(f"Failed to launch Obelisk Customs: {e}")
                QMessageBox.critical(self, "Error", f"Failed to launch login page:\n{str(e)}")
    
    def _generate_generic_card(self, member_data: Dict) -> Optional[str]:
        """Generate a generic card for new member with auto-verification"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            member_id = member_data.get('member_id')
            name = member_data.get('member_profile', {}).get('name', 'Member')
            tier = member_data.get('subscription', {}).get('tier', 'Standard')

            # Create card (512x768)
            card = Image.new('RGB', (512, 768), color='#1a0000')
            draw = ImageDraw.Draw(card)

            # Draw gradient background
            for y in range(768):
                shade = int(26 + (y / 768) * 30)
                draw.line([(0, y), (512, y)], fill=(shade, 0, 0))

            # Draw border
            draw.rectangle([(10, 10), (502, 758)], outline='#dc2626', width=3)

            # Load fonts
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            except:
                font_large = font_medium = font_small = ImageFont.load_default()

            # Draw text elements
            draw.text((256, 100), "AURORA ARCHIVE", fill='#dc2626', font=font_large, anchor='mm')
            draw.text((256, 150), "Member Card", fill='#fca5a5', font=font_medium, anchor='mm')
            draw.text((256, 300), name, fill='#ffffff', font=font_medium, anchor='mm')
            draw.text((256, 350), f"Tier: {tier}", fill='#fca5a5', font=font_small, anchor='mm')
            draw.text((256, 400), f"ID: {member_id}", fill='#9ca3af', font=font_small, anchor='mm')
            draw.text((256, 700), "Generic Card - Customize in Archive Sanctum",
                     fill='#6b7280', font=font_small, anchor='mm')

            # Save card
            card_dir = Path("data/cards")
            card_dir.mkdir(parents=True, exist_ok=True)
            card_path = card_dir / f"{member_id}_generic.png"
            card.save(card_path)

            # Apply seal
            sealed_path = self.seal_comp.embed_and_composite(str(card_path), member_data, None)

            if sealed_path:
                final_path = self.db.save_member_card(member_id, sealed_path)

                # Mark card as verified
                self.db.update_member(member_id, {
                    'card_data': {
                        'valid': True,
                        'crimson_collective': {
                            'verified': True,
                            'verification_date': datetime.now().isoformat(),
                            'obelisk_approved': True
                        }
                    }
                })

                logger.info(f"Generated and verified generic card for {member_id}")
                return final_path

            return None

        except Exception as e:
            logger.error(f"Generic card generation error: {e}", exc_info=True)
            return None


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Create and show window
    window = MemberManagerGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
