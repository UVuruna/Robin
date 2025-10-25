# utils/diagnostic.py
# VERSION: 1.0 - System Diagnostic with console support

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
    QProgressBar,
    QApplication,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from config.config import PATH


class DiagnosticWorker(QThread):
    """Worker thread for system diagnostics."""

    progress = Signal(int)
    log = Signal(str)
    finished = Signal(bool)

    def __init__(self, quick: bool = False):
        super().__init__()
        self.quick = quick

    def run(self):
        """Run diagnostics."""
        try:
            self.log.emit("=" * 60)
            mode = "QUICK" if self.quick else "FULL"
            self.log.emit(f"{mode} SYSTEM DIAGNOSTIC")
            self.log.emit("=" * 60 + "\n")

            checks = [
                ("Python Environment", self.check_python),
                ("Required Libraries", self.check_libraries),
                ("File Structure", self.check_files),
                ("Coordinates File", self.check_coordinates),
                ("Database", self.check_database),
            ]

            if not self.quick:
                checks.extend(
                    [
                        ("Screen Capture", self.check_screen_capture),
                        ("OCR Engine", self.check_ocr),
                    ]
                )

            total = len(checks)
            passed = 0

            for i, (name, check_func) in enumerate(checks):
                self.log.emit(f"[{i + 1}/{total}] Checking {name}...")

                try:
                    result = check_func()
                    if result:
                        self.log.emit(f"  ✓ {name}: OK")
                        passed += 1
                    else:
                        self.log.emit(f"  ✗ {name}: FAILED")
                except Exception as e:
                    self.log.emit(f"  ✗ {name}: ERROR - {e}")

                progress_val = int((i + 1) / total * 100)
                self.progress.emit(progress_val)
                self.log.emit("")

            self.log.emit("=" * 60)
            self.log.emit(f"RESULTS: {passed}/{total} checks passed")
            self.log.emit("=" * 60)

            success = passed == total
            if success:
                self.log.emit("\n✅ ALL CHECKS PASSED - System is ready!")
            else:
                self.log.emit(
                    f"\n⚠️ {total - passed} checks failed - Review errors above"
                )

            self.finished.emit(success)

        except Exception as e:
            self.log.emit(f"\n❌ FATAL ERROR: {e}")
            import traceback

            self.log.emit(traceback.format_exc())
            self.finished.emit(False)

    def check_python(self) -> bool:
        """Check Python version."""
        import sys

        version = sys.version_info
        self.log.emit(f"    Python {version.major}.{version.minor}.{version.micro}")
        return version.major == 3 and version.minor >= 8

    def check_libraries(self) -> bool:
        """Check required libraries."""
        required = [
            "PySide6",
            "cv2",
            "numpy",
            "mss",
            "pytesseract",
            "PIL",
            "pandas",
        ]

        missing = []
        for lib in required:
            try:
                __import__(lib)
                self.log.emit(f"    ✓ {lib}")
            except ImportError:
                self.log.emit(f"    ✗ {lib} (MISSING)")
                missing.append(lib)

        return len(missing) == 0

    def check_files(self) -> bool:
        """Check file structure."""
        required_dirs = [
            "core",
            "utils",
            "gui",
            "data",
            "data/coordinates",
            "logs",
        ]

        all_exist = True
        for dir_path in required_dirs:
            path = Path(dir_path)
            if path.exists():
                self.log.emit(f"    ✓ {dir_path}/")
            else:
                self.log.emit(f"    ✗ {dir_path}/ (MISSING)")
                all_exist = False

        return all_exist

    def check_coordinates(self) -> bool:
        """Check coordinates file."""
        coords_file = PATH.screen_regions

        if not coords_file.exists():
            self.log.emit("    ✗ Coordinates file not found")
            return False

        try:
            import json

            with open(coords_file, "r") as f:
                data = json.load(f)

            has_layouts = "layouts" in data
            has_regions = "regions" in data

            self.log.emit("    ✓ File exists")
            self.log.emit(f"    ✓ Layouts: {len(data.get('layouts', {}))}")
            self.log.emit(f"    ✓ Regions: {len(data.get('regions', {}))}")

            return has_layouts and has_regions

        except Exception as e:
            self.log.emit(f"    ✗ Error reading file: {e}")
            return False

    def check_database(self) -> bool:
        """Check database."""
        db_file = PATH.main_game_db

        if not db_file.exists():
            self.log.emit("    ⚠ Database file not found (will be created)")
            return True

        try:
            import sqlite3

            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            conn.close()

            self.log.emit("    ✓ Database exists")
            self.log.emit(f"    ✓ Tables: {len(tables)}")

            return True

        except Exception as e:
            self.log.emit(f"    ✗ Error: {e}")
            return False

    def check_screen_capture(self) -> bool:
        """Check screen capture."""
        try:
            import mss

            with mss.mss() as sct:
                monitors = sct.monitors
                self.log.emit(f"    ✓ Monitors detected: {len(monitors) - 1}")
                return True
        except Exception as e:
            self.log.emit(f"    ✗ Error: {e}")
            return False

    def check_ocr(self) -> bool:
        """Check OCR engine."""
        try:
            import pytesseract

            version = pytesseract.get_tesseract_version()
            self.log.emit(f"    ✓ Tesseract version: {version}")
            return True
        except Exception as e:
            self.log.emit(f"    ✗ Error: {e}")
            return False


class DiagnosticDialog(QDialog):
    """System Diagnostic Dialog."""

    def __init__(self, quick: bool = False, parent=None):
        super().__init__(parent)

        self.quick = quick
        self.worker = None

        mode = "Quick" if quick else "Full"
        self.setWindowTitle(f"{mode} System Diagnostic")
        self.setMinimumSize(700, 600)
        self.setWindowFlags(Qt.WindowType.Window)

        self.init_ui()

        # Auto-start diagnostic
        self.start_diagnostic()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        mode = "Quick" if self.quick else "Full"
        title = QLabel(f"🏥 {mode} System Diagnostic")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        # Log area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; "
            "font-family: Consolas; font-size: 10pt;"
        )
        layout.addWidget(self.log_text)

        # Buttons
        btn_layout = QHBoxLayout()

        self.rerun_btn = QPushButton("🔄 Run Again")
        self.rerun_btn.clicked.connect(self.start_diagnostic)
        self.rerun_btn.setEnabled(False)
        btn_layout.addWidget(self.rerun_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def log(self, message: str):
        """Add log message."""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def start_diagnostic(self):
        """Start diagnostic."""
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.rerun_btn.setEnabled(False)

        self.worker = DiagnosticWorker(self.quick)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.diagnostic_finished)
        self.worker.start()

    def diagnostic_finished(self, success: bool):
        """Handle diagnostic completion."""
        self.rerun_btn.setEnabled(True)


if __name__ == "__main__":
    """Console mode execution."""
    print("=" * 70)
    print("SYSTEM DIAGNOSTIC - Console Mode")
    print("=" * 70)

    mode = input("Run quick check? (y/n, default=n): ").strip().lower()
    quick = mode == "y"

    app = QApplication(sys.argv)
    dialog = DiagnosticDialog(quick=quick)
    sys.exit(dialog.exec())
