# ========================================
# regions/my_money.py
# VERSION: 6.0 - Simplified with new ScreenReader
# ========================================

from typing import Optional

from core.screen_reader import ScreenReader
from regions.base_region import Region
from utils.logger import AviatorLogger


class MyMoney(Region):
    """Read player's account balance."""

    def __init__(self, screen_reader: ScreenReader):
        super().__init__(screen_reader)
        self.logger = AviatorLogger.get_logger("MyMoney")

    def read_text(self) -> Optional[float]:
        """
        Read money value in format: 1,234.56

        Returns:
            Float money value or None
        """
        try:
            money = self.screen_reader.read_money()

            if money is not None:
                self.logger.debug(f"My money: {money:.2f}")

            return money

        except Exception as e:
            self.logger.error(f"Error reading my money: {e}")
            return None
