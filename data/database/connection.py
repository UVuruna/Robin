"""
Module: Database Connection
Purpose: SQLite connection management (single connection, no pool)
Version: 2.0

This module provides:
- Single SQLite connection per database file
- WAL mode for better performance
- Thread-safe operations
- Context manager support
- Database initialization
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Any, List, Tuple


class DatabaseConnection:
    """
    SQLite database connection manager.

    Features:
    - Single connection per database (SQLite limitation)
    - WAL mode for concurrent reads
    - Thread-safe operations
    - Automatic database initialization
    - Schema creation
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to database file (uses default if None)
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Set database path
        if db_path is None:
            from config.settings import PATH
            db_path = PATH.main_game_db

        self.db_path = Path(db_path)

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Thread lock for connection safety
        self._lock = threading.RLock()

        # Connection
        self._connection: Optional[sqlite3.Connection] = None

        # Initialize connection
        self._initialize_connection()

        # Create tables if they don't exist
        self._create_tables()

        self.logger.info(f"Database connection initialized: {self.db_path}")

    def _initialize_connection(self):
        """Initialize SQLite connection with optimizations."""
        self._connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-threaded access
            isolation_level="DEFERRED",  # Default transaction mode
            timeout=30.0  # Wait up to 30 seconds for lock
        )

        # Enable WAL mode for better concurrency
        self._connection.execute("PRAGMA journal_mode = WAL")

        # Performance optimizations
        self._connection.execute("PRAGMA synchronous = NORMAL")  # Faster, still safe
        self._connection.execute("PRAGMA cache_size = 10000")  # 10,000 pages cache
        self._connection.execute("PRAGMA temp_store = MEMORY")  # Store temp data in RAM
        self._connection.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O

        # Enable foreign keys
        self._connection.execute("PRAGMA foreign_keys = ON")

        self.logger.debug("Connection initialized with WAL mode and optimizations")

    def _create_tables(self):
        """Create database tables if they don't exist."""
        with self._lock:
            cursor = self._connection.cursor()

            # Rounds table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bookmaker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    final_score REAL NOT NULL,
                    total_players INTEGER DEFAULT 0,
                    players_left INTEGER DEFAULT 0,
                    total_money REAL DEFAULT 0.0,
                    my_money REAL,
                    duration_seconds REAL DEFAULT 0.0,
                    loading_duration_ms INTEGER DEFAULT 0
                )
            """)

            # Thresholds table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS thresholds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bookmaker TEXT NOT NULL,
                    round_id INTEGER,
                    threshold REAL NOT NULL,
                    actual_score REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    players_left INTEGER,
                    total_money REAL,
                    FOREIGN KEY (round_id) REFERENCES rounds(id)
                )
            """)

            # RGB samples table (for ML training)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rgb_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bookmaker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    r_avg REAL NOT NULL,
                    g_avg REAL NOT NULL,
                    b_avg REAL NOT NULL,
                    r_std REAL NOT NULL,
                    g_std REAL NOT NULL,
                    b_std REAL NOT NULL,
                    phase INTEGER
                )
            """)

            # Bets table (for betting history)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bookmaker TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    amount REAL NOT NULL,
                    auto_stop REAL NOT NULL,
                    entry_score REAL DEFAULT 1.0,
                    exit_score REAL DEFAULT 0.0,
                    profit REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'pending',
                    placed_at TEXT NOT NULL,
                    ended_at TEXT
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rounds_bookmaker_timestamp
                ON rounds(bookmaker, timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_thresholds_bookmaker_timestamp
                ON thresholds(bookmaker, timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_thresholds_round_id
                ON thresholds(round_id)
            """)

            self._connection.commit()
            self.logger.info("Database tables created/verified")

    def execute(
        self,
        query: str,
        params: Tuple[Any, ...] = ()
    ) -> int:
        """
        Execute a single query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Last row ID for INSERT, affected rows for UPDATE/DELETE

        Example:
            >>> db = DatabaseConnection()
            >>> row_id = db.execute("INSERT INTO rounds (bookmaker, final_score) VALUES (?, ?)", ("Mozzart", 3.45))
        """
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            self._connection.commit()
            return cursor.lastrowid

    def execute_many(
        self,
        query: str,
        params_list: List[Tuple[Any, ...]]
    ) -> int:
        """
        Execute multiple queries with different parameters (batch operation).

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Number of rows affected

        Example:
            >>> db = DatabaseConnection()
            >>> params = [("Mozzart", 3.45), ("BalkanBet", 2.11)]
            >>> db.execute_many("INSERT INTO rounds (bookmaker, final_score) VALUES (?, ?)", params)
        """
        with self._lock:
            cursor = self._connection.cursor()
            cursor.executemany(query, params_list)
            self._connection.commit()
            return cursor.rowcount

    def fetchone(
        self,
        query: str,
        params: Tuple[Any, ...] = ()
    ) -> Optional[Tuple]:
        """
        Fetch one result from query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single row as tuple, or None if no results

        Example:
            >>> db = DatabaseConnection()
            >>> row = db.fetchone("SELECT * FROM rounds WHERE id = ?", (123,))
        """
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetchall(
        self,
        query: str,
        params: Tuple[Any, ...] = ()
    ) -> List[Tuple]:
        """
        Fetch all results from query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of rows as tuples

        Example:
            >>> db = DatabaseConnection()
            >>> rows = db.fetchall("SELECT * FROM rounds WHERE bookmaker = ?", ("Mozzart",))
        """
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    @contextmanager
    def transaction(self):
        """
        Context manager for explicit transactions.

        Example:
            >>> db = DatabaseConnection()
            >>> with db.transaction():
            ...     db.execute("INSERT INTO rounds ...")
            ...     db.execute("INSERT INTO thresholds ...")
        """
        with self._lock:
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def get_connection(self) -> sqlite3.Connection:
        """
        Get raw SQLite connection (use with caution).

        Returns:
            SQLite connection object
        """
        return self._connection

    def close(self):
        """Close database connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                self.logger.info("Database connection closed")

    def cleanup(self):
        """Cleanup resources (alias for close)."""
        self.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Singleton instance management
_db_instances = {}
_db_lock = threading.Lock()


def get_database(db_path: Optional[Path] = None) -> DatabaseConnection:
    """
    Get or create database connection (singleton per path).

    Args:
        db_path: Path to database file

    Returns:
        DatabaseConnection instance
    """
    global _db_instances

    # Use default path if none provided
    if db_path is None:
        from config.settings import PATH
        db_path = PATH.main_game_db

    db_path_str = str(db_path)

    with _db_lock:
        if db_path_str not in _db_instances:
            _db_instances[db_path_str] = DatabaseConnection(db_path)

        return _db_instances[db_path_str]


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    db = DatabaseConnection()

    # Test insert
    row_id = db.execute(
        "INSERT INTO rounds (bookmaker, timestamp, final_score) VALUES (?, datetime('now'), ?)",
        ("Test", 3.45)
    )
    print(f"Inserted row ID: {row_id}")

    # Test select
    row = db.fetchone("SELECT * FROM rounds WHERE id = ?", (row_id,))
    print(f"Retrieved row: {row}")

    # Test batch insert
    params = [
        ("Test1", 2.11),
        ("Test2", 5.67),
        ("Test3", 10.23)
    ]
    count = db.execute_many(
        "INSERT INTO rounds (bookmaker, timestamp, final_score) VALUES (?, datetime('now'), ?)",
        params
    )
    print(f"Batch inserted {count} rows")

    db.close()
