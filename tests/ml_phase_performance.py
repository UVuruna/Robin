# tests/ml_phase_performance.py
# VERSION: 2.1 - NO DELAY (Performance test)
# NOTE: This file is already optimized - no changes needed
# No delay in performance tests to measure pure ML speed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QGroupBox, QProgressBar, QSpinBox, QCheckBox, QRadioButton, QButtonGroup,
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import time
import numpy as np
import pickle
from typing import Dict

class MLPhaseSpeedWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    result = Signal(dict)
    finished = Signal()

    def __init__(self, layout: str, position: str, target_monitor: str, mode: str, value: int, selected_regions: dict):
        super().__init__()
        self.layout = layout
        self.position = position
        self.target_monitor = dual_monitor
        self.mode = mode
        self.value = value
        self.selected_regions = selected_regions

    def run(self):
        try:
            from config.settings import PATH, GamePhase, BetState

            mode_str = f"{self.value}s" if self.mode == "time" else f"{self.value} iterations"
            self.log.emit(f"Initializing benchmark ({mode_str})...")
            self.progress.emit(5)

            # Load models
            try:
                with open(PATH.phase_model, "rb") as f:
                    phase_model = pickle.load(f)
                self.log.emit("  ✓ Game Phase model loaded")
            except Exception as e:
                self.log.emit(f"  ⚠ Game Phase model error: {e}")
                phase_model = None

            try:
                with open(PATH.button_model, "rb") as f:
                    button_model = pickle.load(f)
                self.log.emit("  ✓ Bet Button model loaded")
            except Exception as e:
                self.log.emit(f"  ⚠ Bet Button model error: {e}")
                button_model = None

            from core.capture.region_manager import RegionManager
            manager = RegionManager()

            # Get all regions for this position
            monitor_name = self.target_monitor
            regions = manager.get_all_regions_for_position(self.position, self.layout, monitor_name)

            # Convert Region objects to dict format for compatibility
            coords = {name: region.to_dict() for name, region in regions.items()}

            if not coords:
                self.log.emit("❌ Failed to get coordinates")
                self.finished.emit()
                return

            self.log.emit("✓ Coordinates loaded")
            self.progress.emit(10)

            all_regions = [
                ("phase_region", "game_phase", "Game Phase", phase_model, GamePhase),
                ("play_button_coords_1", "bet_button", "Bet Button 1", button_model, BetState),
                ("play_button_coords_2", "bet_button", "Bet Button 2", button_model, BetState),
            ]

            regions_to_test = [r for r in all_regions if self.selected_regions.get(r[0], False)]

            if not regions_to_test:
                self.log.emit("❌ No regions selected!")
                self.finished.emit()
                return

            self.log.emit(f"\nBenchmarking {len(regions_to_test)} regions:")
            for _, _, label, _, _ in regions_to_test:
                self.log.emit(f"  • {label}")

            results = {}
            total_regions = len(regions_to_test)

            for i, (region_name, region_type, display_name, model, enum_class) in enumerate(regions_to_test):
                self.log.emit(f"\n🔥 Testing {display_name}...")

                if not model:
                    self.log.emit("  ❌ Model not loaded")
                    continue

                if region_name not in coords:
                    self.log.emit("  ⚠ Region not found")
                    continue

                try:
                    reader = ScreenReader(coords[region_name])

                    times = []
                    start_time = time.perf_counter()
                    iterations = 0

                    if self.mode == "time":
                        # Time-based: run for N seconds
                        while True:
                            iter_start = time.perf_counter()

                            img = reader.capture_image()
                            if img is not None:
                                rgb_img = img[:, :, :3]
                                mean_color = rgb_img.mean(axis=(0, 1))
                                r, g, b = mean_color[2], mean_color[1], mean_color[0]
                                _ = model.predict(np.array([[r, g, b]]))[0]

                            iter_time = (time.perf_counter() - iter_start) * 1_000
                            times.append(iter_time)
                            iterations += 1

                            elapsed = time.perf_counter() - start_time
                            if elapsed >= self.value:
                                break

                    else:
                        # Iteration-based: run N iterations
                        for _ in range(self.value):
                            iter_start = time.perf_counter()

                            img = reader.capture_image()
                            if img is not None:
                                rgb_img = img[:, :, :3]
                                mean_color = rgb_img.mean(axis=(0, 1))
                                r, g, b = mean_color[2], mean_color[1], mean_color[0]
                                _ = model.predict(np.array([[r, g, b]]))[0]

                            iter_time = (time.perf_counter() - iter_start) * 1_000
                            times.append(iter_time)
                            iterations += 1

                        elapsed = time.perf_counter() - start_time

                    reader.close()

                    if times:
                        avg_time = sum(times) / len(times)
                        min_time = min(times)
                        max_time = max(times)

                        results[display_name] = {
                            "avg": avg_time,
                            "min": min_time,
                            "max": max_time,
                            "iterations": iterations,
                            "total_time": elapsed,
                        }

                        self.log.emit(f"  ✓ {iterations} iterations in {elapsed:.2f}s")
                        self.log.emit(f"    Avg: {avg_time:.2f}ms | Min: {min_time:.2f}ms | Max: {max_time:.2f}ms")
                    else:
                        self.log.emit("  ❌ No successful iterations")

                except Exception as e:
                    self.log.emit(f"  ❌ Error: {e}")

                progress_val = 10 + int((i + 1) / total_regions * 85)
                self.progress.emit(progress_val)

            self.progress.emit(100)
            self.log.emit("\n" + "=" * 60)
            self.log.emit("BENCHMARK COMPLETE")
            self.log.emit("=" * 60)

            if results:
                total_iters = sum(r["iterations"] for r in results.values())
                total_time = sum(r["total_time"] for r in results.values())
                overall_rate = total_iters / total_time if total_time > 0 else 0

                self.log.emit("\n📊 Overall Statistics:")
                self.log.emit(f"  • Total iterations: {total_iters}")
                self.log.emit(f"  • Total time: {total_time:.2f}s")
                self.log.emit(f"  • Overall rate: {overall_rate:.2f} predictions/sec")

            self.result.emit(results)
            self.finished.emit()

        except Exception as e:
            self.log.emit(f"\n❌ FATAL ERROR: {e}")
            self.finished.emit()


