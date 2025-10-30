# gui/stats_widgets.py
# VERSION: 4.0 - COMPLETE REWORK prema PNG instrukcijama
# CHANGES:
# - Data Collector: TOTAL stats + GRID per-bookmaker layout
# - Betting Agent: TOTAL stats + GRID per-bookmaker layout
# - RGB Collector: TOTAL stats + GRID per-bookmaker layout
# - Session Keeper: TOTAL stats + GRID per-bookmaker layout

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QGroupBox, QGridLayout, QPushButton, QFrame
)
from PySide6.QtCore import QTimer, Signal
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from config.settings import PATH
from utils.logger import AviatorLogger


class DataCollectorStats(QWidget):
    """
    Stats for Main Data Collector - PNG REWORK.

    Layout:
    - TOTAL Stats (gore) - full width
    - GRID Stats (dole) - per bookmaker, grid layout based on config
    - START/STOP buttons per bookmaker
    """

    # Signals za start/stop kontrolu
    start_single = Signal(str)  # bookmaker_name
    stop_single = Signal(str)   # bookmaker_name
    start_all = Signal()
    stop_all = Signal()

    def __init__(self, bookmaker_names: List[str] = None, grid_layout: str = "GRID 2×3"):
        super().__init__()
        self.db_path = PATH.main_game_db
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-DataCollector")

        # Bookmaker configuration - DYNAMIC, not hardcoded!
        self.bookmaker_names = bookmaker_names if bookmaker_names else []
        self.grid_layout = grid_layout
        self.bookmaker_statuses = {name: "INACTIVE" for name in self.bookmaker_names}

        # Tracking
        self.last_round_count = 0
        self.last_check_time = datetime.now()

        # Storage za per-bookmaker labels
        self.single_labels = {}
        self.single_buttons = {}

        self.init_ui()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_and_update_stats)
        self.update_timer.start(2000)  # 2s update

    def init_ui(self):
        """Initialize UI sa TOTAL gore + GRID dole layout."""
        main_layout = QVBoxLayout()

        # TOTAL STATS panel (gore)
        total_panel = self.create_total_stats_panel()
        main_layout.addWidget(total_panel)

        # GRID STATS panel (dole) - stretch
        grid_panel = self.create_grid_stats_panel()
        main_layout.addWidget(grid_panel, stretch=1)

        self.setLayout(main_layout)

    def create_total_stats_panel(self) -> QGroupBox:
        """Create TOTAL statistics panel."""
        group = QGroupBox("Data Collector Stats TOTAL")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #00BCD4; }")

        layout = QGridLayout()

        # Labels
        self.lbl_started = QLabel("--:--:--")
        self.lbl_total_inputs = QLabel("0")
        self.lbl_error_count = QLabel("0")
        self.lbl_inputs_per_min = QLabel("0.0")
        self.lbl_avg_score = QLabel("0.00x")

        # Layout - 2 columns
        layout.addWidget(QLabel("Started:"), 0, 0)
        layout.addWidget(self.lbl_started, 0, 1)

        layout.addWidget(QLabel("Total Inputs:"), 0, 2)
        layout.addWidget(self.lbl_total_inputs, 0, 3)

        layout.addWidget(QLabel("Error count:"), 1, 0)
        layout.addWidget(self.lbl_error_count, 1, 1)

        layout.addWidget(QLabel("Inputs / min:"), 1, 2)
        layout.addWidget(self.lbl_inputs_per_min, 1, 3)

        layout.addWidget(QLabel("Average score:"), 2, 0)
        layout.addWidget(self.lbl_avg_score, 2, 1)

        # START/STOP buttons (TOTAL)
        self.btn_start_all = QPushButton("⏵ START")
        self.btn_stop_all = QPushButton("⏹ STOP")

        self.btn_start_all.clicked.connect(self.start_all.emit)
        self.btn_stop_all.clicked.connect(self.stop_all.emit)

        layout.addWidget(self.btn_start_all, 2, 2)
        layout.addWidget(self.btn_stop_all, 2, 3)

        # Set session start
        self.lbl_started.setText(self.session_start.strftime("%H:%M:%S"))

        group.setLayout(layout)
        return group

    def create_grid_stats_panel(self) -> QGroupBox:
        """Create GRID per-bookmaker stats panel."""
        group = QGroupBox("Data Collector Stats per bookmaker")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #4CAF50; }")

        # Parse grid layout (e.g., "GRID 2×3" -> 2 rows, 3 cols)
        rows, cols = self.parse_grid_layout(self.grid_layout)

        grid_layout = QGridLayout()

        # Create per-bookmaker cards
        for idx, bookmaker_name in enumerate(self.bookmaker_names):
            row = idx // cols
            col = idx % cols

            card = self.create_bookmaker_card(bookmaker_name)
            grid_layout.addWidget(card, row, col)

        group.setLayout(grid_layout)
        return group

    def create_bookmaker_card(self, bookmaker_name: str) -> QFrame:
        """Create pojedinačnu karticu za bookmaker."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(1)

        layout = QVBoxLayout()

        # Header - Bookmaker name
        lbl_name = QLabel(bookmaker_name)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_name)

        # STATUS
        lbl_status_title = QLabel("STATUS:")
        lbl_status = QLabel("INACTIVE")
        lbl_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(lbl_status_title)
        layout.addWidget(lbl_status)

        # Stats grid
        stats_layout = QGridLayout()

        lbl_total_inputs = QLabel("0")
        lbl_inputs_per_min = QLabel("0.0")
        lbl_last_score = QLabel("0.00x")
        lbl_avg_score = QLabel("0.00x")

        stats_layout.addWidget(QLabel("Total Inputs:"), 0, 0)
        stats_layout.addWidget(lbl_total_inputs, 0, 1)

        stats_layout.addWidget(QLabel("Inputs / min:"), 1, 0)
        stats_layout.addWidget(lbl_inputs_per_min, 1, 1)

        stats_layout.addWidget(QLabel("Last score:"), 2, 0)
        stats_layout.addWidget(lbl_last_score, 2, 1)

        stats_layout.addWidget(QLabel("Average score:"), 3, 0)
        stats_layout.addWidget(lbl_avg_score, 3, 1)

        layout.addLayout(stats_layout)

        # Buttons
        btn_start = QPushButton("⏵ START")
        btn_stop = QPushButton("⏹ STOP")

        btn_start.clicked.connect(lambda: self.start_single.emit(bookmaker_name))
        btn_stop.clicked.connect(lambda: self.stop_single.emit(bookmaker_name))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_stop)
        layout.addLayout(btn_layout)

        frame.setLayout(layout)

        # Store references
        self.single_labels[bookmaker_name] = {
            'status': lbl_status,
            'total_inputs': lbl_total_inputs,
            'inputs_per_min': lbl_inputs_per_min,
            'last_score': lbl_last_score,
            'avg_score': lbl_avg_score
        }

        self.single_buttons[bookmaker_name] = {
            'start': btn_start,
            'stop': btn_stop
        }

        return frame

    def parse_grid_layout(self, grid_str: str) -> tuple:
        """Parse grid string like 'GRID 2×3' -> (2, 3)."""
        try:
            parts = grid_str.split()
            if len(parts) == 2:
                dims = parts[1].split('×')
                return int(dims[0]), int(dims[1])
        except:
            pass
        return 2, 3  # Default

    def fetch_and_update_stats(self):
        """Fetch stats from DB."""
        conn = self.get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # TOTAL stats
            cursor.execute("""
                SELECT COUNT(*), AVG(final_score)
                FROM rounds WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))

            row = cursor.fetchone()
            total_inputs = row[0] or 0
            avg_score = row[1] or 0.0

            # Calculate inputs/min
            elapsed_minutes = (datetime.now() - self.session_start).total_seconds() / 60.0
            inputs_per_min = total_inputs / elapsed_minutes if elapsed_minutes > 0 else 0.0

            # Error count (placeholder - implement based on error tracking)
            error_count = 0

            conn.close()

            # Update TOTAL panel
            self.lbl_total_inputs.setText(f"{total_inputs:,}")
            self.lbl_error_count.setText(str(error_count))
            self.lbl_inputs_per_min.setText(f"{inputs_per_min:.1f}")
            self.lbl_avg_score.setText(f"{avg_score:.2f}x")

            # Update per-bookmaker stats (placeholder - needs bookmaker-specific queries)
            self.update_per_bookmaker_stats(conn)

        except Exception as e:
            self.logger.debug(f"Stats fetch error: {e}")
            if conn:
                conn.close()

    def update_per_bookmaker_stats(self, conn):
        """Update per-bookmaker stats (placeholder)."""
        # TODO: Implement bookmaker-specific queries
        # For now, just update placeholders
        pass

    def update_bookmaker_status(self, bookmaker_name: str, status: str):
        """Update bookmaker status from external signal."""
        if bookmaker_name in self.single_labels:
            lbl = self.single_labels[bookmaker_name]['status']
            lbl.setText(status)
            if status == "ACTIVE":
                lbl.setStyleSheet("color: green; font-weight: bold;")
                # Disable START button
                self.single_buttons[bookmaker_name]['start'].setEnabled(False)
                self.single_buttons[bookmaker_name]['stop'].setEnabled(True)
            else:
                lbl.setStyleSheet("color: red; font-weight: bold;")
                self.single_buttons[bookmaker_name]['start'].setEnabled(True)
                self.single_buttons[bookmaker_name]['stop'].setEnabled(False)

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Get DB connection."""
        try:
            if not self.db_path or not self.db_path.exists():
                return None
            return sqlite3.connect(str(self.db_path))
        except:
            return None


class BettingAgentStats(QWidget):
    """
    Stats for Betting Agent - PNG REWORK.

    Layout identičan kao Data Collector:
    - TOTAL Stats (gore)
    - GRID Stats (dole) per bookmaker
    """

    start_single = Signal(str)
    stop_single = Signal(str)
    cancel_stop_single = Signal(str)
    instant_stop_single = Signal(str)
    start_all = Signal()
    stop_all = Signal()

    def __init__(self, bookmaker_names: List[str] = None, grid_layout: str = "GRID 2×3"):
        super().__init__()
        self.db_path = PATH.betting_history_db
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-BettingAgent")

        # Bookmaker configuration - DYNAMIC, not hardcoded!
        self.bookmaker_names = bookmaker_names if bookmaker_names else []
        self.grid_layout = grid_layout
        self.bookmaker_statuses = {name: "INACTIVE" for name in self.bookmaker_names}

        self.single_labels = {}
        self.single_buttons = {}

        self.init_ui()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_and_update_stats)
        self.update_timer.start(3000)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QVBoxLayout()

        total_panel = self.create_total_stats_panel()
        main_layout.addWidget(total_panel)

        grid_panel = self.create_grid_stats_panel()
        main_layout.addWidget(grid_panel, stretch=1)

        self.setLayout(main_layout)

    def create_total_stats_panel(self) -> QGroupBox:
        """Create TOTAL stats panel."""
        group = QGroupBox("Betting Stats TOTAL")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #FF9800; }")

        layout = QGridLayout()

        self.lbl_started = QLabel("--:--:--")
        self.lbl_session_duration = QLabel("0h 0m 0s")
        self.lbl_total_bets = QLabel("0")
        self.lbl_error_count = QLabel("0")
        self.lbl_total_profit = QLabel("0.00 RSD")
        self.lbl_profit_per_hour = QLabel("0.00 RSD/h")
        self.lbl_avg_score = QLabel("0.00x")
        self.lbl_big_loss_count = QLabel("0")

        # Layout
        layout.addWidget(QLabel("Started:"), 0, 0)
        layout.addWidget(self.lbl_started, 0, 1)

        layout.addWidget(QLabel("Session Duration:"), 0, 2)
        layout.addWidget(self.lbl_session_duration, 0, 3)

        layout.addWidget(QLabel("Total Bets:"), 1, 0)
        layout.addWidget(self.lbl_total_bets, 1, 1)

        layout.addWidget(QLabel("Error count:"), 1, 2)
        layout.addWidget(self.lbl_error_count, 1, 3)

        layout.addWidget(QLabel("Total Profit:"), 2, 0)
        layout.addWidget(self.lbl_total_profit, 2, 1)

        layout.addWidget(QLabel("Profit / hour:"), 2, 2)
        layout.addWidget(self.lbl_profit_per_hour, 2, 3)

        layout.addWidget(QLabel("Average score:"), 3, 0)
        layout.addWidget(self.lbl_avg_score, 3, 1)

        layout.addWidget(QLabel("Big Loss count:"), 3, 2)
        layout.addWidget(self.lbl_big_loss_count, 3, 3)

        # Buttons
        self.btn_start_all = QPushButton("⏵ START")
        self.btn_cancel_stop_all = QPushButton("⏸ CANCEL STOP")
        self.btn_instant_stop_all = QPushButton("⏹ INSTANT STOP")

        self.btn_start_all.clicked.connect(self.start_all.emit)

        layout.addWidget(self.btn_start_all, 4, 0)
        layout.addWidget(self.btn_cancel_stop_all, 4, 1)
        layout.addWidget(self.btn_instant_stop_all, 4, 2)

        self.lbl_started.setText(self.session_start.strftime("%H:%M:%S"))

        group.setLayout(layout)
        return group

    def create_grid_stats_panel(self) -> QGroupBox:
        """Create GRID per-bookmaker panel."""
        group = QGroupBox("Betting Stats per bookmaker")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #4CAF50; }")

        rows, cols = self.parse_grid_layout(self.grid_layout)
        grid_layout = QGridLayout()

        for idx, bookmaker_name in enumerate(self.bookmaker_names):
            row = idx // cols
            col = idx % cols
            card = self.create_bookmaker_card(bookmaker_name)
            grid_layout.addWidget(card, row, col)

        group.setLayout(grid_layout)
        return group

    def create_bookmaker_card(self, bookmaker_name: str) -> QFrame:
        """Create bookmaker card."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(1)

        layout = QVBoxLayout()

        lbl_name = QLabel(bookmaker_name)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_name)

        lbl_status = QLabel("INACTIVE")
        lbl_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(QLabel("STATUS:"))
        layout.addWidget(lbl_status)

        stats_layout = QGridLayout()

        lbl_balance = QLabel("20,000 RSD")
        lbl_total_profit = QLabel("0 RSD")
        lbl_profit_per_hour = QLabel("0 RSD/h")
        lbl_avg_score = QLabel("0.00x")
        lbl_big_loss = QLabel("0")

        stats_layout.addWidget(QLabel("Balance:"), 0, 0)
        stats_layout.addWidget(lbl_balance, 0, 1)

        stats_layout.addWidget(QLabel("Total Profit:"), 1, 0)
        stats_layout.addWidget(lbl_total_profit, 1, 1)

        stats_layout.addWidget(QLabel("Profit / hour:"), 2, 0)
        stats_layout.addWidget(lbl_profit_per_hour, 2, 1)

        stats_layout.addWidget(QLabel("Average score:"), 3, 0)
        stats_layout.addWidget(lbl_avg_score, 3, 1)

        stats_layout.addWidget(QLabel("Big Loss count:"), 4, 0)
        stats_layout.addWidget(lbl_big_loss, 4, 1)

        layout.addLayout(stats_layout)

        # Buttons
        btn_start = QPushButton("⏵ START")
        btn_cancel = QPushButton("⏸ CANCEL STOP")
        btn_instant = QPushButton("⏹ INSTANT STOP")

        btn_start.clicked.connect(lambda: self.start_single.emit(bookmaker_name))
        btn_cancel.clicked.connect(lambda: self.cancel_stop_single.emit(bookmaker_name))
        btn_instant.clicked.connect(lambda: self.instant_stop_single.emit(bookmaker_name))

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_instant)
        layout.addLayout(btn_layout)

        frame.setLayout(layout)

        self.single_labels[bookmaker_name] = {
            'status': lbl_status,
            'balance': lbl_balance,
            'total_profit': lbl_total_profit,
            'profit_per_hour': lbl_profit_per_hour,
            'avg_score': lbl_avg_score,
            'big_loss': lbl_big_loss
        }

        self.single_buttons[bookmaker_name] = {
            'start': btn_start,
            'cancel': btn_cancel,
            'instant': btn_instant
        }

        return frame

    def parse_grid_layout(self, grid_str: str) -> tuple:
        """Parse grid layout."""
        try:
            parts = grid_str.split()
            if len(parts) == 2:
                dims = parts[1].split('×')
                return int(dims[0]), int(dims[1])
        except:
            pass
        return 2, 3

    def fetch_and_update_stats(self):
        """Fetch betting stats."""
        conn = self.get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*), SUM(profit), AVG(score)
                FROM betting_history WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))

            row = cursor.fetchone()
            total_bets = row[0] or 0
            total_profit = row[1] or 0.0
            avg_score = row[2] or 0.0

            # Calculate profit/hour
            elapsed_hours = (datetime.now() - self.session_start).total_seconds() / 3600.0
            profit_per_hour = total_profit / elapsed_hours if elapsed_hours > 0 else 0.0

            # Session duration
            duration = datetime.now() - self.session_start
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            seconds = duration.seconds % 60

            conn.close()

            # Update UI
            self.lbl_total_bets.setText(f"{total_bets:,}")
            self.lbl_total_profit.setText(f"{total_profit:.2f} RSD")
            self.lbl_profit_per_hour.setText(f"{profit_per_hour:.2f} RSD/h")
            self.lbl_avg_score.setText(f"{avg_score:.2f}x")
            self.lbl_session_duration.setText(f"{hours}h {minutes}m {seconds}s")

        except Exception as e:
            self.logger.debug(f"Stats fetch error: {e}")
            if conn:
                conn.close()

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Get DB connection."""
        try:
            if not self.db_path or not self.db_path.exists():
                return None
            return sqlite3.connect(str(self.db_path))
        except:
            return None


class RGBCollectorStats(QWidget):
    """RGB Collector Stats - TOTAL + GRID layout."""

    start_single = Signal(str)
    stop_single = Signal(str)
    start_all = Signal()
    stop_all = Signal()

    def __init__(self, bookmaker_names: List[str] = None, grid_layout: str = "GRID 2×3"):
        super().__init__()
        self.db_path = PATH.rgb_training_db
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-RGBCollector")

        # Bookmaker configuration - DYNAMIC, not hardcoded!
        self.bookmaker_names = bookmaker_names if bookmaker_names else []
        self.grid_layout = grid_layout

        self.single_labels = {}
        self.single_buttons = {}

        self.init_ui()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_and_update_stats)
        self.update_timer.start(3000)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QVBoxLayout()

        total_panel = self.create_total_stats_panel()
        main_layout.addWidget(total_panel)

        grid_panel = self.create_grid_stats_panel()
        main_layout.addWidget(grid_panel, stretch=1)

        self.setLayout(main_layout)

    def create_total_stats_panel(self) -> QGroupBox:
        """Create TOTAL stats."""
        group = QGroupBox("RGB Collector Stats TOTAL")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #9C27B0; }")

        layout = QGridLayout()

        self.lbl_samples_collected = QLabel("0")
        self.lbl_sample_rate = QLabel("0.0 Hz")
        self.lbl_storage_size = QLabel("0 MB")
        self.lbl_last_sample = QLabel("--:--:--")

        layout.addWidget(QLabel("Samples collected:"), 0, 0)
        layout.addWidget(self.lbl_samples_collected, 0, 1)

        layout.addWidget(QLabel("Sample rate:"), 0, 2)
        layout.addWidget(self.lbl_sample_rate, 0, 3)

        layout.addWidget(QLabel("Storage size:"), 1, 0)
        layout.addWidget(self.lbl_storage_size, 1, 1)

        layout.addWidget(QLabel("Last sample:"), 1, 2)
        layout.addWidget(self.lbl_last_sample, 1, 3)

        # Buttons
        self.btn_start_all = QPushButton("⏵ START")
        self.btn_stop_all = QPushButton("⏹ STOP")

        self.btn_start_all.clicked.connect(self.start_all.emit)
        self.btn_stop_all.clicked.connect(self.stop_all.emit)

        layout.addWidget(self.btn_start_all, 2, 0)
        layout.addWidget(self.btn_stop_all, 2, 1)

        group.setLayout(layout)
        return group

    def create_grid_stats_panel(self) -> QGroupBox:
        """Create GRID panel."""
        group = QGroupBox("RGB Stats per bookmaker")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #4CAF50; }")

        rows, cols = self.parse_grid_layout(self.grid_layout)
        grid_layout = QGridLayout()

        for idx, bookmaker_name in enumerate(self.bookmaker_names):
            row = idx // cols
            col = idx % cols
            card = self.create_bookmaker_card(bookmaker_name)
            grid_layout.addWidget(card, row, col)

        group.setLayout(grid_layout)
        return group

    def create_bookmaker_card(self, bookmaker_name: str) -> QFrame:
        """Create bookmaker card."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(1)

        layout = QVBoxLayout()

        lbl_name = QLabel(bookmaker_name)
        lbl_name.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_name)

        lbl_status = QLabel("INACTIVE")
        lbl_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(QLabel("STATUS:"))
        layout.addWidget(lbl_status)

        stats_layout = QGridLayout()

        lbl_samples = QLabel("0")
        lbl_rate = QLabel("0.0 Hz")

        stats_layout.addWidget(QLabel("Samples:"), 0, 0)
        stats_layout.addWidget(lbl_samples, 0, 1)

        stats_layout.addWidget(QLabel("Rate:"), 1, 0)
        stats_layout.addWidget(lbl_rate, 1, 1)

        layout.addLayout(stats_layout)

        # Buttons
        btn_start = QPushButton("⏵ START")
        btn_stop = QPushButton("⏹ STOP")

        btn_start.clicked.connect(lambda: self.start_single.emit(bookmaker_name))
        btn_stop.clicked.connect(lambda: self.stop_single.emit(bookmaker_name))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_stop)
        layout.addLayout(btn_layout)

        frame.setLayout(layout)

        self.single_labels[bookmaker_name] = {
            'status': lbl_status,
            'samples': lbl_samples,
            'rate': lbl_rate
        }

        self.single_buttons[bookmaker_name] = {
            'start': btn_start,
            'stop': btn_stop
        }

        return frame

    def parse_grid_layout(self, grid_str: str) -> tuple:
        """Parse grid."""
        try:
            parts = grid_str.split()
            if len(parts) == 2:
                dims = parts[1].split('×')
                return int(dims[0]), int(dims[1])
        except:
            pass
        return 2, 3

    def fetch_and_update_stats(self):
        """Fetch RGB stats."""
        conn = self.get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM phase_rgb WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))

            total_samples = cursor.fetchone()[0] or 0

            # Calculate rate
            elapsed_seconds = (datetime.now() - self.session_start).total_seconds()
            sample_rate = total_samples / elapsed_seconds if elapsed_seconds > 0 else 0.0

            conn.close()

            self.lbl_samples_collected.setText(f"{total_samples:,}")
            self.lbl_sample_rate.setText(f"{sample_rate:.1f} Hz")

        except Exception as e:
            self.logger.debug(f"Stats fetch error: {e}")
            if conn:
                conn.close()

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Get DB connection."""
        try:
            if not self.db_path or not self.db_path.exists():
                return None
            return sqlite3.connect(str(self.db_path))
        except:
            return None


class SessionKeeperStats(QWidget):
    """Session Keeper Stats - TOTAL + GRID layout."""

    start_single = Signal(str)
    stop_single = Signal(str)
    start_all = Signal()
    stop_all = Signal()

    def __init__(self, bookmaker_names: List[str] = None, grid_layout: str = "GRID 2×3"):
        super().__init__()
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-SessionKeeper")

        # Bookmaker configuration - DYNAMIC, not hardcoded!
        self.bookmaker_names = bookmaker_names if bookmaker_names else []
        self.grid_layout = grid_layout

        self.single_labels = {}
        self.single_buttons = {}

        self.init_ui()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QVBoxLayout()

        total_panel = self.create_total_stats_panel()
        main_layout.addWidget(total_panel)

        grid_panel = self.create_grid_stats_panel()
        main_layout.addWidget(grid_panel, stretch=1)

        self.setLayout(main_layout)

    def create_total_stats_panel(self) -> QGroupBox:
        """Create TOTAL stats."""
        group = QGroupBox("Session Keeper Stats TOTAL")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #607D8B; }")

        layout = QGridLayout()

        self.lbl_active_sessions = QLabel("0/6")
        self.lbl_total_clicks = QLabel("0")
        self.lbl_avg_interval = QLabel("0s")
        self.lbl_next_click = QLabel("--s")

        layout.addWidget(QLabel("Active sessions:"), 0, 0)
        layout.addWidget(self.lbl_active_sessions, 0, 1)

        layout.addWidget(QLabel("Total clicks sent:"), 0, 2)
        layout.addWidget(self.lbl_total_clicks, 0, 3)

        layout.addWidget(QLabel("Avg interval:"), 1, 0)
        layout.addWidget(self.lbl_avg_interval, 1, 1)

        layout.addWidget(QLabel("Next click in:"), 1, 2)
        layout.addWidget(self.lbl_next_click, 1, 3)

        # Buttons
        self.btn_start_all = QPushButton("⏵ START")
        self.btn_stop_all = QPushButton("⏹ STOP")

        self.btn_start_all.clicked.connect(self.start_all.emit)
        self.btn_stop_all.clicked.connect(self.stop_all.emit)

        layout.addWidget(self.btn_start_all, 2, 0)
        layout.addWidget(self.btn_stop_all, 2, 1)

        group.setLayout(layout)
        return group

    def create_grid_stats_panel(self) -> QGroupBox:
        """Create GRID panel."""
        group = QGroupBox("Session Stats per bookmaker")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #4CAF50; }")

        rows, cols = self.parse_grid_layout(self.grid_layout)
        grid_layout = QGridLayout()

        for idx, bookmaker_name in enumerate(self.bookmaker_names):
            row = idx // cols
            col = idx % cols
            card = self.create_bookmaker_card(bookmaker_name)
            grid_layout.addWidget(card, row, col)

        group.setLayout(grid_layout)
        return group

    def create_bookmaker_card(self, bookmaker_name: str) -> QFrame:
        """Create bookmaker card."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(1)

        layout = QVBoxLayout()

        lbl_name = QLabel(bookmaker_name)
        lbl_name.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_name)

        lbl_status = QLabel("PAUSED")
        lbl_status.setStyleSheet("color: gray; font-weight: bold;")
        layout.addWidget(QLabel("STATUS:"))
        layout.addWidget(lbl_status)

        stats_layout = QGridLayout()

        lbl_clicks = QLabel("0")
        lbl_next_in = QLabel("--")
        lbl_last = QLabel("--")

        stats_layout.addWidget(QLabel("Clicks:"), 0, 0)
        stats_layout.addWidget(lbl_clicks, 0, 1)

        stats_layout.addWidget(QLabel("Next in:"), 1, 0)
        stats_layout.addWidget(lbl_next_in, 1, 1)

        stats_layout.addWidget(QLabel("Last:"), 2, 0)
        stats_layout.addWidget(lbl_last, 2, 1)

        layout.addLayout(stats_layout)

        # Buttons
        btn_start = QPushButton("⏵ START")
        btn_stop = QPushButton("⏹ STOP")

        btn_start.clicked.connect(lambda: self.start_single.emit(bookmaker_name))
        btn_stop.clicked.connect(lambda: self.stop_single.emit(bookmaker_name))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_stop)
        layout.addLayout(btn_layout)

        frame.setLayout(layout)

        self.single_labels[bookmaker_name] = {
            'status': lbl_status,
            'clicks': lbl_clicks,
            'next_in': lbl_next_in,
            'last': lbl_last
        }

        self.single_buttons[bookmaker_name] = {
            'start': btn_start,
            'stop': btn_stop
        }

        return frame

    def parse_grid_layout(self, grid_str: str) -> tuple:
        """Parse grid."""
        try:
            parts = grid_str.split()
            if len(parts) == 2:
                dims = parts[1].split('×')
                return int(dims[0]), int(dims[1])
        except:
            pass
        return 2, 3

    def update_display(self):
        """Update display (placeholder)."""
        # TODO: Implement actual updates from SessionKeeper agents
        pass

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Not needed for SessionKeeper."""
        return None
