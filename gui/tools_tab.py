# gui/tools_tab.py
# VERSION: 7.0 - Refactored to use RegionManager (v4.0 architecture)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from typing import Dict, List
import json
from config.settings import PATH, AVAILABLE_GRIDS
from core.capture.region_manager import RegionManager

class ToolsTab(QWidget):
    """Tools tab - ULTRA COMPACT version with collapsible sections."""

    def __init__(self, config: Dict = None):
        super().__init__()
        self.config = config or {}
        self.region_manager = RegionManager()
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
            with open(PATH.bookmakers, "r") as f:
                data = json.load(f)
            bookmakers_set = set()
            for group in data.get("server_groups", []):
                bookmakers_set.update(group.get("bookmakers", []))
            self.all_bookmakers = sorted(list(bookmakers_set))
        except:
            self.all_bookmakers = []

    def _populate_monitor_dropdown(self):
        """Populate monitor dropdown with detected monitors."""
        monitors = self.region_manager.get_monitor_setup()

        if len(monitors) == 1:
            # Single monitor
            monitor = list(monitors.values())[0]
            label = f"Primary - {monitor.width}x{monitor.height}"
            self.monitor_combo.addItem(label, userData="primary")
        else:
            # Multiple monitors - format as requested
            sorted_monitors = sorted(monitors.items(), key=lambda x: monitors[x[0]].x if x[0] in monitors else 0)

            for i, (key, monitor) in enumerate(sorted_monitors):
                if i == 0:
                    # First monitor (leftmost)
                    label = f"Monitor {monitor.index} (Left) - {monitor.width}x{monitor.height}"
                    self.monitor_combo.addItem(label, userData="left")
                elif i == len(sorted_monitors) - 1:
                    # Last monitor (rightmost)
                    label = f"Monitor {monitor.index} (Right) - {monitor.width}x{monitor.height}"
                    self.monitor_combo.addItem(label, userData="right")
                else:
                    # Middle monitors
                    label = f"Monitor {monitor.index} (Center {i}) - {monitor.width}x{monitor.height}"
                    self.monitor_combo.addItem(label, userData=f"center_{i}")

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
        self.layout_combo.addItems(AVAILABLE_GRIDS)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        row1.addWidget(self.layout_combo, 1)

        row1.addWidget(QLabel("Pos:"))
        self.position_combo = QComboBox()
        row1.addWidget(self.position_combo, 1)

        row1.addWidget(QLabel("Monitor:"))
        self.monitor_combo = QComboBox()
        self._populate_monitor_dropdown()
        row1.addWidget(self.monitor_combo, 1)

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

        # Update positions based on layout
        self.position_combo.clear()
        positions = self._get_positions_for_layout(layout)
        if positions:
            self.position_combo.addItems(positions)

        # Update grid
        if self.bookmaker_grid is not None:
            self.update_bookmaker_grid()

        # Update presets
        self.update_preset_combo()

    def _get_positions_for_layout(self, layout: str) -> List[str]:
        """Get position names for a given layout."""
        try:
            positions = self.region_manager.generate_position_names(layout)
            # Add "ALL" option for visualizer
            position_list = list(positions.keys())
            position_list.append("ALL")
            return position_list
        except ValueError:
            return []

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
            _, cols = self.region_manager.parse_grid_format(layout_name)
        except ValueError:
            return

        # Get positions (without "ALL")
        all_positions = self._get_positions_for_layout(layout_name)
        positions = [p for p in all_positions if p != "ALL"]

        for i, pos_label in enumerate(positions):
            row = i // cols
            col = i % cols

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
            with open(PATH.bookmaker_presets, "r") as f:
                config = json.load(f)
            
            presets = config.get(layout, {})
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
            with open(PATH.bookmaker_presets, "r") as f:
                config = json.load(f)

            preset = config.get(layout, {}).get(preset_name)
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
            # Load presets
            if PATH.bookmaker_presets.exists():
                with open(PATH.bookmaker_presets, "r") as f:
                    presets = json.load(f)
            else:
                presets = {}

            # Create layout structure if needed
            if layout not in presets:
                presets[layout] = {}

            # Save preset
            presets[layout][preset_name] = bookmakers

            # Write presets
            with open(PATH.bookmaker_presets, "w") as f:
                json.dump(presets, f, indent=2)

            # Save tools_last to last_setup.json
            if PATH.last_setup.exists():
                with open(PATH.last_setup, "r") as f:
                    last_setup = json.load(f)
            else:
                last_setup = {}

            last_setup["tools_last"] = {
                "layout": layout,
                "position": self.position_combo.currentText(),
                "target_monitor": self.monitor_combo.currentData(),
                "preset": preset_name,
            }

            with open(PATH.last_setup, "w") as f:
                json.dump(last_setup, f, indent=2)

            QMessageBox.information(self, "Success", f"Preset '{preset_name}' saved!")
            self.update_preset_combo()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def load_last_config(self):
        """Load last used config."""
        try:
            # Load from last_setup.json, not bookmaker_presets.json
            if not PATH.last_setup.exists():
                return

            with open(PATH.last_setup, "r") as f:
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

            # Monitor (with backward compatibility)
            if "target_monitor" in last:
                target = last["target_monitor"]
                # Find dropdown item by userData
                for i in range(self.monitor_combo.count()):
                    if self.monitor_combo.itemData(i) == target:
                        self.monitor_combo.setCurrentIndex(i)
                        break
            elif "dual_monitor" in last:
                # Backward compatibility: dual_monitor=True → "right", False → "primary"
                target = "right" if last["dual_monitor"] else "primary"
                for i in range(self.monitor_combo.count()):
                    if self.monitor_combo.itemData(i) == target:
                        self.monitor_combo.setCurrentIndex(i)
                        break

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
        """Get current settings (layout, position, target_monitor)."""
        return (
            self.layout_combo.currentText(),
            self.position_combo.currentText(),
            self.monitor_combo.currentData(),  # Returns userData (e.g., "right", "left", "primary")
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