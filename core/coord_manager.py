# core/coord_manager.py
# VERSION: 6.0 - Updated for layout + shared regions structure

import json
from pathlib import Path
from typing import Dict, Optional, List

from utils.logger import AviatorLogger


class CoordsManager:
    """
    Coordinate manager for new JSON format.

    JSON Structure:
    {
      "layouts": {
        "layout_4": {"TL": {...}, "TR": {...}, "BL": {...}, "BR": {...}},
        "layout_6": {"TL": {...}, "TC": {...}, ...},
        "layout_8": {"TL": {...}, "TCL": {...}, ...}
      },
      "regions": {
        "score_region_small": {...},
        ...
      }
    }
    """

    DEFAULT_FILE = "data/json/screen_regions.json"
    DUAL_MONITOR_OFFSET = 3840

    def __init__(self, coords_file: str = DEFAULT_FILE):
        self.coords_file = Path(coords_file)
        self.logger = AviatorLogger.get_logger("CoordsManager")
        self._ensure_file_exists()
        self.data = self._load_json()

    def _ensure_file_exists(self) -> None:
        """Create directory and empty JSON if doesn't exist."""
        self.coords_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.coords_file.exists():
            default_data = {"layouts": {}, "regions": {}}
            with open(self.coords_file, "w") as f:
                json.dump(default_data, f, indent=2)
            self.logger.info(f"Created new coordinates file: {self.coords_file}")

    def _load_json(self) -> Dict:
        """Load JSON data."""
        try:
            with open(self.coords_file, "r") as f:
                data = json.load(f)

            if "layouts" not in data:
                data["layouts"] = {}
            if "regions" not in data:
                data["regions"] = {}

            return data
        except Exception as e:
            self.logger.error(f"Error loading coordinates: {e}")
            return {"layouts": {}, "regions": {}}

    def reload(self) -> None:
        """Reload JSON from file."""
        self.data = self._load_json()

    def get_available_layouts(self) -> List[str]:
        """Get list of available layouts."""
        return list(self.data.get("layouts", {}).keys())

    def get_positions_for_layout(self, layout: str) -> List[str]:
        """Get position codes for a layout."""
        layout_data = self.data.get("layouts", {}).get(layout, {})
        return list(layout_data.keys())

    def get_position_offset(self, layout: str, position_code: str) -> Optional[Dict]:
        """Get offset for position in layout."""
        layout_data = self.data.get("layouts", {}).get(layout, {})
        return layout_data.get(position_code)

    def get_all_regions(self) -> Dict[str, Dict]:
        """Get all defined regions."""
        return self.data.get("regions", {})

    def calculate_coords(
        self, layout: str, position_code: str, dual_monitor: bool = False
    ) -> Optional[Dict]:
        """
        Calculate final coordinates for position.

        Args:
            layout: Layout name (e.g., 'layout_6')
            position_code: Position code (e.g., 'TL')
            dual_monitor: If True, add dual monitor offset

        Returns:
            Dict with final coordinates for all regions
        """
        try:
            position = self.get_position_offset(layout, position_code)
            if not position:
                self.logger.error(f"Position {position_code} not found in {layout}")
                return None

            regions = self.get_all_regions()
            if not regions:
                self.logger.error("No regions defined")
                return None

            offset_left = position.get("left", 0)
            offset_top = position.get("top", 0)

            if dual_monitor:
                offset_left += self.DUAL_MONITOR_OFFSET

            final_coords = {}
            for region_name, region_data in regions.items():
                if isinstance(region_data, dict) and "left" in region_data:
                    final_coords[region_name] = {
                        "left": region_data["left"] + offset_left,
                        "top": region_data["top"] + offset_top,
                        "width": region_data["width"],
                        "height": region_data["height"],
                    }

            self.logger.info(
                f"Calculated coords: {layout} @ {position_code} "
                f"(offset: +{offset_left}, +{offset_top})"
            )
            return final_coords

        except Exception as e:
            self.logger.error(f"Error calculating coordinates: {e}", exc_info=True)
            return None

    def save_regions(self, regions: Dict[str, Dict]) -> bool:
        """Save region base coordinates."""
        try:
            if "regions" not in self.data:
                self.data["regions"] = {}

            self.data["regions"].update(regions)

            with open(self.coords_file, "w") as f:
                json.dump(self.data, f, indent=2)

            self.logger.info(f"Saved {len(regions)} regions")
            return True

        except Exception as e:
            self.logger.error(f"Error saving regions: {e}", exc_info=True)
            return False

    def display_info(self) -> None:
        """Display configuration info."""
        print("\n" + "=" * 70)
        print("COORDINATE SYSTEM INFO")
        print("=" * 70)

        layouts = self.get_available_layouts()
        print(f"\n📐 Available Layouts ({len(layouts)}):")
        for layout in layouts:
            positions = self.get_positions_for_layout(layout)
            print(f"  • {layout:12s} → Positions: {', '.join(positions)}")

        regions = self.get_all_regions()
        print(f"\n🎯 Defined Regions ({len(regions)}):")
        for region_name, coords in list(regions.items())[:5]:
            print(
                f"  • {region_name:25s} → "
                f"({coords['left']}, {coords['top']}, "
                f"{coords['width']}x{coords['height']})"
            )
        if len(regions) > 5:
            print(f"  ... and {len(regions) - 5} more")

        print("\n" + "=" * 70)


if __name__ == "__main__":
    manager = CoordsManager()
    manager.display_info()
