"""
Module: Round Model
Purpose: Data model for completed game rounds
Version: 2.0

This module provides:
- Round data structure for database storage
- Validation of round data
- Serialization/deserialization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from data_layer.models.base import BaseModel


@dataclass
class Round(BaseModel):
    """
    Completed round data model.

    Stores information about a finished Aviator game round including:
    - Final score (crash point)
    - Player statistics
    - Money totals
    - Round timing information
    """

    # Identification
    bookmaker: str = ""

    # Timing
    timestamp: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    loading_duration_ms: int = 0

    # Score
    final_score: float = 0.0

    # Player statistics
    total_players: int = 0
    players_left: int = 0  # Players who cashed out

    # Money statistics
    total_money: float = 0.0
    my_money: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert round to dictionary for database insertion.

        Returns:
            Dictionary with all round data
        """
        return {
            "id": self.id,
            "bookmaker": self.bookmaker,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration_seconds": self.duration_seconds,
            "loading_duration_ms": self.loading_duration_ms,
            "final_score": self.final_score,
            "total_players": self.total_players,
            "players_left": self.players_left,
            "total_money": self.total_money,
            "my_money": self.my_money
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Round":
        """
        Create Round from dictionary.

        Args:
            data: Dictionary with round data

        Returns:
            Round instance
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
            timestamp=timestamp,
            duration_seconds=data.get("duration_seconds", 0.0),
            loading_duration_ms=data.get("loading_duration_ms", 0),
            final_score=data.get("final_score", 0.0),
            total_players=data.get("total_players", 0),
            players_left=data.get("players_left", 0),
            total_money=data.get("total_money", 0.0),
            my_money=data.get("my_money")
        )

    def validate(self) -> bool:
        """
        Validate round data.

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not self.bookmaker:
            logging.warning("Round validation failed: missing bookmaker")
            return False

        # Validate final score
        if self.final_score < 1.0 or self.final_score > 10000.0:
            logging.warning(f"Round validation failed: invalid final_score {self.final_score}")
            return False

        # Validate players
        if self.total_players < 0 or self.players_left < 0:
            logging.warning("Round validation failed: invalid player counts")
            return False

        if self.players_left > self.total_players:
            logging.warning("Round validation failed: players_left > total_players")
            return False

        # Validate money
        if self.total_money < 0.0:
            logging.warning("Round validation failed: negative total_money")
            return False

        # Validate duration
        if self.duration_seconds < 0.0 or self.duration_seconds > 300.0:  # Max 5 minutes
            logging.warning(f"Round validation failed: invalid duration {self.duration_seconds}")
            return False

        return True

    def __repr__(self) -> str:
        """String representation of Round."""
        return (
            f"Round(bookmaker={self.bookmaker}, "
            f"score={self.final_score:.2f}x, "
            f"players={self.players_left}/{self.total_players}, "
            f"timestamp={self.timestamp})"
        )


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    # Create test round
    round_data = Round(
        bookmaker="Mozzart",
        final_score=3.45,
        total_players=150,
        players_left=75,
        total_money=50000.0,
        duration_seconds=12.5,
        loading_duration_ms=1200
    )

    print(f"Round: {round_data}")
    print(f"Valid: {round_data.validate()}")
    print(f"Dict: {round_data.to_dict()}")

    # Test serialization
    round_dict = round_data.to_dict()
    round_restored = Round.from_dict(round_dict)
    print(f"Restored: {round_restored}")
