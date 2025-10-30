# gui/centralized_stats_reader.py
# VERSION: 1.0 - Centralized database reader for all stats widgets
# Author: Claude Opus 4.1
# Date: 2024-10-30

"""
Centralized Stats Reader - Single database connection for all widgets.

This module provides a centralized reader that:
1. Uses a single shared database connection
2. Caches query results to avoid redundant queries
3. Provides last round data from memory
4. Reduces database load by 90%+

Instead of each widget creating its own connection and querying every 1-3 seconds,
this reader queries once for all widgets at the configured frequency (30-60 seconds).
"""

import sqlite3
import time
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from threading import Lock
from PySide6.QtCore import QObject, QTimer, Signal

from config.settings import PATH, COLLECT
from utils.logger import AviatorLogger


@dataclass
class CachedStats:
    """Cached statistics with timestamp."""
    data: Dict[str, Any]
    cached_at: float
    ttl: float = 30.0  # Time to live in seconds

    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        return time.time() - self.cached_at < self.ttl


@dataclass
class LastRoundData:
    """Last round data kept in memory for instant access."""
    bookmaker: str
    score: float
    timestamp: str
    players_left: int = 0
    total_money: float = 0.0
    duration: float = 0.0
    cached_at: float = field(default_factory=time.time)


class CentralizedStatsReader(QObject):
    """
    Centralized database reader for all stats widgets.

    Features:
    - Single shared database connection (not per-widget)
    - Caches query results with TTL
    - Keeps last round data in memory
    - Batch queries for all bookmakers at once
    - Thread-safe with locks
    """

    # Signals for data updates
    data_updated = Signal(str, dict)  # collector_type, data
    last_round_updated = Signal(str, dict)  # bookmaker, round_data

    def __init__(self):
        super().__init__()
        self.logger = AviatorLogger.get_logger("CentralizedStatsReader")

        # Database connections (one per database)
        self.connections: Dict[str, sqlite3.Connection] = {}
        self.connection_lock = Lock()

        # Cache storage
        self.cache: Dict[str, CachedStats] = {}
        self.cache_lock = Lock()

        # Last round data (always fresh)
        self.last_rounds: Dict[str, LastRoundData] = {}
        self.last_round_lock = Lock()

        # Configuration
        self.query_frequency = COLLECT.database_query_frequency
        self.cache_ttl = self.query_frequency  # Cache TTL matches query frequency

        # Database paths
        self.db_paths = {
            'main': PATH.main_game_db,
            'betting': PATH.betting_history_db,
            'rgb': PATH.rgb_training_db
        }

        # Initialize connections
        self._init_connections()

        # Setup refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_all_stats)
        self.refresh_timer.start(self.query_frequency * 1000)

        # Initial fetch
        self.refresh_all_stats()

        self.logger.info(
            f"Initialized with query frequency: {self.query_frequency}s, "
            f"cache TTL: {self.cache_ttl}s"
        )

    def _init_connections(self):
        """Initialize database connections."""
        with self.connection_lock:
            for db_name, db_path in self.db_paths.items():
                if db_path.exists():
                    try:
                        conn = sqlite3.connect(
                            str(db_path),
                            check_same_thread=False  # Allow multi-thread access
                        )
                        conn.row_factory = sqlite3.Row  # Return dict-like rows
                        self.connections[db_name] = conn
                        self.logger.debug(f"Connected to {db_name} database")
                    except Exception as e:
                        self.logger.error(f"Failed to connect to {db_name} database: {e}")

    def get_stats(self, collector_type: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get statistics for a collector type.

        Args:
            collector_type: Type of collector ('data', 'betting', 'rgb')
            force_refresh: Force database query even if cache is valid

        Returns:
            Statistics dictionary or None if error
        """
        cache_key = f"stats_{collector_type}"

        # Check cache first (unless forced refresh)
        if not force_refresh:
            with self.cache_lock:
                if cache_key in self.cache and self.cache[cache_key].is_valid():
                    return self.cache[cache_key].data

        # Query database
        stats = self._query_stats(collector_type)

        # Update cache
        if stats:
            with self.cache_lock:
                self.cache[cache_key] = CachedStats(
                    data=stats,
                    cached_at=time.time(),
                    ttl=self.cache_ttl
                )

            # Emit update signal
            self.data_updated.emit(collector_type, stats)

        return stats

    def _query_stats(self, collector_type: str) -> Optional[Dict]:
        """Query database for statistics."""
        try:
            if collector_type == 'data':
                return self._query_data_collector_stats()
            elif collector_type == 'betting':
                return self._query_betting_stats()
            elif collector_type == 'rgb':
                return self._query_rgb_stats()
            else:
                self.logger.warning(f"Unknown collector type: {collector_type}")
                return None
        except Exception as e:
            self.logger.error(f"Error querying {collector_type} stats: {e}")
            return None

    def _query_data_collector_stats(self) -> Dict:
        """Query data collector statistics."""
        conn = self.connections.get('main')
        if not conn:
            return {}

        stats = {
            'total_rounds': 0,
            'average_score': 0.0,
            'thresholds_crossed': {},
            'rounds_per_bookmaker': {},
            'session_start': datetime.now().isoformat()
        }

        try:
            cursor = conn.cursor()

            # Total rounds and average score
            cursor.execute("""
                SELECT COUNT(*) as count, AVG(final_score) as avg_score
                FROM rounds
                WHERE timestamp >= datetime('now', '-24 hours')
            """)
            row = cursor.fetchone()
            if row:
                stats['total_rounds'] = row['count'] or 0
                stats['average_score'] = row['avg_score'] or 0.0

            # Rounds per bookmaker
            cursor.execute("""
                SELECT bookmaker, COUNT(*) as count, AVG(final_score) as avg_score
                FROM rounds
                WHERE timestamp >= datetime('now', '-24 hours')
                GROUP BY bookmaker
            """)
            for row in cursor.fetchall():
                stats['rounds_per_bookmaker'][row['bookmaker']] = {
                    'count': row['count'],
                    'average_score': row['avg_score']
                }

            # Threshold statistics
            cursor.execute("""
                SELECT threshold, COUNT(*) as count
                FROM threshold_scores
                WHERE timestamp >= datetime('now', '-24 hours')
                GROUP BY threshold
            """)
            for row in cursor.fetchall():
                stats['thresholds_crossed'][f"{row['threshold']}x"] = row['count']

        except Exception as e:
            self.logger.error(f"Error querying data collector stats: {e}")

        return stats

    def _query_betting_stats(self) -> Dict:
        """Query betting agent statistics."""
        conn = self.connections.get('betting')
        if not conn:
            return {}

        stats = {
            'total_bets': 0,
            'total_wins': 0,
            'total_losses': 0,
            'total_profit': 0.0,
            'win_rate': 0.0,
            'bets_per_bookmaker': {}
        }

        try:
            cursor = conn.cursor()

            # Total betting statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(profit) as total_profit
                FROM betting_history
                WHERE placed_at >= datetime('now', '-24 hours')
            """)
            row = cursor.fetchone()
            if row:
                stats['total_bets'] = row['total_bets'] or 0
                stats['total_wins'] = row['wins'] or 0
                stats['total_losses'] = row['losses'] or 0
                stats['total_profit'] = row['total_profit'] or 0.0

                if stats['total_bets'] > 0:
                    stats['win_rate'] = (stats['total_wins'] / stats['total_bets']) * 100

            # Per bookmaker statistics
            cursor.execute("""
                SELECT
                    bookmaker,
                    COUNT(*) as bets,
                    SUM(profit) as profit,
                    AVG(exit_score) as avg_score
                FROM betting_history
                WHERE placed_at >= datetime('now', '-24 hours')
                GROUP BY bookmaker
            """)
            for row in cursor.fetchall():
                stats['bets_per_bookmaker'][row['bookmaker']] = {
                    'bets': row['bets'],
                    'profit': row['profit'],
                    'average_score': row['avg_score']
                }

        except Exception as e:
            self.logger.error(f"Error querying betting stats: {e}")

        return stats

    def _query_rgb_stats(self) -> Dict:
        """Query RGB collector statistics."""
        conn = self.connections.get('rgb')
        if not conn:
            return {}

        stats = {
            'total_samples': 0,
            'samples_per_bookmaker': {},
            'sample_rate': 0.0
        }

        try:
            cursor = conn.cursor()

            # Total samples
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM rgb_samples
                WHERE timestamp >= datetime('now', '-1 hour')
            """)
            row = cursor.fetchone()
            if row:
                stats['total_samples'] = row['count'] or 0
                stats['sample_rate'] = stats['total_samples'] / 3600.0  # Per second

            # Per bookmaker samples
            cursor.execute("""
                SELECT bookmaker, COUNT(*) as count
                FROM rgb_samples
                WHERE timestamp >= datetime('now', '-1 hour')
                GROUP BY bookmaker
            """)
            for row in cursor.fetchall():
                stats['samples_per_bookmaker'][row['bookmaker']] = row['count']

        except Exception as e:
            self.logger.error(f"Error querying RGB stats: {e}")

        return stats

    def update_last_round(self, bookmaker: str, round_data: Dict):
        """
        Update last round data (called by collectors).

        Args:
            bookmaker: Bookmaker name
            round_data: Round data dictionary
        """
        with self.last_round_lock:
            self.last_rounds[bookmaker] = LastRoundData(
                bookmaker=bookmaker,
                score=round_data.get('final_score', 0.0),
                timestamp=round_data.get('timestamp', datetime.now().isoformat()),
                players_left=round_data.get('players_left', 0),
                total_money=round_data.get('total_money', 0.0),
                duration=round_data.get('duration', 0.0)
            )

        # Emit signal
        self.last_round_updated.emit(bookmaker, round_data)

    def get_last_round(self, bookmaker: str) -> Optional[Dict]:
        """Get last round data for a bookmaker (instant, from memory)."""
        with self.last_round_lock:
            if bookmaker in self.last_rounds:
                round_data = self.last_rounds[bookmaker]
                return {
                    'score': round_data.score,
                    'timestamp': round_data.timestamp,
                    'players_left': round_data.players_left,
                    'total_money': round_data.total_money,
                    'duration': round_data.duration,
                    'age_seconds': time.time() - round_data.cached_at
                }
        return None

    def get_all_last_rounds(self) -> Dict[str, Dict]:
        """Get all last rounds (instant, from memory)."""
        result = {}
        with self.last_round_lock:
            for bookmaker, round_data in self.last_rounds.items():
                result[bookmaker] = {
                    'score': round_data.score,
                    'timestamp': round_data.timestamp,
                    'players_left': round_data.players_left,
                    'total_money': round_data.total_money,
                    'duration': round_data.duration,
                    'age_seconds': time.time() - round_data.cached_at
                }
        return result

    def refresh_all_stats(self):
        """Refresh all statistics (called by timer)."""
        self.logger.debug("Refreshing all statistics...")

        # Query all collector types
        for collector_type in ['data', 'betting', 'rgb']:
            self.get_stats(collector_type, force_refresh=True)

        self.logger.debug("Statistics refresh complete")

    def set_query_frequency(self, seconds: int):
        """Update query frequency."""
        if 5 <= seconds <= 300:
            self.query_frequency = seconds
            self.cache_ttl = seconds

            # Restart timer with new frequency
            self.refresh_timer.stop()
            self.refresh_timer.start(seconds * 1000)

            self.logger.info(f"Query frequency updated to {seconds} seconds")

    def cleanup(self):
        """Clean up resources."""
        # Stop timer
        self.refresh_timer.stop()

        # Close database connections
        with self.connection_lock:
            for conn in self.connections.values():
                conn.close()

        self.logger.info("Centralized stats reader cleaned up")


# Singleton instance
_stats_reader_instance: Optional[CentralizedStatsReader] = None


def get_stats_reader() -> CentralizedStatsReader:
    """Get or create the singleton stats reader instance."""
    global _stats_reader_instance
    if _stats_reader_instance is None:
        _stats_reader_instance = CentralizedStatsReader()
    return _stats_reader_instance


if __name__ == "__main__":
    # Testing
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    print("=== Centralized Stats Reader Test ===\n")

    reader = get_stats_reader()

    # Test data collector stats
    print("Data Collector Stats:")
    stats = reader.get_stats('data')
    if stats:
        for key, value in stats.items():
            print(f"  {key}: {value}")

    print("\nBetting Agent Stats:")
    stats = reader.get_stats('betting')
    if stats:
        for key, value in stats.items():
            print(f"  {key}: {value}")

    # Test last round data
    print("\nLast Rounds:")
    last_rounds = reader.get_all_last_rounds()
    if last_rounds:
        for bookmaker, data in last_rounds.items():
            print(f"  {bookmaker}: {data}")
    else:
        print("  No last round data available")

    # Simulate last round update
    reader.update_last_round("TestBookmaker", {
        'final_score': 3.45,
        'timestamp': datetime.now().isoformat(),
        'players_left': 123,
        'total_money': 45678.90,
        'duration': 25.5
    })

    print("\nAfter update:")
    last_round = reader.get_last_round("TestBookmaker")
    if last_round:
        print(f"  TestBookmaker: {last_round}")

    # Cleanup
    reader.cleanup()
    print("\nTest complete!")