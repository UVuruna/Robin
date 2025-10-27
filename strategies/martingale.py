"""
Module: Martingale Strategy
Purpose: Classic Martingale betting strategy with custom bet list
Version: 2.0

Martingale strategy:
- User defines bet list: [10, 20, 40, 80, 150, 300, 550, 1000]
- User defines auto_stop multiplier (e.g., 2.3x)
- Win ’ Reset to index 0
- Loss ’ Move to next index (circular)
- Simple, deterministic progression
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from strategies.base_strategy import BaseStrategy, BetDecision


class MartingaleStrategy(BaseStrategy):
    """
    Classic Martingale strategy with custom bet progression list.

    How it works:
    1. User provides bet_list: [10, 20, 40, 80, 150, 300, 550, 1000]
    2. User provides auto_stop: 2.3 (cash out at 2.3x multiplier)
    3. Start at index 0 (first bet in list)
    4. Win ’ index = 0 (reset to start)
    5. Loss ’ index = (index + 1) % len(bet_list) (circular progression)

    Features:
    - Fixed auto_stop multiplier (no dynamic cash-out)
    - Circular bet progression (wraps around at end of list)
    - Accepts big loss when reaching end of list
    - Simple state tracking (just current index)

    Note: This is V1 - simple implementation.
    V2 will use ML to determine optimal bet timing and amounts.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Martingale strategy.

        Args:
            config: Strategy configuration with:
                - bet_list: List[float] - Bet progression (required)
                - auto_stop: float - Cash out multiplier (required)
                - max_balance_risk: float - Max % of balance to risk (optional, default 10%)

        Example config:
            {
                "bet_list": [10, 20, 40, 80, 150, 300, 550, 1000],
                "auto_stop": 2.3,
                "max_balance_risk": 10.0
            }
        """
        super().__init__(config)

        # Required configuration
        if "bet_list" not in self.config:
            raise ValueError("bet_list is required in config")
        if "auto_stop" not in self.config:
            raise ValueError("auto_stop is required in config")

        self.bet_list: List[float] = self.config["bet_list"]
        self.auto_stop: float = self.config["auto_stop"]
        self.max_balance_risk: float = self.config.get("max_balance_risk", 10.0)

        # Validate configuration
        if not self.bet_list or len(self.bet_list) == 0:
            raise ValueError("bet_list cannot be empty")
        if any(bet <= 0 for bet in self.bet_list):
            raise ValueError("All bets in bet_list must be positive")
        if self.auto_stop <= 1.0:
            raise ValueError("auto_stop must be greater than 1.0")

        # State
        self.current_index = 0
        self.cycle_count = 0  # How many times we've wrapped around

        # Statistics
        self.total_wins = 0
        self.total_losses = 0
        self.total_wagered = 0.0
        self.total_profit = 0.0
        self.max_index_reached = 0

        self.logger = logging.getLogger("MartingaleStrategy")
        self.logger.info(
            f"Martingale initialized: bet_list={self.bet_list}, "
            f"auto_stop={self.auto_stop}x"
        )

    def should_bet(self, balance: float, history: List[Any]) -> Dict:
        """
        Decide whether to place a bet.

        Args:
            balance: Current account balance
            history: Recent betting history (not used in simple Martingale)

        Returns:
            BetDecision dictionary
        """
        # Get current bet amount
        bet_amount = self.bet_list[self.current_index]

        # Check if bet exceeds balance
        if bet_amount > balance:
            self.logger.warning(
                f"Bet amount {bet_amount} exceeds balance {balance}. Skipping bet."
            )
            return self._create_decision(
                place_bet=False,
                reason=f"Insufficient balance ({balance} < {bet_amount})"
            )

        # Check max balance risk
        balance_risk_percent = (bet_amount / balance) * 100
        if balance_risk_percent > self.max_balance_risk:
            self.logger.warning(
                f"Bet risk {balance_risk_percent:.1f}% exceeds max risk {self.max_balance_risk}%"
            )
            return self._create_decision(
                place_bet=False,
                reason=f"Risk too high ({balance_risk_percent:.1f}% > {self.max_balance_risk}%)"
            )

        # Place bet
        self.logger.info(
            f"Placing bet: {bet_amount} (index {self.current_index}/{len(self.bet_list)-1}) "
            f"with auto_stop {self.auto_stop}x"
        )

        return self._create_decision(
            place_bet=True,
            amount=bet_amount,
            auto_stop=self.auto_stop,
            reason=f"Martingale index {self.current_index}, cycle {self.cycle_count}"
        )

    def should_cash_out(self, current_score: float, bet_info: Any) -> bool:
        """
        Decide whether to cash out current bet.

        Note: In this strategy, cash-out is handled by auto_stop.
        This method is not used but required by base class.

        Args:
            current_score: Current game multiplier
            bet_info: Information about current bet

        Returns:
            False (auto_stop handles cash-out)
        """
        # Auto-stop handles cash-out timing
        return False

    def on_win(self, bet_info: Any):
        """
        Called when a bet wins.

        Resets index to 0 (restart progression).

        Args:
            bet_info: Information about winning bet
        """
        bet_amount = bet_info.get("amount", 0.0) if isinstance(bet_info, dict) else 0.0
        payout = bet_info.get("payout", 0.0) if isinstance(bet_info, dict) else 0.0
        profit = payout - bet_amount

        self.logger.info(
            f" WIN! Bet: {bet_amount}, Payout: {payout:.2f}, Profit: {profit:.2f}"
        )

        # Update statistics
        self.total_wins += 1
        self.total_wagered += bet_amount
        self.total_profit += profit
        self.consecutive_wins += 1
        self.consecutive_losses = 0

        # Track max index reached before win
        if self.current_index > self.max_index_reached:
            self.max_index_reached = self.current_index

        # Reset to start of bet list
        old_index = self.current_index
        self.current_index = 0

        self.logger.info(
            f"Index reset: {old_index} ’ {self.current_index} "
            f"(Total profit: {self.total_profit:.2f})"
        )

    def on_loss(self, bet_info: Any):
        """
        Called when a bet loses.

        Moves to next index in bet list (circular).

        Args:
            bet_info: Information about losing bet
        """
        bet_amount = bet_info.get("amount", 0.0) if isinstance(bet_info, dict) else 0.0
        loss = bet_amount

        self.logger.info(f"L LOSS! Bet: {bet_amount}")

        # Update statistics
        self.total_losses += 1
        self.total_wagered += bet_amount
        self.total_profit -= loss
        self.consecutive_losses += 1
        self.consecutive_wins = 0

        # Move to next index (circular)
        old_index = self.current_index
        self.current_index = (self.current_index + 1) % len(self.bet_list)

        # Check if we wrapped around (accepted big loss)
        if self.current_index < old_index:
            self.cycle_count += 1
            self.logger.warning(
                f"  Wrapped around bet list! "
                f"Accepting big loss and restarting. "
                f"Cycle count: {self.cycle_count}"
            )

        self.logger.info(
            f"Index progressed: {old_index} ’ {self.current_index} "
            f"(Total profit: {self.total_profit:.2f})"
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get strategy statistics.

        Returns:
            Dictionary with strategy stats
        """
        total_bets = self.total_wins + self.total_losses
        win_rate = (self.total_wins / total_bets * 100) if total_bets > 0 else 0.0

        return {
            "strategy": "Martingale",
            "current_index": self.current_index,
            "current_bet": self.bet_list[self.current_index],
            "auto_stop": self.auto_stop,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "total_bets": total_bets,
            "win_rate": win_rate,
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "total_wagered": self.total_wagered,
            "total_profit": self.total_profit,
            "roi": (
                (self.total_profit / self.total_wagered * 100)
                if self.total_wagered > 0
                else 0.0
            ),
            "cycle_count": self.cycle_count,
            "max_index_reached": self.max_index_reached,
            "bet_list_length": len(self.bet_list)
        }

    def reset_statistics(self):
        """Reset all statistics (keep configuration)."""
        self.total_wins = 0
        self.total_losses = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.total_wagered = 0.0
        self.total_profit = 0.0
        self.cycle_count = 0
        self.max_index_reached = 0
        self.current_index = 0

        self.logger.info("Statistics reset")

    def _create_decision(
        self,
        place_bet: bool,
        amount: float = 0.0,
        auto_stop: float = 2.0,
        reason: str = ""
    ) -> Dict:
        """
        Create a bet decision dictionary.

        Args:
            place_bet: Whether to place bet
            amount: Bet amount
            auto_stop: Auto-stop multiplier
            reason: Decision reason

        Returns:
            BetDecision dictionary
        """
        return {
            "place_bet": place_bet,
            "amount": amount,
            "auto_stop": auto_stop,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Testing
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    print("=== Martingale Strategy Test ===\n")

    # Create strategy
    config = {
        "bet_list": [10, 20, 40, 80, 150, 300, 550, 1000],
        "auto_stop": 2.3,
        "max_balance_risk": 10.0
    }

    strategy = MartingaleStrategy(config)
    balance = 5000.0

    print(f"Initial balance: {balance}")
    print(f"Bet list: {config['bet_list']}")
    print(f"Auto-stop: {config['auto_stop']}x\n")

    # Simulate some bets
    print("=== Simulating Bet Sequence ===\n")

    # Scenario: Loss, Loss, Win
    for i, outcome in enumerate(["loss", "loss", "win"], 1):
        print(f"--- Round {i} ---")

        # Should bet?
        decision = strategy.should_bet(balance, [])
        print(f"Decision: {decision}")

        if decision["place_bet"]:
            bet_amount = decision["amount"]
            auto_stop = decision["auto_stop"]

            # Simulate outcome
            if outcome == "win":
                payout = bet_amount * auto_stop
                balance += (payout - bet_amount)
                strategy.on_win({"amount": bet_amount, "payout": payout})
                print(f"WIN! Payout: {payout:.2f}, New balance: {balance:.2f}")
            else:
                balance -= bet_amount
                strategy.on_loss({"amount": bet_amount})
                print(f"LOSS! New balance: {balance:.2f}")

        print()

    # Show final statistics
    print("=== Final Statistics ===")
    stats = strategy.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    print(f"\nFinal balance: {balance:.2f}")
    print(f"Profit: {balance - 5000:.2f}")
