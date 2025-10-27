"""
Module: SharedState
Purpose: Shared memory state structure for inter-process communication
Version: 2.0

This module provides:
- Multiprocessing-safe shared memory structure
- Game state per bookmaker
- Thread-safe access methods
- State validation and expiry
- Performance monitoring
"""

import logging
import time
from dataclasses import dataclass, field
from multiprocessing.managers import SyncManager
from typing import Any, Dict, Optional

from config.settings import GamePhase, BetState


@dataclass
class BookmakerState:
    """
    State structure for a single bookmaker.

    Contains all relevant game data that needs to be shared between processes.
    """
    bookmaker_name: str

    # Game phase and score
    phase: GamePhase = GamePhase.BETTING
    score: Optional[float] = None
    previous_score: Optional[float] = None

    # Round tracking
    round_start_time: Optional[float] = None
    round_end_time: Optional[float] = None
    loading_start_time: Optional[float] = None
    loading_duration: Optional[float] = None

    # Player statistics
    player_count_current: Optional[int] = None
    player_count_total: Optional[int] = None
    money_total: Optional[float] = None
    my_money: Optional[float] = None

    # Betting state
    bet_button_state: BetState = BetState.READY
    last_bet_amount: Optional[float] = None
    last_auto_stop: Optional[float] = None

    # Metadata
    last_update_time: float = field(default_factory=time.time)
    read_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "bookmaker_name": self.bookmaker_name,
            "phase": int(self.phase),
            "score": self.score,
            "previous_score": self.previous_score,
            "round_start_time": self.round_start_time,
            "round_end_time": self.round_end_time,
            "loading_start_time": self.loading_start_time,
            "loading_duration": self.loading_duration,
            "player_count_current": self.player_count_current,
            "player_count_total": self.player_count_total,
            "money_total": self.money_total,
            "my_money": self.my_money,
            "bet_button_state": int(self.bet_button_state),
            "last_bet_amount": self.last_bet_amount,
            "last_auto_stop": self.last_auto_stop,
            "last_update_time": self.last_update_time,
            "read_count": self.read_count,
            "error_count": self.error_count,
            "last_error": self.last_error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BookmakerState":
        """Create BookmakerState from dictionary."""
        return cls(
            bookmaker_name=data.get("bookmaker_name", "unknown"),
            phase=GamePhase(data.get("phase", GamePhase.BETTING)),
            score=data.get("score"),
            previous_score=data.get("previous_score"),
            round_start_time=data.get("round_start_time"),
            round_end_time=data.get("round_end_time"),
            loading_start_time=data.get("loading_start_time"),
            loading_duration=data.get("loading_duration"),
            player_count_current=data.get("player_count_current"),
            player_count_total=data.get("player_count_total"),
            money_total=data.get("money_total"),
            my_money=data.get("my_money"),
            bet_button_state=BetState(data.get("bet_button_state", BetState.READY)),
            last_bet_amount=data.get("last_bet_amount"),
            last_auto_stop=data.get("last_auto_stop"),
            last_update_time=data.get("last_update_time", time.time()),
            read_count=data.get("read_count", 0),
            error_count=data.get("error_count", 0),
            last_error=data.get("last_error")
        )

    def is_stale(self, max_age_seconds: float = 5.0) -> bool:
        """Check if state is stale (too old)."""
        return (time.time() - self.last_update_time) > max_age_seconds


