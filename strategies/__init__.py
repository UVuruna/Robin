"""Betting strategies for AVIATOR system."""
from strategies.base_strategy import BaseStrategy, BetDecision
from strategies.martingale import MartingaleStrategy

__all__ = [
    'BaseStrategy',
    'BetDecision',
    'MartingaleStrategy'
]