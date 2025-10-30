# gui/tools_tab.py
# VERSION: 8.1 - Fixed initialization order bug
# CHANGES: load_current_settings() now called before init_ui() to prevent AttributeError

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from typing import Dict
import json
from config.settings import PATH
from core.capture.region_manager import RegionManager

class ToolsTab(QWidget):
    """Tools tab - Utils and testing tools only."""

    def __init__(self, config: Dict = None):
        super().__init__()
        self.config = config or {}
        self.region_manager = RegionManager()

        # For tools that need current settings
        self.layout_combo = None
        self.position_combo = None
        self.monitor_combo = None

        self.load_current_settings()
        self.init_ui()

    def load_current_settings(self):
        """Load current settings from last_setup.json for tools to use."""
        try:
            if not PATH.last_setup.exists():
                return

            with open(PATH.last_setup, "r") as f:
                config = json.load(f)

            # Store settings for tools to use
            last = config.get("tools_last", {})
            if last:
                self.current_layout = last.get("layout", "GRID 2×3")
                self.current_position = last.get("position", "Top-Left")
                self.current_monitor = last.get("target_monitor", "primary")
            else:
                # Defaults
                self.current_layout = "GRID 2×3"
                self.current_position = "Top-Left"
                self.current_monitor = "primary"
        except:
            # Defaults on error
            self.current_layout = "GRID 2×3"
            self.current_position = "Top-Left"
            self.current_monitor = "primary"

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title = QLabel("🛠️ Development & Testing Tools")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Info about current settings
        info_group = QGroupBox("📍 Current Configuration")
        info_layout = QVBoxLayout(info_group)

        info_text = QLabel(
            f"Layout: {self.current_layout}\n"
            f"Position: {self.current_position}\n"
            f"Monitor: {self.current_monitor}"
        )
        info_text.setStyleSheet("color: #42A5F5; font-weight: bold;")
        info_layout.addWidget(info_text)

        note = QLabel("(Configure in Settings tab)")
        note.setStyleSheet("color: gray; font-size: 9pt; font-style: italic;")
        info_layout.addWidget(note)

        layout.addWidget(info_group)

        # Tools sections
        layout.addWidget(self.create_region_tools())
        layout.addWidget(self.create_system_tools())
        layout.addWidget(self.create_testing_tools())

        layout.addStretch()

    def get_current_settings(self) -> tuple:
        """Get current settings from loaded configuration."""
        return (
            self.current_layout,
            self.current_position,
            self.current_monitor,
        )

    def create_region_tools(self) -> QGroupBox:
        group = QGroupBox("📐 Region Tools")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        desc = QLabel("Configure and verify screen regions for tracking")
        desc.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()

        btn1 = QPushButton("🎨 Region Editor")
        btn1.setMinimumHeight(35)
        btn1.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        btn1.clicked.connect(self.open_region_editor)
        btn_layout.addWidget(btn1)

        btn2 = QPushButton("📸 Visualizer")
        btn2.setMinimumHeight(35)
        btn2.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        btn2.clicked.connect(self.open_region_visualizer)
        btn_layout.addWidget(btn2)

        layout.addLayout(btn_layout)
        return group

    def create_system_tools(self) -> QGroupBox:
        group = QGroupBox("🔧 Diagnostics")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        desc = QLabel("Run system checks before production runs")
        desc.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()

        btn1 = QPushButton("🏥 Full Diagnostic")
        btn1.setMinimumHeight(35)
        btn1.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )
        btn1.clicked.connect(self.run_full_diagnostic)
        btn_layout.addWidget(btn1)

        btn2 = QPushButton("⚡ Quick Check")
        btn2.setMinimumHeight(35)
        btn2.setStyleSheet(
            "QPushButton { background-color: #FFC107; color: black; font-weight: bold; }"
            "QPushButton:hover { background-color: #FFB300; }"
        )
        btn2.clicked.connect(self.run_quick_check)
        btn_layout.addWidget(btn2)

        layout.addLayout(btn_layout)
        return group

    def create_testing_tools(self) -> QGroupBox:
        group = QGroupBox("🧪 Testing Tools")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        desc = QLabel("Test OCR and ML model accuracy and performance")
        desc.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(desc)

        # OCR Tests
        ocr_label = QLabel("OCR Tests:")
        ocr_label.setStyleSheet("font-weight: bold; color: #9C27B0;")
        layout.addWidget(ocr_label)

        row1 = QHBoxLayout()
        btn1 = QPushButton("🔍 OCR Accuracy")
        btn1.setMinimumHeight(35)
        btn1.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #7B1FA2; }"
        )
        btn1.clicked.connect(self.run_ocr_test)
        row1.addWidget(btn1)

        btn2 = QPushButton("🔥 OCR Speed")
        btn2.setMinimumHeight(35)
        btn2.setStyleSheet(
            "QPushButton { background-color: #E91E63; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #C2185B; }"
        )
        btn2.clicked.connect(self.run_speed_benchmark)
        row1.addWidget(btn2)
        layout.addLayout(row1)

        # ML Tests
        ml_label = QLabel("ML Phase Tests:")
        ml_label.setStyleSheet("font-weight: bold; color: #00BCD4; margin-top: 5px;")
        layout.addWidget(ml_label)

        row2 = QHBoxLayout()
        btn3 = QPushButton("🤖 ML Accuracy")
        btn3.setMinimumHeight(35)
        btn3.setStyleSheet(
            "QPushButton { background-color: #00BCD4; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #0097A7; }"
        )
        btn3.clicked.connect(self.run_ml_accuracy)
        row2.addWidget(btn3)

        btn4 = QPushButton("🚀 ML Speed")
        btn4.setMinimumHeight(35)
        btn4.setStyleSheet(
            "QPushButton { background-color: #009688; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #00796B; }"
        )
        btn4.clicked.connect(self.run_ml_speed)
        row2.addWidget(btn4)
        layout.addLayout(row2)

        return group

    # Tool openers
    def open_region_editor(self):
        layout, position, target_monitor = self.get_current_settings()
        if not layout or not position or position == "ALL":
            QMessageBox.warning(self, "Error", "Select layout and specific position")
            return
        try:
            from utils.region_editor import RegionEditorDialog
            dialog = RegionEditorDialog(layout, position, target_monitor, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def open_region_visualizer(self):
        layout, position, target_monitor = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Select layout and position")
            return
        try:
            from utils.region_visualizer import RegionVisualizerDialog
            dialog = RegionVisualizerDialog(layout, position, target_monitor, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_full_diagnostic(self):
        try:
            from utils.diagnostic import DiagnosticDialog
            dialog = DiagnosticDialog(quick=False, parent=self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_quick_check(self):
        try:
            from utils.diagnostic import DiagnosticDialog
            dialog = DiagnosticDialog(quick=True, parent=self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_ocr_test(self):
        layout, position, target_monitor = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Configure settings first")
            return
        try:
            from tests.ocr_accuracy import OCRTestDialog
            dialog = OCRTestDialog(layout, position, target_monitor, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_speed_benchmark(self):
        layout, position, target_monitor = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Configure settings first")
            return
        try:
            from tests.ocr_performance import SpeedBenchmarkDialog
            dialog = SpeedBenchmarkDialog(layout, position, target_monitor, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_ml_accuracy(self):
        layout, position, target_monitor = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Configure settings first")
            return
        try:
            from tests.ml_phase_accuracy import MLPhaseTestDialog
            dialog = MLPhaseTestDialog(layout, position, target_monitor, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_ml_speed(self):
        layout, position, target_monitor = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Configure settings first")
            return
        try:
            from tests.ml_phase_performance import MLPhaseSpeedDialog
            dialog = MLPhaseSpeedDialog(layout, position, target_monitor, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))