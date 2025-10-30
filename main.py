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
    QTabWidget,
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
from core.communication.event_bus import EventSubscriber, EventType
from gui.tools_tab import ToolsTab
from gui.settings_tab import SettingsTab
from utils.logger import AviatorLogger
from core.capture.region_manager import RegionManager

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
        self.region_manager = RegionManager()  # For coordinate calculation

        # Load config - PROPERLY constructed from new split files
        self._load_config_from_manager()

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

    def _load_config_from_manager(self):
        """Load config from split ConfigManager files into unified self.config dict."""
        last_setup_data = self.config_manager._load_json(self.config_manager.last_setup_file)
        betting_data = self.config_manager.get_betting_agent_config()
        presets_data = self.config_manager.get_bookmaker_presets()
        
        # Construct unified config dict (for backward compatibility with existing code)
        self.config = {
            'last_setup': last_setup_data.get('last_setup'),
            'session_keeper': last_setup_data.get('session_keeper', {'interval': 600}),
            'tools_setup': last_setup_data.get('tools_setup', {}),
            'tools_last': last_setup_data.get('tools_last', {}),
            'betting_agent': betting_data,
            'bookmaker_presets': presets_data,
            'bookmakers': last_setup_data.get('last_setup', {}).get('bookmakers', []) if last_setup_data.get('last_setup') else [],
            'layout': last_setup_data.get('tools_last', {}).get('layout', 'GRID 2×3'),
            'target_monitor': last_setup_data.get('last_setup', {}).get('target_monitor', 'primary') if last_setup_data.get('last_setup') else 'primary'
        }

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

        # Settings tab
        self.settings_tab = SettingsTab(self.config)
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")

        # Connect settings changed signal
        self.settings_tab.settings_changed.connect(self.on_settings_changed)

        # Tools tab
        self.tools_tab = ToolsTab(self.config)
        self.tabs.addTab(self.tools_tab, "🛠️ Tools")

        main_layout.addWidget(self.tabs)

    def on_settings_changed(self, settings):
        """Handle settings changes from Settings tab."""
        # Update config with new settings
        self.config['ocr_method'] = settings.get('ocr_method', 'TESSERACT')
        self.config['image_saving'] = settings.get('image_saving', {})

        # Reload Tools tab to reflect new settings
        if hasattr(self, 'tools_tab'):
            self.tools_tab.load_current_settings()

        self.logger.info(f"Settings updated: OCR={settings.get('ocr_method')}")

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

        Layout: [Stats (left 65-70%)] | [Logs (right 30-35%)]
        NO bottom buttons - buttons are in TOTAL panel inside stats widgets!
        """
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # Splitter for stats (left) and logs (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Extract bookmaker names and grid layout from config
        bookmaker_names = []
        if self.config.get("bookmakers"):
            bookmaker_names = [bm["name"] for bm in self.config["bookmakers"]]
        elif self.config.get("tools_setup", {}).get("bookmakers"):
            # Fallback to tools_setup if last_setup not available
            bookmakers_dict = self.config["tools_setup"]["bookmakers"]
            bookmaker_names = list(bookmakers_dict.values())

        grid_layout = self.config.get("layout", "GRID 2×3")

        # Left: Stats widget (DYNAMIC - reads from config!)
        if app_name == "data_collector":
            stats_widget = DataCollectorStats(bookmaker_names=bookmaker_names, grid_layout=grid_layout)
            self.data_stats = stats_widget
            # Connect signals
            stats_widget.start_all.connect(self.start_data_collector)
            stats_widget.stop_all.connect(self.stop_data_collector)
        elif app_name == "rgb_collector":
            stats_widget = RGBCollectorStats(bookmaker_names=bookmaker_names, grid_layout=grid_layout)
            self.rgb_stats = stats_widget
            # Connect signals
            stats_widget.start_all.connect(self.start_rgb_collector)
            stats_widget.stop_all.connect(self.stop_rgb_collector)
        elif app_name == "betting_agent":
            stats_widget = BettingAgentStats(bookmaker_names=bookmaker_names, grid_layout=grid_layout)
            self.betting_stats = stats_widget
            # Connect signals
            stats_widget.start_all.connect(self.start_betting_agent)
            stats_widget.instant_stop_single.connect(self.stop_betting_agent_instant)
        elif app_name == "session_keeper":
            stats_widget = SessionKeeperStats(bookmaker_names=bookmaker_names, grid_layout=grid_layout)
            self.keeper_stats = stats_widget
            # Connect signals
            stats_widget.start_all.connect(self.start_session_keeper)
            stats_widget.stop_all.connect(self.stop_session_keeper)
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

        # Set splitter sizes (65% stats, 35% logs) - user requested 30-35% for logs on RIGHT
        splitter.setSizes([650, 350])

        layout.addWidget(splitter)

        # NO bottom buttons - they are now in TOTAL panel inside stats widgets!

        return widget


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

        # Calculate coordinates for each bookmaker
        bookmakers_config = []
        layout = self.config.get("layout", "GRID 2×3")
        target_monitor = self.config.get("target_monitor", "primary")

        for bm in self.config.get("bookmakers", []):
            # Calculate coordinates based on position
            coords = self.region_manager.get_bookmaker_regions(
                layout=layout,
                position=bm.get("position", 1),
                target_monitor=target_monitor
            )

            if coords:
                bookmakers_config.append({
                    "name": bm["name"],
                    "position": bm.get("position", 1),
                    "coords": coords
                })

        success = self.app_controller.start_app(
            "data_collector",
            self.config,
            log_callback=self.on_log_received,
        )

        if success:
            # Update button states in stats widget
            if hasattr(self, 'data_stats'):
                self.data_stats.btn_start_all.setEnabled(False)
                self.data_stats.btn_stop_all.setEnabled(True)

            self.data_log.append("=== Data Collector Started (v3.0 Architecture) ===\n")
            self.data_log.append(f"Tracking {len(bookmakers_config)} bookmakers")

            # Show performance info
            self.data_log.append("\n📊 Performance Mode (v3.0):")
            self.data_log.append("  • OCR: PARALLEL (each worker has own)")
            self.data_log.append("  • Database: Shared Batch Writer per TYPE")
            self.data_log.append("  • Communication: Event Bus")

    def stop_data_collector(self):
        """Stop Data Collector and show statistics."""
        # Get final stats before stopping
        stats = self.app_controller.get_worker_status("data_collector")

        self.app_controller.stop_app("data_collector")

        # Update button states in stats widget
        if hasattr(self, 'data_stats'):
            self.data_stats.btn_start_all.setEnabled(True)
            self.data_stats.btn_stop_all.setEnabled(False)

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
            stats_text += f"  • Events failed: {eb.get('events_failed', 0)}\n\n"

    def start_rgb_collector(self):
        """Start RGB Collector."""
        if not self.config.get("bookmakers"):
            QMessageBox.warning(self, "No Config", "Setup bookmakers first!")
            return

        success = self.app_controller.start_app(
            "rgb_collector", self.config, log_callback=self.on_log_received
        )

        if success:
            # Update button states in stats widget
            if hasattr(self, 'rgb_stats'):
                self.rgb_stats.btn_start_all.setEnabled(False)
                self.rgb_stats.btn_stop_all.setEnabled(True)

            self.rgb_log.append("=== RGB Collector Started ===\n")

    def stop_rgb_collector(self):
        """Stop RGB Collector."""
        self.app_controller.stop_app("rgb_collector")

        # Update button states in stats widget
        if hasattr(self, 'rgb_stats'):
            self.rgb_stats.btn_start_all.setEnabled(True)
            self.rgb_stats.btn_stop_all.setEnabled(False)

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
            # Update button states in stats widget
            if hasattr(self, 'betting_stats'):
                self.betting_stats.btn_start_all.setEnabled(False)
                self.betting_stats.btn_cancel_stop_all.setEnabled(True)
                self.betting_stats.btn_instant_stop_all.setEnabled(True)

            self.betting_log.append("=== Betting Agent Started ===\n")

    def stop_betting_agent_graceful(self):
        """Stop Betting Agent (graceful - finish current cycle)."""
        # TODO: Implement graceful stop signal via file/queue
        self.app_controller.stop_app("betting_agent", force=False)

        # Update button states in stats widget
        if hasattr(self, 'betting_stats'):
            self.betting_stats.btn_start_all.setEnabled(True)
            self.betting_stats.btn_cancel_stop_all.setEnabled(False)
            self.betting_stats.btn_instant_stop_all.setEnabled(False)

        self.betting_log.append("\n=== Betting Agent Stopped (Graceful) ===")

    def stop_betting_agent_instant(self):
        """Stop Betting Agent (instant - kill immediately)."""
        self.app_controller.stop_app("betting_agent", force=True)

        # Update button states in stats widget
        if hasattr(self, 'betting_stats'):
            self.betting_stats.btn_start_all.setEnabled(True)
            self.betting_stats.btn_cancel_stop_all.setEnabled(False)
            self.betting_stats.btn_instant_stop_all.setEnabled(False)

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
            # Update button states in stats widget
            if hasattr(self, 'keeper_stats'):
                self.keeper_stats.btn_start_all.setEnabled(False)
                self.keeper_stats.btn_stop_all.setEnabled(True)

            self.keeper_log.append("=== Session Keeper Started ===\n")

    def stop_session_keeper(self):
        """Stop Session Keeper."""
        self.app_controller.stop_app("session_keeper")

        # Update button states in stats widget
        if hasattr(self, 'keeper_stats'):
            self.keeper_stats.btn_start_all.setEnabled(True)
            self.keeper_stats.btn_stop_all.setEnabled(False)

        self.keeper_log.append("\n=== Session Keeper Stopped ===")

    # ========================================================================
    # CONFIG MANAGEMENT
    # ========================================================================

    def open_setup_dialog(self):
        """Open setup configuration dialog."""
        dialog = SetupDialog(self.config, self)
        if dialog.exec():
            # Reload config from ConfigManager after dialog changes
            self._load_config_from_manager()
            QMessageBox.information(
                self,
                "Setup Complete",
                "Configuration updated! Click 'Save Setup' to persist.",
            )

    # Config methods removed - use config_manager directly:
    # - self.config_manager.get_betting_agent_config()
    # - self.config_manager.update_betting_agent_config(bet, stop)
    # - self.config_manager.get_last_setup()
    # - self.config_manager.update_last_setup(monitor, bookmakers)

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
