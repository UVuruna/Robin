# main.py
# Izmene za main.py da koristi novu arhitekturu
"""
INTEGRATION GUIDE za main.py

Ovaj kod pokazuje kako da integrišeš AppControllerV2 u postojeći main.py
Samo zameni relevantne delove u postojećem fajlu.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPushButton,
    QTextEdit,
    QLabel,
    QSplitter,
    QMessageBox,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFont, QPalette, QColor
from gui.config_manager import ConfigManager
from gui.app_controller import AppController
from gui.setup_dialog import SetupDialog
from gui.stats_widgets import (
    DataCollectorStats,
    RGBCollectorStats,
    BettingAgentStats,
    SessionKeeperStats,
)
from gui.app_controller import AppController
from core.communication.event_bus import EventBus, EventSubscriber, EventType
from gui.tools_tab import ToolsTab
from utils.logger import AviatorLogger

class AviatorControlPanel(QMainWindow):
    """
    Main GUI control panel for Aviator applications.

    Features:
    - Tab-based layout for each app
    - Setup configuration with save/load
    - Live logs streaming (real-time via thread callback)
    - Real-time statistics (DB polling every 2-3 sec)
    - Start/Stop control for each app
    """

    def __init__(self):
        super().__init__()

        self.logger = AviatorLogger.get_logger("GUI")
        self.config_manager = ConfigManager()
        self.app_controller = AppController()

        # Load last config
        self.config = self.config_manager.load_config()

        self.init_ui()
        self.apply_dark_theme()

        self.logger.info("GUI initialized")
        
        self.event_subscriber = EventSubscriber("GUI-Main")
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        """Subscribe to important events for GUI updates"""
        self.event_subscriber.subscribe(EventType.ROUND_END, self._on_round_end_event)
        self.event_subscriber.subscribe(EventType.THRESHOLD_CROSSED, self._on_threshold_event)
        self.event_subscriber.subscribe(EventType.DATA_COLLECTED, self._on_data_collected_event)

    def init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("🎰 Aviator Control Panel v2.0")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Top buttons
        # Top buttons removed - now in Tools tab

        # Tab widget
        self.tabs = QTabWidget()

        # Data Collector tab
        self.tabs.addTab(self.create_app_tab("data_collector"), "📊 Data Collector")

        # RGB Collector tab
        self.tabs.addTab(self.create_app_tab("rgb_collector"), "🎨 RGB Collector")

        # Betting Agent tab
        self.tabs.addTab(self.create_app_tab("betting_agent"), "💰 Betting Agent")

        # Session Keeper tab
        self.tabs.addTab(self.create_app_tab("session_keeper"), "⏰ Session Keeper")

        # Tools tab
        self.tools_tab = ToolsTab(self.config)
        self.tabs.addTab(self.tools_tab, "🛠️ Tools")

        main_layout.addWidget(self.tabs)

    def _on_round_end_event(self, event):
        """Handle round end events from workers"""
        bookmaker = event.data.get('bookmaker')
        score = event.data.get('final_score')
        
        # Update stats widget if it exists
        if hasattr(self, 'data_stats'):
            # Trigger stats refresh
            self.data_stats.fetch_and_update_stats()
        
        # Add to appropriate log
        log_msg = f"[{bookmaker}] Round ended: {score:.2f}x"
        if hasattr(self, 'data_log'):
            self.data_log.append(log_msg)

    def _on_threshold_event(self, event):
        """Handle threshold crossed events"""
        bookmaker = event.data.get('bookmaker')
        threshold = event.data.get('threshold')
        
        log_msg = f"[{bookmaker}] Threshold {threshold}x crossed"
        if hasattr(self, 'data_log'):
            self.data_log.append(log_msg)

    def _on_data_collected_event(self, event):
        """Handle data collection events"""
        bookmaker = event.data.get('bookmaker')
        count = event.data.get('count', 0)
        data_type = event.data.get('type', 'unknown')
    
        # Route to appropriate log
        if data_type == 'rgb' and hasattr(self, 'rgb_log'):
            self.rgb_log.append(f"[{bookmaker}] Collected {count} RGB samples")

    def create_app_tab(self, app_name: str) -> QWidget:
        """
        Create tab for an app.

        Layout: [Stats (left)] | [Logs (right)]
                [Control Buttons (bottom)]
        """
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # Splitter for stats (left) and logs (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Stats widget
        if app_name == "data_collector":
            stats_widget = DataCollectorStats()
            self.data_stats = stats_widget
        elif app_name == "rgb_collector":
            stats_widget = RGBCollectorStats()
            self.rgb_stats = stats_widget
        elif app_name == "betting_agent":
            stats_widget = BettingAgentStats()
            self.betting_stats = stats_widget
        elif app_name == "session_keeper":
            stats_widget = SessionKeeperStats()
            self.keeper_stats = stats_widget
        else:
            stats_widget = QLabel("No stats available")

        splitter.addWidget(stats_widget)

        # Right: Logs
        log_widget = QTextEdit()
        log_widget.setReadOnly(True)
        log_widget.setFont(QFont("Courier New", 9))
        log_widget.setPlaceholderText(f"Logs for {app_name} will appear here...")

        # Store log widget reference
        if app_name == "data_collector":
            self.data_log = log_widget
        elif app_name == "rgb_collector":
            self.rgb_log = log_widget
        elif app_name == "betting_agent":
            self.betting_log = log_widget
        elif app_name == "session_keeper":
            self.keeper_log = log_widget

        splitter.addWidget(log_widget)

        # Set splitter sizes (30% stats, 70% logs)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

        # Bottom: Control buttons
        layout.addLayout(self.create_control_buttons(app_name))

        return widget

    def create_control_buttons(self, app_name: str) -> QHBoxLayout:
        """Create START/STOP buttons for app."""
        layout = QHBoxLayout()

        if app_name == "data_collector":
            self.btn_start_data = QPushButton("▶️ START")
            self.btn_stop_data = QPushButton("⏹️ STOP")
            self.btn_stop_data.setEnabled(False)

            self.btn_start_data.clicked.connect(self.start_data_collector)
            self.btn_stop_data.clicked.connect(self.stop_data_collector)

            layout.addWidget(self.btn_start_data)
            layout.addWidget(self.btn_stop_data)

        elif app_name == "rgb_collector":
            self.btn_start_rgb = QPushButton("▶️ START")
            self.btn_stop_rgb = QPushButton("⏹️ STOP")
            self.btn_stop_rgb.setEnabled(False)

            self.btn_start_rgb.clicked.connect(self.start_rgb_collector)
            self.btn_stop_rgb.clicked.connect(self.stop_rgb_collector)

            layout.addWidget(self.btn_start_rgb)
            layout.addWidget(self.btn_stop_rgb)

        elif app_name == "betting_agent":
            self.btn_start_betting = QPushButton("▶️ START")
            self.btn_stop_betting_graceful = QPushButton("🛑 GRACEFUL STOP")
            self.btn_stop_betting_instant = QPushButton("⚡ INSTANT STOP")

            self.btn_stop_betting_graceful.setEnabled(False)
            self.btn_stop_betting_instant.setEnabled(False)

            self.btn_start_betting.clicked.connect(self.start_betting_agent)
            self.btn_stop_betting_graceful.clicked.connect(
                self.stop_betting_agent_graceful
            )
            self.btn_stop_betting_instant.clicked.connect(
                self.stop_betting_agent_instant
            )

            layout.addWidget(self.btn_start_betting)
            layout.addWidget(self.btn_stop_betting_graceful)
            layout.addWidget(self.btn_stop_betting_instant)

        elif app_name == "session_keeper":
            self.btn_start_keeper = QPushButton("▶️ START")
            self.btn_stop_keeper = QPushButton("⏹️ STOP")
            self.btn_stop_keeper.setEnabled(False)

            self.btn_start_keeper.clicked.connect(self.start_session_keeper)
            self.btn_stop_keeper.clicked.connect(self.stop_session_keeper)

            layout.addWidget(self.btn_start_keeper)
            layout.addWidget(self.btn_stop_keeper)

        layout.addStretch()
        return layout

    # ========================================================================
    # LOG CALLBACK - Real-time log streaming
    # ========================================================================

    def on_log_received(self, app_name: str, log_line: str):
        """
        Callback for real-time log updates from background thread.
        Thread-safe - Qt handles cross-thread signals automatically.

        Args:
            app_name: Name of the app sending the log
            log_line: Log line text
        """
        # Find the right log widget
        if app_name == "data_collector":
            widget = self.data_log
        elif app_name == "rgb_collector":
            widget = self.rgb_log
        elif app_name == "betting_agent":
            widget = self.betting_log
        elif app_name == "session_keeper":
            widget = self.keeper_log
        else:
            return

        # Append log (thread-safe in Qt)
        widget.append(log_line)

        # Auto-scroll to bottom
        scrollbar = widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ========================================================================
    # APP CONTROLS
    # ========================================================================

    def start_data_collector(self):
        """Start Data Collector with new architecture."""
        if not self.config.get("bookmakers"):
            # Show setup dialog first
            self.open_setup_dialog()
            if not self.config.get("bookmakers"):
                QMessageBox.warning(self, "No Config", "Setup cancelled!")
                return
        
        # Prepare bookmakers config with coordinates
        bookmakers_config = []
        for bm in self.config.get("bookmakers", []):
            # Get coordinates from coord_manager
            coords = self.coords_manager.calculate_coords(
                self.config.get("layout", "layout_6"),
                bm["position"],
                self.config.get("dual_monitor", False)
            )
            
            if coords:
                bookmakers_config.append({
                    "name": bm["name"],
                    "position": bm["position"],
                    "coords": coords
                })
        
        # Update config with coordinates
        self.config["bookmakers"] = bookmakers_config
        
        success = self.app_controller.start_app(
            "data_collector",
            self.config,
            log_callback=self.on_log_received,
        )

        if success:
            self.btn_start_data.setEnabled(False)
            self.btn_stop_data.setEnabled(True)
            self.data_log.append("=== Data Collector Started (V2 Architecture) ===\n")
            self.data_log.append(f"Tracking {len(bookmakers_config)} bookmakers")
            
            # Show performance info
            self.data_log.append("\n📊 Performance Mode:")
            self.data_log.append("  • OCR: Shared Reader (optimized)")
            self.data_log.append("  • Database: Batch Writer (50x faster)")
            self.data_log.append("  • Communication: Event Bus")

    def stop_data_collector(self):
        """Stop Data Collector and show statistics."""
        # Get final stats before stopping
        stats = self.app_controller.get_worker_status("data_collector")
        
        self.app_controller.stop_app("data_collector")
        self.btn_start_data.setEnabled(True)
        self.btn_stop_data.setEnabled(False)
        
        # Show statistics
        if stats.get("workers"):
            self.data_log.append("\n📊 Final Statistics:")
            for worker_name, worker_stats in stats["workers"].items():
                if worker_stats:
                    self.data_log.append(f"  {worker_name}:")
                    self.data_log.append(f"    • Uptime: {worker_stats.get('uptime', 0):.0f}s")
                    self.data_log.append(f"    • Restarts: {worker_stats.get('restart_count', 0)}")
        
        self.data_log.append("\n=== Data Collector Stopped ===")

    def show_system_stats(self):
        """Show overall system statistics in a dialog"""
        stats = self.app_controller.get_stats()
        
        stats_text = "🎯 SYSTEM STATISTICS\n" + "="*50 + "\n\n"
        
        # Process manager stats
        if 'process_manager' in stats:
            pm = stats['process_manager']
            stats_text += "📦 Process Manager:\n"
            stats_text += f"  • Total started: {pm.get('total_started', 0)}\n"
            stats_text += f"  • Total crashed: {pm.get('total_crashed', 0)}\n"
            stats_text += f"  • Total restarted: {pm.get('total_restarted', 0)}\n\n"
        
        # Event bus stats
        if 'event_bus' in stats:
            eb = stats['event_bus']
            stats_text += "📨 Event Bus:\n"
            stats_text += f"  • Events sent: {eb.get('events_sent', 0)}\n"
            stats_text += f"  • Events processed: {eb.get('events_processed', 0)}\n"
            stats_text += f"  • Events failed: {eb.get('events_failed', 0)}\n

    def start_rgb_collector(self):
        """Start RGB Collector."""
        if not self.config.get("bookmakers"):
            QMessageBox.warning(self, "No Config", "Setup bookmakers first!")
            return

        success = self.app_controller.start_app(
            "rgb_collector", self.config, log_callback=self.on_log_received
        )

        if success:
            self.btn_start_rgb.setEnabled(False)
            self.btn_stop_rgb.setEnabled(True)
            self.rgb_log.append("=== RGB Collector Started ===\n")

    def stop_rgb_collector(self):
        """Stop RGB Collector."""
        self.app_controller.stop_app("rgb_collector")
        self.btn_start_rgb.setEnabled(True)
        self.btn_stop_rgb.setEnabled(False)
        self.rgb_log.append("\n=== RGB Collector Stopped ===")

    def start_betting_agent(self):
        """Start Betting Agent."""
        if not self.config.get("bookmakers"):
            QMessageBox.warning(self, "No Config", "Setup bookmakers first!")
            return

        if not self.config.get("betting_agent"):
            QMessageBox.warning(self, "No Config", "Configure Betting Agent first!")
            return

        success = self.app_controller.start_app(
            "betting_agent", self.config, log_callback=self.on_log_received
        )

        if success:
            self.btn_start_betting.setEnabled(False)
            self.btn_stop_betting_graceful.setEnabled(True)
            self.btn_stop_betting_instant.setEnabled(True)
            self.betting_log.append("=== Betting Agent Started ===\n")

    def stop_betting_agent_graceful(self):
        """Stop Betting Agent (graceful - finish current cycle)."""
        # TODO: Implement graceful stop signal via file/queue
        self.app_controller.stop_app("betting_agent", force=False)
        self.btn_start_betting.setEnabled(True)
        self.btn_stop_betting_graceful.setEnabled(False)
        self.btn_stop_betting_instant.setEnabled(False)
        self.betting_log.append("\n=== Betting Agent Stopped (Graceful) ===")

    def stop_betting_agent_instant(self):
        """Stop Betting Agent (instant - kill immediately)."""
        self.app_controller.stop_app("betting_agent", force=True)
        self.btn_start_betting.setEnabled(True)
        self.btn_stop_betting_graceful.setEnabled(False)
        self.btn_stop_betting_instant.setEnabled(False)
        self.betting_log.append("\n=== Betting Agent Stopped (Instant) ===")

    def start_session_keeper(self):
        """Start Session Keeper."""
        if not self.config.get("bookmakers"):
            QMessageBox.warning(self, "No Config", "Setup bookmakers first!")
            return

        success = self.app_controller.start_app(
            "session_keeper", self.config, log_callback=self.on_log_received
        )

        if success:
            self.btn_start_keeper.setEnabled(False)
            self.btn_stop_keeper.setEnabled(True)
            self.keeper_log.append("=== Session Keeper Started ===\n")

    def stop_session_keeper(self):
        """Stop Session Keeper."""
        self.app_controller.stop_app("session_keeper")
        self.btn_start_keeper.setEnabled(True)
        self.btn_stop_keeper.setEnabled(False)
        self.keeper_log.append("\n=== Session Keeper Stopped ===")

    # ========================================================================
    # CONFIG MANAGEMENT
    # ========================================================================

    def open_setup_dialog(self):
        """Open setup configuration dialog."""
        dialog = SetupDialog(self.config, self)
        if dialog.exec():
            self.config = dialog.get_config()
            QMessageBox.information(
                self,
                "Setup Complete",
                "Configuration updated! Click 'Save Setup' to persist.",
            )

    def save_config(self):
        """Save current config to file."""
        if self.config_manager.save_config(self.config):
            QMessageBox.information(self, "Saved", "Configuration saved to config.json")
        else:
            QMessageBox.warning(self, "Error", "Failed to save configuration")

    def load_config(self):
        """Load config from file."""
        self.config = self.config_manager.load_config()
        if self.config:
            QMessageBox.information(
                self, "Loaded", "Configuration loaded from config.json"
            )
        else:
            QMessageBox.warning(self, "Error", "No saved configuration found")

    # ========================================================================
    # THEME
    # ========================================================================

    def apply_dark_theme(self):
        """Apply dark theme to GUI."""
        app: QApplication = QApplication.instance()
        app.setStyle("Fusion")

        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        app.setPalette(dark_palette)

    # ========================================================================
    # CLEANUP
    # ========================================================================

    def closeEvent(self, event: QEvent):
        """Handle window close - stop all apps."""
        reply = QMessageBox.question(
            self,
            "Quit?",
            "Stop all running apps and quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("Shutting down - stopping all apps...")
            self.app_controller.stop_all()
            event.accept()
        else:
            event.ignore()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = AviatorControlPanel()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
