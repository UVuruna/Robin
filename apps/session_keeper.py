# apps/session_keeper.py
# VERSION: 1.0 - NEW
# PURPOSE: Keep sessions active by periodically entering random bet values
# NOTE: Does NOT place actual bets - only enters values to prevent inactivity kick

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import random
from typing import Dict
from multiprocessing import Process
from multiprocessing.synchronize import Event as EventType

from apps.base_app import BaseAviatorApp
from core.gui_controller import GUIController
from utils.logger import AviatorLogger


class SessionKeeper(BaseAviatorApp):
    """
    Session keeper application.
    Keeps bookmaker sessions active by periodically entering random bet values.

    Does NOT place actual bets - only updates input fields.
    """

    def __init__(self):
        super().__init__(
            app_name="SessionKeeper",
            database_name="session_keeper.db",  # Not really used, but required by base
        )

    def setup_database(self):
        """No database needed for session keeper."""
        pass

    def create_worker_process(self, bookmaker_name: str, coords: Dict):
        """Create session keeper process for one bookmaker."""
        return SessionKeeperProcess(
            bookmaker_name=bookmaker_name,
            coords=coords,
            shutdown_event=self.shutdown_event,
        )

    def run(self):
        """Main run method."""
        print("\n" + "=" * 60)
        print("🔄 SESSION KEEPER v1.0")
        print("=" * 60)
        print("\nKeeps bookmaker sessions active by:")
        print("  • Periodically entering random bet amounts (10-20)")
        print("  • Periodically entering random auto cashout (1.00-3.50)")
        print("  • Does NOT place actual bets")
        print("  • Default interval: 10 minutes")
        print("=" * 60)

        # Get number of bookmakers
        while True:
            try:
                num = int(input("\nHow many bookmakers to keep active? (1-6): "))
                if 1 <= num <= 6:
                    break
                print("❌ Please enter 1-6")
            except ValueError:
                print("❌ Invalid input")

        # Setup bookmakers
        bookmakers_config = self.select_bookmakers_interactive(num)

        if not bookmakers_config:
            print("\n❌ No bookmakers configured!")
            return

        # Verify regions
        if not self.verify_regions(bookmakers_config):
            print("\n❌ User cancelled. Fix regions and try again.")
            return

        # Start processes
        self.start_processes(bookmakers_config)

        # Wait
        print("\n🔄 Keeping sessions active... (Ctrl+C to stop)")
        self.wait_for_processes()

        print("\n✅ Session keeper stopped")


class SessionKeeperProcess(Process):
    """Worker process for one bookmaker."""

    DEFAULT_INTERVAL = 600  # 10 minutes

    # Random value ranges
    BET_AMOUNT_MIN = 10
    BET_AMOUNT_MAX = 20
    AUTO_CASHOUT_MIN = 1.00
    AUTO_CASHOUT_MAX = 3.50

    def __init__(
        self,
        bookmaker_name: str,
        coords: Dict,
        shutdown_event: EventType,
        interval: int = None,
    ):
        super().__init__(name=f"SessionKeeper-{bookmaker_name}")
        self.bookmaker_name = bookmaker_name
        self.coords = coords
        self.shutdown_event = shutdown_event
        self.interval = interval or self.DEFAULT_INTERVAL

        self.logger = None
        self.gui = None

    def run(self):
        """Main process loop."""
        self.logger = AviatorLogger.get_logger(f"SessionKeeper-{self.bookmaker_name}")
        self.logger.info(f"Process started (interval: {self.interval}s)")

        try:
            # Setup GUI controller
            self.gui = GUIController()

            # Extract center coordinates for clicking
            self.play_amount_center = (
                self.coords["play_amount_coords_1"]["left"]
                + self.coords["play_amount_coords_1"]["width"] // 2,
                self.coords["play_amount_coords_1"]["top"]
                + self.coords["play_amount_coords_1"]["height"] // 2,
            )

            self.auto_play_center = (
                self.coords["auto_play_coords_1"]["left"]
                + self.coords["auto_play_coords_1"]["width"] // 2,
                self.coords["auto_play_coords_1"]["top"]
                + self.coords["auto_play_coords_1"]["height"] // 2,
            )

            # Main loop
            while not self.shutdown_event.is_set():
                self.update_fields()

                # Wait for next interval (check shutdown every second)
                for _ in range(self.interval):
                    if self.shutdown_event.is_set():
                        break
                    time.sleep(1)

        except Exception as e:
            self.logger.critical(f"Critical error: {e}", exc_info=True)
        finally:
            self.logger.info("Process stopped")

    def update_fields(self):
        """Update bet amount and auto cashout fields with random values."""
        try:
            # Generate random values
            bet_amount = random.randint(self.BET_AMOUNT_MIN, self.BET_AMOUNT_MAX)
            auto_cashout = round(
                random.uniform(self.AUTO_CASHOUT_MIN, self.AUTO_CASHOUT_MAX), 2
            )

            # Update bet amount
            self.gui.click(self.play_amount_center)
            time.sleep(0.05)
            self.gui.select_all()
            self.gui.type_text(str(bet_amount))
            time.sleep(0.05)

            # Update auto cashout
            self.gui.click(self.auto_play_center)
            time.sleep(0.05)
            self.gui.select_all()
            self.gui.type_text(f"{auto_cashout:.2f}")
            time.sleep(0.05)

            self.logger.info(
                f"Updated fields: bet={bet_amount}, auto_cashout={auto_cashout:.2f}x"
            )

        except Exception as e:
            self.logger.error(f"Error updating fields: {e}")


def main():
    keeper = SessionKeeper()
    keeper.run()


if __name__ == "__main__":
    main()
