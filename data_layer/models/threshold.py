"""
Module: Threshold Model
Purpose: Data model for threshold crossings during game rounds
Version: 2.0

This module provides:
- Threshold crossing data structure
- Validation of threshold data
- Serialization/deserialization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from data_layer.models.base import BaseModel


@dataclass
class Threshold(BaseModel):
    """
    Threshold crossing data model.

    Stores information about when a game score crosses a predefined threshold
    (e.g., 1.5x, 2.0x, 3.0x, 5.0x, 10.0x).

    This data is useful for:
    - Statistical analysis of round behaviors
    - Pattern recognition
    - Strategy optimization
    """

    # Identification
    bookmaker: str = ""
    round_id: Optional[int] = None  # FK to Round table

    # Threshold data
    threshold: float = 0.0  # Target threshold (e.g., 2.0)
    actual_score: float = 0.0  # Actual score when threshold crossed

    # Timing
    timestamp: datetime = field(default_factory=datetime.now)

    # Additional statistics at threshold crossing
    players_left: Optional[int] = None
    total_money: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert threshold to dictionary for database insertion.

        Returns:
            Dictionary with all threshold data
        """
        return {
            "id": self.id,
            "bookmaker": self.bookmaker,
            "round_id": self.round_id,
            "threshold": self.threshold,
            "actual_score": self.actual_score,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "players_left": self.players_left,
            "total_money": self.total_money
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Threshold":
        """
        Create Threshold from dictionary.

        Args:
            data: Dictionary with threshold data

        Returns:
            Threshold instance
        """
        # Parse timestamp if it's a string
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            id=data.get("id"),
            bookmaker=data.get("bookmaker", ""),
            round_id=data.get("round_id"),
            threshold=data.get("threshold", 0.0),
            actual_score=data.get("actual_score", 0.0),
            timestamp=timestamp,
            players_left=data.get("players_left"),
            total_money=data.get("total_money")
        )

    def validate(self) -> bool:
        """
        Validate threshold data.

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not self.bookmaker:
            logging.warning("Threshold validation failed: missing bookmaker")
            return False

        # Validate threshold value (common thresholds: 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0)
        if self.threshold < 1.0 or self.threshold > 100.0:
            logging.warning(f"Threshold validation failed: invalid threshold {self.threshold}")
            return False

        # Validate actual score
        if self.actual_score < self.threshold:
            logging.warning(
                f"Threshold validation failed: actual_score {self.actual_score} < threshold {self.threshold}"
            )
            return False

        # Actual score should be close to threshold (within tolerance)
        # We allow up to 0.5x difference for detection lag
        tolerance = 0.5
        if self.actual_score > self.threshold + tolerance:
            logging.warning(
                f"Threshold validation warning: actual_score {self.actual_score} "
                f"too far from threshold {self.threshold}"
            )
            # Don't fail validation, just warn

        # Validate optional player count
        if self.players_left is not None and self.players_left < 0:
            logging.warning("Threshold validation failed: negative players_left")
            return False

        # Validate optional money
        if self.total_money is not None and self.total_money < 0.0:
            logging.warning("Threshold validation failed: negative total_money")
            return False

        return True

    def get_accuracy(self) -> float:
        """
        Get detection accuracy (how close actual_score is to threshold).

        Returns:
            Difference between actual score and threshold
        """
        return abs(self.actual_score - self.threshold)

    def is_accurate(self, tolerance: float = 0.1) -> bool:
        """
        Check if threshold detection was accurate.

        Args:
            tolerance: Maximum allowed difference

        Returns:
            True if detection was within tolerance
        """
        return self.get_accuracy() <= tolerance

    def __repr__(self) -> str:
        """String representation of Threshold."""
        accuracy = self.get_accuracy()
        return (
            f"Threshold(bookmaker={self.bookmaker}, "
            f"threshold={self.threshold:.1f}x, "
            f"actual={self.actual_score:.2f}x, "
            f"accuracy={accuracy:.3f}, "
            f"timestamp={self.timestamp})"
        )


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    # Create test threshold
    threshold_data = Threshold(
        bookmaker="Mozzart",
        round_id=12345,
        threshold=2.0,
        actual_score=2.03,
        players_left=100,
        total_money=25000.0
    )

    print(f"Threshold: {threshold_data}")
    print(f"Valid: {threshold_data.validate()}")
    print(f"Accurate: {threshold_data.is_accurate(tolerance=0.1)}")
    print(f"Accuracy: {threshold_data.get_accuracy():.3f}x")
    print(f"Dict: {threshold_data.to_dict()}")

    # Test serialization
    threshold_dict = threshold_data.to_dict()
    threshold_restored = Threshold.from_dict(threshold_dict)
    print(f"Restored: {threshold_restored}")
