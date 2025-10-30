"""GUI components for AVIATOR Control Panel."""
from gui.app_controller import AppController
from gui.config_manager import ConfigManager
from gui.setup_dialog import SetupDialog
from gui.stats_widgets import (
    DataCollectorStats,
    RGBCollectorStats,
    BettingAgentStats,
    SessionKeeperStats
)
from gui.tools_tab import ToolsTab
from gui.settings_tab import SettingsTab

__all__ = [
    'AppController',
    'ConfigManager',
    'SetupDialog',
    'DataCollectorStats',
    'RGBCollectorStats',
    'BettingAgentStats',
    'SessionKeeperStats',
    'ToolsTab',
    'SettingsTab'
]