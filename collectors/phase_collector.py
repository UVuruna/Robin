"""
Module: Phase Collector
Purpose: Collects game phase transitions for ML training and analysis
Version: 2.0

This collector tracks game phase changes and collects data for:
- Phase transition patterns
- Phase duration statistics
- ML model training data
- Game flow analysis
"""

import logging
import time
from typing import Dict, Optional, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from collectors.base_collector import BaseCollector
from core.communication.shared_state import SharedGameState, BookmakerState, GamePhase
from core.communication.event_bus import EventPublisher, EventType
from data_layer.database.batch_writer import BatchDatabaseWriter


@dataclass
class PhaseTransition:
    """Represents a phase transition."""
    from_phase: GamePhase
    to_phase: GamePhase
    timestamp: float
    score_at_transition: Optional[float] = None
    duration_in_previous_phase: Optional[float] = None


class PhaseCollector(BaseCollector):
    """
    Collector for game phase transitions.

    Tracks:
    - Phase changes (BETTING ’ PLAYING ’ ENDED, etc.)
    - Duration in each phase
    - Score at phase transitions
    - Phase patterns for analysis

    This data is useful for:
    - Understanding game flow
    - Training ML models for phase prediction
    - Detecting anomalies in game behavior
    - Optimizing betting timing
    """

    def __init__(
        self,
        bookmaker: str,
        shared_state: SharedGameState,
        db_writer: BatchDatabaseWriter,
        event_publisher: Optional[EventPublisher] = None
    ):
        """
        Initialize phase collector.

        Args:
            bookmaker: Name of bookmaker
            shared_state: SharedGameState instance
            db_writer: BatchDatabaseWriter instance
            event_publisher: Optional EventPublisher
        """
        super().__init__(bookmaker, shared_state, db_writer, event_publisher)

        # Phase tracking
        self.current_phase: GamePhase = GamePhase.UNKNOWN
        self.previous_phase: GamePhase = GamePhase.UNKNOWN
        self.phase_start_time: Optional[float] = None
        self.phase_history: List[PhaseTransition] = []

        # Statistics
        self.phase_transitions_collected = 0
        self.phase_durations: Dict[GamePhase, List[float]] = {
            phase: [] for phase in GamePhase
        }

        self.logger.info(f"Phase collector initialized for {bookmaker}")

    def get_collection_name(self) -> str:
        """Get collector name."""
        return "PhaseCollector"

    def collect_cycle(self) -> None:
        """
        Collect phase transition data.

        Checks current phase and detects transitions.
        Records transition data when phase changes.
        """
        # Get current state
        state = self.get_current_state()
        if not state:
            return

        new_phase = state.phase
        current_score = state.score

        # Check for phase transition
        if new_phase != self.current_phase:
            self._handle_phase_transition(
                from_phase=self.current_phase,
                to_phase=new_phase,
                score=current_score,
                timestamp=time.time()
            )

    def _handle_phase_transition(
        self,
        from_phase: GamePhase,
        to_phase: GamePhase,
        score: Optional[float],
        timestamp: float
    ) -> None:
        """
        Handle a phase transition.

        Args:
            from_phase: Previous phase
            to_phase: New phase
            score: Score at transition
            timestamp: Transition timestamp
        """
        # Calculate duration in previous phase
        duration = None
        if self.phase_start_time is not None:
            duration = timestamp - self.phase_start_time

        # Log transition
        self.logger.info(
            f"Phase transition: {from_phase.value} ’ {to_phase.value} "
            f"(duration: {duration:.2f}s, score: {score})"
        )

        # Create transition record
        transition = PhaseTransition(
            from_phase=from_phase,
            to_phase=to_phase,
            timestamp=timestamp,
            score_at_transition=score,
            duration_in_previous_phase=duration
        )

        # Store in history
        self.phase_history.append(transition)
        if len(self.phase_history) > 100:  # Keep last 100 transitions
            self.phase_history.pop(0)

        # Update duration statistics
        if duration is not None and from_phase != GamePhase.UNKNOWN:
            self.phase_durations[from_phase].append(duration)
            # Keep last 50 durations per phase
            if len(self.phase_durations[from_phase]) > 50:
                self.phase_durations[from_phase].pop(0)

        # Save to database
        phase_data = {
            "bookmaker": self.bookmaker,
            "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
            "from_phase": from_phase.value,
            "to_phase": to_phase.value,
            "score_at_transition": score,
            "duration_seconds": duration
        }

        if self.write_to_database("phase_transitions", phase_data):
            self.phase_transitions_collected += 1

        # Publish event
        self.publish_event(
            EventType.PHASE_CHANGE,
            {
                "from_phase": from_phase.value,
                "to_phase": to_phase.value,
                "score": score,
                "duration": duration
            },
            priority=3  # Medium priority
        )

        # Update state
        self.previous_phase = self.current_phase
        self.current_phase = to_phase
        self.phase_start_time = timestamp

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate phase transition data.

        Args:
            data: Phase data to validate

        Returns:
            True if valid
        """
        required_fields = ["bookmaker", "timestamp", "from_phase", "to_phase"]

        # Check required fields
        for field in required_fields:
            if field not in data:
                self.logger.warning(f"Missing required field: {field}")
                return False

        # Validate phase values
        try:
            from_phase = GamePhase(data["from_phase"])
            to_phase = GamePhase(data["to_phase"])
        except ValueError:
            self.logger.warning(f"Invalid phase values: {data['from_phase']} ’ {data['to_phase']}")
            return False

        # Validate score if present
        if data.get("score_at_transition") is not None:
            score = data["score_at_transition"]
            if not isinstance(score, (int, float)) or score < 0:
                self.logger.warning(f"Invalid score: {score}")
                return False

        # Validate duration if present
        if data.get("duration_seconds") is not None:
            duration = data["duration_seconds"]
            if not isinstance(duration, (int, float)) or duration < 0:
                self.logger.warning(f"Invalid duration: {duration}")
                return False
            # Sanity check: duration shouldn't be too long
            if duration > 600:  # 10 minutes
                self.logger.warning(f"Suspiciously long phase duration: {duration}s")
                return False

        return True

    def get_phase_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about phase durations.

        Returns:
            Dictionary with phase statistics
        """
        phase_stats = {}

        for phase, durations in self.phase_durations.items():
            if durations:
                phase_stats[phase.value] = {
                    "count": len(durations),
                    "avg_duration": sum(durations) / len(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                    "total_time": sum(durations)
                }

        return phase_stats

    def get_recent_transitions(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent phase transitions.

        Args:
            count: Number of recent transitions to return

        Returns:
            List of transition dictionaries
        """
        recent = self.phase_history[-count:] if self.phase_history else []

        return [
            {
                "from_phase": t.from_phase.value,
                "to_phase": t.to_phase.value,
                "timestamp": datetime.fromtimestamp(t.timestamp).isoformat(),
                "score": t.score_at_transition,
                "duration": t.duration_in_previous_phase
            }
            for t in recent
        ]

    def get_phase_pattern(self, length: int = 5) -> List[str]:
        """
        Get recent phase pattern.

        Args:
            length: Number of recent phases to include

        Returns:
            List of phase names
        """
        if not self.phase_history:
            return []

        recent = self.phase_history[-length:]
        pattern = [t.from_phase.value for t in recent]

        # Add current phase if available
        if recent:
            pattern.append(recent[-1].to_phase.value)

        return pattern

    def get_stats(self) -> Dict[str, Any]:
        """
        Get collector statistics.

        Returns:
            Dictionary with statistics
        """
        base_stats = super().get_stats()

        # Add phase-specific stats
        base_stats.update({
            "phase_transitions_collected": self.phase_transitions_collected,
            "current_phase": self.current_phase.value,
            "previous_phase": self.previous_phase.value,
            "phase_statistics": self.get_phase_statistics(),
            "recent_pattern": self.get_phase_pattern()
        })

        return base_stats

    def cleanup(self) -> None:
        """Cleanup collector resources."""
        self.logger.info("Phase collector cleanup")

        # Log final phase statistics
        phase_stats = self.get_phase_statistics()
        self.logger.info(f"Phase statistics: {phase_stats}")

        # Log recent pattern
        pattern = self.get_phase_pattern()
        self.logger.info(f"Recent phase pattern: {' ’ '.join(pattern)}")

        # Call base cleanup
        super().cleanup()


if __name__ == "__main__":
    # Testing
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    from core.communication.shared_state import get_shared_state
    from data_layer.database.batch_writer import BatchConfig

    print("=== Phase Collector Test ===\n")

    # Create collector
    shared_state = get_shared_state()
    db_config = BatchConfig(batch_size=10, flush_interval=1.0)
    db_writer = BatchDatabaseWriter("test_phases.db", db_config)

    collector = PhaseCollector(
        bookmaker="TestBookmaker",
        shared_state=shared_state,
        db_writer=db_writer
    )

    # Simulate some phase transitions
    test_phases = [
        (GamePhase.BETTING, None),
        (GamePhase.LOADING, None),
        (GamePhase.PLAYING, 1.0),
        (GamePhase.PLAYING, 2.5),
        (GamePhase.ENDED, 3.45),
        (GamePhase.LOADING, None),
        (GamePhase.BETTING, None)
    ]

    print("Simulating phase transitions...\n")

    for phase, score in test_phases:
        # Simulate state
        shared_state.update_state(
            bookmaker="TestBookmaker",
            phase=phase,
            score=score
        )

        # Run collection cycle
        collector.run_cycle()
        time.sleep(0.5)

    # Show statistics
    print("\n=== Statistics ===")
    stats = collector.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    print("\n=== Recent Transitions ===")
    recent = collector.get_recent_transitions(5)
    for trans in recent:
        print(f"{trans['from_phase']} ’ {trans['to_phase']} (score: {trans['score']}, duration: {trans['duration']:.2f}s)")

    print("\n=== Recent Pattern ===")
    pattern = collector.get_phase_pattern()
    print(" ’ ".join(pattern))

    # Cleanup
    collector.cleanup()
    db_writer.stop()
