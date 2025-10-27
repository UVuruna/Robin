"""
AVIATOR - Multi-Bookmaker Game Tracking & Automation System

Real-time data collection, ML predictions, and automated betting for Aviator game.
"""

__version__ = "2.0.0"
__author__ = "AVIATOR Team"

# Core imports for easy access
from core.communication.event_bus import EventBus, EventPublisher, EventSubscriber
from orchestration.process_manager import ProcessManager
from orchestration.shared_reader import SharedGameStateReader

# Initialize logging on import
from utils.logger import init_logging
init_logging()

__all__ = [
    'EventBus',
    'EventPublisher', 
    'EventSubscriber',
    'ProcessManager',
    'SharedGameStateReader',
    '__version__'
]

# Package metadata
__doc__ = """
AVIATOR Project
===============

High-performance system for simultaneous tracking of multiple online bookmakers.

Key Features:
- OCR speed < 15ms with template matching
- Support for 6+ bookmakers in parallel
- Batch database operations (50x faster)
- Event-driven architecture
- Automatic crash recovery
- ML-powered predictions

For more information, see README.md
"""