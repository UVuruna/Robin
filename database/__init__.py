# =============================================================================
# FILE: database/__init__.py
# VERSION: 6.0 - Safe, no circular deps
# =============================================================================
"""
Database Layer Package

Models:
- MainGameDatabase: Game statistics
- RGBTrainingDatabase: RGB training data
- BettingHistoryDatabase: Betting history
- initialize_all_databases: Setup helper

Usage:
    from database import MainGameDatabase, initialize_all_databases
"""

from database.models import (
    MainGameDatabase,
    RGBTrainingDatabase,
    BettingHistoryDatabase,
    initialize_all_databases,
)

__all__ = [
    "MainGameDatabase",
    "RGBTrainingDatabase",
    "BettingHistoryDatabase",
    "initialize_all_databases",
]

__version__ = "6.0.0"
