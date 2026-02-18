"""
The Archive Sanctum - Member Landing Page
Where authenticated souls enter the Crimson Collective

Over-engineered features:
- Dynamic soulcard display with 3D rotation
- Constellation dashboard showing account nodes
- Animated tier badges with particle effects
- Timeline visualization of member journey
- Quest-style menu system
- Real-time stats and achievements
- Subscription upgrade portal flag
- Cryptic poetic status messages
- Hidden easter eggs and secret interactions

Python 3.10+ | PyQt6
"""

import sys
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QGridLayout, QScrollArea,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem,
    QProgressBar, QTextEdit, QDialog, QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, 
    pyqtSignal, QPointF, QRectF, QSequentialAnimationGroup
)
from PyQt6.QtGui import (
    QFont, QPixmap, QPainter, QColor, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath
)

# Import steganography for card data
try:
    from steganography_module import CardSteganography
    STEG_AVAILABLE = True
except ImportError:
    STEG_AVAILABLE = False


class ConstellationNode(QGraphicsEllipseItem):
    """A node in the constellation dashboard"""
    
    def __init__(self, x: float, y: float, radius: float, color: QColor, label: str):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.setPos(x, y)
        self.label = label
        self.active = False
        
        # Gradient fill
        gradient = QRadialGradient(0, 0, radius)
        gradient.setColorAt(0, color.lighter(150))
        gradient.setColorAt(1, color)
        self.setBrush(QBrush(gradient))
        
        # Glowing border
        pen = QPen(color.lighter(180))
        pen.setWidth(2)
        self.setPen(pen)
        
        # Enable hover
        self.setAcceptHoverEvents(True)
    
    def hoverEnterEvent(self, event):
        """Glow on hover"""
        pen = self.pen()
        pen.setWidth(4)
        self.setPen(pen)
    
    def hoverLeaveEvent(self, event):
        """Return to normal"""
        pen = self.pen()
        pen.setWidth(2)
        self.setPen(pen)
    
    def activate(self):
        """Activate this node with animation"""
        self.active = True
        # Pulsing animation would go here


class ConstellationDashboard(QGraphicsView):
    """
    Over-engineered constellation visualization of account status
    
    Nodes represent different aspects:
    - Soulcard (center)
    - Subscription tier
    - Books rented
    - Generations used
    - Achievements
    - Timeline milestones
    """
    
    node_clicked = pyqtSignal(str)  # node_type
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Style
        self.setStyleSheet("""
            QGraphicsView {
                background-color: #0a0a0a;
                border: 2px solid #dc2626;
                border-radius: 12px;
            }
        """)
        
        self.nodes: Dict[str, ConstellationNode] = {}
        self.connections: List[QGraphicsLineItem] = []
        
    def setup_constellation(self, card_data: Dict):
        """Build the constellation based on card data"""
        self.scene.clear()
        self.nodes.clear()
        self.connections.clear()
        
        # Center point
        cx, cy = 200, 150
        
        # Create nodes in circular pattern
        node_configs = [
            ("soulcard", 0, 80, QColor("#dc2626"), "Soulcard"),
            ("tier", 45, 60, QColor("#f59e0b"), "Tier"),
            ("generations", 90, 60, QColor("#8b5cf6"), "Generations"),
            ("books", 135, 60, QColor("#06b6d4"), "Books"),
            ("timeline", 180, 60, QColor("#10b981"), "Timeline"),
            ("achievements", 225, 60, QColor("#ec4899"), "Achievements"),
            ("status", 270, 60, QColor("#f97316"), "Status"),
            ("upgrades", 315, 60, QColor("#eab308"), "Upgrades"),
        ]
        
        # Create nodes
        for node_id, angle, distance, color, label in node_configs:
            import math
            x = cx + distance * math.cos(math.radians(angle))
            y = cy + distance * math.sin(math.radians(angle))
            
            node = ConstellationNode(x, y, 15, color, label)
            node.setData(0, node_id)  # Store ID in node data
            self.nodes[node_id] = node
            self.scene.addItem(node)
        
        # Connect all nodes to center (soulcard)
        center_node = self.nodes["soulcard"]
        for node_id, node in self.nodes.items():
            if node_id != "soulcard":
                line = QGraphicsLineItem(
                    center_node.x(), center_node.y(),
                    node.x(), node.y()
                )
                pen = QPen(QColor(220, 38, 38, 80))  # Semi-transparent crimson
                pen.setWidth(1)
                line.setPen(pen)
                self.connections.append(line)
                self.scene.addItem(line)
        
        # Set scene size
        self.setSceneRect(-50, -50, 500, 400)
    
    def mousePressEvent(self, event):
        """Handle node clicks"""
        item = self.itemAt(event.pos())
        if isinstance(item, ConstellationNode):
            node_id = item.data(0)
            self.node_clicked.emit(node_id)
        super().mousePressEvent(event)


class AchievementBadge(QFrame):
    """Individual achievement badge with icon and description"""
    
    def __init__(self, icon: str, title: str, description: str, unlocked: bool = False):
        super().__init__()
        self.unlocked = unlocked
        
        self.setFixedSize(120, 140)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {'rgba(220, 38, 38, 0.2)' if unlocked else 'rgba(50, 50, 50, 0.2)'};
                border: 2px solid {'#dc2626' if unlocked else '#3f3f3f'};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            font-size: 36px;
            color: {'#dc2626' if unlocked else '#666'};
        """)
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: bold;
            color: {'#ff6b6b' if unlocked else '#666'};
        """)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"""
            font-size: 9px;
            color: {'#999' if unlocked else '#555'};
        """)
        layout.addWidget(desc_label)


