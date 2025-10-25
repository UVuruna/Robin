# ========================================
# regions/other_count.py
# VERSION: 6.0 - New format (234/567), 3 methods
# ========================================

from typing import Optional

from core.screen_reader import ScreenReader
from regions.base_region import Region
from utils.logger import AviatorLogger


class OtherCount(Region):
    """
    Read player count in format: 234/567 (left/total).

    Methods:
    - get_total_players() → 567
    - get_left_players() → 234
    - get_escaped_players() → 567 - 234 = 333
    """

    def __init__(self, screen_reader: ScreenReader):
        super().__init__(screen_reader)
        self.logger = AviatorLogger.get_logger("OtherCount")

        # Cache last reading
        self._last_left: Optional[int] = None
        self._last_total: Optional[int] = None

    def _read_count(self) -> bool:
        """
        Read and cache player count.

        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.screen_reader.read_player_count()

            if result is not None:
                self._last_left, self._last_total = result
                self.logger.debug(f"Player count: {self._last_left}/{self._last_total}")
                return True
            else:
                return False

        except Exception as e:
            self.logger.error(f"Error reading player count: {e}")
            return False

    def get_total_players(self) -> Optional[int]:
        """
        Get total number of players in the round.

        Returns:
            Total players or None
        """
        if self._read_count():
            return self._last_total
        return None

    def get_left_players(self) -> Optional[int]:
        """
        Get number of players still in the game.

        Returns:
            Players left or None
        """
        if self._read_count():
            return self._last_left
        return None

    def get_escaped_players(self) -> Optional[int]:
        """
        Get number of players who escaped (cashed out).

        Returns:
            Escaped players (total - left) or None
        """
        if self._read_count():
            if self._last_total is not None and self._last_left is not None:
                escaped = self._last_total - self._last_left
                self.logger.debug(f"Escaped players: {escaped}")
                return escaped
        return None

    def read_text(self) -> Optional[dict]:
        """
        Legacy method for compatibility.

        Returns:
            Dict with all counts or None
        """
        if self._read_count():
            return {
                "total_players": self._last_total,
                "left_players": self._last_left,
                "escaped_players": self._last_total - self._last_left,
            }
        return None
