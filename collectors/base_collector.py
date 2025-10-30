"""
Module: Base Collector
Purpose: Abstract base class for all data collectors
Version: 2.0

This module provides the base class that all collectors must extend.
Following the architecture principles:
- Uses SharedGameState for data access (no direct OCR)
- Uses BatchDatabaseWriter for efficient database operations
- Uses EventBus for communication
- Implements proper error handling and statistics tracking
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from core.communication.shared_state import SharedGameState, BookmakerState
from core.communication.event_bus import EventPublisher, EventType
from data.database.batch_writer import BatchDatabaseWriter


@dataclass
class CollectorStats:
    """Statistics tracked by collectors."""
    cycles_completed: int = 0
    data_points_collected: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)
    last_collection_time: Optional[float] = None

    def uptime_seconds(self) -> float:
        """Get collector uptime in seconds."""
        return time.time() - self.start_time

    def collection_rate(self) -> float:
        """Get data points per second."""
        uptime = self.uptime_seconds()
        if uptime > 0:
            return self.data_points_collected / uptime
        return 0.0


class BaseCollector(ABC):
    """
    Abstract base class for all collectors.

    Collectors are responsible for:
    1. Reading data from SharedGameState (NOT direct OCR)
    2. Processing and validating data
    3. Writing to database via BatchDatabaseWriter
    4. Publishing events via EventBus
    5. Tracking statistics

    Subclasses must implement:
    - collect_cycle(): Main collection logic
    - validate_data(): Data validation before writing
    - get_collection_name(): Identifier for this collector
    """

    def __init__(
        self,
        bookmaker: str,
        shared_state: SharedGameState,
        db_writer: BatchDatabaseWriter,
        event_publisher: Optional[EventPublisher] = None
    ):
        """
        Initialize base collector.

        Args:
            bookmaker: Name of bookmaker this collector monitors
            shared_state: SharedGameState instance for data access
            db_writer: BatchDatabaseWriter for database operations
            event_publisher: Optional EventPublisher for events
        """
        self.bookmaker = bookmaker
        self.shared_state = shared_state
        self.db_writer = db_writer
        self.event_publisher = event_publisher or EventPublisher(
            f"{self.get_collection_name()}-{bookmaker}"
        )

        # Statistics
        self.stats = CollectorStats()

        # State tracking
        self.last_state: Optional[BookmakerState] = None
        self.is_running = False

        # Logging
        self.logger = logging.getLogger(
            f"{self.get_collection_name()}-{bookmaker}"
        )
        self.logger.setLevel(logging.INFO)

    @abstractmethod
    def collect_cycle(self) -> None:
        """
        Perform one collection cycle.

        This is the main method that subclasses must implement.
        Should:
        1. Read current state from shared_state
        2. Process data based on business logic
        3. Validate data
        4. Write to database (via batch writer)
        5. Publish events if needed

        Raises:
            Exception: Any errors during collection
        """
        pass

    @abstractmethod
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate data before writing to database.

        Args:
            data: Data dictionary to validate

        Returns:
            True if data is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_collection_name(self) -> str:
        """
        Get the name of this collector.

        Returns:
            Collector name (e.g., "MainCollector", "PhaseCollector")
        """
        pass

    def get_current_state(self) -> Optional[BookmakerState]:
        """
        Get current state from shared memory.

        Returns:
            BookmakerState or None if not available
        """
        try:
            state = self.shared_state.get_state(self.bookmaker)
            self.last_state = state
            return state
        except Exception as e:
            self.logger.error(f"Failed to get state: {e}")
            self.stats.errors += 1
            return None

    def write_to_database(self, table: str, data: Dict[str, Any]) -> bool:
        """
        Write data to database via batch writer.

        Args:
            table: Table name
            data: Data dictionary to write

        Returns:
            True if write was successful or queued
        """
        try:
            # Validate data first
            if not self.validate_data(data):
                self.logger.warning(f"Data validation failed, skipping write: {data}")
                return False

            # Add to batch writer
            self.db_writer.write(table, data)
            self.stats.data_points_collected += 1
            return True

        except Exception as e:
            self.logger.error(f"Failed to write to database: {e}")
            self.stats.errors += 1
            return False

    def publish_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        priority: int = 5
    ) -> None:
        """
        Publish an event via EventBus.

        Args:
            event_type: Type of event
            data: Event data
            priority: Event priority (0=highest, 9=lowest)
        """
        try:
            # Add bookmaker to event data
            data["bookmaker"] = self.bookmaker
            data["collector"] = self.get_collection_name()
            data["timestamp"] = datetime.now().isoformat()

            self.event_publisher.publish(event_type, data, priority)

        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            self.stats.errors += 1

    def run_cycle(self) -> bool:
        """
        Run one collection cycle with error handling.

        Returns:
            True if cycle completed successfully
        """
        try:
            cycle_start = time.time()

            # Run collection logic
            self.collect_cycle()

            # Update statistics
            self.stats.cycles_completed += 1
            self.stats.last_collection_time = time.time()

            # Log slow cycles
            cycle_duration = time.time() - cycle_start
            if cycle_duration > 1.0:  # Cycles should be fast
                self.logger.warning(
                    f"Slow collection cycle: {cycle_duration:.2f}s"
                )

            return True

        except Exception as e:
            self.logger.error(f"Collection cycle failed: {e}", exc_info=True)
            self.stats.errors += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get collector statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "collector": self.get_collection_name(),
            "bookmaker": self.bookmaker,
            "cycles_completed": self.stats.cycles_completed,
            "data_points_collected": self.stats.data_points_collected,
            "errors": self.stats.errors,
            "uptime_seconds": self.stats.uptime_seconds(),
            "uptime_hours": self.stats.uptime_seconds() / 3600.0,
            "collection_rate": self.stats.collection_rate(),
            "error_rate": (
                self.stats.errors / self.stats.cycles_completed * 100
                if self.stats.cycles_completed > 0
                else 0.0
            ),
            "last_collection": self.stats.last_collection_time
        }

    def log_stats(self) -> None:
        """Log current statistics."""
        stats = self.get_stats()
        self.logger.info(
            f"Stats: {stats['cycles_completed']} cycles, "
            f"{stats['data_points_collected']} data points, "
            f"{stats['errors']} errors, "
            f"{stats['collection_rate']:.2f} points/sec"
        )

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = CollectorStats()
        self.logger.info("Statistics reset")

    def cleanup(self) -> None:
        """
        Cleanup collector resources.

        Subclasses can override to add custom cleanup logic.
        """
        self.logger.info(f"Cleaning up {self.get_collection_name()}")

        # Log final statistics
        self.log_stats()

        # Mark as not running
        self.is_running = False

        self.logger.info("Collector cleanup complete")


if __name__ == "__main__":
    # Example usage / testing
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    from core.communication.shared_state import get_shared_state
    from data.database.batch_writer import BatchConfig

    # Example concrete collector for testing
    class TestCollector(BaseCollector):
        def collect_cycle(self) -> None:
            state = self.get_current_state()
            if state:
                print(f"Current phase: {state.phase}, score: {state.score}")

        def validate_data(self, data: Dict[str, Any]) -> bool:
            return True  # Accept all data for testing

        def get_collection_name(self) -> str:
            return "TestCollector"

    # Create test collector
    shared_state = get_shared_state()
    db_config = BatchConfig(batch_size=10, flush_interval=1.0)
    db_writer = BatchDatabaseWriter("test.db", db_config)

    collector = TestCollector(
        bookmaker="TestBookmaker",
        shared_state=shared_state,
        db_writer=db_writer
    )

    print(f"\nTest collector created: {collector.get_collection_name()}")
    print(f"Initial stats: {collector.get_stats()}")

    # Run a few cycles
    for i in range(5):
        success = collector.run_cycle()
        print(f"Cycle {i+1}: {'Success' if success else 'Failed'}")
        time.sleep(0.1)

    # Show final stats
    print(f"\nFinal stats: {collector.get_stats()}")

    # Cleanup
    collector.cleanup()
