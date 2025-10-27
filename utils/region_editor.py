# utils/region_editor.py
# VERSION: 8.0 - Improved keys + arrows + better navigation

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QGroupBox,
    QWidget,
    QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap, QImage, QKeyEvent, QWheelEvent
import numpy as np
import cv2
import mss
import json
import traceback

class RegionEditorDialog(QDialog):
    """Region Editor - saves RELATIVE coordinates."""

    REGION_KEYS = [
        "score_region_small",
        "score_region_medium",
        "score_region_large",
        "my_money_region",
        "other_count_region",
        "other_money_region",
        "phase_region",
        "play_amount_coords_1",
        "play_button_coords_1",
        "auto_play_coords_1",
        "play_amount_coords_2",
        "play_button_coords_2",
        "auto_play_coords_2",
    ]

    REGION_COLORS = {
        "score_region_small": (0, 255, 0),
        "score_region_medium": (0, 255, 255),
        "score_region_large": (0, 128, 255),
        "my_money_region": (255, 0, 0),
        "other_count_region": (255, 0, 255),
        "other_money_region": (255, 255, 0),
        "phase_region": (128, 0, 128),
        "play_amount_coords_1": (0, 0, 255),
        "play_button_coords_1": (255, 128, 0),
        "auto_play_coords_1": (128, 255, 0),
        "play_amount_coords_2": (0, 128, 128),
        "play_button_coords_2": (128, 128, 255),
        "auto_play_coords_2": (255, 255, 128),
    }

    def __init__(self, layout: str, position: str, dual_monitor: bool, parent=None):
        super().__init__(parent)

        self.layout = layout
        self.position = position
        self.dual_monitor = dual_monitor
        self.screen_offset = 3840 if dual_monitor else 0

        self.coords_file = Path("data/json/screen_regions.json")
        self.coords = {}
        self.current_region_index = 0
        self.shift_pressed = False
        self.sct = None
        self.position_offset = None
        self.preview_width = 1280
        self.preview_height = 1044
        self.zoom_level = 1.0

        self.setWindowTitle(f"Region Editor - {layout} @ {position}")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1600, 900)

        try:
            self._load_coords()
            self._get_position_offset()
            self.sct = mss.mss()
            self.init_ui()

            self.timer = QTimer()
            self.timer.timeout.connect(self.update_preview)
            self.timer.start(50)

            # Force maximized
            self.setWindowState(Qt.WindowState.WindowMaximized)

            self.log("✅ Region Editor initialized")
            self.log(f"Layout: {layout}, Position: {position}")
            self.log(f"Dual Monitor: {dual_monitor}")

        except Exception as e:
            error_msg = f"Initialization error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            self.reject()

    def _load_coords(self):
        """Load RELATIVE coordinates from file."""
        try:
            if not self.coords_file.exists():
                default_data = {
                    "layouts": {},
                    "regions": {
                        key: {"left": 100, "top": 100, "width": 200, "height": 100}
                        for key in self.REGION_KEYS
                    },
                }
                self.coords_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.coords_file, "w") as f:
                    json.dump(default_data, f, indent=2)

            with open(self.coords_file, "r") as f:
                data = json.load(f)

            if "regions" in data and isinstance(data["regions"], dict):
                self.coords = data["regions"]
            else:
                self.coords = {
                    key: {"left": 100, "top": 100, "width": 200, "height": 100}
                    for key in self.REGION_KEYS
                }

            for key in self.REGION_KEYS:
                if key not in self.coords:
                    self.coords[key] = {
                        "left": 100,
                        "top": 100,
                        "width": 200,
                        "height": 100,
                    }

        except Exception as e:
            print(f"Error loading coords: {e}")
            self.coords = {
                key: {"left": 100, "top": 100, "width": 200, "height": 100}
                for key in self.REGION_KEYS
            }

    def _get_position_offset(self):
        """Get position offset from RegionManager."""
        try:
            from core.capture.region_manager import RegionManager

            manager = RegionManager()
            monitor_name = "right" if self.dual_monitor else "primary"
            offsets = manager.calculate_layout_offsets(self.layout, monitor_name)

            if self.position not in offsets:
                raise ValueError(
                    f"Position {self.position} not found in layout {self.layout}"
                )

            offset_x, offset_y = offsets[self.position]
            self.position_offset = {"left": offset_x, "top": offset_y}

            if "layout_4" in self.layout:
                self.preview_width, self.preview_height = 1920, 1044
            elif "layout_6" in self.layout:
                self.preview_width, self.preview_height = 1280, 1044
            elif "layout_8" in self.layout:
                self.preview_width, self.preview_height = 960, 1044
            else:
                self.preview_width, self.preview_height = 1280, 1044

        except Exception as e:
            error_msg = f"Failed to get position offset: {e}"
            print(error_msg)
            raise ValueError(error_msg)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # LEFT PANEL
        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        title = QLabel(f"🎨 Region Editor\n{self.layout} @ {self.position}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #2196F3; padding: 10px;")
        left_layout.addWidget(title)

        instructions = self.create_instructions()
        left_layout.addWidget(instructions)

        self.current_region_label = QLabel(f"Current: {self.REGION_KEYS[0]}")
        self.current_region_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_region_label.setStyleSheet(
            "color: white; background-color: #4CAF50; "
            "font-weight: bold; font-size: 11pt; padding: 8px; border-radius: 4px;"
        )
        left_layout.addWidget(self.current_region_label)

        log_group = QGroupBox("📋 Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; "
            "font-family: Consolas; font-size: 9pt;"
        )
        log_layout.addWidget(self.log_text)
        left_layout.addWidget(log_group)

        self.save_close_btn = QPushButton("💾 Save and Close")
        self.save_close_btn.setMinimumHeight(45)
        self.save_close_btn.clicked.connect(self.save_and_close)
        self.save_close_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; font-size: 11pt; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        left_layout.addWidget(self.save_close_btn)

        self.quit_btn = QPushButton("🚫 Quit without Saving")
        self.quit_btn.setMinimumHeight(45)
        self.quit_btn.clicked.connect(self.reject)
        self.quit_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; "
            "font-weight: bold; font-size: 11pt; border-radius: 4px; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        left_layout.addWidget(self.quit_btn)

        left_layout.addStretch()

        # RIGHT PANEL
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_title = QLabel("📸 Live Preview (Scroll to Zoom, Middle Click to Fit)")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_title.setStyleSheet("font-size: 11pt; font-weight: bold; padding: 5px;")
        right_layout.addWidget(preview_title)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "background-color: #2b2b2b; border: 2px solid #555;"
        )
        self.preview_label.setMinimumSize(800, 600)
        right_layout.addWidget(self.preview_label)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

    def create_instructions(self) -> QGroupBox:
        """Create instructions panel."""
        group = QGroupBox("⌨️ Controls")
        layout = QVBoxLayout(group)

        text = """
<b style="color:#4CAF50;">MOVE:</b> W/A/S/D or Arrow Keys<br>
<b style="color:#2196F3;">RESIZE:</b> I/K (height), J/L (width)<br>
<b style="color:#FF9800;">NEXT:</b> M or Tab<br>
<b style="color:#FF9800;">PREV:</b> N or Alt+Tab<br>
<b style="color:#F44336;">SHIFT:</b> + key = 10px steps<br>
<b style="color:#9C27B0;">ZOOM:</b> Mouse Scroll Up/Down<br>
<b style="color:#9C27B0;">FIT:</b> Middle Mouse Button
        """

        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet("padding: 10px; font-size: 10pt;")
        layout.addWidget(label)

        return group

    def log(self, message: str):
        """Add message to log."""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zoom, middle button for fit."""
        if event.buttons() == Qt.MouseButton.MiddleButton:
            self.fit_to_screen()
        else:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_level = min(self.zoom_level * 1.2, 5.0)
            elif delta < 0:
                self.zoom_level = max(self.zoom_level / 1.2, 0.1)

    def fit_to_screen(self):
        """Fit preview to screen."""
        self.zoom_level = 1.0

    def update_preview(self):
        """Update live preview - displays RELATIVE coords."""
        try:
            if not self.position_offset:
                return

            # Calculate ABSOLUTE screen position
            left = self.position_offset["left"] + self.screen_offset
            top = self.position_offset["top"]

            monitor = {
                "left": left,
                "top": top,
                "width": self.preview_width,
                "height": self.preview_height,
            }

            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Draw regions - RELATIVE coordinates
            current_name = self.REGION_KEYS[self.current_region_index]

            for region_name, coords in self.coords.items():
                if region_name not in self.REGION_KEYS:
                    continue

                x1, y1 = coords["left"], coords["top"]
                x2 = x1 + coords["width"]
                y2 = y1 + coords["height"]

                color = self.REGION_COLORS.get(region_name, (255, 255, 255))
                thickness = 5 if region_name == current_name else 2

                cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

                # Draw cross at center
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                cross_size = 8

                cv2.line(
                    img,
                    (center_x - cross_size, center_y),
                    (center_x + cross_size, center_y),
                    color,
                    2,
                )
                cv2.line(
                    img,
                    (center_x, center_y - cross_size),
                    (center_x, center_y + cross_size),
                    color,
                    2,
                )

                label = region_name
                if region_name == current_name:
                    label += " [SELECTED]"

                cv2.putText(
                    img,
                    label,
                    (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    cv2.LINE_AA,
                )

            # Apply zoom
            if self.zoom_level != 1.0:
                new_width = int(img.shape[1] * self.zoom_level)
                new_height = int(img.shape[0] * self.zoom_level)
                img = cv2.resize(
                    img, (new_width, new_height), interpolation=cv2.INTER_LINEAR
                )

            # Convert to QPixmap
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = 3 * w
            q_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

            label_size = self.preview_label.size()
            pixmap = QPixmap.fromImage(q_image).scaled(
                label_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.preview_label.setPixmap(pixmap)

        except Exception as e:
            if not hasattr(self, "_preview_error_shown"):
                self._preview_error_shown = True
                print(f"Preview error: {e}")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard input - IMPROVED KEYS."""
        key = event.key()

        if key == Qt.Key.Key_Shift:
            self.shift_pressed = True
            return

        step = 10 if self.shift_pressed else 1
        current_name = self.REGION_KEYS[self.current_region_index]
        coords = self.coords[current_name]

        changed = False

        # MOVE: W/A/S/D or Arrow Keys
        if key in (Qt.Key.Key_W, Qt.Key.Key_Up):
            coords["top"] -= step
            changed = True
        elif key in (Qt.Key.Key_S, Qt.Key.Key_Down):
            coords["top"] += step
            changed = True
        elif key in (Qt.Key.Key_A, Qt.Key.Key_Left):
            coords["left"] -= step
            changed = True
        elif key in (Qt.Key.Key_D, Qt.Key.Key_Right):
            coords["left"] += step
            changed = True

        # RESIZE: I/K/J/L
        elif key == Qt.Key.Key_I:
            coords["height"] = max(10, coords["height"] - step)
            changed = True
        elif key == Qt.Key.Key_K:
            coords["height"] += step
            changed = True
        elif key == Qt.Key.Key_J:
            coords["width"] = max(10, coords["width"] - step)
            changed = True
        elif key == Qt.Key.Key_L:
            coords["width"] += step
            changed = True

        # NEXT: M or Tab
        elif key in (Qt.Key.Key_M, Qt.Key.Key_Tab):
            self.current_region_index = (self.current_region_index + 1) % len(
                self.REGION_KEYS
            )
            self.update_current_region_display()

        # PREV: N or Alt+Tab (Shift+Tab in practice)
        elif key == Qt.Key.Key_N or (
            key == Qt.Key.Key_Tab
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.current_region_index = (self.current_region_index - 1) % len(
                self.REGION_KEYS
            )
            self.update_current_region_display()

        if changed:
            self.log(
                f"{current_name}: L={coords['left']} T={coords['top']} "
                f"W={coords['width']} H={coords['height']}"
            )

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Shift:
            self.shift_pressed = False

    def update_current_region_display(self):
        current = self.REGION_KEYS[self.current_region_index]
        self.current_region_label.setText(f"Current: {current}")
        self.log(f"→ Switched to: {current}")

    def save_and_close(self):
        """Save RELATIVE coordinates to file."""
        try:
            with open(self.coords_file, "r") as f:
                all_data = json.load(f)

            if "regions" not in all_data:
                all_data["regions"] = {}

            # Save RELATIVE coordinates directly
            all_data["regions"] = self.coords

            with open(self.coords_file, "w") as f:
                json.dump(all_data, f, indent=2)

            self.log("✅ SAVED RELATIVE COORDINATES!")
            QMessageBox.information(self, "Success", "Regions saved successfully!")
            self.accept()

        except Exception as e:
            error_msg = f"Save error: {e}"
            self.log(f"❌ {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)

    def closeEvent(self, event):
        if hasattr(self, "timer"):
            self.timer.stop()
        if self.sct:
            self.sct.close()
        event.accept()


if __name__ == "__main__":
    """Console mode execution."""
    print("=" * 70)
    print("REGION EDITOR - Console Mode")
    print("=" * 70)

    layout = input("Enter layout (layout_4/layout_6/layout_8): ").strip()
    position = input("Enter position (TL/TR/BL/BR/TC/BC/etc): ").strip()
    dual_str = input("Dual monitor? (y/n): ").strip().lower()
    dual_monitor = dual_str == "y"

    app = QApplication(sys.argv)
    dialog = RegionEditorDialog(layout, position, dual_monitor)
    sys.exit(dialog.exec())
