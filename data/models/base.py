"""
Module: Base Data Models
Purpose: Data models for database operations
Version: 2.0

This module provides:
- Dataclass-based models (simple, no ORM)
- Round, Threshold, Bet, RGB sample models
- Easy serialization to/from dictionaries
- Type safety and validation
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class BaseModel:
    """Base model with common functionality."""
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary for database insertion.

        Returns:
            Dictionary representation
        """
        raise NotImplementedError("Subclasses must implement to_dict()")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """
        Create model instance from dictionary.

        Args:
            data: Dictionary with model data

        Returns:
            Model instance
        """
        raise NotImplementedError("Subclasses must implement from_dict()")

    def validate(self) -> bool:
        """
        Validate model data.

        Returns:
            True if valid, False otherwise
        """
        return True  # Override in subclasses


# Export all models for easy import
__all__ = [
    "BaseModel",
    "Round",
    "Threshold",
    "Bet",
    "RGBSample"
]


# NOTE: Round, Threshold, Bet, and RGBSample are defined in separate files
# for better organization. They will be implemented in:
# - round.py
# - threshold.py
# - bet.py (future)
# - rgb_sample.py (future)
