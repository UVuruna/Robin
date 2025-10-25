# =============================================================================
# FILE: regions/__init__.py
# VERSION: 6.0 - Score removed from auto-import
# REASON: Score depends on EventCollector → causes circular import
# =============================================================================
"""
Screen Region Readers Package

Base classes (safe to import):
- base_region: Base Region class
- game_phase: GamePhaseDetector (no external deps)

Simple readers (safe to import):
- my_money: MyMoney reader
- other_count: OtherCount reader
- other_money: OtherMoney reader

Complex readers (import directly):
- score: Score reader (import directly, not from __init__)

Usage:
    from regions import MyMoney, OtherCount, OtherMoney, GamePhaseDetector
    from regions.score import Score  # Direct import!
"""

from regions.base_region import Region
from regions.game_phase import GamePhaseDetector
from regions.my_money import MyMoney
from regions.other_count import OtherCount
from regions.other_money import OtherMoney

# DO NOT import Score here - it depends on EventCollector!
# Users must: from regions.score import Score

__all__ = [
    "Region",
    "GamePhaseDetector",
    "MyMoney",
    "OtherCount",
    "OtherMoney",
    # 'Score',  # ❌ Removed - import directly
]

__version__ = "6.0.0"