class QuestMenuItem(QPushButton):
    """Over-engineered menu item styled as a quest/mission"""
    
    def __init__(self, icon: str, title: str, description: str, difficulty: str = "Normal"):
        super().__init__()
        
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Difficulty colors
        diff_colors = {
            "Easy": "#10b981",
            "Normal": "#f59e0b",
            "Hard": "#ef4444",
            "Epic": "#8b5cf6"
        }
        diff_color = diff_colors.get(difficulty, "#f59e0b")
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(127, 29, 29, 0.3), stop:1 rgba(220, 38, 38, 0.2));
                border: 2px solid #7f1d1d;
                border-left: 4px solid {diff_color};
                border-radius: 8px;
                text-align: left;
                padding: 12px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(185, 28, 28, 0.4), stop:1 rgba(220, 38, 38, 0.3));
                border: 2px solid #dc2626;
                border-left: 4px solid {diff_color};
            }}
        """)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            font-size: 32px;
            color: {diff_color};
        """)
        layout.addWidget(icon_label)
        
        # Text area
        text_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #ff6b6b;
        """)
        text_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            font-size: 11px;
            color: #999;
        """)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, stretch=1)
        
        # Difficulty badge
        diff_badge = QLabel(difficulty)
        diff_badge.setFixedSize(60, 24)
        diff_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diff_badge.setStyleSheet(f"""
            background-color: {diff_color};
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
        """)
        layout.addWidget(diff_badge)


class SubscriptionUpgradeDialog(QDialog):
    """Separate GUI for subscription upgrades - over-engineered comparison"""
    
    def __init__(self, current_tier: str, parent=None):
        super().__init__(parent)
        self.current_tier = current_tier
        self.setWindowTitle("🔺 Tier Ascension Portal")
        self.setMinimumSize(1000, 700)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("⚡ ASCEND YOUR TIER ⚡")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: #eab308;
            padding: 20px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #7c2d12, stop:1 #b91c1c);
            border-radius: 12px;
        """)
        layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel("Choose your path through the Crimson Collective")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #999; padding: 10px;")
        layout.addWidget(subtitle)
        
        # Tier comparison grid
        tiers_layout = QHBoxLayout()
        
        # Kids Tier
        kids_tier = self.create_tier_card(
            "Kids", "$5/month", "#06b6d4",
            ["5 generations/day", "Basic features", "Safe content only", 
             "Parental controls", "Educational focus"],
            self.current_tier == "Kids"
        )
        tiers_layout.addWidget(kids_tier)
        
        # Standard Tier
        standard_tier = self.create_tier_card(
            "Standard", "$10/month", "#8b5cf6",
            ["10 generations/day", "Standard features", "Community access",
             "Book rentals (5/month)", "Basic customization"],
            self.current_tier == "Standard"
        )
        tiers_layout.addWidget(standard_tier)
        
        # Premium Tier
        premium_tier = self.create_tier_card(
            "Premium", "$15/month", "#eab308",
            ["UNLIMITED generations", "ALL features", "Priority support",
             "Unlimited book rentals", "Advanced customization",
             "Exclusive events", "Early access"],
            self.current_tier == "Premium"
        )
        tiers_layout.addWidget(premium_tier)
        
        layout.addLayout(tiers_layout)
        
        # Comparison matrix
        comparison = QLabel("📊 Full feature comparison available in settings")
        comparison.setAlignment(Qt.AlignmentFlag.AlignCenter)
        comparison.setStyleSheet("""
            font-size: 12px;
            color: #666;
            padding: 20px;
            font-style: italic;
        """)
        layout.addWidget(comparison)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("✖ Not Now")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        upgrade_btn = QPushButton("⚡ Begin Ascension")
        upgrade_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ca8a04, stop:1 #eab308);
                color: white;
                border: 2px solid #fbbf24;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #eab308, stop:1 #fbbf24);
            }
        """)
        upgrade_btn.clicked.connect(self.accept)
        button_layout.addWidget(upgrade_btn)
        
        layout.addLayout(button_layout)
        
        # Dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0a;
            }
            QPushButton {
                background-color: #7f1d1d;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #991b1b;
            }
        """)
    
    def create_tier_card(self, name: str, price: str, color: str, 
                        features: List[str], is_current: bool):
        """Create a tier comparison card"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(0, 0, 0, 0.5);
                border: 3px solid {color if is_current else '#3f3f3f'};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        # Current badge
        if is_current:
            current_badge = QLabel("✓ CURRENT")
            current_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            current_badge.setStyleSheet(f"""
                background-color: {color};
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
            """)
            layout.addWidget(current_badge)
        
        # Tier name
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {color};
            padding: 10px;
        """)
        layout.addWidget(name_label)
        
        # Price
        price_label = QLabel(price)
        price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        price_label.setStyleSheet("""
            font-size: 18px;
            color: #999;
            padding-bottom: 20px;
        """)
        layout.addWidget(price_label)
        
        # Features
        for feature in features:
            feature_label = QLabel(f"• {feature}")
            feature_label.setWordWrap(True)
            feature_label.setStyleSheet("""
                font-size: 12px;
                color: #ccc;
                padding: 4px;
            """)
            layout.addWidget(feature_label)
        
        layout.addStretch()
        
        return card


class PlaceholderQuestDialog(QDialog):
    """
    Placeholder GUI for main quest tabs
    Shows example data with refresh and return to sanctum buttons
    """
    
    def __init__(self, quest_name: str, quest_icon: str, parent=None):
        super().__init__(parent)
        self.quest_name = quest_name
        self.quest_icon = quest_icon
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle(f"{self.quest_icon} {self.quest_name}")
        self.setMinimumSize(900, 600)
        
        # Dark crimson theme
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0a;
                color: #ff6b6b;
            }
            QLabel {
                color: #ff6b6b;
            }
            QPushButton {
                background-color: #7f1d1d;
                color: #fbbf24;
                border: 2px solid #dc2626;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                border-color: #ef4444;
            }
            QTextEdit {
                background-color: rgba(127, 29, 29, 0.2);
                border: 2px solid #7f1d1d;
                border-radius: 8px;
                color: #ccc;
                padding: 10px;
                font-family: 'Courier New';
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header
        header = QLabel(f"{self.quest_icon} {self.quest_name}")
        header.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #dc2626;
            padding-bottom: 10px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Status message
        status = QLabel("🚧 This section is under construction")
        status.setStyleSheet("""
            font-size: 14px;
            color: #fbbf24;
            font-style: italic;
        """)
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status)
        
        # Example data area
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)
        self.load_example_data()
        layout.addWidget(self.data_display)
        
        # Button row
        button_layout = QHBoxLayout()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.clicked.connect(self.refresh_data)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        # Return to Sanctum button
        return_btn = QPushButton("🏛️ Return to Sanctum")
        return_btn.setStyleSheet("""
            QPushButton {
                background-color: #991b1b;
                color: #fbbf24;
                border: 2px solid #dc2626;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
                border-color: #ef4444;
            }
        """)
        return_btn.clicked.connect(self.accept)
        button_layout.addWidget(return_btn)
        
        layout.addLayout(button_layout)
    
    def load_example_data(self):
        """Load example data based on quest type"""
        example_data = {
            "Browse Tome Archives": """