class MLPhaseSpeedDialog(QDialog):
    def __init__(self, layout: str, position: str, target_monitor: str, parent=None):
        super().__init__(parent)
        self.layout = layout
        self.position = position
        self.target_monitor = dual_monitor
        self.worker = None

        self.setWindowTitle(f"ML Phase Speed - {layout} @ {position}")
        self.setMinimumSize(900, 700)
        self.setWindowFlags(Qt.WindowType.Window)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(f"🚀 ML Phase Performance Test\n{self.layout} @ {self.position}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        info = QLabel("Measures ML model prediction speed (no delays)")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(info)

        # COMPACT CONFIG (1 row)
        config_group = QGroupBox("⚙️ Configuration")
        config_layout = QHBoxLayout(config_group)

        config_layout.addWidget(QLabel("Mode:"))
        self.mode_group = QButtonGroup()
        self.time_radio = QRadioButton("⏱️ Time")
        self.iter_radio = QRadioButton("🔢 Iterations")
        self.time_radio.setChecked(True)
        self.mode_group.addButton(self.time_radio)
        self.mode_group.addButton(self.iter_radio)
        config_layout.addWidget(self.time_radio)
        config_layout.addWidget(self.iter_radio)

        config_layout.addWidget(QLabel("Value:"))
        self.value_spin = QSpinBox()
        self.value_spin.setMinimum(1)
        self.value_spin.setMaximum(1000)
        self.value_spin.setValue(10)
        self.value_spin.setMaximumWidth(80)
        config_layout.addWidget(self.value_spin)

        config_layout.addWidget(QLabel("Regions:"))

        self.region_checkboxes = {}
        regions = [
            ("phase_region", "🎮 Phase"),
            ("play_button_coords_1", "🔴 Btn 1"),
            ("play_button_coords_2", "🔴 Btn 2"),
        ]

        for region_name, label in regions:
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.region_checkboxes[region_name] = checkbox
            config_layout.addWidget(checkbox)

        config_layout.addStretch()
        layout.addWidget(config_group)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        table_group = QGroupBox("Performance Results")
        table_layout = QVBoxLayout(table_group)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Region", "Avg (ms)", "Min (ms)", "Max (ms)", "Iterations"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.results_table)
        layout.addWidget(table_group)

        log_group = QGroupBox("Test Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 9pt;")
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ Run Benchmark")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.run_btn.clicked.connect(self.start_benchmark)
        btn_layout.addWidget(self.run_btn)

        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(40)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def get_selected_regions(self) -> dict:
        return {name: checkbox.isChecked() for name, checkbox in self.region_checkboxes.items()}

    def log(self, message: str):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def start_benchmark(self):
        selected_regions = self.get_selected_regions()
        if not any(selected_regions.values()):
            QMessageBox.warning(self, "No Regions", "Select at least one region")
            return

        mode = "time" if self.time_radio.isChecked() else "iterations"
        value = self.value_spin.value()

        self.log_text.clear()
        self.results_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(False)

        self.worker = MLPhaseSpeedWorker(self.layout, self.position, self.target_monitor, mode, value, selected_regions)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log)
        self.worker.result.connect(self.display_results)
        self.worker.finished.connect(self.benchmark_finished)
        self.worker.start()

    def display_results(self, results: Dict):
        self.results_table.setRowCount(len(results))
        for row, (region_name, data) in enumerate(results.items()):
            self.results_table.setItem(row, 0, QTableWidgetItem(region_name))

            avg_item = QTableWidgetItem(f"{data['avg']:.2f}")
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(row, 1, avg_item)

            min_item = QTableWidgetItem(f"{data['min']:.2f}")
            min_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(row, 2, min_item)

            max_item = QTableWidgetItem(f"{data['max']:.2f}")
            max_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(row, 3, max_item)

            iter_item = QTableWidgetItem(str(data["iterations"]))
            iter_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(row, 4, iter_item)

    def benchmark_finished(self):
        self.run_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = MLPhaseSpeedDialog("GRID 2×3", "Top-Left", False)
    sys.exit(dialog.exec())