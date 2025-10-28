"""
Module: RegionManager
Purpose: Multi-monitor coordinate management with dynamic layout calculation
Version: 2.0

This module handles:
- Multi-monitor setup detection
- Dynamic coordinate calculation based on monitor configuration
- Layout management (2x2, 2x3, 2x4 grids)
- Region coordinate transformation for different screen positions
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import mss
import platform

# Import win32api only on Windows
if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
else:
    WIN32_AVAILABLE = False


def get_taskbar_height() -> int:
    """
    Get Windows taskbar height.

    Returns:
        Taskbar height in pixels. Falls back to 72px if detection fails.
    """
    if WIN32_AVAILABLE:
        try:
            # Get full screen height and work area height
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            work_area = win32api.GetSystemMetrics(win32con.SM_CYFULLSCREEN)
            taskbar_height = screen_height - work_area

            # Sanity check (taskbar usually 40-100px)
            if 30 <= taskbar_height <= 150:
                return taskbar_height
        except Exception as e:
            logging.getLogger("RegionManager").warning(f"Failed to detect taskbar height: {e}")

    # Fallback to approximation (4% of 2160 = ~86px, close to typical 72px)
    # User can override in config if needed
    return 72


@dataclass
class MonitorInfo:
    """Monitor information structure."""
    index: int
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False

    def __repr__(self):
        return f"Monitor{self.index}({self.width}x{self.height} at {self.x},{self.y})"


@dataclass
class Region:
    """Screen region with coordinates."""
    left: int
    top: int
    width: int
    height: int
    name: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height
        }

    def __repr__(self):
        return f"Region({self.name}: {self.left},{self.top} {self.width}x{self.height})"


class RegionManager:
    """
    Manages screen regions across multiple monitors with dynamic coordinate calculation.

    Features:
    - Auto-detects monitor configuration
    - Calculates coordinates for different layouts (4, 6, 8 bookmakers)
    - Handles dual/triple monitor setups
    - Transforms base regions to specific grid positions
    """

    # Layout position names
    LAYOUT_4_POSITIONS = ["TL", "TR", "BL", "BR"]  # 2x2
    LAYOUT_6_POSITIONS = ["TL", "TC", "TR", "BL", "BC", "BR"]  # 2x3
    LAYOUT_8_POSITIONS = ["TL", "TCL", "TCR", "TR", "BL", "BCL", "BCR", "BR"]  # 2x4

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize RegionManager.

        Args:
            config_path: Path to screen_regions.json configuration file
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Load configuration
        if config_path is None:
            from config.settings import PATH
            config_path = PATH.screen_regions

        self.config_path = config_path
        self.config = self._load_config()

        # Detect monitors
        self.monitors = self._detect_monitors()
        self.logger.info(f"Detected {len(self.monitors)} monitor(s): {self.monitors}")

        # Taskbar height (can be overridden in config)
        self.taskbar_height = self.config.get("taskbar_height", None)
        if self.taskbar_height is None:
            self.taskbar_height = get_taskbar_height()
        self.logger.info(f"Taskbar height: {self.taskbar_height}px")

        # Cache for calculated layouts
        self._layout_cache: Dict[str, Dict[str, Tuple[int, int]]] = {}

    def _load_config(self) -> Dict:
        """Load screen regions configuration from JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration: {e}")
            raise

    def _detect_monitors(self) -> List[MonitorInfo]:
        """
        Detect all connected monitors using MSS.

        Returns:
            List of MonitorInfo objects
        """
        monitors = []

        with mss.mss() as sct:
            # Monitor 0 is the "All monitors" virtual monitor in MSS
            for i, monitor in enumerate(sct.monitors[1:], start=1):
                mon_info = MonitorInfo(
                    index=i,
                    x=monitor["left"],
                    y=monitor["top"],
                    width=monitor["width"],
                    height=monitor["height"],
                    is_primary=(monitor["left"] == 0 and monitor["top"] == 0)
                )
                monitors.append(mon_info)

        return monitors

    def get_monitor_setup(self) -> Dict[str, MonitorInfo]:
        """
        Get monitor setup with logical names.

        Returns:
            Dictionary with "left", "center", "right" monitors (if they exist)
        """
        if not self.monitors:
            return {}

        # Sort monitors by X position
        sorted_monitors = sorted(self.monitors, key=lambda m: m.x)

        setup = {}
        if len(sorted_monitors) == 1:
            setup["primary"] = sorted_monitors[0]
        elif len(sorted_monitors) == 2:
            setup["left"] = sorted_monitors[0]
            setup["right"] = sorted_monitors[1]
        elif len(sorted_monitors) >= 3:
            setup["left"] = sorted_monitors[0]
            setup["center"] = sorted_monitors[1]
            setup["right"] = sorted_monitors[2]

        return setup

    def calculate_layout_offsets(
        self,
        layout: str,
        target_monitor: str = "primary"
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate position offsets for a given layout on specified monitor.

        Args:
            layout: Layout name ("layout_4", "layout_6", "layout_8")
            target_monitor: Monitor to use ("primary", "left", "right", "center")

        Returns:
            Dictionary mapping position names to (offset_x, offset_y) tuples

        Example:
            For layout_6 on a 1920x1080 monitor:
            {
                "TL": (0, 0),
                "TC": (640, 0),
                "TR": (1280, 0),
                "BL": (0, 540),
                "BC": (640, 540),
                "BR": (1280, 540)
            }
        """
        cache_key = f"{layout}_{target_monitor}"
        if cache_key in self._layout_cache:
            return self._layout_cache[cache_key]

        # Get monitor info
        monitor_setup = self.get_monitor_setup()

        if target_monitor not in monitor_setup:
            self.logger.warning(f"Monitor '{target_monitor}' not found, using primary")
            target_monitor = list(monitor_setup.keys())[0]

        monitor = monitor_setup[target_monitor]

        # Determine grid dimensions
        if layout == "layout_4":
            rows, cols = 2, 2
            positions = self.LAYOUT_4_POSITIONS
        elif layout == "layout_6":
            rows, cols = 2, 3
            positions = self.LAYOUT_6_POSITIONS
        elif layout == "layout_8":
            rows, cols = 2, 4
            positions = self.LAYOUT_8_POSITIONS
        else:
            raise ValueError(f"Unknown layout: {layout}")

        # Calculate cell dimensions (subtract taskbar height from monitor height)
        effective_height = monitor.height - self.taskbar_height

        cell_width = monitor.width // cols
        cell_height = effective_height // rows

        # Calculate offsets for each position
        offsets = {}

        for idx, pos_name in enumerate(positions):
            row = idx // cols
            col = idx % cols

            offset_x = monitor.x + (col * cell_width)
            offset_y = monitor.y + (row * cell_height)

            offsets[pos_name] = (offset_x, offset_y)

        self._layout_cache[cache_key] = offsets
        self.logger.debug(f"Calculated offsets for {layout} on {target_monitor}: {offsets}")

        return offsets

    def get_region(
        self,
        region_name: str,
        position: str = "TL",
        layout: str = "layout_6",
        target_monitor: str = "primary"
    ) -> Region:
        """
        Get region coordinates for a specific grid position.

        Args:
            region_name: Name of region from config (e.g., "score_region_small")
            position: Grid position (e.g., "TL", "TC", "BR")
            layout: Layout name ("layout_4", "layout_6", "layout_8")
            target_monitor: Monitor to use ("primary", "left", "right")

        Returns:
            Region object with calculated coordinates

        Example:
            >>> manager.get_region("score_region_small", position="TC", layout="layout_6")
            Region(score_region_small: 1088,399 380x130)
        """
        # Get base region from config
        if region_name not in self.config.get("regions", {}):
            raise ValueError(f"Region '{region_name}' not found in configuration")

        base_region = self.config["regions"][region_name]

        # Get layout offset for this position
        offsets = self.calculate_layout_offsets(layout, target_monitor)

        if position not in offsets:
            raise ValueError(f"Position '{position}' not valid for {layout}")

        offset_x, offset_y = offsets[position]

        # Apply offset to base coordinates
        return Region(
            left=base_region["left"] + offset_x,
            top=base_region["top"] + offset_y,
            width=base_region["width"],
            height=base_region["height"],
            name=f"{region_name}_{position}"
        )

    def get_all_regions_for_position(
        self,
        position: str,
        layout: str = "layout_6",
        target_monitor: str = "primary"
    ) -> Dict[str, Region]:
        """
        Get all regions for a specific bookmaker position.

        Args:
            position: Grid position (e.g., "TL", "BC")
            layout: Layout name
            target_monitor: Monitor to use

        Returns:
            Dictionary mapping region names to Region objects

        Example:
            >>> regions = manager.get_all_regions_for_position("TL")
            >>> regions["score_region_small"]
            Region(score_region_small_TL: 448,399 380x130)
        """
        regions = {}

        for region_name in self.config.get("regions", {}).keys():
            try:
                regions[region_name] = self.get_region(
                    region_name,
                    position,
                    layout,
                    target_monitor
                )
            except Exception as e:
                self.logger.warning(f"Could not get region {region_name}: {e}")

        return regions

    def get_bookmaker_regions(
        self,
        bookmaker_name: str,
        bookmaker_config: Dict
    ) -> Dict[str, Region]:
        """
        Get all regions for a specific bookmaker based on its configuration.

        Args:
            bookmaker_name: Name of the bookmaker
            bookmaker_config: Configuration dict with 'position', 'layout', 'monitor'

        Returns:
            Dictionary of all regions for this bookmaker

        Example:
            >>> config = {"position": "TC", "layout": "layout_6", "monitor": "primary"}
            >>> regions = manager.get_bookmaker_regions("Mozzart", config)
        """
        position = bookmaker_config.get("position", "TL")
        layout = bookmaker_config.get("layout", "layout_6")
        monitor = bookmaker_config.get("monitor", "primary")

        return self.get_all_regions_for_position(position, layout, monitor)

    def visualize_layout(
        self,
        layout: str = "layout_6",
        target_monitor: str = "primary"
    ) -> str:
        """
        Create ASCII visualization of layout.

        Args:
            layout: Layout name
            target_monitor: Monitor to visualize

        Returns:
            String with ASCII layout visualization
        """
        offsets = self.calculate_layout_offsets(layout, target_monitor)

        # Determine dimensions
        if layout == "layout_4":
            rows, cols = 2, 2
        elif layout == "layout_6":
            rows, cols = 2, 3
        elif layout == "layout_8":
            rows, cols = 2, 4
        else:
            return "Unknown layout"

        # Build visualization
        lines = [f"\n=== {layout.upper()} on {target_monitor} ===\n"]

        for row in range(rows):
            row_positions = []
            for col in range(cols):
                idx = row * cols + col
                pos_name = list(offsets.keys())[idx]
                x, y = offsets[pos_name]
                row_positions.append(f"[{pos_name:3s}:{x:5d},{y:4d}]")
            lines.append(" ".join(row_positions))

        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """
        Get statistics about region manager.

        Returns:
            Dictionary with statistics
        """
        return {
            "monitors_detected": len(self.monitors),
            "monitor_details": [str(m) for m in self.monitors],
            "regions_configured": len(self.config.get("regions", {})),
            "layouts_cached": len(self._layout_cache),
            "config_path": str(self.config_path)
        }

    def cleanup(self):
        """Cleanup resources (currently minimal)."""
        self._layout_cache.clear()
        self.logger.info("RegionManager cleaned up")


# Convenience function for quick access
def get_region_manager() -> RegionManager:
    """Get or create singleton RegionManager instance."""
    if not hasattr(get_region_manager, "_instance"):
        get_region_manager._instance = RegionManager()
    return get_region_manager._instance


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    manager = RegionManager()
    print(manager.visualize_layout("layout_6", "primary"))

    # Test region retrieval
    region = manager.get_region("score_region_small", "TC", "layout_6")
    print(f"\nScore region at TC position: {region}")

    # Show stats
    stats = manager.get_stats()
    print("\nRegion Manager Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
