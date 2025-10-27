"""
Module: Main Data Collector
Purpose: Main data collector for rounds and threshold tracking
Version: 2.0 (Refactored to use BaseCollector and Phase 1 modules)

This collector:
- Tracks complete rounds (start to end)
- Monitors threshold crossings (1.5x, 2.0x, 2.5x, etc.)
- Records round statistics (duration, players, money)
- Uses SharedGameState for instant data access (no OCR)
"""

import time
import logging
from typing import Dict, Optional, Any, Set, List
from datetime import datetime

from collectors.base_collector import BaseCollector
from core.communication.shared_state import SharedGameState, GamePhase
from core.communication.event_bus import EventPublisher, EventType
from data_layer.database.batch_writer import BatchDatabaseWriter


class MainDataCollector(BaseCollector):
    """
    Main data collector - tracks rounds and thresholds.

    Features:
    - Round lifecycle tracking (start → active → end)
    - Threshold crossing detection with tolerance
    - Comprehensive round statistics
    - Event publishing for all important events
    """

    # Thresholds to track
    THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]
    THRESHOLD_TOLERANCE = 0.08  # ±0.08x tolerance

    def __init__(
        self,
        bookmaker: str,
        shared_state: SharedGameState,
        db_writer: BatchDatabaseWriter,
        event_publisher: Optional[EventPublisher] = None
    ):
        """
        Initialize main data collector.

        Args:
            bookmaker: Name of bookmaker
            shared_state: SharedGameState instance
            db_writer: BatchDatabaseWriter instance
            event_publisher: Optional EventPublisher
        """
        super().__init__(bookmaker, shared_state, db_writer, event_publisher)

        # Round tracking
        self.current_round_id = None
        self.round_start_time: Optional[float] = None
        self.thresholds_crossed: Set[float] = set()
        self.threshold_data: List[Dict] = []

        # State tracking
        self.last_phase = GamePhase.UNKNOWN
        self.last_score: Optional[float] = None

        # Statistics
        self.rounds_collected = 0
        self.thresholds_collected = 0

        self.logger.info(f"Main collector initialized for {bookmaker}")

    def get_collection_name(self) -> str:
        """Get collector name."""
        return "MainCollector"

    def collect_cycle(self) -> None:
        """
        Perform one collection cycle.

        Checks for phase changes and tracks thresholds during active rounds.
        """
        # Get current state
        state = self.get_current_state()
        if not state:
            return

        current_phase = state.phase
        current_score = state.score

        # Handle phase changes
        if current_phase != self.last_phase:
            self._handle_phase_change(self.last_phase, current_phase, state)

        # Track during active game
        if self._is_active_phase(current_phase):
            self._track_active_game(current_score, state)

        # Update tracking
        self.last_phase = current_phase
        self.last_score = current_score

    def _is_active_phase(self, phase: GamePhase) -> bool:
        """Check if phase is active (game in progress)."""
        return phase in [GamePhase.PLAYING, GamePhase.STARTED]

    def _handle_phase_change(
        self,
        old_phase: GamePhase,
        new_phase: GamePhase,
        state
    ) -> None:
        """
        Handle phase transitions.

        Args:
            old_phase: Previous phase
            new_phase: New phase
            state: Current state
        """
        self.logger.debug(f"Phase change: {old_phase.value} → {new_phase.value}")

        # Round started
        if self._is_round_start(old_phase, new_phase):
            self._handle_round_start(state)

        # Round ended
        elif self._is_round_end(old_phase, new_phase):
            self._handle_round_end(state)

    def _is_round_start(self, old_phase: GamePhase, new_phase: GamePhase) -> bool:
        """Check if this is a round start transition."""
        return (
            new_phase in [GamePhase.STARTED, GamePhase.PLAYING] and
            old_phase in [GamePhase.BETTING, GamePhase.LOADING, GamePhase.UNKNOWN]
        )

    def _is_round_end(self, old_phase: GamePhase, new_phase: GamePhase) -> bool:
        """Check if this is a round end transition."""
        return (
            new_phase == GamePhase.ENDED and
            old_phase in [GamePhase.PLAYING, GamePhase.STARTED]
        )

    def _handle_round_start(self, state) -> None:
        """Handle round start."""
        self.logger.info(f"🎬 Round started for {self.bookmaker}")

        # Reset round data
        self.round_start_time = time.time()
        self.thresholds_crossed.clear()
        self.threshold_data.clear()

        # Publish event
        self.publish_event(
            EventType.ROUND_START,
            {"start_time": self.round_start_time},
            priority=2
        )

    def _handle_round_end(self, state) -> None:
        """Handle round end and save to database."""
        final_score = state.score or self.last_score

        if not final_score:
            self.logger.warning("Round ended without final score")
            return

        self.logger.info(f"🔴 Round ended: {final_score:.2f}x")

        # Calculate round duration
        duration = None
        if self.round_start_time:
            duration = time.time() - self.round_start_time

        # Save round to database
        round_data = {
            "bookmaker": self.bookmaker,
            "timestamp": datetime.now().isoformat(),
            "final_score": final_score,
            "total_players": state.player_count_total,
            "players_left": state.player_count_current,
            "total_money": state.total_money,
            "duration_seconds": duration
        }

        if self.write_to_database("rounds", round_data):
            self.rounds_collected += 1

        # Save threshold data
        for threshold in self.threshold_data:
            if self.write_to_database("threshold_scores", threshold):
                self.thresholds_collected += 1

        # Publish event
        self.publish_event(
            EventType.ROUND_END,
            {
                "final_score": final_score,
                "duration": duration,
                "thresholds_crossed": len(self.threshold_data)
            },
            priority=2
        )

        # Log stats periodically
        if self.rounds_collected % 10 == 0:
            self.log_stats()

    def _track_active_game(self, current_score: Optional[float], state) -> None:
        """
        Track thresholds during active game.

        Args:
            current_score: Current score
            state: Current state
        """
        if not current_score or not self.last_score:
            return

        # Check if score is rising
        if current_score > self.last_score:
            # Check for threshold crossing
            threshold = self._check_threshold_crossed(self.last_score, current_score)

            if threshold and threshold not in self.thresholds_crossed:
                self._handle_threshold_crossed(current_score, threshold, state)

    def _check_threshold_crossed(
        self,
        prev_score: float,
        current_score: float
    ) -> Optional[float]:
        """
        Check if a threshold was crossed.

        Args:
            prev_score: Previous score
            current_score: Current score

        Returns:
            Threshold value if crossed, None otherwise
        """
        for threshold in self.THRESHOLDS:
            if threshold in self.thresholds_crossed:
                continue

            if prev_score < threshold <= current_score:
                # Check tolerance
                distance = abs(current_score - threshold)

                if distance <= self.THRESHOLD_TOLERANCE:
                    self.logger.info(
                        f"✓ Threshold {threshold}x crossed at {current_score:.2f}x"
                    )
                else:
                    self.logger.warning(
                        f"⚠ Threshold {threshold}x crossed far at {current_score:.2f}x"
                    )

                return threshold

        return None

    def _handle_threshold_crossed(
        self,
        score: float,
        threshold: float,
        state
    ) -> None:
        """
        Handle threshold crossing.

        Args:
            score: Score at crossing
            threshold: Threshold value
            state: Current state
        """
        # Mark as crossed
        self.thresholds_crossed.add(threshold)

        # Create threshold record
        threshold_record = {
            "bookmaker": self.bookmaker,
            "timestamp": datetime.now().isoformat(),
            "threshold": threshold,
            "actual_score": score,
            "players_left": state.player_count_current,
            "total_money": state.total_money
        }

        self.threshold_data.append(threshold_record)

        # Publish event
        self.publish_event(
            EventType.THRESHOLD_CROSSED,
            {
                "threshold": threshold,
                "score": score,
                "players_left": state.player_count_current,
                "total_money": state.total_money
            },
            priority=4
        )

        self.logger.debug(f"Threshold {threshold}x data collected")

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate data before writing to database.

        Args:
            data: Data to validate

        Returns:
            True if valid
        """
        # Check required fields based on table
        if "threshold" in data:
            # Threshold data
            required = ["bookmaker", "timestamp", "threshold", "actual_score"]
            for field in required:
                if field not in data:
                    return False

            # Validate threshold and score
            threshold = data.get("threshold")
            score = data.get("actual_score")
            if not isinstance(threshold, (int, float)) or not isinstance(score, (int, float)):
                return False
            if threshold < 0 or score < 0:
                return False

        else:
            # Round data
            required = ["bookmaker", "timestamp", "final_score"]
            for field in required:
                if field not in data:
                    return False

            # Validate score
            score = data.get("final_score")
            if not isinstance(score, (int, float)) or score < 1.0:
                return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        base_stats = super().get_stats()

        # Add main collector specific stats
        base_stats.update({
            "rounds_collected": self.rounds_collected,
            "thresholds_collected": self.thresholds_collected,
            "current_phase": self.last_phase.value,
            "last_score": self.last_score,
            "avg_thresholds_per_round": (
                self.thresholds_collected / self.rounds_collected
                if self.rounds_collected > 0
                else 0.0
            )
        })

        return base_stats


if __name__ == "__main__":
    # Testing
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    from core.communication.shared_state import get_shared_state
    from data_layer.database.batch_writer import BatchConfig

    print("=== Main Collector Test ===\n")

    # Create collector
    shared_state = get_shared_state()
    db_config = BatchConfig(batch_size=10, flush_interval=1.0)
    db_writer = BatchDatabaseWriter("test_main.db", db_config)
    db_writer.start()

    collector = MainDataCollector(
        bookmaker="TestBookmaker",
        shared_state=shared_state,
        db_writer=db_writer
    )

    # Simulate round
    print("Simulating game round...\n")

    # Round start
    shared_state.update_state(
        bookmaker="TestBookmaker",
        phase=GamePhase.STARTED,
        score=1.0
    )
    collector.run_cycle()
    time.sleep(0.1)

    # Playing - cross some thresholds
    for score in [1.2, 1.5, 1.8, 2.0, 2.3, 2.5, 3.0]:
        shared_state.update_state(
            bookmaker="TestBookmaker",
            phase=GamePhase.PLAYING,
            score=score
        )
        collector.run_cycle()
        time.sleep(0.1)

    # Round end
    shared_state.update_state(
        bookmaker="TestBookmaker",
        phase=GamePhase.ENDED,
        score=3.45
    )
    collector.run_cycle()

    # Show statistics
    print("\n=== Statistics ===")
    stats = collector.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    # Cleanup
    collector.cleanup()
    db_writer.stop()
