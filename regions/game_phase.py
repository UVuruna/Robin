# regions/game_phase.py
# VERSION: 3.0 - Self-validating phase detection
# CHANGES: Only get_phase() method, validates phase transitions

import pickle
import numpy as np
import mss
from typing import Optional

from core.screen_reader import ScreenReader
from regions.base_region import Region
from utils.logger import AviatorLogger
from config.config import AppConstants, GamePhase


class GamePhaseDetector(Region):
    """
    Game phase detector with self-validating transition logic.

    Valid phase transitions:
    - SCORE_HIGH → SCORE_HIGH or SCORE_MID
    - SCORE_MID → SCORE_MID or SCORE_LOW
    - SCORE_LOW → SCORE_LOW or BETTING or LOADING or START
    - BETTING → BETTING or ENDED
    - ENDED → any (can end at 1.00x)
    - LOADING → any (short, often missed)
    - START → any (very short <200ms, often missed)
    """

    def __init__(
        self, screen_reader: ScreenReader, model_path: str = AppConstants.model_file
    ):
        super().__init__(screen_reader)
        self.logger = AviatorLogger.get_logger("GamePhaseDetector")
        self.model_path = model_path
        self.kmeans = self._load_model()
        self._sct = None

        # Track previous phase for validation
        self.previous_phase: Optional[GamePhase] = None
        self.current_phase: Optional[GamePhase] = None

    def _load_model(self):
        """Load K-means model from pickle file."""
        try:
            with open(self.model_path, "rb") as f:
                kmeans = pickle.load(f)
            self.logger.info(f"Loaded K-means model: {self.model_path}")
            return kmeans
        except FileNotFoundError:
            self.logger.error(f"Model file not found: {self.model_path}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading model: {e}")
            raise

    def _get_mean_rgb(self) -> Optional[np.ndarray]:
        """Capture region and calculate mean RGB color."""
        try:
            if self._sct is None:
                self._sct = mss.mss()

            bbox = {
                "top": self.screen_reader.region["top"],
                "left": self.screen_reader.region["left"],
                "width": self.screen_reader.region["width"],
                "height": self.screen_reader.region["height"],
            }

            img = np.array(self._sct.grab(bbox))[:, :, :3]
            mean_color = img.mean(axis=(0, 1))
            rgb = mean_color[::-1]  # BGR to RGB

            return rgb.reshape(1, -1)

        except Exception as e:
            self.logger.error(f"Error capturing RGB: {e}")
            return None

    def _predict_phase_raw(self, rgb: np.ndarray) -> Optional[int]:
        """Predict phase using K-means model (raw cluster ID)."""
        try:
            cluster = self.kmeans.predict(rgb)[0]
            return int(cluster)
        except Exception as e:
            self.logger.error(f"Prediction error: {e}")
            return None

    def _is_valid_phase(self, phase: int) -> bool:
        """Check if phase is valid GamePhase enum value."""
        try:
            GamePhase(phase)
            return True
        except ValueError:
            return False

    def _is_valid_transition(self, from_phase: GamePhase, to_phase: GamePhase) -> bool:
        """
        Validate phase transition according to game rules.

        CORRECT PHASE ORDER:
        BETTING → LOADING → START → SCORE_LOW → SCORE_MID → SCORE_HIGH → ENDED

        Valid transitions:
        - BETTING → BETTING, LOADING, START, SCORE_LOW, ENDED (crash at 1.00x)
        - LOADING → LOADING, START, SCORE_LOW (skip START)
        - START → START, SCORE_LOW
        - SCORE_LOW → SCORE_LOW, SCORE_MID, ENDED
        - SCORE_MID → SCORE_MID, SCORE_HIGH, ENDED
        - SCORE_HIGH → SCORE_HIGH, ENDED
        - ENDED → ENDED, BETTING (new round)
        """
        if from_phase == GamePhase.BETTING:
            return to_phase in [
                GamePhase.BETTING,
                GamePhase.LOADING,
                GamePhase.START,
                GamePhase.SCORE_LOW,
                GamePhase.ENDED,  # Can crash immediately at 1.00x
            ]

        elif from_phase == GamePhase.LOADING:
            return to_phase in [
                GamePhase.LOADING,
                GamePhase.START,
                GamePhase.SCORE_LOW,  # Can skip START if it's too short
            ]

        elif from_phase == GamePhase.START:
            return to_phase in [GamePhase.START, GamePhase.SCORE_LOW]

        elif from_phase == GamePhase.SCORE_LOW:
            return to_phase in [
                GamePhase.SCORE_LOW,
                GamePhase.SCORE_MID,  # Score increases
                GamePhase.ENDED,  # Can end in LOW phase
            ]

        elif from_phase == GamePhase.SCORE_MID:
            return to_phase in [
                GamePhase.SCORE_MID,
                GamePhase.SCORE_HIGH,  # Score increases
                GamePhase.ENDED,  # Can end in MID phase
            ]

        elif from_phase == GamePhase.SCORE_HIGH:
            return to_phase in [GamePhase.SCORE_HIGH, GamePhase.ENDED]

        elif from_phase == GamePhase.ENDED:
            return to_phase in [
                GamePhase.ENDED,
                GamePhase.BETTING,  # New round starts
            ]

        # If no previous phase, accept any
        return True

    def get_phase(self) -> Optional[GamePhase]:
        """
        Get current game phase with self-validation.

        Returns:
            GamePhase enum or None if detection failed
        """
        try:
            # Get RGB and predict
            rgb = self._get_mean_rgb()
            if rgb is None:
                return None

            phase_raw = self._predict_phase_raw(rgb)
            if phase_raw is None or not self._is_valid_phase(phase_raw):
                return None

            detected_phase = GamePhase(phase_raw)

            # Validate transition
            if self.current_phase is not None:
                if not self._is_valid_transition(self.current_phase, detected_phase):
                    self.logger.warning(
                        f"Invalid transition: {self.current_phase.name} → {detected_phase.name}"
                    )
                    # Keep current phase, don't update
                    return self.current_phase

            # Valid transition - update state
            self.previous_phase = self.current_phase
            self.current_phase = detected_phase

            if AppConstants.debug:
                self.logger.debug(f"Phase: {detected_phase.name}")

            return detected_phase

        except Exception as e:
            self.logger.error(f"Error detecting phase: {e}")
            return None

    def read_text(self) -> Optional[dict]:
        """Legacy method for compatibility."""
        phase = self.get_phase()
        return {"phase": phase.value} if phase else None

    def close(self):
        """Clean up resources."""
        if self._sct:
            self._sct.close()
            self._sct = None
