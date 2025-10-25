# core/event_collector.py
# VERSION: 1.0 - NEW FILE
# PURPOSE: Coordinates data collection when score detects THRESHOLD or ENDED

from typing import Dict, Optional, Any
from datetime import datetime

from regions.my_money import MyMoney
from regions.other_count import OtherCount
from regions.other_money import OtherMoney
from utils.logger import AviatorLogger


class EventCollector:
    """
    Collects data from multiple regions when triggered by score events.

    Events:
    1. THRESHOLD reached (1.5x, 2.0x, 2.5x, 3.0x, 4.0x, 5.0x)
       → Collects: score, players_escaped, other_money_won

    2. ENDED (game finished)
       → For betting_agent: score, my_money, auto_cashout
       → For data_collector: score, total_players, players_escaped, other_money_won
    """

    def __init__(
        self,
        my_money: MyMoney,
        other_count: OtherCount,
        other_money: OtherMoney,
        bookmaker: str,
    ):
        self.my_money = my_money
        self.other_count = other_count
        self.other_money = other_money
        self.bookmaker = bookmaker

        self.logger = AviatorLogger.get_logger(f"EventCollector-{bookmaker}")

    def collect_threshold_data(self, score: float) -> Optional[Dict[str, Any]]:
        """
        Collect data when score reaches a threshold.

        Args:
            score: Current score (e.g., 2.0, 3.0, 5.0)

        Returns:
            Dict with threshold data or None if collection failed
        """
        try:
            players_escaped = self.other_count.get_escaped_players()
            other_money_won = self.other_money.read_text()

            if players_escaped is None or other_money_won is None:
                self.logger.warning(f"Failed to collect threshold data at {score:.2f}x")
                return None

            data = {
                "event_type": "THRESHOLD",
                "bookmaker": self.bookmaker,
                "timestamp": datetime.now(),
                "score": score,
                "players_escaped": players_escaped,
                "other_money_won": other_money_won,
            }

            self.logger.info(
                f"Threshold {score:.2f}x: "
                f"escaped={players_escaped}, money={other_money_won:.2f}"
            )

            return data

        except Exception as e:
            self.logger.error(f"Error collecting threshold data: {e}")
            return None

    def collect_ended_for_betting(
        self, score: float, auto_cashout: float
    ) -> Optional[Dict[str, Any]]:
        """
        Collect data when game ends (for betting_agent).

        Args:
            score: Final score
            auto_cashout: Configured auto-cashout value

        Returns:
            Dict with ended data or None if collection failed
        """
        try:
            my_money = self.my_money.read_text()

            if my_money is None:
                self.logger.warning("Failed to read my_money for ENDED")
                return None

            data = {
                "event_type": "ENDED_BETTING",
                "bookmaker": self.bookmaker,
                "timestamp": datetime.now(),
                "score": score,
                "my_money": my_money,
                "auto_cashout": auto_cashout,
                "result": score >= auto_cashout,  # WIN or LOSS
            }

            self.logger.info(
                f"Game ended: score={score:.2f}x, "
                f"money={my_money:.2f}, result={'WIN' if data['result'] else 'LOSS'}"
            )

            return data

        except Exception as e:
            self.logger.error(f"Error collecting ended data (betting): {e}")
            return None

    def collect_ended_for_data(self, score: float) -> Optional[Dict[str, Any]]:
        """
        Collect data when game ends (for data_collector).

        Args:
            score: Final score

        Returns:
            Dict with ended data or None if collection failed
        """
        try:
            total_players = self.other_count.get_total_players()
            players_escaped = self.other_count.get_escaped_players()
            other_money_won = self.other_money.read_text()

            if None in [total_players, players_escaped, other_money_won]:
                self.logger.warning("Failed to collect complete data for ENDED")
                return None

            data = {
                "event_type": "ENDED_DATA",
                "bookmaker": self.bookmaker,
                "timestamp": datetime.now(),
                "score": score,
                "total_players": total_players,
                "players_escaped": players_escaped,
                "other_money_won": other_money_won,
            }

            self.logger.info(
                f"Game ended: score={score:.2f}x, "
                f"players={players_escaped}/{total_players}, money={other_money_won:.2f}"
            )

            return data

        except Exception as e:
            self.logger.error(f"Error collecting ended data (data collector): {e}")
            return None

    def collect_ended_full(
        self, score: float, auto_cashout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Collect ALL data when game ends (for both betting and data collection).

        Args:
            score: Final score
            auto_cashout: Optional auto-cashout value (for betting)

        Returns:
            Dict with all ended data or None if collection failed
        """
        try:
            my_money = self.my_money.read_text()
            total_players = self.other_count.get_total_players()
            players_escaped = self.other_count.get_escaped_players()
            other_money_won = self.other_money.read_text()

            if None in [my_money, total_players, players_escaped, other_money_won]:
                self.logger.warning("Failed to collect complete ENDED data")
                return None

            data = {
                "event_type": "ENDED_FULL",
                "bookmaker": self.bookmaker,
                "timestamp": datetime.now(),
                "score": score,
                "my_money": my_money,
                "total_players": total_players,
                "players_escaped": players_escaped,
                "other_money_won": other_money_won,
            }

            if auto_cashout is not None:
                data["auto_cashout"] = auto_cashout
                data["result"] = score >= auto_cashout

            self.logger.info(
                f"Game ended (FULL): score={score:.2f}x, money={my_money:.2f}, "
                f"players={players_escaped}/{total_players}, won={other_money_won:.2f}"
            )

            return data

        except Exception as e:
            self.logger.error(f"Error collecting full ended data: {e}")
            return None