═══════════════════════════════════════════════════════════════
📚 TOME ARCHIVES - AVAILABLE BOOKS
═══════════════════════════════════════════════════════════════

Category: Fiction
─────────────────────────────────────────────────────────────
  📖 The Crimson Chronicles (Volume I-III)
     Author: Aurora Scribe | Rating: ⭐⭐⭐⭐⭐
     Status: Available | Format: Digital
  
  📖 Shadows of the Archive
     Author: Guild Master Erebus | Rating: ⭐⭐⭐⭐
     Status: Available | Format: Digital
  
  📖 Tales from the Void
     Author: Crimson Collective | Rating: ⭐⭐⭐⭐⭐
     Status: Available | Format: Digital

Category: Technical
─────────────────────────────────────────────────────────────
  📘 Advanced Steganography Techniques
     Author: Dr. Cipher | Rating: ⭐⭐⭐⭐
     Status: Available | Format: Digital + Audio
  
  📘 Python Sorcery: A Guild's Guide
     Author: Code Mage Alliance | Rating: ⭐⭐⭐⭐⭐
     Status: Available | Format: Digital

Category: Archive History
─────────────────────────────────────────────────────────────
  📕 The First Era: Digital Arcana Origins
     Author: Archive Keepers | Rating: ⭐⭐⭐⭐⭐
     Status: Available | Format: Sealed Manuscript
""",
            "Active Rentals": """
═══════════════════════════════════════════════════════════════
🎯 YOUR ACTIVE RENTALS
═══════════════════════════════════════════════════════════════

Current Rentals: 3 / 5 (Premium Tier Limit)
─────────────────────────────────────────────────────────────

📖 The Crimson Chronicles (Volume I)
   Rented: 5 days ago
   Due: 9 days remaining
   Progress: 67% complete
   [Extend Rental] [Return Now] [Add Bookmark]

📘 Advanced Steganography Techniques  
   Rented: 12 days ago
   Due: 2 days remaining ⚠️
   Progress: 89% complete
   [Extend Rental] [Return Now] [Add Bookmark]

📕 The First Era: Digital Arcana Origins
   Rented: 2 days ago
   Due: 12 days remaining
   Progress: 23% complete
   [Extend Rental] [Return Now] [Add Bookmark]

═══════════════════════════════════════════════════════════════
Rental History: 47 books | Completion Rate: 94%
═══════════════════════════════════════════════════════════════
""",
            "Achievement Gallery": """
═══════════════════════════════════════════════════════════════
🏆 ACHIEVEMENT GALLERY
═══════════════════════════════════════════════════════════════

Unlocked: 23 / 50 Achievements
Total Points: 1,847 / 5,000
─────────────────────────────────────────────────────────────

🥇 RARE ACHIEVEMENTS
─────────────────────────────────────────────────────────────
  ⭐ First Steps (100 pts) - Unlocked Dec 1, 2025
     "Created your first soulcard"
  
  ⭐ Crimson Initiate (200 pts) - Unlocked Dec 2, 2025
     "Passed Obelisk validation 10 times"
  
  ⭐ Tome Collector (250 pts) - Unlocked Dec 5, 2025
     "Rented 25 books from the Archive"

🥈 COMMON ACHIEVEMENTS  
─────────────────────────────────────────────────────────────
  ✨ Card Crafter (50 pts) - Unlocked Dec 1, 2025
     "Generated 5 soulcards"
  
  ✨ Archive Explorer (50 pts) - Unlocked Dec 3, 2025
     "Visited all Archive sections"
  
  ✨ Loyal Member (75 pts) - Unlocked Dec 7, 2025
     "Active for 7 consecutive days"

