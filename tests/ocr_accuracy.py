# tests/ocr_accuracy.py
# VERSION: 5.0 - CONFIGURABLE DELAY + METHOD CACHE
# CHANGES:
# - Added delay_ms spinner (0-1000ms, default 0ms for static tests)
# - Method reference extracted before loop (no if/elif overhead)

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

class OCRTestWorker(QThread):
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
            from core.coord_manager import CoordsManager
            from core.screen_reader import ScreenReader

            self.log.emit("Initializing OCR test...")
            self.log.emit(f"Iterations: {self.iterations}")
            self.log.emit(f"Delay: {self.delay_ms}ms between reads")
            self.progress.emit(10)

            manager = CoordsManager()
            coords = manager.calculate_coords(self.layout, self.position, self.dual_monitor)

            if not coords:
                self.log.emit("❌ Failed to get coordinates")
                self.finished.emit({"success": False})
                return

            self.progress.emit(20)
            self.log.emit("✓ Coordinates loaded")

            all_regions = [
                ("score_region_small", "score", "Score Small"),
                ("score_region_medium", "score", "Score Medium"),
                ("score_region_large", "score", "Score Large"),
                ("my_money_region", "money", "My Money"),
                ("other_count_region", "player_count", "Player Count"),
                ("other_money_region", "money", "Other Money"),
            ]

            regions_to_test = [(name, rtype, label) for name, rtype, label in all_regions 
                              if self.selected_regions.get(name, False)]

            if not regions_to_test:
                self.log.emit("❌ No regions selected!")
                self.finished.emit({"success": False})
                return

            self.log.emit(f"\nTesting {len(regions_to_test)} regions:")
            for _, _, label in regions_to_test:
                self.log.emit(f"  • {label}")

            results = {}
            total = len(regions_to_test)
            delay_sec = self.delay_ms / 1000.0

            for i, (region_name, region_type, label) in enumerate(regions_to_test):
                self.log.emit(f"\nTesting {label}...")

                if region_name not in coords:
                    self.log.emit("  ⚠ Region not found in coords")
                    results[region_name] = {"success": False, "error": "Region not found", "label": label}
                    continue

                try:
                    reader = ScreenReader(coords[region_name])

                    # OPTIMIZED: Extract method reference BEFORE loop!
                    read_method = {
                        "score": reader.read_score,
                        "money": reader.read_money,
                        "player_count": reader.read_player_count
                    }.get(region_type)

                    if not read_method:
                        self.log.emit(f"  ❌ Unknown region type: {region_type}")
                        continue

                    readings = []
                    for _ in range(self.iterations):
                        value = read_method()  # Direct call, no if/elif!
                        readings.append(value)
                        
                        if delay_sec > 0:
                            time.sleep(delay_sec)

                    reader.close()

                    non_none = [r for r in readings if r is not None]
                    successful_reads = len(non_none)

                    if non_none:
                        unique_values = set(map(str, non_none))
                        consistent = len(unique_values) == 1

                        if consistent:
                            self.log.emit(f"  ✓ Consistent: {non_none[0]} ({successful_reads}/{self.iterations})")
                        else:
                            # Show unique values for debugging
                            unique_list = sorted(list(unique_values))
                            self.log.emit(f"  ⚠ Inconsistent: {unique_list} ({successful_reads}/{self.iterations})")
                    else:
                        consistent = False
                        self.log.emit(f"  ❌ All reads failed (0/{self.iterations})")

                    results[region_name] = {
                        "readings": readings,
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

                progress_val = 20 + int((i + 1) / total * 70)
                self.progress.emit(progress_val)

            self.progress.emit(100)
            self.log.emit("\n" + "=" * 60)
            self.log.emit("OCR TEST COMPLETE")
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
                self.log.emit("\n✅ PERFECT! All regions read correctly and consistently")
            elif successful == total:
                self.log.emit(f"\n⚠️ All reads successful but {total - consistent} region(s) inconsistent")
                self.log.emit("   (This is NORMAL if delay > 0 and game is running)")
            else:
                failed = total - successful
                self.log.emit(f"\n❌ {failed} region(s) failed to read")

            self.finished.emit({"success": True, "results": results})

        except Exception as e:
            self.log.emit(f"\n❌ FATAL ERROR: {e}")
            import traceback
            self.log.emit(traceback.format_exc())
            self.finished.emit({"success": False, "error": str(e)})


class OCRTestDialog(QDialog):
    def __init__(self, layout: str, position: str, dual_monitor: bool, parent=None):
        super().__init__(parent)
        self.layout = layout
        self.position = position
        self.dual_monitor = dual_monitor
        self.worker = None

        self.setWindowTitle(f"OCR Test - {layout} @ {position}")
        self.setMinimumSize(900, 650)
        self.setWindowFlags(Qt.WindowType.Window)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(f"🔍 OCR Accuracy Test\n{self.layout} @ {self.position}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        info = QLabel(
            "Testing OCR reading accuracy. Each region is read N times.\n"
            "For STATIC test (consistency check): Set delay to 0ms and PAUSE game.\n"
            "For DYNAMIC test (tracking test): Set delay > 0ms and let game run."
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
        self.delay_spin.setValue(0)  # Default: 0ms (static test)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setMaximumWidth(100)
        self.delay_spin.setToolTip(
            "0ms = Static test (for consistency)\n"
            "50-100ms = Dynamic test (tracking during game)"
        )
        config_layout.addWidget(self.delay_spin)

        config_layout.addWidget(QLabel("Regions:"))
        
        self.region_checkboxes = {}
        regions = [
            ("score_region_small", "Score S"),
            ("score_region_medium", "Score M"),
            ("score_region_large", "Score L"),
            ("my_money_region", "Money"),
            ("other_count_region", "Count"),
            ("other_money_region", "Other $"),
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

        self.worker = OCRTestWorker(
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
    dialog = OCRTestDialog("layout_6", "TL", False)
    sys.exit(dialog.exec())