class SharedGameState:
    """
    Shared memory state manager for multiple bookmakers.

    Features:
    - Process-safe shared memory using multiprocessing.Manager
    - Per-bookmaker state storage
    - Thread-safe access methods
    - State validation and staleness detection
    - Performance statistics
    """

    def __init__(self, manager: Optional[SyncManager] = None):
        """
        Initialize SharedGameState.

        Args:
            manager: multiprocessing.Manager instance (creates new if None)
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Create or use provided manager
        if manager is None:
            manager = SyncManager()

        # Shared memory dictionary
        # Key: bookmaker_name, Value: state dict
        self._shared_dict = manager.dict()

        # Lock for thread safety
        self._lock = manager.RLock()

        # Statistics
        self.stats = {
            "total_reads": 0,
            "total_writes": 0,
            "total_bookmakers": 0,
            "stale_reads": 0
        }

        self.logger.info("SharedGameState initialized")

    def set_state(self, bookmaker_name: str, state: BookmakerState):
        """
        Set state for a bookmaker.

        Args:
            bookmaker_name: Bookmaker identifier
            state: BookmakerState object

        Example:
            >>> shared_state = SharedGameState()
            >>> state = BookmakerState(bookmaker_name="Mozzart", phase=GamePhase.SCORE_LOW, score=3.45)
            >>> shared_state.set_state("Mozzart", state)
        """
        with self._lock:
            # Update timestamp
            state.last_update_time = time.time()

            # Convert to dict for shared memory
            self._shared_dict[bookmaker_name] = state.to_dict()

            # Update stats
            self.stats["total_writes"] += 1
            if bookmaker_name not in self._shared_dict:
                self.stats["total_bookmakers"] += 1

            self.logger.debug(f"Updated state for {bookmaker_name}: phase={state.phase}, score={state.score}")

    def get_state(self, bookmaker_name: str) -> Optional[BookmakerState]:
        """
        Get state for a bookmaker.

        Args:
            bookmaker_name: Bookmaker identifier

        Returns:
            BookmakerState object or None if not found

        Example:
            >>> shared_state = SharedGameState()
            >>> state = shared_state.get_state("Mozzart")
            >>> if state:
            ...     print(f"Score: {state.score}")
        """
        with self._lock:
            state_dict = self._shared_dict.get(bookmaker_name)

            if state_dict:
                self.stats["total_reads"] += 1
                state = BookmakerState.from_dict(state_dict)

                # Check if stale
                if state.is_stale():
                    self.stats["stale_reads"] += 1
                    self.logger.warning(f"Stale state for {bookmaker_name} (age: {time.time() - state.last_update_time:.1f}s)")

                return state
            else:
                self.logger.debug(f"No state found for {bookmaker_name}")
                return None

    def update_field(self, bookmaker_name: str, field_name: str, value: Any):
        """
        Update a single field in bookmaker state.

        Args:
            bookmaker_name: Bookmaker identifier
            field_name: Field name to update
            value: New value

        Example:
            >>> shared_state.update_field("Mozzart", "score", 5.23)
        """
        with self._lock:
            state = self.get_state(bookmaker_name)

            if state:
                # Update field
                setattr(state, field_name, value)
                state.last_update_time = time.time()

                # Save back
                self.set_state(bookmaker_name, state)
            else:
                self.logger.warning(f"Cannot update field for non-existent bookmaker: {bookmaker_name}")

    def update_score(self, bookmaker_name: str, new_score: float):
        """
        Update score for bookmaker (convenience method).

        Args:
            bookmaker_name: Bookmaker identifier
            new_score: New score value
        """
        with self._lock:
            state = self.get_state(bookmaker_name)

            if state:
                state.previous_score = state.score
                state.score = new_score
                state.last_update_time = time.time()
                state.read_count += 1

                self.set_state(bookmaker_name, state)
            else:
                # Create new state if doesn't exist
                state = BookmakerState(
                    bookmaker_name=bookmaker_name,
                    score=new_score
                )
                self.set_state(bookmaker_name, state)

    def update_phase(self, bookmaker_name: str, new_phase: GamePhase):
        """
        Update game phase for bookmaker (convenience method).

        Args:
            bookmaker_name: Bookmaker identifier
            new_phase: New game phase
        """
        self.update_field(bookmaker_name, "phase", new_phase)

    def increment_error_count(self, bookmaker_name: str, error_message: str = ""):
        """
        Increment error count for bookmaker.

        Args:
            bookmaker_name: Bookmaker identifier
            error_message: Optional error description
        """
        with self._lock:
            state = self.get_state(bookmaker_name)

            if state:
                state.error_count += 1
                if error_message:
                    state.last_error = error_message
                state.last_update_time = time.time()

                self.set_state(bookmaker_name, state)

    def get_all_states(self) -> Dict[str, BookmakerState]:
        """
        Get all bookmaker states.

        Returns:
            Dictionary mapping bookmaker names to states
        """
        with self._lock:
            all_states = {}

            for bookmaker_name in self._shared_dict.keys():
                state = self.get_state(bookmaker_name)
                if state:
                    all_states[bookmaker_name] = state

            return all_states

    def get_bookmaker_names(self) -> list[str]:
        """Get list of all tracked bookmaker names."""
        with self._lock:
            return list(self._shared_dict.keys())

    def clear_bookmaker(self, bookmaker_name: str):
        """Remove bookmaker from shared state."""
        with self._lock:
            if bookmaker_name in self._shared_dict:
                del self._shared_dict[bookmaker_name]
                self.logger.info(f"Cleared state for {bookmaker_name}")

    def clear_all(self):
        """Clear all bookmaker states."""
        with self._lock:
            count = len(self._shared_dict)
            self._shared_dict.clear()
            self.logger.warning(f"Cleared all states ({count} bookmakers)")

    def get_stats(self) -> dict:
        """
        Get statistics about shared state usage.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            stale_rate = 0.0
            if self.stats["total_reads"] > 0:
                stale_rate = (self.stats["stale_reads"] / self.stats["total_reads"]) * 100

            return {
                **self.stats,
                "current_bookmakers": len(self._shared_dict),
                "stale_rate": f"{stale_rate:.2f}%"
            }

    def cleanup(self):
        """Cleanup resources."""
        with self._lock:
            self.clear_all()
            self.logger.info(f"SharedGameState cleanup - Stats: {self.get_stats()}")


# Singleton instance management
_shared_state_instance: Optional[SharedGameState] = None


def get_shared_state(manager: Optional[SyncManager] = None) -> SharedGameState:
    """
    Get or create singleton SharedGameState instance.

    Args:
        manager: multiprocessing.Manager (only used on first call)

    Returns:
        SharedGameState instance
    """
    global _shared_state_instance

    if _shared_state_instance is None:
        _shared_state_instance = SharedGameState(manager)

    return _shared_state_instance


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    shared_state = SharedGameState()

    # Create test state
    state = BookmakerState(
        bookmaker_name="Mozzart",
        phase=GamePhase.SCORE_LOW,
        score=3.45
    )

    # Set state
    shared_state.set_state("Mozzart", state)

    # Get state
    retrieved = shared_state.get_state("Mozzart")
    print(f"Retrieved state: phase={retrieved.phase}, score={retrieved.score}")

    # Update score
    shared_state.update_score("Mozzart", 5.67)

    # Get updated state
    updated = shared_state.get_state("Mozzart")
    print(f"Updated state: previous={updated.previous_score}, current={updated.score}")

    # Show stats
    print(f"Stats: {shared_state.get_stats()}")
