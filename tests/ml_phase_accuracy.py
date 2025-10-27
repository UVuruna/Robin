# tests/ml_phase_accuracy.py
# VERSION: 3.0 - CONFIGURABLE DELAY + METHOD CACHE
# CHANGES:
# - Added delay_ms spinner (0-1000ms, default 0ms)
# - Removed hardcoded time.sleep(0.05)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QGroupBox, QProgressBar, QCheckBox, QSpinBox, QApplication, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import time
import numpy as np
import pickle

class MLPhaseTestWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal(dict)

    def __init__(self, layout: str, position: str, dual_monitor: bool, 
                 iterations: int, delay_ms: int, selected_regions: dict):
        super().__init__()
        self.layout = layout
        self.position = position
        self.dual_monitor = dual_monitor
        self.iterations = iterations
        self.delay_ms = delay_ms
        self.selected_regions = selected_regions

    def run(self):
        try:
            from config.settings import PATH, GamePhase, BetState

            self.log.emit("Initializing ML phase test...")
            self.log.emit(f"Iterations: {self.iterations}")
            self.log.emit(f"Delay: {self.delay_ms}ms between reads")
            self.progress.emit(10)

            # Load ML models
            self.log.emit("\nLoading ML models...")
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

            self.progress.emit(20)

            # Get coordinates
            manager = CoordsManager()
            coords = manager.calculate_coords(self.layout, self.position, self.dual_monitor)

            if not coords:
                self.log.emit("❌ Failed to get coordinates")
                self.finished.emit({"success": False})
                return

            self.log.emit("✓ Coordinates loaded")

            # Define regions
            all_regions = [
                ("phase_region", "game_phase", "Game Phase", phase_model, GamePhase),
                ("play_button_coords_1", "bet_button", "Bet Button 1", button_model, BetState),
                ("play_button_coords_2", "bet_button", "Bet Button 2", button_model, BetState),
            ]

            regions_to_test = [r for r in all_regions if self.selected_regions.get(r[0], False)]

            if not regions_to_test:
                self.log.emit("❌ No regions selected!")
                self.finished.emit({"success": False})
                return

            self.log.emit(f"\nTesting {len(regions_to_test)} regions:")
            for _, _, label, _, _ in regions_to_test:
                self.log.emit(f"  • {label}")

            results = {}
            total = len(regions_to_test)
            delay_sec = self.delay_ms / 1000.0

            for i, (region_name, region_type, label, model, enum_class) in enumerate(regions_to_test):
                self.log.emit(f"\nTesting {label}...")

                if not model:
                    self.log.emit("  ❌ Model not loaded")
                    results[region_name] = {"success": False, "error": "Model not loaded", "label": label}
                    continue

                if region_name not in coords:
                    self.log.emit("  ⚠ Region not found in coords")
                    results[region_name] = {"success": False, "error": "Region not found", "label": label}
                    continue

                try:
                    reader = ScreenReader(coords[region_name])

                    predictions = []
                    for _ in range(self.iterations):
                        img = reader.capture_image()
                        if img is None:
                            predictions.append(None)
                            continue

                        # RGB and predict
                        rgb_img = img[:, :, :3]
                        mean_color = rgb_img.mean(axis=(0, 1))
                        r, g, b = mean_color[2], mean_color[1], mean_color[0]  # BGR to RGB

                        prediction = model.predict(np.array([[r, g, b]]))
                        cluster = prediction[0]

                        try:
                            phase = enum_class(cluster)
                            predictions.append(phase)
                        except ValueError:
                            predictions.append(cluster)

                        if delay_sec > 0:
                            time.sleep(delay_sec)

                    reader.close()

                    non_none = [p for p in predictions if p is not None]
                    successful_reads = len(non_none)

                    if non_none:
                        unique_values = set(non_none)
                        consistent = len(unique_values) == 1

                        if consistent:
                            phase_name = non_none[0].name if hasattr(non_none[0], 'name') else str(non_none[0])
                            self.log.emit(f"  ✓ Consistent: {phase_name} ({successful_reads}/{self.iterations})")
                        else:
                            phase_names = [p.name if hasattr(p, 'name') else str(p) for p in unique_values]
                            self.log.emit(f"  ⚠ Inconsistent: {phase_names} ({successful_reads}/{self.iterations})")
                    else:
                        consistent = False
                        self.log.emit(f"  ❌ All reads failed (0/{self.iterations})")

                    results[region_name] = {
                        "predictions": predictions,
                        "consistent": consistent,
                        "success": successful_reads > 0,
                        "successful_reads": successful_reads,
                        "total_reads": self.iterations,
                        "type": region_type,
                        "label": label,
                    }

                except Exception as e:
                    results[region_name] = {"error": str(e), "success": False, "label": label}
                    self.log.emit(f"  ❌ Error: {e}")
                    import traceback
                    self.log.emit(f"  Trace: {traceback.format_exc()}")

                progress_val = 20 + int((i + 1) / total * 70)
                self.progress.emit(progress_val)

            self.progress.emit(100)
            self.log.emit("\n" + "=" * 60)
            self.log.emit("ML PHASE TEST COMPLETE")
            self.log.emit("=" * 60)

            successful = sum(1 for r in results.values() if r.get("success", False))
            consistent = sum(1 for r in results.values() if r.get("consistent", False))

            self.log.emit("\n📊 Results:")
            self.log.emit(f"  • Successful reads: {successful}/{total}")
            self.log.emit(f"  • Consistent reads: {consistent}/{total}")

            total_reads = sum(r.get("total_reads", 0) for r in results.values())
            total_successful = sum(r.get("successful_reads", 0) for r in results.values())
            if total_reads > 0:
                success_rate = (total_successful / total_reads) * 100
                self.log.emit(f"  • Overall success rate: {success_rate:.1f}% ({total_successful}/{total_reads})")

            if successful == total and consistent == total:
                self.log.emit("\n✅ PERFECT! All regions predicted correctly and consistently")
            elif successful == total:
                self.log.emit(f"\n⚠️ All reads successful but {total - consistent} region(s) inconsistent")
                self.log.emit("   (This is NORMAL if delay > 0 and game is running)")
            else:
                failed = total - successful
                self.log.emit(f"\n❌ {failed} region(s) failed to predict")

            self.finished.emit({"success": True, "results": results})

        except Exception as e:
            self.log.emit(f"\n❌ FATAL ERROR: {e}")
            import traceback
            self.log.emit(traceback.format_exc())
            self.finished.emit({"success": False, "error": str(e)})


