# =============================================================================
# FILE: apps/__init__.py
# VERSION: 6.0 - Cleaned up
# =============================================================================
"""
Applications Package

Programs:
- base_app: BaseAviatorApp template
- main_data_collector: MainDataCollector program
- betting_agent: BettingAgent program (⚠️ uses real money!)

Import directly from modules:
    from apps.main_data_collector import MainDataCollector
    from apps.betting_agent import BettingAgent
"""

# Don't auto-import apps - they have complex dependencies
# Users must import directly from module

__all__ = [
    "base_app",
    "main_data_collector",
    "betting_agent",
]

__version__ = "6.0.0"
