# strategies/base_strategy.py
# VERSION: 1.0 - COMPLETE
# PURPOSE: Bazna klasa za sve betting strategije

from abc import ABC, abstractmethod
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class BetDecision:
    """Decision about placing a bet."""
    place_bet: bool
    amount: float = 0.0
    auto_stop: float = 2.0
    reason: str = ""

class BaseStrategy(ABC):
    """
    Bazna klasa za betting strategije.
    Sve custom strategije nasleđuju ovu klasu.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Default settings
        self.base_bet = self.config.get('base_bet', 10.0)
        self.max_bet = self.config.get('max_bet', 1000.0)
        self.target_multiplier = self.config.get('target_multiplier', 2.0)
        self.max_losses = self.config.get('max_losses', 10)
        self.stop_loss = self.config.get('stop_loss', -500.0)
        self.take_profit = self.config.get('take_profit', 500.0)
        
        # State tracking
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_profit = 0.0
        self.current_bet_amount = self.base_bet
        self.bet_history = []
    
    @abstractmethod
    def should_bet(self, balance: float, history: List[Any]) -> Dict:
        """
        Decide whether to place a bet.
        
        Args:
            balance: Current account balance
            history: Recent betting history
            
        Returns:
            BetDecision dictionary
        """
        pass
    
    @abstractmethod
    def should_cash_out(self, current_score: float, bet_info: Any) -> bool:
        """
        Decide whether to cash out current bet.
        
        Args:
            current_score: Current game multiplier
            bet_info: Information about current bet
            
        Returns:
            True if should cash out
        """
        pass
    
    @abstractmethod
    def on_win(self, bet_info: Any):
        """
        Called when a bet wins.
        Update strategy state.
        
        Args:
            bet_info: Information about winning bet
        """
        pass
    
    @abstractmethod
    def on_loss(self, bet_info: Any):
        """
        Called when a bet loses.
        Update strategy state.
        
        Args:
            bet_info: Information about losing bet
        """
        pass
    
    def calculate_next_bet(self) -> float:
        """
        Calculate next bet amount based on strategy.
        Override in subclasses for different progressions.
        
        Returns:
            Next bet amount
        """
        return self.base_bet
    
    def reset(self):
        """Reset strategy to initial state."""
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.current_bet_amount = self.base_bet
        self.bet_history.clear()
    
    def should_stop(self) -> bool:
        """
        Check if should stop betting based on limits.
        
        Returns:
            True if should stop
        """
        # Stop loss reached
        if self.total_profit <= self.stop_loss:
            return True
        
        # Take profit reached
        if self.total_profit >= self.take_profit:
            return True
        
        # Max consecutive losses
        if self.consecutive_losses >= self.max_losses:
            return True
        
        return False
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        total_bets = len(self.bet_history)
        wins = sum(1 for b in self.bet_history if b.get('won'))
        
        return {
            'name': self.__class__.__name__,
            'total_profit': self.total_profit,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'current_bet_amount': self.current_bet_amount,
            'total_bets': total_bets,
            'wins': wins,
            'losses': total_bets - wins,
            'win_rate': (wins / total_bets * 100) if total_bets > 0 else 0
        }
    
    def update_config(self, config: Dict[str, Any]):
        """Update strategy configuration."""
        self.config.update(config)
        
        # Update settings
        self.base_bet = self.config.get('base_bet', self.base_bet)
        self.max_bet = self.config.get('max_bet', self.max_bet)
        self.target_multiplier = self.config.get('target_multiplier', self.target_multiplier)
        self.max_losses = self.config.get('max_losses', self.max_losses)
        self.stop_loss = self.config.get('stop_loss', self.stop_loss)
        self.take_profit = self.config.get('take_profit', self.take_profit)
    
    def log_bet(self, amount: float, auto_stop: float, won: bool, profit: float):
        """Log bet to history."""
        self.bet_history.append({
            'amount': amount,
            'auto_stop': auto_stop,
            'won': won,
            'profit': profit,
            'total_profit': self.total_profit
        })
        
        # Keep only last 100 bets
        if len(self.bet_history) > 100:
            self.bet_history.pop(0)


class SimpleMartingale(BaseStrategy):
    """
    Simple Martingale strategy implementation.
    Doubles bet after each loss, resets after win.
    """
    
    def should_bet(self, balance: float, history: List[Any]) -> Dict:
        """Decide whether to place bet using Martingale."""
        
        # Check if should stop
        if self.should_stop():
            return {
                'place_bet': False,
                'reason': 'Strategy limits reached'
            }
        
        # Check if have enough balance
        if balance < self.current_bet_amount:
            return {
                'place_bet': False,
                'reason': 'Insufficient balance'
            }
        
        return {
            'place_bet': True,
            'amount': self.current_bet_amount,
            'auto_stop': self.target_multiplier,
            'reason': 'Martingale progression'
        }
    
    def should_cash_out(self, current_score: float, bet_info: Any) -> bool:
        """Cash out if target reached."""
        # Simple strategy - rely on auto cash-out
        # Could add manual cash-out logic here
        return False
    
    def on_win(self, bet_info: Any):
        """Reset to base bet after win."""
        self.consecutive_wins += 1
        self.consecutive_losses = 0
        self.total_profit += bet_info.profit
        
        # Reset to base bet
        self.current_bet_amount = self.base_bet
        
        # Log
        self.log_bet(
            bet_info.amount,
            bet_info.auto_stop,
            True,
            bet_info.profit
        )
    
    def on_loss(self, bet_info: Any):
        """Double bet after loss."""
        self.consecutive_losses += 1
        self.consecutive_wins = 0
        self.total_profit -= bet_info.amount
        
        # Double bet (with max limit)
        self.current_bet_amount = min(
            self.current_bet_amount * 2,
            self.max_bet
        )
        
        # Log
        self.log_bet(
            bet_info.amount,
            bet_info.auto_stop,
            False,
            -bet_info.amount
        )