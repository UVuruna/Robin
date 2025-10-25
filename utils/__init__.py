# =============================================================================
# FILE: utils/__init__.py
# VERSION: 6.0 - Utils are scripts, minimal imports
# =============================================================================
"""
Utility Tools Package

Tools (run as scripts):
- region_editor: Interactive region coordinate setup
- region_visualizer: Screenshot verification
- performance_analyzer: Performance metrics
- pre_run_verification: System checks

Import directly:
    from utils.region_editor import RegionEditor
"""

# Utils are primarily scripts - import directly from modules
# No auto-imports to avoid loading unnecessary dependencies

__all__ = [
    "region_editor",
    "region_visualizer",
    "performance_analyzer",
    "pre_run_verification",
    "debug_monitor",
]

__version__ = "6.0.0"