🔒 LOCKED ACHIEVEMENTS
─────────────────────────────────────────────────────────────
  🔒 Master Artisan (500 pts)
     "Generate 100 soulcards"
     Progress: 42 / 100
  
  🔒 Guild Legend (1000 pts)  
     "Reach Premium tier and maintain for 1 year"
     Progress: 9 days / 365 days
""",
            "Account Management": """
═══════════════════════════════════════════════════════════════
📊 ACCOUNT MANAGEMENT
═══════════════════════════════════════════════════════════════

Profile Information
─────────────────────────────────────────────────────────────
  Username: CrimsonMage
  Member ID: CM-2025-001247
  Email: crimsonmage@aurora-archive.void
  Tier: Premium ⭐⭐⭐
  Member Since: December 1, 2025
  Last Login: December 9, 2025 (Today)

Subscription Details
─────────────────────────────────────────────────────────────
  Current Plan: Premium
  Renewal Date: January 1, 2026
  Payment Method: Void Crystal (***-***-1234)
  Auto-Renewal: Enabled ✅

Account Statistics
─────────────────────────────────────────────────────────────
  Total Generations: 42
  Books Rented: 47
  Active Days: 9
  Achievement Points: 1,847
  Guild Reputation: Esteemed

Preferences
─────────────────────────────────────────────────────────────
  Theme: Dark Crimson
  Notifications: Enabled
  Email Updates: Weekly Digest
  Privacy: Guild Members Only
  
[Edit Profile] [Change Password] [Update Payment] [Privacy Settings]
""",
            "Transaction History": """
═══════════════════════════════════════════════════════════════
📜 TRANSACTION HISTORY
═══════════════════════════════════════════════════════════════

Recent Transactions (Last 30 Days)
─────────────────────────────────────────────────────────────

Dec 9, 2025 | 14:23:00
  Type: Card Generation
  Description: AI-generated soulcard (Grok)
  Cost: 1 Generation Credit
  Balance: 58 credits remaining
  Status: ✅ Completed

Dec 8, 2025 | 09:15:33
  Type: Book Rental
  Description: "Advanced Steganography Techniques"
  Cost: 1 Rental Credit
  Balance: 4 rentals remaining
  Status: ✅ Active

Dec 7, 2025 | 19:47:12
  Type: Card Generation
  Description: AI-generated soulcard (Stable Diffusion)
  Cost: 1 Generation Credit  
  Balance: 59 credits remaining
  Status: ✅ Completed

Dec 5, 2025 | 11:30:00
  Type: Tier Upgrade
  Description: Upgraded from Standard to Premium
  Cost: $15.00 (Void Crystals)
  Status: ✅ Processed

Dec 1, 2025 | 08:00:00
  Type: Account Creation
  Description: Welcome to Aurora Archive!
  Cost: $0.00
  Bonus: +10 Generation Credits, +5 Rental Credits
  Status: ✅ Completed

═══════════════════════════════════════════════════════════════
Total Spent: $15.00 | Credits Used: 51 | Books Rented: 47
═══════════════════════════════════════════════════════════════
""",
            "Customization Studio": """
═══════════════════════════════════════════════════════════════
🎨 CUSTOMIZATION STUDIO
═══════════════════════════════════════════════════════════════

Personalize Your Card Generation Experience
─────────────────────────────────────────────────────────────

Saved Style Presets
─────────────────────────────────────────────────────────────
  🌙 Crimson Night (Default)
     "Dark crimson aesthetic with gothic elements"
     Used: 15 times
  
  ⚔️ Warrior's Honor
     "Bold, medieval fantasy with armor and weapons"
     Used: 8 times
  
  ✨ Ethereal Dreams
     "Soft, glowing, magical atmosphere"
     Used: 12 times
  
  🔥 Void Fire
     "Intense flames and dark energy"
     Used: 7 times

Customization Options
─────────────────────────────────────────────────────────────
  Color Palette: [ Crimson Red / Gold / Black ]
  Art Style: [ Anime / Realistic / Fantasy / Abstract ]
  Background: [ Gradient / Textured / Scenic ]
  Border: [ Classic / Ornate / Minimal / None ]
  Effects: [ Glow / Particles / None ]

Default Prompt Settings
─────────────────────────────────────────────────────────────
  Include Character: Yes
  Include Background: Yes
  Include Magical Elements: Yes
  Card Size: 512x768 (Standard)
  Quality: High

[Create New Preset] [Edit Presets] [Reset to Default]
""",
            "Timeline Journey": """
═══════════════════════════════════════════════════════════════
🗺️ TIMELINE JOURNEY
═══════════════════════════════════════════════════════════════

Your Path Through the Crimson Collective
─────────────────────────────────────────────────────────────

December 9, 2025 (Today)
  🎬 Uploaded first video soulcard
  ✨ Generated 2 new cards
  📚 Extended rental: "Advanced Steganography"

December 8, 2025
  📘 Rented: "Advanced Steganography Techniques"
  🏆 Unlocked achievement: "Tome Collector"
  
December 7, 2025
  ✨ Generated 3 cards
  🏆 Unlocked achievement: "Loyal Member"
  ⚙️ Updated profile preferences

December 6, 2025
  📚 Completed reading: "Shadows of the Archive"
  ⭐ Left 5-star review
  
