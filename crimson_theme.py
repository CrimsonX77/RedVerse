"""
Crimson Theme - PyQt6 Styling Module
Crimson/Gold/Black/Silver theme for Dragon Tools

Author: Crimson Valentine
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt


def apply_crimson_theme(widget):
    """
    Apply Crimson/Gold/Black/Silver theme to a PyQt6 widget
    
    Args:
        widget: QWidget or QMainWindow to apply theme to
    """
    
    # Crimson/Gold/Black/Silver color scheme
    stylesheet = """
    QMainWindow, QWidget, QDialog {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 10pt;
    }
    
    QGroupBox {
        border: 2px solid #8B0000;
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #FFD700;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 5px;
        color: #FFD700;
    }
    
    QPushButton {
        background-color: #8B0000;
        color: #FFD700;
        border: 2px solid #B22222;
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: bold;
        min-height: 25px;
    }
    
    QPushButton:hover {
        background-color: #B22222;
        border-color: #DC143C;
    }
    
    QPushButton:pressed {
        background-color: #6B0000;
    }
    
    QPushButton:disabled {
        background-color: #4a4a4a;
        color: #888888;
        border-color: #666666;
    }
    
    QLineEdit, QTextEdit, QPlainTextEdit {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 2px solid #8B0000;
        border-radius: 4px;
        padding: 4px;
        selection-background-color: #8B0000;
        selection-color: #FFD700;
    }
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
        border-color: #DC143C;
    }
    
    QComboBox {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 2px solid #8B0000;
        border-radius: 4px;
        padding: 4px;
        min-height: 25px;
    }
    
    QComboBox:hover {
        border-color: #DC143C;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid #FFD700;
        margin-right: 5px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #2d2d2d;
        color: #e0e0e0;
        selection-background-color: #8B0000;
        selection-color: #FFD700;
        border: 2px solid #8B0000;
    }
    
    QSpinBox {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 2px solid #8B0000;
        border-radius: 4px;
        padding: 4px;
        min-height: 25px;
    }
    
    QSpinBox:hover {
        border-color: #DC143C;
    }
    
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #8B0000;
        border: 1px solid #B22222;
    }
    
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background-color: #B22222;
    }
    
    QCheckBox {
        color: #e0e0e0;
        spacing: 5px;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #8B0000;
        border-radius: 3px;
        background-color: #2d2d2d;
    }
    
    QCheckBox::indicator:checked {
        background-color: #8B0000;
        image: none;
    }
    
    QCheckBox::indicator:checked:after {
        content: "✓";
        color: #FFD700;
    }
    
    QLabel {
        color: #e0e0e0;
    }
    
    QListWidget {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 2px solid #8B0000;
        border-radius: 4px;
        padding: 4px;
    }
    
    QListWidget::item {
        padding: 4px;
        border-radius: 2px;
    }
    
    QListWidget::item:selected {
        background-color: #8B0000;
        color: #FFD700;
    }
    
    QListWidget::item:hover {
        background-color: #4a4a4a;
    }
    
    QProgressBar {
        background-color: #2d2d2d;
        border: 2px solid #8B0000;
        border-radius: 4px;
        text-align: center;
        color: #FFD700;
        min-height: 20px;
    }
    
    QProgressBar::chunk {
        background-color: #8B0000;
        border-radius: 2px;
    }
    
    QScrollBar:vertical {
        background-color: #2d2d2d;
        width: 14px;
        border: 1px solid #8B0000;
    }
    
    QScrollBar::handle:vertical {
        background-color: #8B0000;
        border-radius: 6px;
        min-height: 20px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #B22222;
    }
    
    QScrollBar:horizontal {
        background-color: #2d2d2d;
        height: 14px;
        border: 1px solid #8B0000;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #8B0000;
        border-radius: 6px;
        min-width: 20px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #B22222;
    }
    
    QScrollBar::add-line, QScrollBar::sub-line {
        background: none;
        border: none;
    }
    
    QTabWidget::pane {
        border: 2px solid #8B0000;
        border-radius: 4px;
        background-color: #1a1a1a;
    }
    
    QTabBar::tab {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 2px solid #8B0000;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 6px 12px;
        margin-right: 2px;
    }
    
    QTabBar::tab:selected {
        background-color: #8B0000;
        color: #FFD700;
    }
    
    QTabBar::tab:hover {
        background-color: #4a4a4a;
    }
    
    QMenuBar {
        background-color: #1a1a1a;
        color: #e0e0e0;
        border-bottom: 2px solid #8B0000;
    }
    
    QMenuBar::item:selected {
        background-color: #8B0000;
        color: #FFD700;
    }
    
    QMenu {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 2px solid #8B0000;
    }
    
    QMenu::item:selected {
        background-color: #8B0000;
        color: #FFD700;
    }
    
    QStatusBar {
        background-color: #1a1a1a;
        color: #C0C0C0;
        border-top: 2px solid #8B0000;
    }
    
    QMessageBox {
        background-color: #1a1a1a;
    }
    
    QMessageBox QLabel {
        color: #e0e0e0;
    }
    
    QSplitter::handle {
        background-color: #8B0000;
    }
    
    QSplitter::handle:hover {
        background-color: #DC143C;
    }
    """
    
    widget.setStyleSheet(stylesheet)


def get_crimson_palette():
    """
    Return a QPalette with Crimson theme colors
    
    Returns:
        QPalette: Configured palette
    """
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.ColorRole.Window, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#2d2d2d"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#3d3d3d"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d2d2d"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#8B0000"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFD700"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFD700"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#DC143C"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#8B0000"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFD700"))
    
    return palette
