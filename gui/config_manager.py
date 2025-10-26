# gui/config_manager.py
# VERSION: 1.0
# PURPOSE: Manage config.json for GUI

import json
from config import PATH
from typing import Dict, Any
from utils.logger import AviatorLogger

class ConfigManager:
    """
    Manages configuration file (config.json) for the GUI.

    Config structure:
    {
        "last_setup": {
            "layout": "layout_6",
            "dual_monitor": false,
            "positions": {
                "TL": "BalkanBet",
                "TC": "Merkur",
                "TR": "MaxBet",
                "BL": "Mozzart",
                "BC": "Soccer",
                "BR": "StarBet"
            }
        },
        "betting_agent": {
            "bet_amount": 10.0,
            "auto_stop": 2.0
        },
        "session_keeper": {
            "interval": 600
        }
    }
    """

    CONFIG_FILE = PATH.config

    def __init__(self):
        self.logger = AviatorLogger.get_logger("ConfigManager")
        self.config_file = self.CONFIG_FILE

        # Create default config if not exists
        if not self.config_file.exists():
            self.create_default_config()

    def create_default_config(self):
        """Create default config file."""
        default_config = {
            "last_setup": None,
            "betting_agent": {"bet_amount": 10.0, "auto_stop": 2.0},
            "session_keeper": {"interval": 600},
        }

        self.save_config(default_config)
        self.logger.info("Created default config.json")

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from config.json.

        Returns:
            Dict with configuration
        """
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)

            self.logger.info("Config loaded successfully")
            return config

        except FileNotFoundError:
            self.logger.warning("Config file not found, creating default")
            self.create_default_config()
            return self.load_config()

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}")
            raise

        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            raise

    def save_config(self, config: Dict[str, Any]):
        """
        Save configuration to config.json.

        Args:
            config: Configuration dict to save
        """
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)

            self.logger.info("Config saved successfully")

        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            raise

    def update_last_setup(self, dual_monitor: bool, bookmakers: list):
        """
        Update last_setup in config.

        Args:
            dual_monitor: Boolean for dual monitor setup
            bookmakers: List of dicts with 'name' and 'position'
        """
        config = self.load_config()

        config["last_setup"] = {"dual_monitor": dual_monitor, "bookmakers": bookmakers}

        self.save_config(config)
        self.logger.info("Updated last_setup")

    def update_betting_agent_config(self, bet_amount: float, auto_stop: float):
        """
        Update betting_agent configuration.

        Args:
            bet_amount: Bet amount
            auto_stop: Auto cash-out multiplier
        """
        config = self.load_config()

        config["betting_agent"] = {"bet_amount": bet_amount, "auto_stop": auto_stop}

        self.save_config(config)
        self.logger.info("Updated betting_agent config")

    def update_session_keeper_config(self, interval: int):
        """
        Update session_keeper configuration.

        Args:
            interval: Interval in seconds
        """
        config = self.load_config()

        config["session_keeper"] = {"interval": interval}

        self.save_config(config)
        self.logger.info("Updated session_keeper config")

    def get_last_setup(self) -> Dict[str, Any]:
        """
        Get last setup configuration.

        Returns:
            Dict with last_setup or None if not configured
        """
        config = self.load_config()
        return config.get("last_setup")

    def get_betting_agent_config(self) -> Dict[str, float]:
        """
        Get betting_agent configuration.

        Returns:
            Dict with bet_amount and auto_stop
        """
        config = self.load_config()
        return config.get("betting_agent", {"bet_amount": 10.0, "auto_stop": 2.0})

    def get_session_keeper_config(self) -> Dict[str, int]:
        """
        Get session_keeper configuration.

        Returns:
            Dict with interval
        """
        config = self.load_config()
        return config.get("session_keeper", {"interval": 600})
