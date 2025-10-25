# regions/score.py
# VERSION: 7.0 - Multi-region, triple check, EventCollector
# CHANGES: 3 score regions by phase, triple check for FINAL, uses EventCollector

from typing import Dict, Optional, List
from collections import deque
import time

from config.config import GamePhase
from core.screen_reader import ScreenReader
from core.event_collector import EventCollector
from regions.base_region import Region
from regions.game_phase import GamePhaseDetector
from utils.logger import AviatorLogger


class Score(Region):
    """
    Score reader with:
    - 3 regions (small/medium/large) selected by phase
    - Triple check for FINAL score (strict equality)
    - EventCollector integration
    """

    # Score thresholds to track
    THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

    # Triple check settings
    FINAL_CHECK_COUNT = 3  # Need 3 identical readings
    FINAL_CHECK_INTERVAL = 0.1  # 0.1 sec between checks (total 0.3 sec)

    def __init__(
        self,
        score_region_small: Dict[str, int],
        score_region_medium: Dict[str, int],
        score_region_large: Dict[str, int],
        phase_detector: GamePhaseDetector,
        event_collector: EventCollector,
        auto_stop: Optional[float] = None,
    ):
        """
        Initialize Score reader with multiple regions.

        Args:
            score_region_small: Region for SCORE_LOW (1.00-9.99x)
            score_region_medium: Region for SCORE_MID (10.0-999.9x)
            score_region_large: Region for SCORE_HIGH (1000+x)
            phase_detector: GamePhaseDetector instance
            event_collector: EventCollector instance
            auto_stop: Auto-cashout value (optional)
        """
        # Initialize with small region (most common)
        super().__init__(ScreenReader(score_region_small))

        # Create readers for all three regions
        self.reader_small = ScreenReader(score_region_small)
        self.reader_medium = ScreenReader(score_region_medium)
        self.reader_large = ScreenReader(score_region_large)

        self.phase_detector = phase_detector
        self.event_collector = event_collector
        self.auto_stop = auto_stop

        self.logger = AviatorLogger.get_logger("Score")

        # Threshold tracking
        self.thresholds_reached = set()  # Track which thresholds we've already reported

        # Triple check for FINAL score
        self.recent_scores: deque = deque(maxlen=self.FINAL_CHECK_COUNT)

        # Last known score
        self.last_score: Optional[float] = None

    def _select_reader(self, phase: GamePhase) -> ScreenReader:
        """
        Select appropriate ScreenReader based on phase.

        Args:
            phase: Current game phase

        Returns:
            ScreenReader for that phase
        """
        if phase == GamePhase.SCORE_LOW:
            return self.reader_small
        elif phase == GamePhase.SCORE_MID:
            return self.reader_medium
        elif phase == GamePhase.SCORE_HIGH:
            return self.reader_large
        else:
            # Default to small for BETTING/LOADING/START/ENDED
            return self.reader_small

    def _read_score_from_phase(self, phase: GamePhase) -> Optional[float]:
        """
        Read score using appropriate reader for the phase.

        Args:
            phase: Current game phase

        Returns:
            Score value or None
        """
        reader = self._select_reader(phase)
        score = reader.read_score()

        if score is not None:
            self.last_score = score

        return score

    def _check_final_score(self, phase: GamePhase) -> Optional[float]:
        """
        Triple check for FINAL score.

        Requirements:
        1. Phase must be ENDED
        2. Read score 3 times with 0.1 sec interval
        3. All 3 readings must be STRICTLY equal (===)

        Returns:
            Final score if verified, None otherwise
        """
        if phase != GamePhase.ENDED:
            return None

        self.recent_scores.clear()

        # Take 3 readings
        for i in range(self.FINAL_CHECK_COUNT):
            score = self._read_score_from_phase(phase)

            if score is None:
                self.logger.warning(f"Failed to read score on check {i + 1}")
                return None

            self.recent_scores.append(score)

            if i < self.FINAL_CHECK_COUNT - 1:
                time.sleep(self.FINAL_CHECK_INTERVAL)

        # Check if all readings are STRICTLY equal
        if len(set(self.recent_scores)) == 1:
            final_score = self.recent_scores[0]
            self.logger.info(f"✓ FINAL score verified: {final_score:.2f}x")
            return final_score
        else:
            self.logger.warning(f"Score readings not equal: {list(self.recent_scores)}")
            return None

    def _check_thresholds(self, score: float) -> Optional[List[float]]:
        """
        Check if score crossed any new thresholds.

        Args:
            score: Current score

        Returns:
            List of newly reached thresholds or None
        """
        newly_reached = []

        for threshold in self.THRESHOLDS:
            if score >= threshold and threshold not in self.thresholds_reached:
                newly_reached.append(threshold)
                self.thresholds_reached.add(threshold)

        return newly_reached if newly_reached else None

    def _reset_round(self):
        """Reset tracking for new round."""
        self.thresholds_reached.clear()
        self.recent_scores.clear()
        self.last_score = None

    def read_text(self) -> Optional[Dict]:
        """
        Main read method - detects phase and handles accordingly.

        Returns:
            Dict with event data or None
        """
        try:
            phase = self.phase_detector.get_phase()

            if phase is None:
                return None

            # Handle ENDED phase
            if phase == GamePhase.ENDED:
                return self._handle_ended()

            # Handle BETTING phase (reset for new round)
            elif phase == GamePhase.BETTING:
                self._reset_round()
                return None

            # Handle SCORE phases (running game)
            elif phase in [
                GamePhase.SCORE_LOW,
                GamePhase.SCORE_MID,
                GamePhase.SCORE_HIGH,
            ]:
                return self._handle_running(phase)

            # LOADING, START - no action
            return None

        except Exception as e:
            self.logger.error(f"Error in read_text: {e}")
            return None

    def _handle_ended(self) -> Optional[Dict]:
        """
        Handle ENDED phase.

        1. Triple check for final score
        2. Collect data via EventCollector
        3. Reset for next round

        Returns:
            Event data or None
        """
        try:
            # Triple check final score
            final_score = self._check_final_score(GamePhase.ENDED)

            if final_score is None:
                # Fallback: use last known score if triple check failed
                if self.last_score is not None:
                    self.logger.warning(
                        f"Triple check failed, using last known score: {self.last_score:.2f}x"
                    )
                    final_score = self.last_score
                else:
                    self.logger.error("No final score available")
                    return None

            # Collect data
            if self.auto_stop is not None:
                # For betting agent
                data = self.event_collector.collect_ended_for_betting(
                    final_score, self.auto_stop
                )
            else:
                # For data collector
                data = self.event_collector.collect_ended_for_data(final_score)

            # Reset for next round
            self._reset_round()

            return data

        except Exception as e:
            self.logger.error(f"Error handling ENDED: {e}")
            return None

    def _handle_running(self, phase: GamePhase) -> Optional[Dict]:
        """
        Handle running game (SCORE_LOW/MID/HIGH).

        1. Read score using appropriate region
        2. Check for threshold crossings
        3. Collect threshold data via EventCollector

        Returns:
            Event data or None
        """
        try:
            score = self._read_score_from_phase(phase)

            if score is None:
                return None

            # Check thresholds
            new_thresholds = self._check_thresholds(score)

            if new_thresholds:
                # Collect data for each newly reached threshold
                for threshold in new_thresholds:
                    data = self.event_collector.collect_threshold_data(threshold)

                    if data:
                        # Return first successful threshold data
                        # (in practice, we'd queue multiple events)
                        return data

            return None

        except Exception as e:
            self.logger.error(f"Error handling running game: {e}")
            return None

    def close(self):
        """Clean up all readers."""
        self.reader_small.close()
        self.reader_medium.close()
        self.reader_large.close()
