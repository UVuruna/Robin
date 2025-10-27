"""Screen capture functionality."""
from core.capture.screen_capture import ScreenCapture
from core.capture.region_manager import RegionManager, Region, MonitorInfo, get_region_manager

__all__ = [
    'ScreenCapture',
    'RegionManager',
    'Region',
    'MonitorInfo',
    'get_region_manager'
]