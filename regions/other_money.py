# ========================================
# regions/other_money.py
# VERSION: 6.0 - Simplified with new ScreenReader
# ========================================

from typing import Optional

from core.screen_reader import ScreenReader
from regions.base_region import Region
from utils.logger import AviatorLogger


class OtherMoney(Region):
    """Read total money won by other players."""

    def __init__(self, screen_reader: ScreenReader):
        super().__init__(screen_reader)
        self.logger = AviatorLogger.get_logger("OtherMoney")

    def read_text(self) -> Optional[float]:
        """
        Read total money in format: 12,345.67

        Returns:
            Float money value or None
        """
        try:
            money = self.screen_reader.read_money()

            if money is not None:
                self.logger.debug(f"Other money: {money:.2f}")

            return money

        except Exception as e:
            self.logger.error(f"Error reading other money: {e}")
            return None
