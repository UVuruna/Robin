# gui/stats_queue.py
# VERSION: 1.0
# PURPOSE: Queue system for real-time stats from apps to GUI

import threading
import queue
from typing import Dict, Any, Optional
from datetime import datetime

from utils.logger import AviatorLogger


class StatsCollector:
    """
    Collects stats from apps via shared Queue.

    Apps put stats updates in the queue, GUI reads and displays them.
    CPU-efficient - no DB polling needed.
    """

    def __init__(self):
        self.logger = AviatorLogger.get_logger("StatsCollector")

        # Shared queue for stats (multiprocessing.Queue would be better for cross-process)
        self.stats_queue = queue.Queue(maxsize=1000)

        # Current stats for each app/bookmaker
        self.current_stats: Dict[str, Dict[str, Dict[str, Any]]] = {
            "data_collector": {},
            "rgb_collector": {},
            "betting_agent": {},
            "session_keeper": {},
        }

        self.lock = threading.Lock()

    def put_stats(self, app_name: str, bookmaker: str, stats: Dict[str, Any]):
        """
        Add stats update to queue.

        Args:
            app_name: Name of app
            bookmaker: Bookmaker name
            stats: Stats dict
        """
        try:
            self.stats_queue.put_nowait(
                {
                    "app": app_name,
                    "bookmaker": bookmaker,
                    "timestamp": datetime.now(),
                    "stats": stats,
                }
            )
        except queue.Full:
            # Drop oldest if full
            try:
                self.stats_queue.get_nowait()
                self.stats_queue.put_nowait(
                    {
                        "app": app_name,
                        "bookmaker": bookmaker,
                        "timestamp": datetime.now(),
                        "stats": stats,
                    }
                )
            except queue.Empty:
                pass

    def get_pending_updates(self, max_count: int = 50) -> list:
        """
        Get pending stats updates from queue.

        Args:
            max_count: Maximum updates to retrieve

        Returns:
            List of stats updates
        """
        updates = []

        for _ in range(max_count):
            try:
                update = self.stats_queue.get_nowait()
                updates.append(update)

                # Also update current stats cache
                with self.lock:
                    app = update["app"]
                    bookmaker = update["bookmaker"]
                    self.current_stats[app][bookmaker] = update["stats"]

            except queue.Empty:
                break

        return updates

    def get_current_stats(self, app_name: str, bookmaker: str) -> Optional[Dict]:
        """
        Get current cached stats for app/bookmaker.

        Args:
            app_name: Name of app
            bookmaker: Bookmaker name

        Returns:
            Stats dict or None
        """
        with self.lock:
            return self.current_stats.get(app_name, {}).get(bookmaker)

    def get_all_stats(self, app_name: str) -> Dict[str, Dict]:
        """
        Get all current stats for an app.

        Args:
            app_name: Name of app

        Returns:
            Dict of {bookmaker: stats}
        """
        with self.lock:
            return self.current_stats.get(app_name, {}).copy()


# Singleton instance
_stats_collector = None


def get_stats_collector() -> StatsCollector:
    """Get singleton stats collector instance."""
    global _stats_collector
    if _stats_collector is None:
        _stats_collector = StatsCollector()
    return _stats_collector