December 5, 2025
  🔺 UPGRADED TO PREMIUM TIER
  🎁 Received: +20 Gen Credits, +10 Rental Credits
  📖 Rented: "The First Era: Digital Arcana Origins"

December 4, 2025  
  ✨ Generated first video card
  📚 Rented 2 books
  
December 3, 2025
  🏆 Unlocked achievement: "Archive Explorer"
  ✨ Generated 4 cards

December 2, 2025
  🏆 Unlocked achievement: "Crimson Initiate"
  📚 Rented first book: "The Crimson Chronicles"
  
December 1, 2025
  🎉 ACCOUNT CREATED
  ⭐ Unlocked achievement: "First Steps"
  ✨ Generated first soulcard
  🏛️ Passed Obelisk validation

═══════════════════════════════════════════════════════════════
Total Journey: 9 days | Major Milestones: 5
═══════════════════════════════════════════════════════════════
""",
            "Settings & Support": """
═══════════════════════════════════════════════════════════════
⚙️ SETTINGS & SUPPORT
═══════════════════════════════════════════════════════════════

System Settings
─────────────────────────────────────────────────────────────
  🎨 Theme: Dark Crimson
  🔔 Notifications: Enabled
  📧 Email Updates: Weekly Digest
  🔊 Sound Effects: Enabled
  🌐 Language: English
  💾 Auto-Save: Enabled

Privacy Settings
─────────────────────────────────────────────────────────────
  Profile Visibility: Guild Members Only
  Activity Status: Visible
  Card Gallery: Private
  Achievement Showcase: Public

Generation Settings
─────────────────────────────────────────────────────────────
  Default Backend: Auto-Select
  Image Quality: High
  Save Original Prompts: Yes
  Auto-Seal Cards: Yes
  Verification: Auto-Verify

Support Center
─────────────────────────────────────────────────────────────
  📖 Documentation: View user guides and tutorials
  💬 Contact Support: Submit a ticket
  🐛 Report Bug: Help improve the Archive
  💡 Feature Request: Suggest new features
  ❓ FAQ: Common questions and answers

Quick Actions
─────────────────────────────────────────────────────────────
  [Clear Cache] [Export Data] [Import Backup]
  [Reset Settings] [Check for Updates]

System Information
─────────────────────────────────────────────────────────────
  Version: Aurora Archive v2.0.1
  Python: 3.10.16
  Database: Active
  Last Backup: December 9, 2025 - 00:00:00
  
═══════════════════════════════════════════════════════════════
Need help? Contact: support@aurora-archive.void
═══════════════════════════════════════════════════════════════
"""
        }
        
        # Get appropriate example data
        data = example_data.get(self.quest_name, f"""
═══════════════════════════════════════════════════════════════
{self.quest_icon} {self.quest_name.upper()}
═══════════════════════════════════════════════════════════════

This section is currently under development.

Example data will appear here once the feature is implemented.

