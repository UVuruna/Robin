# apps/base_app.py
# VERSION: 1.0 - Complete parent class for all apps
# PURPOSE: Common functionality for main_data_collector, betting_agent, rgb_collector, session_keeper

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple, Dict
from multiprocessing import Event
from abc import ABC, abstractmethod
import cv2

from core.coord_manager import CoordsManager
from utils.region_visualizer import RegionVisualizer  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
from utils.logger import init_logging, AviatorLogger


class BaseAviatorApp(ABC):
    """
    Abstract base class for all Aviator applications.

    Provides:
    - Database setup
    - Dual monitor support
    - Bookmaker selection
    - Region verification
    - Process management
    - Shutdown handling
    """

    SCREEN_WIDTH = 3840  # For dual monitor offset

    def __init__(self, app_name: str, database_name: str):
        """
        Initialize base application.

        Args:
            app_name: Name for logging (e.g., "MainDataCollector")
            database_name: Database filename (e.g., "main_game_data.db")
        """
        init_logging()
        self.logger = AviatorLogger.get_logger(app_name)
        self.app_name = app_name

        # Database
        self.db_path = Path("data/databases") / database_name
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Coordinates
        self.coords_manager = CoordsManager()

        # Process control
        self.shutdown_event = Event()
        self.processes = []

    @abstractmethod
    def setup_database(self):
        """Setup database tables. Must be implemented by child class."""
        pass

    @abstractmethod
    def create_worker_process(self, *args, **kwargs):
        """Create worker process. Must be implemented by child class."""
        pass

    def get_dual_monitor_offset(self) -> int:
        """
        Get monitor offset for dual monitor setup.

        Returns:
            Offset in pixels (3840 for dual, 0 for single)
        """
        dual_screen = (
            input(
                "\n📺 Are you using DUAL monitors? (press Enter for NO | any key for YES): "
            ).strip()
            != ""
        )

        if dual_screen:
            print("   ✅ DUAL MONITOR MODE - Adding 3840px offset")
            return self.SCREEN_WIDTH
        else:
            print("   ✅ SINGLE MONITOR MODE - No offset")
            return 0

    def select_bookmakers_interactive(
        self, num_bookmakers: int
    ) -> List[Tuple[str, str, Dict]]:
        """
        Interactive bookmaker selection with dual monitor support.

        Args:
            num_bookmakers: Number of bookmakers to configure

        Returns:
            List of tuples: (bookmaker_name, position_code, coordinates)
        """
        available_bookmakers = self.coords_manager.get_available_bookmakers()
        available_positions = self.coords_manager.get_available_positions()

        if not available_bookmakers:
            print("\n❌ No bookmakers configured!")
            print("   Run: python utils/region_editor.py")
            return []

        if not available_positions:
            print("\n❌ No positions configured!")
            print("   Add positions to screen_regions.json")
            return []

        print(f"\n📊 Available bookmakers: {', '.join(available_bookmakers)}")
        print(f"📐 Available positions: {', '.join(available_positions)}")

        # Dual monitor setup
        monitor_offset = self.get_dual_monitor_offset()

        selected = []

        for i in range(1, num_bookmakers + 1):
            print(f"\n--- Bookmaker #{i} ---")

            # Select bookmaker
            while True:
                bookmaker = input("Choose bookmaker: ").strip()
                if bookmaker in available_bookmakers:
                    break
                print(f"❌ Invalid! Choose from: {', '.join(available_bookmakers)}")

            # Select position
            while True:
                position = (
                    input(
                        f"Choose position for {bookmaker} (e.g., TL, TC, TR, BL, BC, BR): "
                    )
                    .strip()
                    .upper()
                )
                if position in available_positions:
                    break
                print(f"❌ Invalid! Choose from: {', '.join(available_positions)}")

            # Calculate coordinates with offset
            coords = self.coords_manager.calculate_coords(
                bookmaker, position, monitor_offset
            )
            if coords:
                selected.append((bookmaker, position, coords))
                print(f"✅ {bookmaker} @ {position}")
            else:
                print(
                    f"❌ Failed to calculate coordinates for {bookmaker} @ {position}"
                )

        return selected

    def verify_regions(self, bookmakers_config: List[Tuple[str, str, Dict]]) -> bool:
        """
        Verify regions with screenshots and user confirmation.

        Args:
            bookmakers_config: List of (bookmaker_name, position_code, coordinates)

        Returns:
            True if user confirms, False otherwise
        """
        print("\n🔍 Verifying regions...")
        print("   Generating screenshots with region overlays...")

        visualizer = RegionVisualizer()

        for bookmaker, position, coords in bookmakers_config:
            identifier = f"{bookmaker}_{position}"
            screenshot_path = visualizer.create_verification_screenshot(
                coords=coords, identifier=identifier, bookmaker_name=bookmaker
            )

            if screenshot_path:
                print(f"   ✅ Screenshot saved: {screenshot_path}")

                # Display screenshot
                try:
                    img = cv2.imread(str(screenshot_path))
                    if img is not None:
                        cv2.imshow(f"Verify: {identifier}", img)
                        cv2.waitKey(1000)  # Show for 1 second
                except Exception as e:
                    self.logger.warning(f"Could not display screenshot: {e}")

        cv2.destroyAllWindows()

        print("\n" + "=" * 60)
        print("📸 REGION VERIFICATION")
        print("=" * 60)
        print(f"Screenshots saved to: {visualizer.output_dir}")
        print("\n⚠️  Please check that all regions align correctly!")
        print("   If regions are misaligned, run: python utils/region_editor.py")
        print("=" * 60)

        confirm = input("\n✅ Do regions look correct? (yes/no): ").strip().lower()

        return confirm == "yes"

    def start_processes(self, bookmakers_config: List[Tuple[str, str, Dict]]):
        """
        Start worker processes for each bookmaker.

        Args:
            bookmakers_config: List of (bookmaker_name, position_code, coordinates)
        """
        print("\n🚀 Starting processes...")

        for bookmaker, position, coords in bookmakers_config:
            process = self.create_worker_process(
                bookmaker_name=bookmaker, coords=coords
            )
            process.start()
            self.processes.append(process)
            print(f"   ✅ Started: {bookmaker} @ {position} (PID: {process.pid})")

        self.logger.info(f"Started {len(self.processes)} process(es)")

    def wait_for_processes(self):
        """Wait for all processes to complete with proper shutdown handling."""
        try:
            for process in self.processes:
                process.join()
        except KeyboardInterrupt:
            print("\n\n⚠️  Shutdown requested...")
            self.shutdown_event.set()

            # Give processes time to cleanup
            for process in self.processes:
                process.join(timeout=5)
                if process.is_alive():
                    print(f"   ⚠️  Terminating {process.name}...")
                    process.terminate()

    @abstractmethod
    def run(self):
        """Main run method. Must be implemented by child class."""
        pass


def main():
    """This file should not be run directly."""
    print("=" * 60)
    print("⚠️  base_app.py is a parent class")
    print("=" * 60)
    print("\nRun one of these programs instead:")
    print("  • python apps/main_data_collector.py")
    print("  • python apps/betting_agent.py")
    print("  • python apps/rgb_collector.py")
    print("  • python apps/session_keeper.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
