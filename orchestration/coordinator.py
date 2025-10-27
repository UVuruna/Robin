"""
Module: Coordinator
Purpose: Multi-worker synchronization and coordination
Version: 2.0

This module provides:
- Synchronization of multiple bookmaker workers
- Round state tracking across workers
- Desync detection and handling
- Alignment monitoring
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from config.settings import GamePhase


class RoundState(Enum):
    """Round synchronization states."""
    WAITING = "waiting"  # Waiting for round to start
    ACTIVE = "active"    # Round is active
    ENDING = "ending"    # Round is ending soon
    ENDED = "ended"      # Round has ended


@dataclass
class WorkerState:
    """State of individual bookmaker worker."""
    name: str
    round_state: RoundState = RoundState.WAITING
    game_phase: GamePhase = GamePhase.BETTING
    current_score: float = 0.0
    round_start_time: Optional[float] = None
    round_end_time: Optional[float] = None
    last_update: float = field(default_factory=time.time)
    is_alive: bool = True

    def get_round_duration(self) -> Optional[float]:
        """Get duration of current round in seconds."""
        if self.round_start_time and self.round_end_time:
            return self.round_end_time - self.round_start_time
        elif self.round_start_time:
            return time.time() - self.round_start_time
        return None

    def is_stale(self, max_age_seconds: float = 5.0) -> bool:
        """Check if worker state is stale."""
        return (time.time() - self.last_update) > max_age_seconds


class Coordinator:
    """
    Coordinates multiple bookmaker workers for synchronized data collection.

    Features:
    - Tracks state of each worker
    - Detects desynchronization
    - Monitors round alignment
    - Provides synchronization metrics
    """

    def __init__(self, bookmakers: List[str]):
        """
        Initialize Coordinator.

        Args:
            bookmakers: List of bookmaker names to coordinate
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        self.bookmakers = bookmakers
        self.states: Dict[str, WorkerState] = {
            name: WorkerState(name) for name in bookmakers
        }

        # Synchronization thresholds
        self.sync_tolerance = 2.0  # seconds - max allowed time difference
        self.round_timeout = 60.0  # seconds - max round duration
        self.stale_threshold = 5.0  # seconds - max time without update

        # Statistics
        self.synchronized_rounds = 0
        self.desync_events = 0
        self.total_rounds = 0

        self.logger.info(f"Coordinator initialized for {len(bookmakers)} bookmakers")

    def update_worker_state(
        self,
        bookmaker: str,
        round_state: RoundState = None,
        game_phase: GamePhase = None,
        score: float = None
    ):
        """
        Update state for specific worker.

        Args:
            bookmaker: Bookmaker name
            round_state: New round state
            game_phase: New game phase
            score: Current score
        """
        if bookmaker not in self.states:
            self.logger.warning(f"Unknown bookmaker: {bookmaker}")
            return

        state = self.states[bookmaker]

        # Update round state
        if round_state is not None:
            old_state = state.round_state
            state.round_state = round_state

            # Track round timing
            if round_state == RoundState.ACTIVE and old_state != RoundState.ACTIVE:
                state.round_start_time = time.time()
                self.logger.debug(f"{bookmaker}: Round started")

            elif round_state == RoundState.ENDED and old_state != RoundState.ENDED:
                state.round_end_time = time.time()
                self.total_rounds += 1
                self.logger.debug(
                    f"{bookmaker}: Round ended (duration: {state.get_round_duration():.1f}s)"
                )

        # Update game phase
        if game_phase is not None:
            state.game_phase = game_phase

        # Update score
        if score is not None:
            state.current_score = score

        # Update timestamp
        state.last_update = time.time()

    def mark_worker_alive(self, bookmaker: str, is_alive: bool = True):
        """
        Mark worker as alive or dead.

        Args:
            bookmaker: Bookmaker name
            is_alive: Whether worker is alive
        """
        if bookmaker in self.states:
            self.states[bookmaker].is_alive = is_alive

            if not is_alive:
                self.logger.warning(f"Worker marked as dead: {bookmaker}")

    def check_synchronization(self) -> bool:
        """
        Check if all workers are synchronized.

        Returns:
            True if synchronized, False if desynchronized

        A desync is detected when:
        - Workers are in different round states
        - Time spread between updates is too large
        - Scores differ significantly
        """
        active_states = [
            s for s in self.states.values()
            if s.is_alive and not s.is_stale(self.stale_threshold)
        ]

        if len(active_states) < 2:
            return True  # Can't be desynced with < 2 workers

        # Check if all in same round state
        round_states = [s.round_state for s in active_states]
        if len(set(round_states)) > 1:
            # Different states - check if within tolerance
            update_times = [s.last_update for s in active_states]
            time_spread = max(update_times) - min(update_times)

            if time_spread > self.sync_tolerance:
                self.desync_events += 1
                self.logger.warning(
                    f"Desync detected: {time_spread:.1f}s spread, "
                    f"states: {set(round_states)}"
                )
                return False

        return True

    def get_round_alignment(self) -> Dict[str, bool]:
        """
        Get alignment status for each worker.

        Alignment is based on score proximity to median score.

        Returns:
            Dictionary mapping bookmaker names to alignment status
        """
        alignment = {}
        median_score = self._get_median_score()

        for name, state in self.states.items():
            if not state.is_alive or state.is_stale(self.stale_threshold):
                alignment[name] = False
                continue

            # Check if aligned with median (within 0.5x tolerance)
            score_diff = abs(state.current_score - median_score)
            alignment[name] = score_diff < 0.5

        return alignment

    def _get_median_score(self) -> float:
        """
        Get median score across all active workers.

        Returns:
            Median score
        """
        scores = [
            s.current_score for s in self.states.values()
            if s.is_alive and not s.is_stale(self.stale_threshold) and s.current_score > 0
        ]

        if not scores:
            return 0.0

        scores.sort()
        n = len(scores)

        if n % 2 == 0:
            return (scores[n // 2 - 1] + scores[n // 2]) / 2
        else:
            return scores[n // 2]

    def should_force_sync(self) -> bool:
        """
        Determine if forced synchronization is needed.

        Forced sync is needed when:
        - A round is stuck (exceeds timeout)
        - Too many workers are stale
        - Desync events are too frequent

        Returns:
            True if forced sync needed, False otherwise
        """
        current_time = time.time()

        # Check for stuck rounds
        for state in self.states.values():
            if state.round_start_time:
                duration = current_time - state.round_start_time
                if duration > self.round_timeout:
                    self.logger.warning(
                        f"Round timeout for {state.name}: {duration:.1f}s"
                    )
                    return True

        # Check for too many stale workers
        stale_count = sum(
            1 for s in self.states.values()
            if s.is_stale(self.stale_threshold)
        )

        if stale_count > len(self.states) / 2:
            self.logger.warning(f"Too many stale workers: {stale_count}/{len(self.states)}")
            return True

        return False

    def reset_round_states(self):
        """Reset all round states (usually after sync)."""
        for state in self.states.values():
            state.round_state = RoundState.WAITING
            state.current_score = 0.0
            state.round_start_time = None
            state.round_end_time = None

        self.synchronized_rounds += 1
        self.logger.info("Round states reset (sync completed)")

    def get_active_workers(self) -> List[str]:
        """
        Get list of active (alive and not stale) workers.

        Returns:
            List of bookmaker names
        """
        return [
            name for name, state in self.states.items()
            if state.is_alive and not state.is_stale(self.stale_threshold)
        ]

    def get_sync_quality(self) -> float:
        """
        Get synchronization quality metric (0.0 - 1.0).

        Returns:
            Quality score where 1.0 is perfect sync
        """
        if self.total_rounds == 0:
            return 1.0

        # Calculate based on desync rate
        desync_rate = self.desync_events / self.total_rounds
        quality = max(0.0, 1.0 - desync_rate)

        return quality

    def get_stats(self) -> dict:
        """
        Get coordinator statistics.

        Returns:
            Dictionary with statistics
        """
        active_workers = self.get_active_workers()
        alignment = self.get_round_alignment()
        aligned_count = sum(1 for a in alignment.values() if a)

        return {
            "total_bookmakers": len(self.bookmakers),
            "active_workers": len(active_workers),
            "stale_workers": len(self.bookmakers) - len(active_workers),
            "total_rounds": self.total_rounds,
            "synchronized_rounds": self.synchronized_rounds,
            "desync_events": self.desync_events,
            "sync_quality": f"{self.get_sync_quality() * 100:.1f}%",
            "aligned_workers": f"{aligned_count}/{len(alignment)}",
            "median_score": f"{self._get_median_score():.2f}x"
        }

    def cleanup(self):
        """Cleanup resources."""
        self.logger.info(f"Coordinator cleanup - Stats: {self.get_stats()}")


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    bookmakers = ["Mozzart", "BalkanBet", "Soccer"]
    coordinator = Coordinator(bookmakers)

    # Simulate some updates
    coordinator.update_worker_state("Mozzart", RoundState.ACTIVE, score=1.5)
    coordinator.update_worker_state("BalkanBet", RoundState.ACTIVE, score=1.52)
    coordinator.update_worker_state("Soccer", RoundState.ACTIVE, score=1.48)

    print(f"Synchronized: {coordinator.check_synchronization()}")
    print(f"Alignment: {coordinator.get_round_alignment()}")
    print(f"Stats: {coordinator.get_stats()}")