Stay tuned for updates from the Crimson Collective! ✨
═══════════════════════════════════════════════════════════════
""")
        
        self.data_display.setPlainText(data)
    
    def refresh_data(self):
        """Refresh the displayed data"""
        self.load_example_data()
        # Add a temporary status update
        current_text = self.data_display.toPlainText()
        timestamp = datetime.now().strftime("%H:%M:%S")
        refresh_msg = f"\n\n[Refreshed at {timestamp}]"
        self.data_display.setPlainText(current_text + refresh_msg)


class ArchiveSanctumWindow(QMainWindow):
    """
    The Archive Sanctum - Over-engineered member landing page
    
    Features:
    - Dynamic soulcard display
    - Constellation dashboard
    - Animated tier badge
    - Quest-style menu system
    - Real-time stats
    - Achievement showcase
    - Subscription upgrade portal
    - Timeline visualization
    - Cryptic status messages
    - Graceful shutdown and logout
    """
    
    # Signal for logout/shutdown
    session_ended = pyqtSignal()
    
    def __init__(self, card_path: str, card_data: Dict):
        super().__init__()
        self.card_path = card_path
        self.card_data = card_data
        self.is_shutting_down = False
        self.active_timers = []
        self.active_dialogs = []
        self.setup_ui()
        self.load_member_data()
        self.start_animations()
    
    def setup_ui(self):
        self.setWindowTitle("🏛️ The Archive Sanctum")
        self.setMinimumSize(1400, 900)
        
        # Dark crimson theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0a0a0a;
                color: #ff6b6b;
            }
            QLabel {
                color: #ff6b6b;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header with animated welcome
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Main content area
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(20)
        
        # Left panel - Soulcard & Stats
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel, stretch=1)
        
        # Center panel - Quest Menu
        center_panel = self.create_center_panel()
        content_layout.addWidget(center_panel, stretch=2)
        
        # Right panel - Constellation & Achievements
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel, stretch=1)
        
        content_scroll.setWidget(content_widget)
        main_layout.addWidget(content_scroll)
        
        # Footer with status
        footer = self.create_footer()
        main_layout.addWidget(footer)
    
    def create_header(self):
        """Over-engineered animated header"""
        header = QFrame()
        header.setFixedHeight(100)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7f1d1d, stop:0.5 #b91c1c, stop:1 #7f1d1d);
                border: 2px solid #dc2626;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(header)
        
        # Title with animated text
        title = QLabel("🏛️ THE ARCHIVE SANCTUM 🏛️")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: #fbbf24;
        """)
        layout.addWidget(title)
        
        # Subtitle - member name from card
        member_name = self.card_data.get('user_id', 'Unknown Member')
        subtitle = QLabel(f"Welcome back, {member_name}")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 16px;
            color: #ff6b6b;
            font-style: italic;
        """)
        layout.addWidget(subtitle)
        self.subtitle_label = subtitle
        
        return header
    
    def create_left_panel(self):
        """Soulcard display and quick stats"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: rgba(127, 29, 29, 0.2);
                border: 2px solid #7f1d1d;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        # Section title
        title = QLabel("📇 Your Soulcard")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #dc2626;
            padding-bottom: 10px;
        """)
        layout.addWidget(title)
        
        # Card image/video preview
        self.card_preview = QLabel()
        self.card_preview.setFixedSize(250, 350)
        self.card_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_preview.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.5);
            border: 2px solid #dc2626;
            border-radius: 8px;
        """)
        
        # Load card image or video
        try:
            # Check if it's a video file
            if self.card_path.lower().endswith('.mp4'):
                # For MP4, show video indicator
                self.card_preview.setText("🎬\n\nVideo\nSoulcard")
                self.card_preview.setStyleSheet("""
                    background-color: rgba(0, 0, 0, 0.5);
                    border: 2px solid #dc2626;
                    border-radius: 8px;
                    font-size: 18px;
                    color: #fbbf24;
                    font-weight: bold;
                """)
                # TODO: Could add QVideoWidget for actual video preview
            else:
                # Load image
                pixmap = QPixmap(self.card_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        240, 340,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.card_preview.setPixmap(scaled_pixmap)
                else:
                    self.card_preview.setText("🎴\n\nSoulcard\nPreview")
        except Exception as e:
            self.card_preview.setText("🎴\n\nSoulcard\nPreview")
        
        layout.addWidget(self.card_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Quick stats
        stats_title = QLabel("📊 Quick Stats")
        stats_title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #dc2626;
            padding-top: 20px;
            padding-bottom: 10px;
        """)
        layout.addWidget(stats_title)
        
        # Stats grid
        stats_grid = QGridLayout()
        
        # Tier
        tier = self.card_data.get('tier', 'Standard')
        stats_grid.addWidget(self.create_stat_item("🏆", "Tier", tier), 0, 0)
        
        # Generations
        stats_grid.addWidget(self.create_stat_item("✨", "Generated", "42"), 0, 1)
        
        # Books
        stats_grid.addWidget(self.create_stat_item("📚", "Books", "7"), 1, 0)
        
        # Days active
        stats_grid.addWidget(self.create_stat_item("📅", "Days", "14"), 1, 1)
        
        layout.addLayout(stats_grid)
        
        layout.addStretch()
        
        return panel
    
    def create_stat_item(self, icon: str, label: str, value: str):
        """Create a stat display item"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid #7f1d1d;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setSpacing(2)
        
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(icon_label)
        
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fbbf24;")
        layout.addWidget(value_label)
        
        label_label = QLabel(label)
        label_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_label.setStyleSheet("font-size: 10px; color: #999;")
        layout.addWidget(label_label)
        
        return widget
    
    def create_center_panel(self):
        """Quest-style main menu"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: rgba(127, 29, 29, 0.2);
                border: 2px solid #7f1d1d;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        # Section title
        title = QLabel("⚔️ Main Quests")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #dc2626;
            padding-bottom: 20px;
        """)
        layout.addWidget(title)
        
        # Quest menu items
        quests = [
            ("📚", "Browse Tome Archives", "Explore the infinite library of knowledge", "Normal"),
            ("✨", "Generate New Card", "Forge a new soulcard with AI magic", "Easy"),
            ("🎯", "Active Rentals", "Manage your currently borrowed tomes", "Normal"),
            ("💎", "Achievement Gallery", "View your earned badges and milestones", "Easy"),
            ("📊", "Account Management", "Configure your profile and preferences", "Normal"),
            ("🔺", "Tier Ascension", "Upgrade your subscription for more power", "Epic"),
            ("📜", "Transaction History", "Review your past activities and payments", "Normal"),
            ("🎨", "Customization Studio", "Personalize your card generation style", "Hard"),
            ("🗺️", "Timeline Journey", "Visualize your path through the Collective", "Normal"),
            ("⚙️", "Settings & Support", "Adjust system settings and get help", "Easy"),
            ("🚪", "Leave Archive", "Return to the Obelisk and end session", "Easy"),
        ]
        
        for icon, title_text, desc, difficulty in quests:
            quest_item = QuestMenuItem(icon, title_text, desc, difficulty)
            
            # Connect actions
            if "Tier Ascension" in title_text:
                quest_item.clicked.connect(self.open_tier_ascension)
            elif "Generate" in title_text:
                quest_item.clicked.connect(self.launch_card_generator)
            elif "Achievement" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Leave Archive" in title_text:
                quest_item.clicked.connect(self.logout_and_close)
            elif "Browse Tome" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Active Rentals" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Account Management" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Transaction History" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Customization Studio" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Timeline Journey" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            elif "Settings & Support" in title_text:
                quest_item.clicked.connect(lambda checked, t=title_text, i=icon: self.open_quest_dialog(t, i))
            
            layout.addWidget(quest_item)
        
        layout.addStretch()
        
        return panel
    
    def create_right_panel(self):
        """Constellation dashboard and achievements"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: rgba(127, 29, 29, 0.2);
                border: 2px solid #7f1d1d;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        # Constellation dashboard
        const_title = QLabel("🌟 Account Constellation")
        const_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #dc2626;
            padding-bottom: 10px;
        """)
        layout.addWidget(const_title)
        
        # Constellation view
        self.constellation = ConstellationDashboard()
        self.constellation.setFixedHeight(300)
        self.constellation.setup_constellation(self.card_data)
        self.constellation.node_clicked.connect(self.on_constellation_node_clicked)
        layout.addWidget(self.constellation)
        
        # Achievement showcase
        achieve_title = QLabel("🏆 Latest Achievements")
        achieve_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #dc2626;
            padding-top: 20px;
            padding-bottom: 10px;
        """)
        layout.addWidget(achieve_title)
        
        # Achievement badges
        achieve_scroll = QScrollArea()
        achieve_scroll.setWidgetResizable(True)
        achieve_scroll.setFixedHeight(180)
        achieve_widget = QWidget()
        achieve_layout = QHBoxLayout(achieve_widget)
        
        # Sample achievements
        achievements = [
            ("🎴", "First Card", "Generated first", True),
            ("📚", "Bookworm", "Rented 5 books", True),
            ("✨", "Prolific", "50 generations", False),
            ("💎", "Premium", "Upgraded tier", False),
        ]
        
        for icon, title, desc, unlocked in achievements:
            badge = AchievementBadge(icon, title, desc, unlocked)
            achieve_layout.addWidget(badge)
        
        achieve_scroll.setWidget(achieve_widget)
        layout.addWidget(achieve_scroll)
        
        layout.addStretch()
        
        return panel
    
    def create_footer(self):
        """Status bar with cryptic messages"""
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("""
            QFrame {
                background-color: rgba(127, 29, 29, 0.3);
                border: 2px solid #7f1d1d;
                border-top: 3px solid #dc2626;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(footer)
        
        # Cryptic status message
        status = QLabel("🔮 The Crimson Collective watches over you...")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet("""
            font-size: 12px;
            color: #999;
            font-style: italic;
        """)
        layout.addWidget(status)
        self.status_label = status
        
        # Session info
        session_info = QLabel(f"Session: Active | Obelisk Verified | Sigil: {self.card_data.get('obelisk_verification', {}).get('verification_sigil', 'Unknown')[:8]}...")
        session_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_info.setStyleSheet("""
            font-size: 10px;
            color: #666;
        """)
        layout.addWidget(session_info)
        
        return footer
    
    def load_member_data(self):
        """Load and process member data from soulcard"""
        # Extract member info from card data
        if 'user_id' in self.card_data:
            self.subtitle_label.setText(f"Welcome back, {self.card_data['user_id']}")
        
        # Check for Obelisk verification
        if 'obelisk_verification' not in self.card_data:
            # This shouldn't happen, but safety check
            self.status_label.setText("⚠️ Warning: Missing Obelisk verification")
    
    def start_animations(self):
        """Start periodic animations and updates"""
        # Rotate cryptic status messages
        self.status_messages = [
            "🔮 The Crimson Collective watches over you...",
            "⚔️ Your journey through the Archive continues...",
            "🌟 New constellations form in your path...",
            "📚 Ancient knowledge awaits your discovery...",
            "✨ Your creative power grows stronger...",
            "🏛️ The Sanctum recognizes your dedication...",
        ]
        self.status_index = 0
        
        # Update status every 5 seconds
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.rotate_status_message)
        self.status_timer.start(5000)
        self.active_timers.append(self.status_timer)
    
    def rotate_status_message(self):
        """Cycle through cryptic status messages"""
        self.status_index = (self.status_index + 1) % len(self.status_messages)
        self.status_label.setText(self.status_messages[self.status_index])
    
    def on_constellation_node_clicked(self, node_id: str):
        """Handle constellation node clicks"""
        actions = {
            "soulcard": "View detailed soulcard information",
            "tier": "Open tier management",
            "generations": "View generation history",
            "books": "Browse active rentals",
            "timeline": "Explore your timeline",
            "achievements": "View all achievements",
            "status": "Check account status",
            "upgrades": "Open tier ascension portal"
        }
        
        if node_id == "upgrades":
            self.open_tier_ascension()
        else:
            # Placeholder for other actions
            self.status_label.setText(f"🔮 {actions.get(node_id, 'Unknown action')}")
    
    def open_tier_ascension(self):
        """Open the subscription upgrade dialog"""
        current_tier = self.card_data.get('tier', 'Standard')
        dialog = SubscriptionUpgradeDialog(current_tier, self)
        self.active_dialogs.append(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_label.setText("⚡ Tier ascension initiated! Processing upgrade...")
            # TODO: Implement actual upgrade logic
        self.active_dialogs.remove(dialog)
    
    def launch_card_generator(self):
        """Launch the Aurora card generator"""
        self.status_label.setText("✨ Launching card generation portal...")
        try:
            import subprocess
            import sys
            
            # Launch aurora_pyqt6_main.py
            aurora_script = Path(__file__).parent / "aurora_pyqt6_main.py"
            subprocess.Popen([
                sys.executable,
                str(aurora_script)
            ])
            
            self.status_label.setText("✨ Card Generator launched!")
            
        except Exception as e:
            self.status_label.setText(f"❌ Failed to launch generator: {e}")
            QMessageBox.warning(
                self,
                "Launch Error",
                f"Failed to launch card generator:\n{e}\n\nMake sure aurora_pyqt6_main.py exists."
            )
    
    def open_quest_dialog(self, quest_name: str, quest_icon: str):
        """Open a placeholder dialog for a quest"""
        self.status_label.setText(f"{quest_icon} Opening {quest_name}...")
        dialog = PlaceholderQuestDialog(quest_name, quest_icon, self)
        self.active_dialogs.append(dialog)
        dialog.exec()
        if dialog in self.active_dialogs:
            self.active_dialogs.remove(dialog)
        self.status_label.setText(f"{quest_icon} Returned from {quest_name}")
    
    def show_achievements(self):
        """Show full achievement gallery"""
        self.open_quest_dialog("Achievement Gallery", "🏆")
    
    def cleanup_timers(self):
        """Stop all active timers"""
        for timer in self.active_timers:
            if timer and timer.isActive():
                timer.stop()
        self.active_timers.clear()
    
    def cleanup_dialogs(self):
        """Close all active dialogs"""
        for dialog in self.active_dialogs[:]:  # Copy list to avoid modification during iteration
            if dialog and dialog.isVisible():
                dialog.close()
        self.active_dialogs.clear()
    
    def cleanup_resources(self):
        """Gracefully clean up all resources"""
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        
        # Update status
        self.status_label.setText("🌙 Closing the Archive Sanctum...")
        
        # Stop all timers
        self.cleanup_timers()
        
        # Close all dialogs
        self.cleanup_dialogs()
        
        # Small delay for visual feedback
        QTimer.singleShot(500, self.finalize_shutdown)
    
    def finalize_shutdown(self):
        """Final shutdown step"""
        self.status_label.setText("✨ The Crimson Collective awaits your return...")
        QTimer.singleShot(1000, self.close)
    
    def logout_and_close(self):
        """Logout with confirmation"""
        if self.is_shutting_down:
            return
        
        # Create logout confirmation dialog
        logout_dialog = QDialog(self)
        logout_dialog.setWindowTitle("Leave the Archive?")
        logout_dialog.setModal(True)
        logout_dialog.setFixedSize(400, 200)
        logout_dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                border: 2px solid #dc2626;
            }
            QLabel {
                color: #ff6b6b;
                font-size: 14px;
            }
            QPushButton {
                background-color: #3f3f3f;
                color: #ccc;
                border: 1px solid #666;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #525252;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(logout_dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Icon and message
        message = QLabel("🚪\n\nAre you sure you wish to leave\nthe Archive Sanctum?")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet("font-size: 16px; color: #fbbf24;")
        layout.addWidget(message)
        
        # Subtext
        subtext = QLabel("Your session will be ended and you will return to the Obelisk.")
        subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtext.setStyleSheet("font-size: 12px; color: #999;")
        subtext.setWordWrap(True)
        layout.addWidget(subtext)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Stay in Archive")
        cancel_btn.clicked.connect(logout_dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        logout_btn = QPushButton("🚪 Leave Archive")
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fbbf24;
                border: 1px solid #dc2626;
            }
            QPushButton:hover {
                background-color: #991b1b;
            }
        """)
        logout_btn.clicked.connect(logout_dialog.accept)
        button_layout.addWidget(logout_btn)
        
        layout.addLayout(button_layout)
        
        self.active_dialogs.append(logout_dialog)
        
        # Show dialog and handle result
        if logout_dialog.exec() == QDialog.DialogCode.Accepted:
            self.active_dialogs.remove(logout_dialog)
            self.cleanup_resources()
            self.session_ended.emit()
        else:
            self.active_dialogs.remove(logout_dialog)
    
    def closeEvent(self, event):
        """Override close event to ensure cleanup"""
        if not self.is_shutting_down:
            event.ignore()
            self.logout_and_close()
        else:
            event.accept()


def main():
    """Launch the Archive Sanctum"""
    import argparse
    
    app = QApplication(sys.argv)
    
    # Set application font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Aurora Archive Sanctum')
    parser.add_argument('--card', type=str, help='Path to validated soulcard')
    parser.add_argument('--validated', action='store_true', help='Card has been Obelisk validated')
    parser.add_argument('--member', type=str, help='Member ID for database lookup')
    
    args, unknown = parser.parse_known_args()
    
    # Determine card path and load card data
    if args.card and Path(args.card).exists():
        card_path = args.card
        
        # Try to extract card data from steganography
        try:
            if STEG_AVAILABLE:
                steg = CardSteganography()
                card_data = steg.extract_data(card_path)
            else:
                # Fallback to basic data
                card_data = {
                    "user_id": "Guest",
                    "tier": "Standard",
                    "obelisk_verification": {
                        "passed": args.validated,
                        "timestamp": datetime.now().isoformat()
                    }
                }
        except Exception as e:
            print(f"Warning: Could not extract card data: {e}")
            card_data = {
                "user_id": "Guest",
                "tier": "Standard",
                "obelisk_verification": {
                    "passed": args.validated,
                    "timestamp": datetime.now().isoformat()
                }
            }
    else:
        # Default test mode with example data
        card_path = str(Path(__file__).parent.parent / "Assets" / "generated_cards" / "test_card.png")
        card_data = {
            "user_id": "CrimsonMage",
            "tier": "Premium",
            "obelisk_verification": {
                "passed": True,
                "verification_sigil": "a7f2d9c4b1e8563a",
                "timestamp": datetime.now().isoformat()
            },
            "crimson_collective": {
                "sigil": "abc123def456",
                "seal": "forged in the Crimson Void where stars bleed light"
            }
        }
    
    # Create and show sanctum
    sanctum = ArchiveSanctumWindow(card_path, card_data)
    sanctum.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
