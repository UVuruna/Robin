# =============================================================================
# FILE: core/__init__.py
# VERSION: 6.0 - EventCollector removed from auto-import
# REASON: EventCollector depends on regions → causes circular import
# =============================================================================
"""
Core Functionality Package

Modules:
- coord_manager: Coordinate system management
- screen_reader: OCR screen reading
- gui_controller: Mouse/keyboard control
- event_collector: Event collector (import directly, not from __init__)

Usage:
    from core import CoordsManager, ScreenReader, GUIController
    from core.event_collector import EventCollector  # Direct import!
"""

from core.coord_manager import CoordsManager
from core.screen_reader import ScreenReader
from core.gui_controller import GUIController

# DO NOT import EventCollector here - it causes circular import!
# Users must: from core.event_collector import EventCollector

__all__ = [
    "CoordsManager",
    "ScreenReader",
    "GUIController",
    # 'EventCollector',  # ❌ Removed - import directly
]

__version__ = "6.0.0"
