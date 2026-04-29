import sys
import math
import time
import random
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QSlider, QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QRadialGradient, QPen

class MemoryNode:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.frequency = 0
        self.last_access = time.time()

class MemoryFieldCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 600)
        self.setMouseTracking(True)

        # State variables
        self.context_pos = QPointF(300.0, 300.0)
        self.nodes = []
        self.max_dist = 400.0  # Distance at which similarity drops to 0

        # Weights (controlled by sliders)
        self.sim_weight = 1.0
        self.freq_weight = 0.5
        self.decay_rate = 0.1

        # Initialize random memory fragments
        self.spawn_nodes(50)

        # Real-time update loop (60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    def spawn_nodes(self, count):
        self.nodes = []
        for _ in range(count):
            x = random.uniform(50, 550)
            y = random.uniform(50, 550)
            self.nodes.append(MemoryNode(x, y))

    def mouseMoveEvent(self, event):
        self.context_pos = event.position()

    def mousePressEvent(self, event):
        click_pos = event.position()
        # Find the clicked node to boost its frequency (simulate access/retrieval)
        for node in self.nodes:
            dist = math.dist((click_pos.x(), click_pos.y()), (node.x, node.y))
            if dist < 20:  # Click radius
                node.frequency += 1
                node.last_access = time.time()
                break

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background: Dark sleek biomechanical/cosmic theme
        painter.fillRect(self.rect(), QColor("#0d0f1a"))

        current_time = time.time()

        # Draw memory nodes (Soulstacker fragments)
        for node in self.nodes:
            # 1. Calculate Similarity (Inverse distance proxy)
            dist = math.dist((self.context_pos.x(), self.context_pos.y()), (node.x, node.y))
            similarity = max(0, 1 - (dist / self.max_dist))

            # 2. Time Decay
            time_delta = current_time - node.last_access
            decay_factor = math.exp(-self.decay_rate * time_delta)

            # 3. Frequency Modifier (Logarithmic)
            freq_mod = math.log1p(node.frequency)

            # 4. Total Relevance Score
            relevance = (self.sim_weight * similarity) + (self.freq_weight * freq_mod * decay_factor)

            # Visual mapping based on relevance
            radius = max(3, min(30, 3 + (relevance * 15)))
            opacity = max(40, min(255, int(relevance * 150)))

            # Nebula-hued gradient for memory shards
            grad = QRadialGradient(node.x, node.y, radius)
            grad.setColorAt(0, QColor(0, 255, 255, opacity))       # Cyan core
            grad.setColorAt(1, QColor(138, 43, 226, int(opacity/3))) # Purple edge

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(node.x, node.y), radius, radius)

        # Draw the Context Node (E-Drive Core)
        ctx_radius = 15
        ctx_grad = QRadialGradient(self.context_pos, ctx_radius * 1.5)
        ctx_grad.setColorAt(0, QColor(255, 191, 0, 255))   # Bright Amber/Gold
        ctx_grad.setColorAt(1, QColor(255, 100, 0, 0))     # Fading to transparent

        painter.setBrush(QBrush(ctx_grad))
        painter.drawEllipse(self.context_pos, ctx_radius, ctx_radius)

        # Core center point
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(self.context_pos, 3, 3)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evyra - Soulstacker Memory Field")
        self.resize(900, 650)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left side: Canvas
        self.canvas = MemoryFieldCanvas()
        main_layout.addWidget(self.canvas, stretch=3)

        # Right side: Control Panel
        control_panel = QFrame()
        control_panel.setFixedWidth(250)
        control_panel.setStyleSheet("""
            QFrame { background-color: #16192b; color: #a9b1d6; border-radius: 8px; }
            QLabel { font-weight: bold; font-family: 'Segoe UI', sans-serif; }
            QSlider::groove:horizontal { background: #24283b; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #ffbf00; width: 14px; margin: -3px 0; border-radius: 7px; }
            QPushButton { background-color: #24283b; color: #ffbf00; border: 1px solid #ffbf00;
                          padding: 8px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #ffbf00; color: #0d0f1a; }
        """)
        panel_layout = QVBoxLayout(control_panel)

        title = QLabel("ARCHITECTURE CONTROLS")
        title.setStyleSheet("font-size: 14px; color: #ffbf00; margin-bottom: 10px;")
        panel_layout.addWidget(title)

        # Sliders
        self.sim_slider, self.sim_label = self.create_slider("Similarity Weight (\u03B1)", 0, 300, 100, panel_layout)
        self.freq_slider, self.freq_label = self.create_slider("Frequency Weight (\u03B2)", 0, 300, 50, panel_layout)
        self.decay_slider, self.decay_label = self.create_slider("Time Decay Rate (\u03BB)", 0, 500, 100, panel_layout)

        self.sim_slider.valueChanged.connect(self.update_weights)
        self.freq_slider.valueChanged.connect(self.update_weights)
        self.decay_slider.valueChanged.connect(self.update_weights)

        panel_layout.addStretch()

        # Reset Button
        reset_btn = QPushButton("Purge & Respawn Fragments")
        reset_btn.clicked.connect(lambda: self.canvas.spawn_nodes(50))
        panel_layout.addWidget(reset_btn)

        main_layout.addWidget(control_panel)

    def create_slider(self, text, min_val, max_val, default, layout):
        label = QLabel(f"{text}: {default/100:.2f}")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        layout.addWidget(label)
        layout.addWidget(slider)
        layout.addSpacing(15)
        return slider, label

    def update_weights(self):
        # Update canvas values
        self.canvas.sim_weight = self.sim_slider.value() / 100.0
        self.canvas.freq_weight = self.freq_slider.value() / 100.0
        self.canvas.decay_rate = self.decay_slider.value() / 1000.0

        # Update labels
        self.sim_label.setText(f"Similarity Weight (\u03B1): {self.canvas.sim_weight:.2f}")
        self.freq_label.setText(f"Frequency Weight (\u03B2): {self.canvas.freq_weight:.2f}")
        self.decay_label.setText(f"Time Decay Rate (\u03BB): {self.canvas.decay_rate:.3f}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
