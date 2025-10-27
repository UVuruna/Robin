"""Betting strategies for AVIATOR system."""
from strategies.base_strategy import BaseStrategy
from strategies.martingale import MartingaleStrategy
from strategies.fibonacci import FibonacciStrategy

__all__ = ['BaseStrategy', 'MartingaleStrategy', 'FibonacciStrategy']