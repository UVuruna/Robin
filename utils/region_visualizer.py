# utils/region_visualizer.py
# VERSION: 10.0 - Refactored to use RegionManager (v4.0 architecture)
# IMPROVEMENTS:
# - Uses RegionManager for coordinate calculation
# - Reads colors from screen_regions.json (same as editor)
# - Middle button works via mousePressEvent
# - Space key as fallback for fit
# - Color legend matches actual colors

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QGroupBox,
    QFileDialog,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QWheelEvent, QMouseEvent
import numpy as np
import cv2
import mss
from datetime import datetime
import json
from core.capture.region_manager import RegionManager

class RegionVisualizerDialog(QDialog):
    """Region Visualizer v10.0 - uses RegionManager."""

    def __init__(self, layout: str, position: str, dual_monitor: bool, parent=None):
        super().__init__(parent)

        self.layout = layout
        self.position = position
        self.dual_monitor = dual_monitor
        self.region_manager = RegionManager()
        self.region_colors = {}

        self.current_image = None
        self.zoom_level = 1.0
        self.filepath = None

        self.setWindowTitle(f"Region Visualizer v9.0 - {layout} @ {position}")
        self.setMinimumSize(1200, 800)
        self.setWindowFlags(Qt.WindowType.Window)

        self._load_colors()
        self.init_ui()
        self.capture_screenshot()

        self.setWindowState(Qt.WindowState.WindowMaximized)

    def _load_colors(self):
        """Load colors from screen_regions.json."""
        try:
            coords_file = Path("data/json/screen_regions.json")
            if coords_file.exists():
                with open(coords_file, "r") as f:
                    data = json.load(f)

                if "region_colors" in data:
                    self.region_colors = {
                        key: tuple(color)
                        for key, color in data["region_colors"].items()
                    }
                    print(f"✅ Loaded {len(self.region_colors)} colors from JSON")
                else:
                    self.region_colors = self._get_default_colors()
                    print("⚠️ No colors in JSON, using defaults")
            else:
                self.region_colors = self._get_default_colors()
                print("⚠️ JSON not found, using defaults")

        except Exception as e:
            print(f"Error loading colors: {e}")
            self.region_colors = self._get_default_colors()

    def _get_default_colors(self) -> dict:
        """Default colors fallback."""
        return {
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

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("📸 Region Visualizer v9.0")
        title_font = title.font()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        controls = self.create_controls()
        layout.addWidget(controls)

        content_layout = QHBoxLayout()

        legend = self.create_legend()
        legend.setMaximumWidth(280)
        content_layout.addWidget(legend)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("background-color: #2b2b2b;")

        self.image_label = QLabel("Capturing...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Enable mouse tracking for middle button
        self.image_label.setMouseTracking(True)
        self.image_label.mousePressEvent = self.image_mouse_press

        self.scroll_area.setWidget(self.image_label)

        # Wheel events for zoom
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.scroll_area.wheelEvent = self.wheel_zoom

        content_layout.addWidget(self.scroll_area, 1)
        layout.addLayout(content_layout, 1)

        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Save As...")
        self.save_btn.clicked.connect(self.save_as)
        btn_layout.addWidget(self.save_btn)

        self.open_folder_btn = QPushButton("📁 Open Folder")
        self.open_folder_btn.clicked.connect(self.open_folder)
        btn_layout.addWidget(self.open_folder_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def create_controls(self) -> QGroupBox:
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)

        self.capture_btn = QPushButton("📷 Re-Capture")
        self.capture_btn.clicked.connect(self.capture_screenshot)
        layout.addWidget(self.capture_btn)

        layout.addWidget(QLabel("|"))

        self.zoom_in_btn = QPushButton("➕ Zoom In (Scroll Up)")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("➖ Zoom Out (Scroll Down)")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        layout.addWidget(self.zoom_out_btn)

        self.fit_btn = QPushButton("⛶ Fit (Middle Click or Space)")
        self.fit_btn.clicked.connect(self.fit_to_panel)
        layout.addWidget(self.fit_btn)

        layout.addStretch()
        return group

    def create_legend(self) -> QGroupBox:
        """Create color legend from JSON colors."""
        group = QGroupBox("Region Colors (from JSON)")
        layout = QVBoxLayout(group)

        # Map region names to friendly names
        friendly_names = {
            "score_region_small": "Score Small",
            "score_region_medium": "Score Medium",
            "score_region_large": "Score Large",
            "my_money_region": "My Money",
            "other_count_region": "Other Count",
            "other_money_region": "Other Money",
            "phase_region": "Phase",
            "play_amount_coords_1": "Play Amount 1",
            "play_button_coords_1": "Play Button 1",
            "auto_play_coords_1": "Auto Play 1",
            "play_amount_coords_2": "Play Amount 2",
            "play_button_coords_2": "Play Button 2",
            "auto_play_coords_2": "Auto Play 2",
        }

        for region_key, friendly_name in friendly_names.items():
            if region_key in self.region_colors:
                # BGR to RGB for display
                bgr_color = self.region_colors[region_key]
                rgb_color = (bgr_color[2], bgr_color[1], bgr_color[0])
                hex_color = f"#{rgb_color[0]:02X}{rgb_color[1]:02X}{rgb_color[2]:02X}"

                label = QLabel(
                    f'<span style="color: {hex_color}; font-size:14pt;">●</span> {friendly_name}'
                )
                layout.addWidget(label)

        layout.addStretch()
        return group

    def image_mouse_press(self, event: QMouseEvent):
        """Handle middle mouse button on image."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.fit_to_panel()
            print("🖱️ Middle button clicked - Fit to panel")

    def wheel_zoom(self, event: QWheelEvent):
        """Handle mouse wheel for zoom."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
        elif delta < 0:
            self.zoom_out()

    def keyPressEvent(self, event):
        """Handle Space key for fit."""
        if event.key() == Qt.Key.Key_Space:
            self.fit_to_panel()
            print("⌨️ Space key - Fit to panel")

    def capture_screenshot(self):
        self.capture_btn.setEnabled(False)
        self.capture_btn.setText("Capturing...")

        try:
            if self.position == "ALL":
                image = self.capture_all_positions()
            else:
                image = self.capture_single_position()

            if image is not None:
                self.current_image = image
                self.zoom_level = 1.0
                self.display_image()
                self.fit_to_panel()
            else:
                QMessageBox.critical(self, "Error", "Failed to capture screenshot.")

        finally:
            self.capture_btn.setEnabled(True)
            self.capture_btn.setText("📷 Re-Capture")

    def capture_single_position(self) -> np.ndarray:
        """Capture single position with regions."""
        try:
            # Get offset using RegionManager
            monitor_name = "right" if self.dual_monitor else "primary"
            offsets = self.region_manager.calculate_layout_offsets(self.layout, monitor_name)

            if self.position not in offsets:
                return None

            offset_x, offset_y = offsets[self.position]

            if "layout_4" in self.layout:
                width, height = 1920, 1044
            elif "layout_6" in self.layout:
                width, height = 1280, 1044
            elif "layout_8" in self.layout:
                width, height = 960, 1044
            else:
                width, height = 1280, 1044

            with mss.mss() as sct:
                monitor = {"left": offset_x, "top": offset_y, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Draw regions using JSON colors
            regions = self.region_manager.config.get("regions", {})
            if regions:
                for region_name, region_coords in regions.items():
                    if region_name in self.region_colors:
                        self.draw_region(img, region_name, region_coords)

            # Title
            title = f"REGION VISUALIZATION: {self.layout} @ {self.position}"
            if self.dual_monitor:
                title += " (Right Monitor)"

            cv2.putText(
                img, title, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2
            )

            return img

        except Exception as e:
            print(f"Capture error: {e}")
            import traceback

            traceback.print_exc()
            return None

    def capture_all_positions(self) -> np.ndarray:
        """Capture all positions in grid layout."""
        try:
            # Determine monitor to capture
            monitor_setup = self.region_manager.get_monitor_setup()
            if self.dual_monitor and "right" in monitor_setup:
                target_monitor = monitor_setup["right"]
            else:
                target_monitor = list(monitor_setup.values())[0]

            left, top = target_monitor.x, target_monitor.y
            width, height = target_monitor.width, target_monitor.height

            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Draw regions for ALL positions
            regions = self.region_manager.config.get("regions", {})
            monitor_name = "right" if self.dual_monitor else "primary"
            offsets = self.region_manager.calculate_layout_offsets(self.layout, monitor_name)

            for position_code, (offset_x, offset_y) in offsets.items():
                if regions:
                    for region_name, region_coords in regions.items():
                        if region_name in self.region_colors:
                            abs_coords = {
                                "left": region_coords["left"] + offset_x - left,
                                "top": region_coords["top"] + offset_y - top,
                                "width": region_coords["width"],
                                "height": region_coords["height"],
                            }
                            self.draw_region(img, region_name, abs_coords)

            title = f"FULL LAYOUT: {self.layout} (ALL POSITIONS)"
            if self.dual_monitor:
                title += " - Right Monitor"

            cv2.putText(
                img, title, (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3
            )

            return img

        except Exception as e:
            print(f"Capture ALL error: {e}")
            import traceback

            traceback.print_exc()
            return None

    def draw_region(self, image: np.ndarray, region_name: str, coords: dict):
        """Draw region with cross at center using JSON colors."""
        x1 = coords["left"]
        y1 = coords["top"]
        x2 = x1 + coords["width"]
        y2 = y1 + coords["height"]

        # Use JSON colors
        color = self.region_colors.get(region_name, (255, 255, 255))

        # Draw rectangle
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)

        # Draw cross at center
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        cross_size = 10

        cv2.line(
            image,
            (center_x - cross_size, center_y),
            (center_x + cross_size, center_y),
            color,
            2,
        )
        cv2.line(
            image,
            (center_x, center_y - cross_size),
            (center_x, center_y + cross_size),
            color,
            2,
        )

        # Draw label
        label = f"{region_name.upper()}"
        cv2.putText(
            image,
            label,
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    def display_image(self):
        if self.current_image is None:
            return

        img_display = self.current_image.copy()
        if self.zoom_level != 1.0:
            new_width = int(img_display.shape[1] * self.zoom_level)
            new_height = int(img_display.shape[0] * self.zoom_level)
            img_display = cv2.resize(
                img_display, (new_width, new_height), interpolation=cv2.INTER_CUBIC
            )

        img_rgb = cv2.cvtColor(img_display, cv2.COLOR_BGR2RGB)
        height, width, channel = img_rgb.shape
        bytes_per_line = 3 * width
        q_image = QImage(
            img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888
        )
        pixmap = QPixmap.fromImage(q_image)

        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(pixmap.size())

    def zoom_in(self):
        if self.current_image is None:
            return
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)
        self.display_image()

    def zoom_out(self):
        if self.current_image is None:
            return
        self.zoom_level = max(self.zoom_level / 1.25, 0.1)
        self.display_image()

    def fit_to_panel(self):
        if self.current_image is None:
            return

        available_width = self.scroll_area.viewport().width() - 20
        available_height = self.scroll_area.viewport().height() - 20

        img_height, img_width = self.current_image.shape[:2]

        width_ratio = available_width / img_width
        height_ratio = available_height / img_height

        self.zoom_level = min(width_ratio, height_ratio)
        self.display_image()

    def save_as(self):
        if self.current_image is None:
            return

        output_dir = Path("screenshots/visualizations")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{self.layout}_{self.position}_{timestamp}.png"
        default_path = str(output_dir / default_filename)

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", default_path, "PNG Image (*.png)"
        )

        if filepath:
            cv2.imwrite(filepath, self.current_image)
            self.filepath = filepath
            QMessageBox.information(self, "Saved", f"Image saved to:\n{filepath}")

    def open_folder(self):
        folder = Path("screenshots/visualizations")
        folder.mkdir(parents=True, exist_ok=True)

        import subprocess
        import platform

        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", str(folder)])
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")


if __name__ == "__main__":
    """Console mode execution."""
    print("=" * 70)
    print("REGION VISUALIZER v9.0 - JSON Colors + Fixed Middle Button")
    print("=" * 70)

    layout = input("Enter layout (layout_4/layout_6/layout_8): ").strip()
    position = input("Enter position (TL/TR/BL/BR/TC/BC/etc or ALL): ").strip()
    dual_str = input("Dual monitor? (y/n): ").strip().lower()
    dual_monitor = dual_str == "y"

    app = QApplication(sys.argv)
    dialog = RegionVisualizerDialog(layout, position, dual_monitor)
    sys.exit(dialog.exec())
