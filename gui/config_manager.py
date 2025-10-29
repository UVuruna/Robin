# gui/config_manager.py
# VERSION: 2.0 - Split config files (last_setup, betting_agent, bookmaker_presets)
# PURPOSE: Manage user configuration files

import json
from config.settings import PATH
from typing import Dict, Any, Optional
from utils.logger import AviatorLogger

class ConfigManager:
    """
    Manages user configuration files in config/user/ folder.

    Now split into 3 separate files:
    - last_setup.json: Last GUI setup (layout, monitor, bookmakers)
    - betting_agent.json: Betting agent settings (bet_amount, auto_stop)
    - bookmaker_presets.json: User-defined bookmaker layout presets
    """

    def __init__(self):
        self.logger = AviatorLogger.get_logger("ConfigManager")

        # User config files
        self.last_setup_file = PATH.last_setup
        self.betting_agent_file = PATH.betting_agent_config
        self.bookmaker_presets_file = PATH.bookmaker_presets

        # Create default configs if not exist
        self._ensure_user_configs()

    def _ensure_user_configs(self):
        """Create default user config files if they don't exist."""
        # last_setup.json
        if not self.last_setup_file.exists():
            default_last_setup = {
                "last_setup": None,
                "session_keeper": {"interval": 600},
                "tools_setup": {
                    "layout": "layout_6",
                    "position": "TL",
                    "dual_monitor": True,
                    "bookmakers": {}
                },
                "tools_last": {
                    "layout": "layout_6",
                    "position": "TL",
                    "dual_monitor": True,
                    "preset": "main"
                }
            }
            self._save_json(self.last_setup_file, default_last_setup)
            self.logger.info("Created default last_setup.json")

        # betting_agent.json
        if not self.betting_agent_file.exists():
            default_betting = {"bet_amount": 10.0, "auto_stop": 2.0}
            self._save_json(self.betting_agent_file, default_betting)
            self.logger.info("Created default betting_agent.json")

        # bookmaker_presets.json
        if not self.bookmaker_presets_file.exists():
            default_presets = {"layout_6": {"main": {}, "secondary": {}}}
            self._save_json(self.bookmaker_presets_file, default_presets)
            self.logger.info("Created default bookmaker_presets.json")

    def _load_json(self, file_path) -> Dict[str, Any]:
        """Load JSON file with error handling."""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {file_path}")
            self._ensure_user_configs()
            return self._load_json(file_path)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {file_path}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading {file_path}: {e}")
            raise

    def _save_json(self, file_path, data: Dict[str, Any]):
        """Save JSON file with compact format."""
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

            self.logger.info(f"Saved {file_path.name}")
        except Exception as e:
            self.logger.error(f"Error saving {file_path}: {e}")
            raise

    # === LAST SETUP ===

    def get_last_setup(self) -> Optional[Dict[str, Any]]:
        """Get last setup configuration."""
        data = self._load_json(self.last_setup_file)
        return data.get("last_setup")

    def update_last_setup(self, target_monitor: str, bookmakers: list):
        """
        Update last_setup.

        Args:
            target_monitor: Monitor identifier (e.g., "primary", "left", "right")
            bookmakers: List of dicts with 'name' and 'position'
        """
        data = self._load_json(self.last_setup_file)
        data["last_setup"] = {"target_monitor": target_monitor, "bookmakers": bookmakers}
        self._save_json(self.last_setup_file, data)
        self.logger.info("Updated last_setup")

    # === BETTING AGENT ===

    def get_betting_agent_config(self) -> Dict[str, float]:
        """Get betting_agent configuration."""
        data = self._load_json(self.betting_agent_file)
        return data

    def update_betting_agent_config(self, bet_amount: float, auto_stop: float):
        """
        Update betting_agent configuration.

        Args:
            bet_amount: Bet amount
            auto_stop: Auto cash-out multiplier
        """
        data = {"bet_amount": bet_amount, "auto_stop": auto_stop}
        self._save_json(self.betting_agent_file, data)
        self.logger.info("Updated betting_agent config")

    # === SESSION KEEPER ===

    def get_session_keeper_config(self) -> Dict[str, int]:
        """Get session_keeper configuration."""
        data = self._load_json(self.last_setup_file)
        return data.get("session_keeper", {"interval": 600})

    def update_session_keeper_config(self, interval: int):
        """
        Update session_keeper configuration.

        Args:
            interval: Interval in seconds
        """
        data = self._load_json(self.last_setup_file)
        data["session_keeper"] = {"interval": interval}
        self._save_json(self.last_setup_file, data)
        self.logger.info("Updated session_keeper config")

    # === BOOKMAKER PRESETS ===

    def get_bookmaker_presets(self) -> Dict[str, Any]:
        """Get bookmaker presets."""
        return self._load_json(self.bookmaker_presets_file)

    def update_bookmaker_presets(self, presets: Dict[str, Any]):
        """
        Update bookmaker presets.

        Args:
            presets: Presets dict
        """
        self._save_json(self.bookmaker_presets_file, presets)
        self.logger.info("Updated bookmaker presets")
