# apps/betting_agent.py
# VERSION: 2.0 - Refactored with base_app parent class
# PURPOSE: Automated bet placement (DEMO MODE RECOMMENDED!)
# WARNING: Uses real money! Test thoroughly first!

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import sqlite3
from typing import Dict
from multiprocessing import Process, Lock
from multiprocessing.synchronize import Event as EventType, Lock as LockType
from datetime import datetime

from apps.base_app import BaseAviatorApp
from core.screen_reader import ScreenReader
from core.gui_controller import GUIController
from core.event_collector import EventCollector
from regions.score import Score
from regions.other_count import OtherCount
from regions.other_money import OtherMoney
from regions.my_money import MyMoney
from regions.game_phase import GamePhaseDetector
from config.config import GamePhase
from utils.logger import AviatorLogger


class BettingAgent(BaseAviatorApp):
    """
    Automated betting agent.

    ⚠️  WARNING: This uses REAL MONEY!
    Only use in DEMO MODE for testing!
    """

    def __init__(self):
        super().__init__(app_name="BettingAgent", database_name="betting_history.db")
        self.bet_lock = Lock()  # Transaction safety

    def setup_database(self):
        """Create database tables."""
        self.logger.info("Setting up betting database...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bookmaker TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                bet_amount REAL,
                auto_stop REAL,
                final_score REAL,
                money_before REAL,
                money_after REAL,
                profit REAL,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bets_bookmaker 
            ON bets(bookmaker, timestamp)
        """)

        conn.commit()
        conn.close()

        self.logger.info(f"Betting database ready: {self.db_path}")

    def configure_betting(self) -> Dict:
        """Interactive betting configuration for single bookmaker."""
        print("\n" + "=" * 60)
        print("⚠️  BETTING CONFIGURATION")
        print("=" * 60)

        # Select bookmaker
        bookmakers_config = self.select_bookmakers_interactive(num_bookmakers=1)

        if not bookmakers_config:
            return None

        bookmaker, position, coords = bookmakers_config[0]

        # Betting parameters
        print("\n" + "=" * 60)
        print("BETTING PARAMETERS")
        print("=" * 60)

        try:
            bet_amount = float(input("Bet amount (e.g., 10.00): "))
            auto_stop = float(input("Auto cash-out multiplier (e.g., 2.0): "))
        except ValueError:
            print("❌ Invalid input!")
            return None

        # Confirm
        print("\n" + "=" * 60)
        print("CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Bookmaker: {bookmaker}")
        print(f"Position: {position}")
        print(f"Bet amount: {bet_amount:.2f}")
        print(f"Auto cash-out: {auto_stop:.2f}x")
        print("=" * 60)

        confirm = (
            input("\n⚠️  WARNING: This will use REAL money! Continue? (yes/no): ")
            .strip()
            .lower()
        )

        if confirm != "yes":
            print("❌ Cancelled by user")
            return None

        return {
            "bookmaker": bookmaker,
            "position": position,
            "coords": coords,
            "bet_amount": bet_amount,
            "auto_stop": auto_stop,
        }

    def create_worker_process(self, **kwargs):
        """Create betting process (single bookmaker only)."""
        return BettingProcess(
            config=kwargs["config"],
            db_path=self.db_path,
            bet_lock=self.bet_lock,
            shutdown_event=self.shutdown_event,
        )

    def run(self):
        """Main run method."""
        print("\n" + "=" * 60)
        print("💰 BETTING AGENT v2.0")
        print("=" * 60)
        print("\n⚠️  WARNING: This agent uses REAL MONEY!")
        print("   Only use in DEMO MODE for testing!")
        print("   Test thoroughly before using with real funds!")
        print("=" * 60)

        self.setup_database()

        config = self.configure_betting()
        if not config:
            return

        # Verify regions
        bookmakers_config = [
            (config["bookmaker"], config["position"], config["coords"])
        ]
        if not self.verify_regions(bookmakers_config):
            print("\n❌ User cancelled. Fix regions and try again.")
            return

        # Start betting
        print("\n🚀 Starting betting agent...")
        process = self.create_worker_process(config=config)
        process.start()
        self.processes.append(process)

        print(f"   ✅ Started: {config['bookmaker']} @ {config['position']}")
        print("\n💰 Betting active... (Ctrl+C to stop)")

        self.wait_for_processes()

        print("\n✅ Betting agent stopped")


class BettingProcess(Process):
    """Worker process for betting."""

    def __init__(
        self, config: Dict, db_path: Path, bet_lock: LockType, shutdown_event: EventType
    ):
        super().__init__(name=f"BettingAgent-{config['bookmaker']}")
        self.config = config
        self.db_path = db_path
        self.bet_lock = bet_lock
        self.shutdown_event = shutdown_event

        self.logger = None
        self.current_money = 0.0
        self.bet_placed = False

    def run(self):
        """Main process loop."""
        self.logger = AviatorLogger.get_logger(
            f"BettingAgent-{self.config['bookmaker']}"
        )
        self.logger.info("Process started")

        try:
            # Setup components
            self.setup_components()

            # Read initial balance
            self.current_money = self.my_money.read_text() or 0.0
            self.logger.info(f"Starting balance: {self.current_money:.2f}")

            # Main betting loop
            while not self.shutdown_event.is_set():
                phase = self.phase_detector.get_phase()

                if phase == GamePhase.BETTING and not self.bet_placed:
                    # Place bet
                    self.place_bet()
                    self.bet_placed = True

                elif phase == GamePhase.ENDED and self.bet_placed:
                    # Collect round result
                    self.handle_round_end()
                    self.bet_placed = False

                time.sleep(0.1)

        except Exception as e:
            self.logger.critical(f"Critical error: {e}", exc_info=True)
        finally:
            self.logger.info("Process stopped")

    def setup_components(self):
        """Setup screen readers and GUI controller."""
        coords = self.config["coords"]

        # Create readers for 3 score regions
        score_reader_small = ScreenReader(coords["score_region_small"])
        score_reader_medium = ScreenReader(coords["score_region_medium"])
        score_reader_large = ScreenReader(coords["score_region_large"])

        my_money_reader = ScreenReader(coords["my_money_region"])
        other_count_reader = ScreenReader(coords["other_count_region"])
        other_money_reader = ScreenReader(coords["other_money_region"])
        phase_reader = ScreenReader(coords["phase_region"])

        # Create region handlers
        self.my_money = MyMoney(my_money_reader)
        other_count = OtherCount(other_count_reader)
        other_money = OtherMoney(other_money_reader)
        self.phase_detector = GamePhaseDetector(phase_reader)

        # Create event collector
        event_collector = EventCollector(
            my_money=self.my_money,
            other_count=other_count,
            other_money=other_money,
            bookmaker=self.config["bookmaker"],
        )

        # Create score with 3 regions
        self.score = Score(
            score_region_small=coords["score_region_small"],
            score_region_medium=coords["score_region_medium"],
            score_region_large=coords["score_region_large"],
            phase_detector=self.phase_detector,
            event_collector=event_collector,
            auto_stop=self.config["auto_stop"],
        )

        # GUI controller
        self.gui = GUIController()

    def place_bet(self) -> bool:
        """
        Place a bet (transaction-safe).

        Returns:
            True if bet placed successfully, False otherwise
        """
        with self.bet_lock:
            try:
                coords = self.config["coords"]

                # Extract center coordinates for clicking
                play_amount_center = (
                    coords["play_amount_coords_1"]["left"]
                    + coords["play_amount_coords_1"]["width"] // 2,
                    coords["play_amount_coords_1"]["top"]
                    + coords["play_amount_coords_1"]["height"] // 2,
                )

                auto_play_center = (
                    coords["auto_play_coords_1"]["left"]
                    + coords["auto_play_coords_1"]["width"] // 2,
                    coords["auto_play_coords_1"]["top"]
                    + coords["auto_play_coords_1"]["height"] // 2,
                )

                play_button_center = (
                    coords["play_button_coords_1"]["left"]
                    + coords["play_button_coords_1"]["width"] // 2,
                    coords["play_button_coords_1"]["top"]
                    + coords["play_button_coords_1"]["height"] // 2,
                )

                # Set bet amount
                self.gui.click(play_amount_center)
                time.sleep(0.05)
                self.gui.select_all()
                self.gui.type_text(str(self.config["bet_amount"]))
                time.sleep(0.05)

                # Set auto cashout
                self.gui.click(auto_play_center)
                time.sleep(0.05)
                self.gui.select_all()
                self.gui.type_text(str(self.config["auto_stop"]))
                time.sleep(0.05)

                # Click play button
                self.gui.click(play_button_center)

                self.logger.info(
                    f"Bet placed: {self.config['bet_amount']:.2f} @ {self.config['auto_stop']:.2f}x"
                )
                return True

            except Exception as e:
                self.logger.error(f"Error placing bet: {e}")
                return False

    def handle_round_end(self):
        """Handle round end - collect result and save to database."""
        try:
            event_data = self.score.read_text()

            if event_data and event_data.get("event_type") == "ENDED_BETTING":
                money_after = event_data["my_money"]
                profit = money_after - self.current_money
                status = "WIN" if event_data["result"] else "LOSS"

                # Save to database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO bets 
                    (bookmaker, timestamp, bet_amount, auto_stop, final_score, 
                     money_before, money_after, profit, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        self.config["bookmaker"],
                        datetime.now().isoformat(),
                        self.config["bet_amount"],
                        self.config["auto_stop"],
                        event_data["score"],
                        self.current_money,
                        money_after,
                        profit,
                        status,
                    ),
                )

                conn.commit()
                conn.close()

                self.logger.info(
                    f"Round ended: {event_data['score']:.2f}x, "
                    f"Status: {status}, Profit: {profit:+.2f}"
                )

                # Update balance
                self.current_money = money_after

        except Exception as e:
            self.logger.error(f"Error handling round end: {e}")


def main():
    agent = BettingAgent()
    agent.run()


if __name__ == "__main__":
    main()