class MLPhaseTestDialog(QDialog):
    def __init__(self, layout: str, position: str, dual_monitor: bool, parent=None):
        super().__init__(parent)
        self.layout = layout
        self.position = position
        self.dual_monitor = dual_monitor
        self.worker = None

        self.setWindowTitle(f"ML Phase Test - {layout} @ {position}")
        self.setMinimumSize(900, 650)
        self.setWindowFlags(Qt.WindowType.Window)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(f"🤖 ML Phase Accuracy Test\n{self.layout} @ {self.position}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        info = QLabel(
            "Testing ML model accuracy for Game Phase and Bet Button detection.\n"
            "For STATIC test: Set delay to 0ms. For DYNAMIC test: Set delay > 0ms."
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(info)

        # COMPACT CONFIG (1 row)
        config_group = QGroupBox("⚙️ Configuration")
        config_layout = QHBoxLayout(config_group)

        config_layout.addWidget(QLabel("Iterations:"))
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setMinimum(1)
        self.iterations_spin.setMaximum(100)
        self.iterations_spin.setValue(30)
        self.iterations_spin.setMaximumWidth(80)
        config_layout.addWidget(self.iterations_spin)

        config_layout.addWidget(QLabel("Delay (ms):"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setMinimum(0)
        self.delay_spin.setMaximum(1000)
        self.delay_spin.setValue(0)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setMaximumWidth(100)
        config_layout.addWidget(self.delay_spin)

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

        log_group = QGroupBox("Test Output")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 10pt;")
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ Run Test")
        self.run_btn.clicked.connect(self.start_test)
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
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

    def start_test(self):
        selected_regions = self.get_selected_regions()
        if not any(selected_regions.values()):
            QMessageBox.warning(self, "No Regions", "Select at least one region")
            return

        iterations = self.iterations_spin.value()
        delay_ms = self.delay_spin.value()
        
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(False)

        self.worker = MLPhaseTestWorker(
            self.layout, self.position, self.dual_monitor, 
            iterations, delay_ms, selected_regions
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.test_finished)
        self.worker.start()

    def test_finished(self, results: dict):
        self.run_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = MLPhaseTestDialog("layout_6", "TL", False)
    sys.exit(dialog.exec())