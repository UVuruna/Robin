# config/settings.py
# VERSION: 6.0 - FIXED: Added START phase
# CHANGES: Added GamePhase.START = 6 for complete phase cycle

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import List

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

class GamePhase(IntEnum):
    """
    Game phase enumeration.

    CORRECT PHASE ORDER:
    BETTING (2) → LOADING (1) → START (6) → SCORE_LOW (3) → SCORE_MID (4) → SCORE_HIGH (5) → ENDED (0)

    Notes:
    - LOADING and START are very short (<1 sec) and may be missed
    - SCORE phases (LOW/MID/HIGH) are optional depending on how high the score goes
    - Game can end at 1.00x (goes directly from BETTING to ENDED)
    """

    ENDED = 2  # Game crashed/ended
    LOADING = 5  # Loading between rounds
    BETTING = 0  # Betting window open
    SCORE_LOW = 1  # Score 1.00x - 9.99x
    SCORE_MID = 3  # Score 10.00x - 99.99x
    SCORE_HIGH = 4  # Score 100.00x +
    START = 6  # Game just started (<200ms, often missed)


class BetState(IntEnum):
    """Bet button state enumeration."""

    READY = 1  # Green - Can place bet
    INACTIVE = 0  # Orange - Game in progress, can Cash Out
    ACTIVE = 2  # Red - Bet placed, waiting for round to Start


# Grid layout configurations
AVAILABLE_GRIDS = [
    "GRID 2×2",
    "GRID 2×3",
    "GRID 2×4",
    "GRID 3×3",
    "GRID 3×4",
]


@dataclass
class PathConfig:
    """Path configuration for all data directories."""

    # Root directories
    project_root: Path = PROJECT_ROOT
    config_dir: Path = PROJECT_ROOT / "config"
    data_dir: Path = PROJECT_ROOT / "data"
    logs_dir: Path = PROJECT_ROOT / "logs"

    # Config subdirectories
    config_static_dir: Path = config_dir / "static"
    config_user_dir: Path = config_dir / "user"

    # Data subdirectories
    database_dir: Path = data_dir / "databases"
    models_dir: Path = data_dir / "models"
    screenshots_dir: Path = data_dir / "screenshots"

    # Static config files (version-controlled)
    screen_regions: Path = config_static_dir / "screen_regions.json"
    bookmakers: Path = config_static_dir / "bookmakers.json"
    stylus_css: Path = config_static_dir / "stylus_css.json"
    ml_models: Path = config_static_dir / "ml_models.json"

    # User config files (NOT in Git)
    betting_agent_config: Path = config_user_dir / "betting_agent.json"
    last_setup: Path = config_user_dir / "last_setup.json"
    bookmaker_presets: Path = config_user_dir / "bookmaker_presets.json"

    # Database files
    main_game_db: Path = database_dir / "main_game_data.db"
    rgb_training_db: Path = database_dir / "rgb_training_data.db"
    betting_history_db: Path = database_dir / "betting_history.db"

    # ML model files
    phase_model: Path = models_dir / "game_phase_kmeans.pkl"
    button_model: Path = models_dir / "bet_button_kmeans.pkl"

    def ensure_directories(self):
        """Create all necessary directories."""
        directories = [
            self.config_dir,
            self.config_static_dir,
            self.config_user_dir,
            self.data_dir,
            self.logs_dir,
            self.database_dir,
            self.models_dir,
            self.screenshots_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@dataclass
class OCRConfig:
    """OCR configuration for Tesseract."""

    # Tesseract executable path (auto-detected if not specified)
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    oem: int = 3  # OCR Engine Mode (3 = Default - works without lang when whitelist used)
    psm: int = 7  # Page Segmentation Mode (7 = single line)

    # Whitelists for different region types
    tesseract_whitelist = {
        "score": "0123456789.", # Reads: "1.52x", "12.34x", "100.00x"
        "money": "0123456789.", # Reads: "1,234.56", "12,345.78", "123,456.78"
        "player_count": "0123456789/", # Reads: "123/1234", "45/2134"
    }

    # Template matching thresholds
    template_threshold: float = 0.99  # 99%+ accuracy required
    template_method: int = 5  # cv2.TM_CCOEFF_NORMED


@dataclass
class CollectionConfig:
    """Data collection configuration."""

    # Score thresholds to track
    score_thresholds: List[float] = None

    # Collection intervals
    phase_check_interval: float = 0.1  # seconds
    score_read_interval: float = 0.2  # seconds

    # Batch sizes for database
    batch_size_rounds: int = 50
    batch_size_thresholds: int = 50
    batch_size_rgb: int = 5 * 6 * 30  # 0.2 seconds for 6 regions every 30 seconds

    def __post_init__(self):
        if self.score_thresholds is None:
            self.score_thresholds = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]


@dataclass
class BettingConfig:
    """Betting agent configuration."""

    # Bet amounts
    min_bet_amount: float = 10.0
    max_bet_amount: float = 10000.0
    default_bet_amount: float = 10.0

    # Auto cash-out
    min_auto_stop: float = 1.1
    max_auto_stop: float = 100.0
    default_auto_stop: float = 2.0

    # Timing
    click_delay: float = 0.1
    action_delay: float = 0.2
    round_end_wait: float = 2.0

    # Transaction safety
    use_bet_lock: bool = True
    lock_timeout: float = 30.0


@dataclass
class LoggingConfig:
    """Logging configuration."""

    # Log file settings
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    # Format
    format: str = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"

    # Levels (for different modules)
    default_level: str = "INFO"
    ocr_level: str = "WARNING"
    database_level: str = "INFO"


# Global config instances
PATH = PathConfig()
OCR = OCRConfig()
COLLECT = CollectionConfig()
BETTING = BettingConfig()
LOGGING = LoggingConfig()


# Ensure directories exist
PATH.ensure_directories()
