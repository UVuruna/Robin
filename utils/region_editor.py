# utils/region_editor.py
# VERSION: 9.0 - RGB colors from JSON, new config paths

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
from PySide6.QtGui import QFont, QPixmap, QImage, QKeyEvent
import numpy as np
import cv2
import mss
import json
import traceback
from config.settings import PATH

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

    # Region colors are loaded from JSON - NO HARD-CODED COLORS!

    def __init__(self, layout: str, position: str, target_monitor: str, parent=None):
        super().__init__(parent)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        self.layout = layout
        self.position = position
        self.target_monitor = target_monitor

        self.coords_file = PATH.screen_regions
        self.coords = {}
        self.region_colors_rgb = {}  # RGB colors from JSON
        self.current_region_index = 0
        self.shift_pressed = False
        self.ctrl_pressed = False
        self.position_offset = None
        self.preview_padding = 50  # Padding around regions
        # preview_width and preview_height calculated dynamically based on regions

        self.setWindowTitle(f"Region Editor - {layout} @ {position}")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1600, 900)

        try:
            self._load_coords()
            self._get_position_offset()
            self.init_ui()

            self.timer = QTimer()
            self.timer.timeout.connect(self.update_preview)
            self.timer.start(100)  # 10 FPS instead of 20 FPS

            # Force maximized
            self.setWindowState(Qt.WindowState.WindowMaximized)

            self.log("✅ Region Editor initialized")
            self.log(f"Layout: {layout}, Position: {position}")
            self.log(f"Target Monitor: {target_monitor}")

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

            # Load region colors from JSON (RGB format - will convert to BGR for OpenCV)
            if "region_colors" in data and isinstance(data["region_colors"], dict):
                self.region_colors_rgb = data["region_colors"]
            else:
                raise ValueError("region_colors not found in screen_regions.json!")

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
            offsets = manager.calculate_layout_offsets(self.layout, self.target_monitor)

            if self.position not in offsets:
                raise ValueError(
                    f"Position {self.position} not found in layout {self.layout}"
                )

            offset_x, offset_y = offsets[self.position]
            self.position_offset = {"left": offset_x, "top": offset_y}

            # Get cell dimensions dynamically from RegionManager
            self.preview_width, self.preview_height = manager.get_cell_dimensions(
                self.layout, self.target_monitor
            )

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
        self._update_region_label_color(self.REGION_KEYS[0])  # Set initial color from JSON
        left_layout.addWidget(self.current_region_label)

        # LOG SECTION
        log_group = QGroupBox("📋 Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        self.log_text.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; "
            "font-family: Consolas; font-size: 9pt;"
        )
        log_layout.addWidget(self.log_text)
        left_layout.addWidget(log_group, 1)

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

        preview_title = QLabel("📸 Live Preview")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_title.setStyleSheet("font-size: 10pt; font-weight: bold; padding: 2px;")
        preview_title.setMaximumHeight(30)
        right_layout.addWidget(preview_title)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "background-color: #2b2b2b; border: 2px solid #555;"
        )
        self.preview_label.setMinimumSize(600, 400)  # Smaller minimum for cropped view
        right_layout.addWidget(self.preview_label)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

    def create_instructions(self) -> QGroupBox:
        """Create instructions panel."""
        group = QGroupBox("⌨️ Controls")
        layout = QVBoxLayout(group)

        text = """
            <b style="color:#4CAF50;">MOVE:</b> W/A/S/D<br>
            <b style="color:#2196F3;">RESIZE (Increase):</b> Arrow Keys ↑/↓/←/→<br>
            <b style="color:#2196F3;">RESIZE (Decrease):</b> CTRL + Arrow Keys<br>
            <b style="color:#FF9800;">NEXT REGION:</b> M or SPACE<br>
            <b style="color:#FF9800;">PREV REGION:</b> N or SHIFT+SPACE<br>
            <b style="color:#F44336;">FAST MODE:</b> SHIFT + key = 10 pixel steps
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

    def _calculate_preview_bounds(self):
        """Calculate bounding box for all regions + padding."""
        # Find min/max coordinates across all regions
        min_x = min_y = float('inf')
        max_x = max_y = 0

        for region_name, coords in self.coords.items():
            if region_name not in self.REGION_KEYS:
                continue

            x1 = coords["left"]
            y1 = coords["top"]
            x2 = x1 + coords["width"]
            y2 = y1 + coords["height"]

            min_x = min(min_x, x1)
            min_y = min(min_y, y1)
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)

        # Add padding
        min_x = max(0, min_x - self.preview_padding)
        min_y = max(0, min_y - self.preview_padding)
        max_x = max_x + self.preview_padding
        max_y = max_y + self.preview_padding

        return int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y)

    def update_preview(self):
        """Update live preview - displays RELATIVE coords."""
        try:
            if not self.position_offset:
                return

            # Calculate dynamic preview bounds based on regions
            crop_x, crop_y, crop_width, crop_height = self._calculate_preview_bounds()

            # position_offset already contains ABSOLUTE coordinates from RegionManager
            left = self.position_offset["left"] + crop_x
            top = self.position_offset["top"] + crop_y

            monitor = {
                "left": left,
                "top": top,
                "width": crop_width,
                "height": crop_height,
            }

            # Use context manager for reliable screenshot
            with mss.mss() as sct:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Draw regions - RELATIVE coordinates adjusted for crop
            current_name = self.REGION_KEYS[self.current_region_index]

            for region_name, coords in self.coords.items():
                if region_name not in self.REGION_KEYS:
                    continue

                # Adjust coordinates relative to cropped image
                x1 = coords["left"] - crop_x
                y1 = coords["top"] - crop_y
                x2 = x1 + coords["width"]
                y2 = y1 + coords["height"]

                # Get RGB color from JSON and convert to BGR for OpenCV
                rgb = self.region_colors_rgb.get(region_name, [255, 255, 255])
                bgr = (rgb[2], rgb[1], rgb[0])  # RGB → BGR for cv2.rectangle()
                thickness = 5 if region_name == current_name else 2

                cv2.rectangle(img, (x1, y1), (x2, y2), bgr, thickness)

                # Draw cross at center
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                cross_size = 8

                cv2.line(
                    img,
                    (center_x - cross_size, center_y),
                    (center_x + cross_size, center_y),
                    bgr,
                    2,
                )
                cv2.line(
                    img,
                    (center_x, center_y - cross_size),
                    (center_x, center_y + cross_size),
                    bgr,
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
                    bgr,  # Use bgr variable defined above
                    1,
                    cv2.LINE_AA,
                )

            # Convert to QPixmap
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = 3 * w
            q_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

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
        
        elif key == Qt.Key.Key_Control:
            self.ctrl_pressed = True
            return

        step = 10 if self.shift_pressed else 1
        size = step * -1 if self.ctrl_pressed else step
        current_name = self.REGION_KEYS[self.current_region_index]
        coords = self.coords[current_name]

        changed = False

        # MOVE: W/A/S/D or Arrow Keys
        if key == Qt.Key.Key_W:
            coords["top"] -= step
            changed = True
        elif key == Qt.Key.Key_S:
            coords["top"] += step
            changed = True
        elif key == Qt.Key.Key_A:
            coords["left"] -= step
            changed = True
        elif key == Qt.Key.Key_D:
            coords["left"] += step
            changed = True

        # RESIZE: I/K/J/L
        elif key == Qt.Key.Key_Up:
            coords["height"] = max(10, coords["height"] + size)
            coords["top"] -= size
            changed = True
        elif key == Qt.Key.Key_Down:
            coords["height"] = max(10, coords["height"] + size)
            changed = True
        elif key == Qt.Key.Key_Left:
            coords["width"] = max(10, coords["width"] + size)
            coords["left"] -= size
            changed = True
        elif key == Qt.Key.Key_Right:
            coords["width"] = max(10, coords["width"] + size)
            changed = True

        # NEXT: M or Tab
        elif key in (Qt.Key.Key_M, Qt.Key.Key_Space):
            self.current_region_index = (self.current_region_index + 1) % len(
                self.REGION_KEYS
            )
            self.update_current_region_display()

        # PREV: N or Alt+Tab (Shift+Tab in practice)
        elif key == Qt.Key.Key_N or (
            key == Qt.Key.Key_Space and self.shift_pressed
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
        
        elif event.key() == Qt.Key.Key_Control:
            self.ctrl_pressed = False

    def _update_region_label_color(self, region_name: str):
        """Update label color dynamically from JSON region_colors (RGB format)."""
        if region_name not in self.region_colors_rgb:
            # Fallback to default green if color not found
            hex_color = "#FFFFFF"
        else:
            # Convert RGB list to hex #RRGGBB
            rgb = self.region_colors_rgb[region_name]
            hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        # Update label stylesheet with dynamic color
        self.current_region_label.setStyleSheet(
            f"color: black; background-color: {hex_color}; "
            "font-weight: bold; font-size: 11pt; padding: 8px; border-radius: 4px;"
        )

    def update_current_region_display(self):
        current = self.REGION_KEYS[self.current_region_index]
        self.current_region_label.setText(f"Current: {current}")
        self._update_region_label_color(current)  # Update color from JSON
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
        if hasattr(self, "sct") and self.sct:
            self.sct.close()
        event.accept()


if __name__ == "__main__":
    """Console mode execution."""
    print("=" * 70)
    print("REGION EDITOR - Console Mode")
    print("=" * 70)

    layout = input("Enter layout (layout_4/layout_6/layout_8): ").strip()
    position = input("Enter position (TL/TR/BL/BR/TC/BC/etc): ").strip()
    target_monitor = input("Target monitor (primary/left/right/center_1): ").strip() or "primary"

    app = QApplication(sys.argv)
    dialog = RegionEditorDialog(layout, position, target_monitor)
    sys.exit(dialog.exec())
