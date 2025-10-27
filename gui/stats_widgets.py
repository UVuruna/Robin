# gui/stats_widgets.py
# VERSION: 3.1 - COMPLETE with all 4 stats classes

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QGroupBox, QGridLayout
)
from PySide6.QtCore import QTimer
import sqlite3
from datetime import datetime
from typing import Dict, Optional
from config.settings import PATH
from utils.logger import AviatorLogger

class DataCollectorStats(QWidget):
    """Stats for Main Data Collector - with performance metrics."""

    def __init__(self):
        super().__init__()
        self.db_path = PATH.main_game_db
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-DataCollector")
        
        self.last_round_count = 0
        self.last_check_time = datetime.now()
        
        self.init_ui()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_and_update_stats)
        self.update_timer.start(2000)

    def init_ui(self):
        """Initialize UI with 50-50 split."""
        main_layout = QHBoxLayout()
        
        perf_group = self.create_performance_panel()
        session_group = self.create_session_panel()
        
        main_layout.addWidget(perf_group, stretch=1)
        main_layout.addWidget(session_group, stretch=1)
        
        self.setLayout(main_layout)

    def create_performance_panel(self) -> QGroupBox:
        """Create performance metrics panel."""
        group = QGroupBox("⚡ Performance")
        layout = QGridLayout()
        
        self.lbl_rounds_per_min = QLabel("0.0")
        self.lbl_thresholds_per_min = QLabel("0.0")
        self.lbl_state = QLabel("IDLE")
        self.lbl_last_round = QLabel("--:--:--")
        
        layout.addWidget(QLabel("Rounds/min:"), 0, 0)
        layout.addWidget(self.lbl_rounds_per_min, 0, 1)
        
        layout.addWidget(QLabel("Thresholds/min:"), 1, 0)
        layout.addWidget(self.lbl_thresholds_per_min, 1, 1)
        
        layout.addWidget(QLabel("State:"), 2, 0)
        layout.addWidget(self.lbl_state, 2, 1)
        
        layout.addWidget(QLabel("Last Round:"), 3, 0)
        layout.addWidget(self.lbl_last_round, 3, 1)
        
        self.lbl_state.setStyleSheet("font-weight: bold; color: #4CAF50;")
        
        group.setLayout(layout)
        return group

    def create_session_panel(self) -> QGroupBox:
        """Create session statistics panel."""
        group = QGroupBox("📊 Session Stats")
        layout = QGridLayout()
        
        self.lbl_session_start = QLabel("--:--:--")
        self.lbl_total_rounds = QLabel("0")
        self.lbl_total_thresholds = QLabel("0")
        self.lbl_avg_score = QLabel("0.00x")
        
        layout.addWidget(QLabel("Started:"), 0, 0)
        layout.addWidget(self.lbl_session_start, 0, 1)
        
        layout.addWidget(QLabel("Total Rounds:"), 1, 0)
        layout.addWidget(self.lbl_total_rounds, 1, 1)
        
        layout.addWidget(QLabel("Total Thresholds:"), 2, 0)
        layout.addWidget(self.lbl_total_thresholds, 2, 1)
        
        layout.addWidget(QLabel("Avg Score:"), 3, 0)
        layout.addWidget(self.lbl_avg_score, 3, 1)
        
        self.lbl_session_start.setText(self.session_start.strftime("%H:%M:%S"))
        
        group.setLayout(layout)
        return group

    def fetch_and_update_stats(self):
        """Fetch stats from DB."""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*), AVG(final_score)
                FROM rounds WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))
            
            row = cursor.fetchone()
            total_rounds = row[0] or 0
            avg_score = row[1] or 0.0
            
            cursor.execute("""
                SELECT COUNT(*) FROM threshold_scores WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))
            total_thresholds = cursor.fetchone()[0] or 0
            
            conn.close()
            
            self.update_display({
                'total_rounds': total_rounds,
                'total_thresholds': total_thresholds,
                'avg_score': avg_score
            })
            
        except Exception as e:
            self.logger.error(f"Stats fetch error: {e}")
            if conn:
                conn.close()

    def update_display(self, stats: Dict):
        """Update UI."""
        self.lbl_total_rounds.setText(str(stats['total_rounds']))
        self.lbl_total_thresholds.setText(str(stats['total_thresholds']))
        self.lbl_avg_score.setText(f"{stats['avg_score']:.2f}x")

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Get DB connection."""
        try:
            if not self.db_path or not self.db_path.exists():
                return None
            return sqlite3.connect(str(self.db_path))
        except:
            return None


class RGBCollectorStats(QWidget):
    """Stats for RGB Collector."""

    def __init__(self):
        super().__init__()
        self.db_path = PATH.rgb_training_db
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-RGBCollector")
        
        self.init_ui()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_and_update_stats)
        self.update_timer.start(3000)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QVBoxLayout()
        
        group = QGroupBox("📊 RGB Collection Stats")
        layout = QGridLayout()
        
        self.lbl_session_start = QLabel("--:--:--")
        self.lbl_total_samples = QLabel("0")
        self.lbl_samples_per_sec = QLabel("0.0")
        
        layout.addWidget(QLabel("Started:"), 0, 0)
        layout.addWidget(self.lbl_session_start, 0, 1)
        
        layout.addWidget(QLabel("Total Samples:"), 1, 0)
        layout.addWidget(self.lbl_total_samples, 1, 1)
        
        layout.addWidget(QLabel("Samples/sec:"), 2, 0)
        layout.addWidget(self.lbl_samples_per_sec, 2, 1)
        
        self.lbl_session_start.setText(self.session_start.strftime("%H:%M:%S"))
        
        group.setLayout(layout)
        main_layout.addWidget(group)
        self.setLayout(main_layout)

    def fetch_and_update_stats(self):
        """Fetch stats from DB."""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM phase_rgb WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))
            
            total_samples = cursor.fetchone()[0] or 0
            
            conn.close()
            
            self.update_display({'total_samples': total_samples})
            
        except Exception as e:
            self.logger.error(f"Stats fetch error: {e}")
            if conn:
                conn.close()

    def update_display(self, stats: Dict):
        """Update UI."""
        self.lbl_total_samples.setText(f"{stats['total_samples']:,}")

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Get DB connection."""
        try:
            if not self.db_path or not self.db_path.exists():
                return None
            return sqlite3.connect(str(self.db_path))
        except:
            return None


class BettingAgentStats(QWidget):
    """Stats for Betting Agent."""

    def __init__(self):
        super().__init__()
        self.db_path = PATH.betting_history_db
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-BettingAgent")
        
        self.init_ui()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_and_update_stats)
        self.update_timer.start(3000)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QVBoxLayout()
        
        group = QGroupBox("📊 Betting Stats")
        layout = QGridLayout()
        
        self.lbl_session_start = QLabel("--:--:--")
        self.lbl_total_bets = QLabel("0")
        self.lbl_total_profit = QLabel("0.00")
        self.lbl_win_rate = QLabel("0%")
        
        layout.addWidget(QLabel("Started:"), 0, 0)
        layout.addWidget(self.lbl_session_start, 0, 1)
        
        layout.addWidget(QLabel("Total Bets:"), 1, 0)
        layout.addWidget(self.lbl_total_bets, 1, 1)
        
        layout.addWidget(QLabel("Total Profit:"), 2, 0)
        layout.addWidget(self.lbl_total_profit, 2, 1)
        
        layout.addWidget(QLabel("Win Rate:"), 3, 0)
        layout.addWidget(self.lbl_win_rate, 3, 1)
        
        self.lbl_session_start.setText(self.session_start.strftime("%H:%M:%S"))
        
        group.setLayout(layout)
        main_layout.addWidget(group)
        self.setLayout(main_layout)

    def fetch_and_update_stats(self):
        """Fetch stats from DB."""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*), SUM(profit)
                FROM betting_history WHERE timestamp >= ?
            """, (self.session_start.isoformat(),))
            
            row = cursor.fetchone()
            total_bets = row[0] or 0
            total_profit = row[1] or 0.0
            
            conn.close()
            
            self.update_display({
                'total_bets': total_bets,
                'total_profit': total_profit
            })
            
        except Exception as e:
            self.logger.error(f"Stats fetch error: {e}")
            if conn:
                conn.close()

    def update_display(self, stats: Dict):
        """Update UI."""
        self.lbl_total_bets.setText(str(stats['total_bets']))
        self.lbl_total_profit.setText(f"{stats['total_profit']:.2f}")

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Get DB connection."""
        try:
            if not self.db_path or not self.db_path.exists():
                return None
            return sqlite3.connect(str(self.db_path))
        except:
            return None


class SessionKeeperStats(QWidget):
    """Stats for Session Keeper."""

    def __init__(self):
        super().__init__()
        self.session_start = datetime.now()
        self.logger = AviatorLogger.get_logger("Stats-SessionKeeper")
        
        self.init_ui()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

    def init_ui(self):
        """Initialize UI."""
        main_layout = QVBoxLayout()
        
        group = QGroupBox("📊 Session Keeper Stats")
        layout = QGridLayout()
        
        self.lbl_session_start = QLabel("--:--:--")
        self.lbl_session_duration = QLabel("00:00:00")
        self.lbl_clicks_sent = QLabel("0")
        self.lbl_last_click = QLabel("--:--:--")
        
        layout.addWidget(QLabel("Started:"), 0, 0)
        layout.addWidget(self.lbl_session_start, 0, 1)
        
        layout.addWidget(QLabel("Duration:"), 1, 0)
        layout.addWidget(self.lbl_session_duration, 1, 1)
        
        layout.addWidget(QLabel("Clicks Sent:"), 2, 0)
        layout.addWidget(self.lbl_clicks_sent, 2, 1)
        
        layout.addWidget(QLabel("Last Click:"), 3, 0)
        layout.addWidget(self.lbl_last_click, 3, 1)
        
        self.lbl_session_start.setText(self.session_start.strftime("%H:%M:%S"))
        
        group.setLayout(layout)
        main_layout.addWidget(group)
        self.setLayout(main_layout)

    def update_display(self):
        """Update UI."""
        now = datetime.now()
        duration = (now - self.session_start).total_seconds()
        
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        self.lbl_session_duration.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")