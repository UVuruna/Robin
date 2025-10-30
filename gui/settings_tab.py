# gui/settings_tab.py
# VERSION: 1.0 - New SETTINGS tab with OCR and Image saving options

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QMessageBox, QInputDialog,
    QCheckBox, QRadioButton, QButtonGroup, QSpinBox, QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from typing import Dict, List
import json
from config.settings import PATH, AVAILABLE_GRIDS
from core.capture.region_manager import RegionManager


class SettingsTab(QWidget):
    """Settings tab - Configuration for OCR, Image saving, and bookmaker setup."""

    # Signal emitted when settings change
    settings_changed = Signal(dict)

    def __init__(self, config: Dict = None):
        super().__init__()
        self.config = config or {}
        self.region_manager = RegionManager()
        self.bookmaker_checkboxes = {}
        self.bookmaker_grid = None
        self.bookmaker_grid_widget = None
        self.all_bookmakers = []
        self.image_save_checkboxes = {}

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

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title = QLabel("⚙️ Application Settings")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # OCR Settings
        layout.addWidget(self.create_ocr_settings())

        # Image Saving Settings
        layout.addWidget(self.create_image_saving_settings())

        # Performance Settings
        layout.addWidget(self.create_performance_settings())

        # Bookmaker Setup (from original tools tab)
        layout.addWidget(self.create_bookmaker_settings())

        # Save button
        save_btn = QPushButton("💾 Save All Settings")
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 12pt; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        save_btn.clicked.connect(self.save_all_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

    def create_ocr_settings(self) -> QGroupBox:
        """Create OCR method selection section."""
        group = QGroupBox("🔍 OCR Settings")
        layout = QVBoxLayout(group)

        desc = QLabel("Select the OCR method for text recognition")
        desc.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(desc)

        # OCR method selection
        self.ocr_button_group = QButtonGroup()

        methods_layout = QHBoxLayout()

        # Tesseract option
        self.tesseract_radio = QRadioButton("Tesseract (Accurate)")
        self.tesseract_radio.setToolTip("Standard OCR - 100ms per read, high accuracy")
        self.tesseract_radio.setChecked(True)
        self.ocr_button_group.addButton(self.tesseract_radio, 0)
        methods_layout.addWidget(self.tesseract_radio)

        # Template option
        self.template_radio = QRadioButton("Template Matching (Fast)")
        self.template_radio.setToolTip("Template-based - 10-15ms per read, requires templates")
        self.ocr_button_group.addButton(self.template_radio, 1)
        methods_layout.addWidget(self.template_radio)

        # CNN option
        self.cnn_radio = QRadioButton("CNN Model (Future)")
        self.cnn_radio.setToolTip("Neural network based - requires trained model")
        self.cnn_radio.setEnabled(False)  # Disabled for now
        self.ocr_button_group.addButton(self.cnn_radio, 2)
        methods_layout.addWidget(self.cnn_radio)

        methods_layout.addStretch()
        layout.addLayout(methods_layout)

        # Status label
        self.ocr_status_label = QLabel("Current: TESSERACT")
        self.ocr_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.ocr_status_label)

        # Connect signals
        self.ocr_button_group.buttonClicked.connect(self.on_ocr_method_changed)

        return group

    def create_image_saving_settings(self) -> QGroupBox:
        """Create image saving settings section."""
        group = QGroupBox("📸 Image Saving (for CNN Training)")
        layout = QVBoxLayout(group)

        desc = QLabel("Select regions to save images for future CNN model training")
        desc.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(desc)

        # Checkbox grid for regions
        grid = QGridLayout()

        regions = [
            ("score", "Score (e.g., 2.35x)"),
            ("my_money", "My Money"),
            ("player_count", "Player Count"),
            ("player_money", "Player Money"),
            ("auto_play", "Auto Play"),
            ("play_amount", "Play Amount")
        ]

        for i, (key, label) in enumerate(regions):
            row = i // 2
            col = i % 2

            checkbox = QCheckBox(label)
            checkbox.setToolTip(f"Save images for {label} region")
            self.image_save_checkboxes[key] = checkbox

            # Default: only score is checked
            if key == "score":
                checkbox.setChecked(True)

            grid.addWidget(checkbox, row, col)

        layout.addLayout(grid)

        # Save path info
        info_label = QLabel(f"Images will be saved to: {PATH.screenshots_dir}")
        info_label.setStyleSheet("color: #666; font-size: 8pt; font-style: italic;")
        layout.addWidget(info_label)

        return group

    def create_performance_settings(self) -> QGroupBox:
        """Create performance settings section."""
        group = QGroupBox("⚡ Performance Settings")
        layout = QVBoxLayout(group)

        desc = QLabel("Configure database query frequency and caching")
        desc.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(desc)

        # Database query frequency
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Database Query Frequency:"))

        self.query_freq_spinbox = QSpinBox()
        self.query_freq_spinbox.setMinimum(5)
        self.query_freq_spinbox.setMaximum(300)
        self.query_freq_spinbox.setValue(30)  # Default 30 seconds
        self.query_freq_spinbox.setSuffix(" seconds")
        self.query_freq_spinbox.setToolTip(
            "How often stats widgets query the database\n"
            "Lower = more updates but higher CPU usage\n"
            "Recommended: 30-60 seconds"
        )
        freq_layout.addWidget(self.query_freq_spinbox)

        # Visual slider for easier adjustment
        self.query_freq_slider = QSlider(Qt.Orientation.Horizontal)
        self.query_freq_slider.setMinimum(5)
        self.query_freq_slider.setMaximum(300)
        self.query_freq_slider.setValue(30)
        self.query_freq_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.query_freq_slider.setTickInterval(30)
        freq_layout.addWidget(self.query_freq_slider)

        # Connect slider and spinbox
        self.query_freq_slider.valueChanged.connect(self.query_freq_spinbox.setValue)
        self.query_freq_spinbox.valueChanged.connect(self.query_freq_slider.setValue)

        layout.addLayout(freq_layout)

        # Explanation labels
        info_layout = QGridLayout()
        info_layout.addWidget(QLabel("5-10 sec:"), 0, 0)
        info_layout.addWidget(QLabel("Real-time (high CPU)"), 0, 1)
        info_layout.addWidget(QLabel("30-60 sec:"), 1, 0)
        info_layout.addWidget(QLabel("Recommended (balanced)"), 1, 1)
        info_layout.addWidget(QLabel("120+ sec:"), 2, 0)
        info_layout.addWidget(QLabel("Low frequency (may miss updates)"), 2, 1)

        # Style the labels
        for i in range(info_layout.rowCount()):
            label = info_layout.itemAtPosition(i, 1).widget()
            label.setStyleSheet("color: gray; font-size: 8pt;")

        layout.addLayout(info_layout)

        # Current status
        self.perf_status_label = QLabel("Current: 30 seconds (Recommended)")
        self.perf_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.perf_status_label)

        # Update status label on change
        self.query_freq_spinbox.valueChanged.connect(self.update_perf_status)

        return group

    def update_perf_status(self, value: int):
        """Update performance status label based on frequency."""
        if value <= 10:
            status = f"Current: {value} seconds (Real-time - High CPU)"
            color = "#FF9800"  # Orange
        elif value <= 60:
            status = f"Current: {value} seconds (Recommended)"
            color = "#4CAF50"  # Green
        else:
            status = f"Current: {value} seconds (Low frequency)"
            color = "#2196F3"  # Blue

        self.perf_status_label.setText(status)
        self.perf_status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def create_bookmaker_settings(self) -> QGroupBox:
        """Create bookmaker configuration section (from original tools tab)."""
        group = QGroupBox("🎰 Bookmaker Configuration")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # Row 1: Layout + Position + Monitor + Preset
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

        # Row 2: Bookmaker grid
        self.bookmaker_grid_widget = QWidget()
        self.bookmaker_grid = QGridLayout(self.bookmaker_grid_widget)
        self.bookmaker_grid.setSpacing(5)
        self.bookmaker_grid.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.bookmaker_grid_widget)

        # Row 3: Preset save button
        row3 = QHBoxLayout()
        save_preset_btn = QPushButton("💾 Save Preset")
        save_preset_btn.setMaximumWidth(120)
        save_preset_btn.clicked.connect(self.save_preset)
        row3.addWidget(save_preset_btn)
        row3.addStretch()
        layout.addLayout(row3)

        # Initialize
        if self.layout_combo.count() > 0:
            self.on_layout_changed(self.layout_combo.currentText())

        return group

    def _populate_monitor_dropdown(self):
        """Populate monitor dropdown with detected monitors."""
        monitors = self.region_manager.get_monitor_setup()

        if len(monitors) == 1:
            # Single monitor
            monitor = list(monitors.values())[0]
            label = f"Primary - {monitor.width}x{monitor.height}"
            self.monitor_combo.addItem(label, userData="primary")
        else:
            # Multiple monitors
            sorted_monitors = sorted(monitors.items(),
                                   key=lambda x: monitors[x[0]].x if x[0] in monitors else 0)

            for i, (key, monitor) in enumerate(sorted_monitors):
                if i == 0:
                    label = f"Monitor {monitor.index} (Left) - {monitor.width}x{monitor.height}"
                    self.monitor_combo.addItem(label, userData="left")
                elif i == len(sorted_monitors) - 1:
                    label = f"Monitor {monitor.index} (Right) - {monitor.width}x{monitor.height}"
                    self.monitor_combo.addItem(label, userData="right")
                else:
                    label = f"Monitor {monitor.index} (Center {i}) - {monitor.width}x{monitor.height}"
                    self.monitor_combo.addItem(label, userData=f"center_{i}")

    def on_layout_changed(self, layout: str):
        if not layout:
            return

        # Update positions
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
            position_list = list(positions.keys())
            position_list.append("ALL")
            return position_list
        except ValueError:
            return []

    def update_bookmaker_grid(self):
        if self.bookmaker_grid is None:
            return

        # Clear existing
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

            # Create container
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
        """Save bookmaker configuration as preset."""
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

            QMessageBox.information(self, "Success", f"Preset '{preset_name}' saved!")
            self.update_preset_combo()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")

    def on_ocr_method_changed(self, button):
        """Handle OCR method change."""
        methods = ["TESSERACT", "TEMPLATE", "CNN"]
        selected = methods[self.ocr_button_group.id(button)]
        self.ocr_status_label.setText(f"Current: {selected}")

        # Update color based on selection
        colors = {
            "TESSERACT": "#4CAF50",
            "TEMPLATE": "#2196F3",
            "CNN": "#9C27B0"
        }
        self.ocr_status_label.setStyleSheet(f"color: {colors[selected]}; font-weight: bold;")

    def get_selected_bookmakers(self) -> Dict[str, str]:
        """Get currently selected bookmakers."""
        bookmakers = {}
        for pos, combo in self.bookmaker_checkboxes.items():
            bookmaker = combo.currentText().strip()
            if bookmaker:
                bookmakers[pos] = bookmaker
        return bookmakers

    def get_current_settings(self) -> tuple:
        """Get current settings (layout, position, monitor)."""
        return (
            self.layout_combo.currentText(),
            self.position_combo.currentText(),
            self.monitor_combo.currentData(),
        )

    def save_all_settings(self):
        """Save all settings to config files."""
        try:
            # Load existing last_setup.json
            if PATH.last_setup.exists():
                with open(PATH.last_setup, "r") as f:
                    config = json.load(f)
            else:
                config = {}

            # Get OCR method
            ocr_methods = ["TESSERACT", "TEMPLATE", "CNN"]
            ocr_method = ocr_methods[self.ocr_button_group.checkedId()]

            # Get image saving settings
            image_saving = {}
            for key, checkbox in self.image_save_checkboxes.items():
                image_saving[key] = checkbox.isChecked()

            # Get performance settings
            database_query_frequency = self.query_freq_spinbox.value()

            # Update config
            config["ocr_method"] = ocr_method
            config["image_saving"] = image_saving
            config["database_query_frequency"] = database_query_frequency

            # Save bookmaker setup
            config["tools_last"] = {
                "layout": self.layout_combo.currentText(),
                "position": self.position_combo.currentText(),
                "target_monitor": self.monitor_combo.currentData(),
                "preset": self.preset_combo.currentText() if self.preset_combo.currentText() != "(select)" else None,
            }

            # Write to file
            with open(PATH.last_setup, "w") as f:
                json.dump(config, f, indent=2)

            # Emit signal with new settings
            self.settings_changed.emit({
                "ocr_method": ocr_method,
                "image_saving": image_saving
            })

            QMessageBox.information(self, "Success", "All settings saved successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{e}")

    def load_last_config(self):
        """Load last saved configuration."""
        try:
            if not PATH.last_setup.exists():
                return

            with open(PATH.last_setup, "r") as f:
                config = json.load(f)

            # Load OCR method
            ocr_method = config.get("ocr_method", "TESSERACT")
            if ocr_method == "TESSERACT":
                self.tesseract_radio.setChecked(True)
            elif ocr_method == "TEMPLATE":
                self.template_radio.setChecked(True)
            elif ocr_method == "CNN":
                self.cnn_radio.setChecked(True)

            # Load image saving settings
            image_saving = config.get("image_saving", {})
            for key, checkbox in self.image_save_checkboxes.items():
                checkbox.setChecked(image_saving.get(key, key == "score"))

            # Load performance settings
            database_query_frequency = config.get("database_query_frequency", 30)
            self.query_freq_spinbox.setValue(database_query_frequency)
            self.query_freq_slider.setValue(database_query_frequency)
            self.update_perf_status(database_query_frequency)

            # Load bookmaker setup
            last = config.get("tools_last", {})
            if last:
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

                # Monitor
                if "target_monitor" in last:
                    target = last["target_monitor"]
                    for i in range(self.monitor_combo.count()):
                        if self.monitor_combo.itemData(i) == target:
                            self.monitor_combo.setCurrentIndex(i)
                            break

                # Preset
                if "preset" in last and last["preset"]:
                    idx = self.preset_combo.findText(last["preset"])
                    if idx >= 0:
                        self.preset_combo.setCurrentIndex(idx)

        except Exception as e:
            print(f"Failed to load config: {e}")