"""
Module: RegionManager
Purpose: Multi-monitor coordinate management with dynamic layout calculation
Version: 3.0 - GRID System

This module handles:
- Multi-monitor setup detection
- Dynamic coordinate calculation based on monitor configuration
- Flexible GRID layout system (GRID 2×3, GRID 3×4, etc.)
- Human-readable position names (Top-Left, Bottom-Middle)
- Region coordinate transformation for different screen positions
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import mss
import platform
from config.settings import AVAILABLE_GRIDS

# Import win32api only on Windows
if platform.system() == "Windows":
    try:
        import win32api  # type: ignore
        import win32con  # type: ignore
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
else:
    WIN32_AVAILABLE = False


def get_taskbar_height() -> int:
    """
    Get Windows taskbar height (accounting for DPI scaling).

    Returns:
        Taskbar height in pixels. Falls back to 72px if detection fails.
    """
    if WIN32_AVAILABLE:
        try:
            # Get full screen height and work area height (DPI-scaled values)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            work_area = win32api.GetSystemMetrics(win32con.SM_CYFULLSCREEN)
            taskbar_height_scaled = screen_height - work_area

            # Get DPI scale factor (100% = 96 DPI, 150% = 144 DPI, 200% = 192 DPI)
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.SetProcessDPIAware()
                dpi = user32.GetDpiForSystem()
                scale_factor = dpi / 96.0  # 96 DPI = 100% scaling

                # Unscale the taskbar height
                taskbar_height = round(taskbar_height_scaled / scale_factor)
            except:
                # If DPI detection fails, use scaled value
                taskbar_height = taskbar_height_scaled

            # Sanity check (taskbar usually 40-100px at 100% scaling)
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
    - Flexible GRID system (GRID 2×2, GRID 2×3, GRID 2×4, GRID 3×3, GRID 3×4)
    - Human-readable position names (Top-Left, Middle 1-Middle 2, Bottom-Right)
    - Dynamic position generation on-the-fly
    - Handles dual/triple monitor setups
    - Transforms base regions to specific grid positions
    """

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

        # Cache for position names
        self._position_names_cache: Dict[str, Dict[str, Tuple[int, int]]] = {}

    def parse_grid_format(self, grid_name: str) -> Tuple[int, int]:
        """
        Parse GRID format to extract rows and cols.

        Args:
            grid_name: "GRID 2×3" or "GRID 2x3"

        Returns:
            (rows, cols) tuple

        Raises:
            ValueError: If format is invalid

        Example:
            >>> parse_grid_format("GRID 2×3")
            (2, 3)
            >>> parse_grid_format("GRID 3x4")
            (3, 4)
        """
        try:
            # Remove "GRID " prefix
            if not grid_name.startswith("GRID "):
                raise ValueError(f"Grid name must start with 'GRID ': {grid_name}")

            dimensions = grid_name.replace("GRID ", "")

            # Try Unicode × first
            if '×' in dimensions:
                parts = dimensions.split('×')
            # Fallback to x
            elif 'x' in dimensions:
                parts = dimensions.split('x')
            else:
                raise ValueError(f"Invalid grid format (missing × or x): {grid_name}")

            if len(parts) != 2:
                raise ValueError(f"Invalid grid format (expected RxC): {grid_name}")

            rows = int(parts[0].strip())
            cols = int(parts[1].strip())

            if rows < 2 or cols < 2:
                raise ValueError(f"Grid must be at least 2×2: {grid_name}")

            return rows, cols

        except (ValueError, AttributeError) as e:
            raise ValueError(f"Failed to parse grid format '{grid_name}': {e}")

    def _generate_row_names(self, rows: int) -> List[str]:
        """
        Generate row names based on number of rows.

        Logic:
        - 2 rows: [Top, Bottom]
        - 3 rows: [Top, Middle, Bottom]
        - 4+ rows: [Top, Middle 1, Middle 2, ..., Bottom]

        Args:
            rows: Number of rows

        Returns:
            List of row names
        """
        if rows < 2:
            raise ValueError("Must have at least 2 rows")

        if rows == 2:
            return ["Top", "Bottom"]

        # 3+ rows: Top, Middle(s), Bottom
        names = ["Top"]

        # Middle rows
        middle_count = rows - 2
        if middle_count == 1:
            names.append("Middle")
        else:
            for i in range(1, middle_count + 1):
                names.append(f"Middle {i}")

        names.append("Bottom")
        return names

    def _generate_col_names(self, cols: int) -> List[str]:
        """
        Generate column names based on number of columns.

        Logic:
        - 2 cols: [Left, Right]
        - 3 cols: [Left, Middle, Right]
        - 4+ cols: [Left, Middle 1, Middle 2, ..., Right]

        Args:
            cols: Number of columns

        Returns:
            List of column names
        """
        if cols < 2:
            raise ValueError("Must have at least 2 columns")

        if cols == 2:
            return ["Left", "Right"]

        # 3+ cols: Left, Middle(s), Right
        names = ["Left"]

        # Middle columns
        middle_count = cols - 2
        if middle_count == 1:
            names.append("Middle")
        else:
            for i in range(1, middle_count + 1):
                names.append(f"Middle {i}")

        names.append("Right")
        return names

    def generate_position_names(self, grid_name: str) -> Dict[str, Tuple[int, int]]:
        """
        Generate position names for grid.

        Args:
            grid_name: "GRID 2×3"

        Returns:
            {"Top-Left": (0, 0), "Top-Middle": (0, 1), "Top-Right": (0, 2), ...}

        Example:
            >>> generate_position_names("GRID 2×3")
            {
                "Top-Left": (0, 0),
                "Top-Middle": (0, 1),
                "Top-Right": (0, 2),
                "Bottom-Left": (1, 0),
                "Bottom-Middle": (1, 1),
                "Bottom-Right": (1, 2)
            }
        """
        # Check cache
        if grid_name in self._position_names_cache:
            return self._position_names_cache[grid_name]

        rows, cols = self.parse_grid_format(grid_name)

        row_names = self._generate_row_names(rows)
        col_names = self._generate_col_names(cols)

        positions = {}
        for row_idx, row_name in enumerate(row_names):
            for col_idx, col_name in enumerate(col_names):
                position_name = f"{row_name}-{col_name}"
                positions[position_name] = (row_idx, col_idx)

        # Cache result
        self._position_names_cache[grid_name] = positions

        return positions

    def position_to_matrix(self, position: str, grid_name: str) -> Tuple[int, int]:
        """
        Convert human-readable position to matrix coordinates.

        Args:
            position: "Top-Left", "Middle 1-Middle 2", etc.
            grid_name: "GRID 2×3"

        Returns:
            (row, col) tuple

        Raises:
            ValueError: If position not found in grid
        """
        positions = self.generate_position_names(grid_name)

        if position not in positions:
            available = list(positions.keys())
            raise ValueError(
                f"Position '{position}' not found in {grid_name}. "
                f"Available positions: {available}"
            )

        return positions[position]

    def matrix_to_position(self, row: int, col: int, grid_name: str) -> str:
        """
        Convert matrix coordinates to human-readable position.

        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            grid_name: "GRID 2×3"

        Returns:
            Position name like "Top-Left"

        Raises:
            ValueError: If coordinates out of bounds
        """
        rows, cols = self.parse_grid_format(grid_name)

        if row < 0 or row >= rows:
            raise ValueError(f"Row {row} out of bounds for {grid_name} (0-{rows-1})")
        if col < 0 or col >= cols:
            raise ValueError(f"Col {col} out of bounds for {grid_name} (0-{cols-1})")

        positions = self.generate_position_names(grid_name)

        # Reverse lookup
        for position_name, (r, c) in positions.items():
            if r == row and c == col:
                return position_name

        raise ValueError(f"Position ({row}, {col}) not found in {grid_name}")

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
        Get monitor setup with spatial grid positions.

        Uses spatial algorithm:
        1. Group monitors by Y coordinate (rows)
        2. Sort each row by X coordinate (columns)
        3. Generate grid positions (row, col)
        4. Create descriptive labels (Top-Left, Bottom-Right, etc.)

        Returns:
            Dictionary with monitor labels as keys (e.g., "Left", "Top-Right")
        """
        if not self.monitors:
            return {}

        if len(self.monitors) == 1:
            return {"primary": self.monitors[0]}

        # Step I: Group monitors by Y position (rows)
        y_positions = sorted(set(m.y for m in self.monitors))
        rows = {}
        for y in y_positions:
            rows[y] = [m for m in self.monitors if m.y == y]

        # Step II: Sort each row by X position (columns)
        for monitors_in_row in rows.values():
            monitors_in_row.sort(key=lambda m: m.x)

        # Step III: Create grid positions
        grid_positions = []
        for row_idx, (y, monitors_in_row) in enumerate(sorted(rows.items())):
            for col_idx, monitor in enumerate(monitors_in_row):
                grid_positions.append((monitor, (row_idx, col_idx)))

        # Step IV: Generate labels
        num_rows = len(rows)
        num_cols = max(len(monitors_in_row) for monitors_in_row in rows.values())

        # Row labels
        if num_rows == 1:
            row_labels = [""]
        elif num_rows == 2:
            row_labels = ["Top", "Bottom"]
        else:
            row_labels = ["Top"]
            for i in range(1, num_rows - 1):
                row_labels.append(f"Middle-{i}")
            row_labels.append("Bottom")

        # Column labels
        if num_cols == 1:
            col_labels = [""]
        elif num_cols == 2:
            col_labels = ["Left", "Right"]
        else:
            col_labels = ["Left"]
            for i in range(1, num_cols - 1):
                col_labels.append(f"Center-{i}")
            col_labels.append("Right")

        # Step V: Build setup dictionary
        setup = {}
        for monitor, (row, col) in grid_positions:
            row_label = row_labels[row] if row < len(row_labels) else ""
            col_label = col_labels[col] if col < len(col_labels) else ""

            if row_label and col_label:
                label = f"{row_label}-{col_label}"
            elif row_label:
                label = row_label
            elif col_label:
                label = col_label
            else:
                label = "Primary"

            setup[label] = monitor

        # Also add "primary" key for convenience
        for mon in self.monitors:
            if mon.is_primary:
                setup["primary"] = mon
                break

        return setup

    def calculate_layout_offsets(
        self,
        layout: str,
        target_monitor: str = "primary"
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate position offsets for a given layout on specified monitor.

        Args:
            layout: Grid layout ("GRID 2×3", "GRID 3×4", etc.)
            target_monitor: Monitor to use ("primary", "left", "right", "center")

        Returns:
            Dictionary mapping position names to (offset_x, offset_y) tuples

        Example:
            For "GRID 2×3" on a 1920x1080 monitor:
            {
                "Top-Left": (0, 0),
                "Top-Middle": (640, 0),
                "Top-Right": (1280, 0),
                "Bottom-Left": (0, 540),
                "Bottom-Middle": (640, 540),
                "Bottom-Right": (1280, 540)
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

        # Parse grid dimensions and generate positions
        rows, cols = self.parse_grid_format(layout)
        positions = self.generate_position_names(layout)

        # Calculate cell dimensions (subtract taskbar height from monitor height)
        effective_height = monitor.height - self.taskbar_height

        cell_width = monitor.width // cols
        cell_height = effective_height // rows

        # Calculate offsets for each position
        offsets = {}

        for pos_name, (row, col) in positions.items():
            offset_x = monitor.x + (col * cell_width)
            offset_y = monitor.y + (row * cell_height)

            offsets[pos_name] = (offset_x, offset_y)

        self._layout_cache[cache_key] = offsets
        self.logger.debug(f"Calculated offsets for {layout} on {target_monitor}: {offsets}")

        return offsets

    def get_cell_dimensions(
        self,
        layout: str,
        target_monitor: str = "primary"
    ) -> Tuple[int, int]:
        """
        Get cell width and height for a given layout on specified monitor.

        Args:
            layout: Grid layout ("GRID 2×3", "GRID 3×4", etc.)
            target_monitor: Monitor to use ("primary", "left", "right", "center")

        Returns:
            Tuple of (cell_width, cell_height)

        Example:
            For "GRID 2×3" on a 3840x2160 monitor:
            Returns: (1280, 1044)  # 3840/3, (2160-72)/2
        """
        # Get monitor info
        monitor_setup = self.get_monitor_setup()

        if target_monitor not in monitor_setup:
            self.logger.warning(f"Monitor '{target_monitor}' not found, using primary")
            target_monitor = list(monitor_setup.keys())[0]

        monitor = monitor_setup[target_monitor]

        # Parse grid dimensions
        rows, cols = self.parse_grid_format(layout)

        # Calculate cell dimensions (subtract taskbar height from monitor height)
        effective_height = monitor.height - self.taskbar_height

        cell_width = monitor.width // cols
        cell_height = effective_height // rows

        return cell_width, cell_height

    def get_region(
        self,
        region_name: str,
        position: str = "Top-Left",
        layout: str = "GRID 2×3",
        target_monitor: str = "primary"
    ) -> Region:
        """
        Get region coordinates for a specific grid position.

        Args:
            region_name: Name of region from config (e.g., "score_region_small")
            position: Grid position (e.g., "Top-Left", "Bottom-Middle")
            layout: Grid layout ("GRID 2×3", "GRID 3×4", etc.)
            target_monitor: Monitor to use ("primary", "left", "right")

        Returns:
            Region object with calculated coordinates

        Example:
            >>> manager.get_region("score_region_small", position="Top-Middle", layout="GRID 2×3")
            Region(score_region_small: 1088,399 380x130)
        """
        # Get base region from config
        if region_name not in self.config.get("regions", {}):
            raise ValueError(f"Region '{region_name}' not found in configuration")

        base_region = self.config["regions"][region_name]

        # Get layout offset for this position
        offsets = self.calculate_layout_offsets(layout, target_monitor)

        if position not in offsets:
            available = list(offsets.keys())
            raise ValueError(
                f"Position '{position}' not valid for {layout}. "
                f"Available: {available}"
            )

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
        layout: str = "GRID 2×3",
        target_monitor: str = "primary"
    ) -> Dict[str, Region]:
        """
        Get all regions for a specific bookmaker position.

        Args:
            position: Grid position (e.g., "Top-Left", "Bottom-Middle")
            layout: Grid layout ("GRID 2×3", etc.)
            target_monitor: Monitor to use

        Returns:
            Dictionary mapping region names to Region objects

        Example:
            >>> regions = manager.get_all_regions_for_position("Top-Left")
            >>> regions["score_region_small"]
            Region(score_region_small_Top-Left: 448,399 380x130)
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
            >>> config = {"position": "Top-Middle", "layout": "GRID 2×3", "monitor": "primary"}
            >>> regions = manager.get_bookmaker_regions("Mozzart", config)
        """
        position = bookmaker_config.get("position", "TL")
        layout = bookmaker_config.get("layout", "GRID 2×3")
        monitor = bookmaker_config.get("monitor", "primary")

        return self.get_all_regions_for_position(position, layout, monitor)

    def visualize_layout(
        self,
        layout: str = "GRID 2×3",
        target_monitor: str = "primary"
    ) -> str:
        """
        Create ASCII visualization of layout.

        Args:
            layout: Grid layout ("GRID 2×3", etc.)
            target_monitor: Monitor to visualize

        Returns:
            String with ASCII layout visualization
        """
        try:
            rows, cols = self.parse_grid_format(layout)
            offsets = self.calculate_layout_offsets(layout, target_monitor)
        except ValueError as e:
            return f"Error: {e}"

        # Build visualization
        lines = [f"\n=== {layout} on {target_monitor} ===\n"]

        for row in range(rows):
            row_positions = []
            for col in range(cols):
                # Find position name for this (row, col)
                pos_name = self.matrix_to_position(row, col, layout)
                x, y = offsets[pos_name]
                # Use shorter display format for positions
                display_name = pos_name.replace("Top-", "T-").replace("Bottom-", "B-").replace("Middle", "M")
                row_positions.append(f"[{display_name:12s}:{x:5d},{y:4d}]")
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
        self._position_names_cache.clear()
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
    print(manager.visualize_layout("GRID 2×3", "primary"))

    # Test region retrieval
    region = manager.get_region("score_region_small", "Top-Middle", "GRID 2×3")
    print(f"\nScore region at Top-Middle position: {region}")

    # Show stats
    stats = manager.get_stats()
    print("\nRegion Manager Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
