# gui/tools_tab.py
# VERSION: 6.0 - ULTRA COMPACT + Named Bookmaker Presets

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QCheckBox, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from typing import Dict
import json
from config.settings import PATH

class ToolsTab(QWidget):
    """Tools tab - ULTRA COMPACT version with collapsible sections."""

    def __init__(self, config: Dict = None):
        super().__init__()
        self.config = config or {}
        self.coords_manager = CoordsManager()
        self.bookmaker_checkboxes = {}
        self.bookmaker_grid = None
        self.bookmaker_grid_widget = None
        self.all_bookmakers = []

        self._load_bookmakers()
        self.init_ui()
        self.load_last_config()

    def _load_bookmakers(self):
        """Load all bookmakers from config."""
        try:
            with open(PATH.bookmaker_config, "r") as f:
                data = json.load(f)
            bookmakers_set = set()
            for group in data.get("server_groups", []):
                bookmakers_set.update(group.get("bookmakers", []))
            self.all_bookmakers = sorted(list(bookmakers_set))
        except:
            self.all_bookmakers = []

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

        # Settings (COMPACT)
        layout.addWidget(self.create_compact_settings())

        # Tools sections
        layout.addWidget(self.create_region_tools())
        layout.addWidget(self.create_system_tools())
        layout.addWidget(self.create_testing_tools())

        layout.addStretch()

    def create_compact_settings(self) -> QGroupBox:
        """ULTRA COMPACT settings section."""
        group = QGroupBox("⚙️ Settings")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # Row 1: Layout + Position + Dual + Preset selector
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        layouts = self.coords_manager.get_available_layouts()
        if layouts:
            self.layout_combo.addItems(layouts)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        row1.addWidget(self.layout_combo, 1)

        row1.addWidget(QLabel("Pos:"))
        self.position_combo = QComboBox()
        row1.addWidget(self.position_combo, 1)

        self.dual_check = QCheckBox("Dual")
        self.dual_check.setToolTip("Dual monitor (browser on RIGHT)")
        row1.addWidget(self.dual_check)

        row1.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("(select)")
        self.preset_combo.currentTextChanged.connect(self.load_preset)
        row1.addWidget(self.preset_combo, 1)

        layout.addLayout(row1)

        # Row 2: Bookmaker grid (INLINE - no groupbox)
        self.bookmaker_grid_widget = QWidget()
        self.bookmaker_grid = QGridLayout(self.bookmaker_grid_widget)
        self.bookmaker_grid.setSpacing(5)
        self.bookmaker_grid.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.bookmaker_grid_widget)

        # Row 3: Action buttons (small)
        row3 = QHBoxLayout()
        save_btn = QPushButton("💾 Save Preset")
        save_btn.setMaximumWidth(120)
        save_btn.clicked.connect(self.save_preset)
        row3.addWidget(save_btn)

        row3.addStretch()
        layout.addLayout(row3)

        # Initialize
        if self.layout_combo.count() > 0:
            self.on_layout_changed(self.layout_combo.currentText())

        return group

    def on_layout_changed(self, layout: str):
        if not layout:
            return

        # Update positions
        self.position_combo.clear()
        positions = self.coords_manager.get_positions_for_layout(layout)
        if positions:
            self.position_combo.addItems(positions)
        self.position_combo.addItem("ALL")

        # Update grid
        if self.bookmaker_grid is not None:
            self.update_bookmaker_grid()

        # Update presets
        self.update_preset_combo()

    def update_bookmaker_grid(self):
        if self.bookmaker_grid is None:
            return

        while self.bookmaker_grid.count():
            item = self.bookmaker_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.bookmaker_checkboxes.clear()

        layout_name = self.layout_combo.currentText()
        if not layout_name:
            return

        try:
            num_positions = int(layout_name.split("_")[1])
        except:
            num_positions = 6

        rows = 2
        cols = num_positions // 2

        positions = self.coords_manager.get_positions_for_layout(layout_name)
        if not positions:
            positions = [""] * num_positions

        for i in range(num_positions):
            row = i // cols
            col = i % cols

            pos_label = positions[i] if i < len(positions) else f"P{i+1}"

            # Create horizontal layout for label + combo
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(2, 2, 2, 2)
            container_layout.setSpacing(5)

            # Position label
            label = QLabel(f"{pos_label}:")
            label.setStyleSheet("color: #42A5F5; font-weight: bold; font-size: 10pt;")
            label.setMinimumWidth(30)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            container_layout.addWidget(label)

            # Bookmaker combo
            combo = QComboBox()
            combo.setMinimumHeight(28)
            combo.addItem("")
            combo.addItems(self.all_bookmakers)
            container_layout.addWidget(combo, 1)

            self.bookmaker_grid.addWidget(container, row, col)
            self.bookmaker_checkboxes[pos_label] = combo

    def update_preset_combo(self):
        """Update preset dropdown for current layout."""
        layout = self.layout_combo.currentText()
        if not layout:
            return

        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("(select)")

        try:
            with open(PATH.config, "r") as f:
                config = json.load(f)
            
            presets = config.get("bookmaker_presets", {}).get(layout, {})
            for preset_name in presets.keys():
                self.preset_combo.addItem(preset_name)

        except:
            pass

        self.preset_combo.blockSignals(False)

    def load_preset(self, preset_name: str):
        """Load bookmaker preset."""
        if preset_name == "(select)" or not preset_name:
            return

        layout = self.layout_combo.currentText()
        if not layout:
            return

        try:
            with open(PATH.config, "r") as f:
                config = json.load(f)

            preset = config.get("bookmaker_presets", {}).get(layout, {}).get(preset_name)
            if preset:
                for pos, bookmaker in preset.items():
                    if pos in self.bookmaker_checkboxes:
                        combo = self.bookmaker_checkboxes[pos]
                        index = combo.findText(bookmaker)
                        if index >= 0:
                            combo.setCurrentIndex(index)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load preset:\n{e}")

    def save_preset(self):
        """Save bookmaker configuration as named preset."""
        layout = self.layout_combo.currentText()
        if not layout:
            QMessageBox.warning(self, "Error", "Select layout first")
            return

        bookmakers = self.get_selected_bookmakers()
        if not bookmakers:
            QMessageBox.warning(self, "Error", "No bookmakers selected")
            return

        preset_name, ok = QInputDialog.getText(
            self, "Save Preset", "Enter preset name:"
        )

        if not ok or not preset_name:
            return

        try:
            # Load config
            if PATH.config.exists():
                with open(PATH.config, "r") as f:
                    config = json.load(f)
            else:
                config = {}

            # Create structure
            if "bookmaker_presets" not in config:
                config["bookmaker_presets"] = {}
            if layout not in config["bookmaker_presets"]:
                config["bookmaker_presets"][layout] = {}

            # Save preset
            config["bookmaker_presets"][layout][preset_name] = bookmakers

            # Save last used
            config["tools_last"] = {
                "layout": layout,
                "position": self.position_combo.currentText(),
                "dual_monitor": self.dual_check.isChecked(),
                "preset": preset_name,
            }

            # Write
            with open(PATH.config, "w") as f:
                json.dump(config, f, indent=2)

            QMessageBox.information(self, "Success", f"Preset '{preset_name}' saved!")
            self.update_preset_combo()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def load_last_config(self):
        """Load last used config."""
        try:
            with open(PATH.config, "r") as f:
                config = json.load(f)

            last = config.get("tools_last", {})
            if not last:
                return

            # Layout
            if "layout" in last:
                idx = self.layout_combo.findText(last["layout"])
                if idx >= 0:
                    self.layout_combo.setCurrentIndex(idx)

            # Position
            if "position" in last:
                idx = self.position_combo.findText(last["position"])
                if idx >= 0:
                    self.position_combo.setCurrentIndex(idx)

            # Dual
            if "dual_monitor" in last:
                self.dual_check.setChecked(last["dual_monitor"])

            # Preset
            if "preset" in last:
                idx = self.preset_combo.findText(last["preset"])
                if idx >= 0:
                    self.preset_combo.setCurrentIndex(idx)

        except:
            pass

    def get_selected_bookmakers(self) -> Dict[str, str]:
        bookmakers = {}
        for pos, combo in self.bookmaker_checkboxes.items():
            bookmaker = combo.currentText().strip()
            if bookmaker:
                bookmakers[pos] = bookmaker
        return bookmakers

    def get_current_settings(self) -> tuple:
        return (
            self.layout_combo.currentText(),
            self.position_combo.currentText(),
            self.dual_check.isChecked(),
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
        layout, position, dual = self.get_current_settings()
        if not layout or not position or position == "ALL":
            QMessageBox.warning(self, "Error", "Select layout and specific position")
            return
        try:
            from utils.region_editor import RegionEditorDialog
            dialog = RegionEditorDialog(layout, position, dual, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def open_region_visualizer(self):
        layout, position, dual = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Select layout and position")
            return
        try:
            from utils.region_visualizer import RegionVisualizerDialog
            dialog = RegionVisualizerDialog(layout, position, dual, self)
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
        layout, position, dual = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Select layout and position")
            return
        try:
            from tests.ocr_accuracy import OCRTestDialog
            dialog = OCRTestDialog(layout, position, dual, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_speed_benchmark(self):
        layout, position, dual = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Select layout and position")
            return
        try:
            from tests.ocr_performance import SpeedBenchmarkDialog
            dialog = SpeedBenchmarkDialog(layout, position, dual, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_ml_accuracy(self):
        layout, position, dual = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Select layout and position")
            return
        try:
            from tests.ml_phase_accuracy import MLPhaseTestDialog
            dialog = MLPhaseTestDialog(layout, position, dual, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_ml_speed(self):
        layout, position, dual = self.get_current_settings()
        if not layout or not position:
            QMessageBox.warning(self, "Error", "Select layout and position")
            return
        try:
            from tests.ml_phase_performance import MLPhaseSpeedDialog
            dialog = MLPhaseSpeedDialog(layout, position, dual, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))