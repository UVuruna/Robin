# agents/strategy_executor.py
# VERSION: 1.0
# PURPOSE: Strategy decision engine - stateless decision making

"""
StrategyExecutor - Donosi odluke o betting strategiji na osnovu istorije rundi.

Architecture:
    - Stateless funkcija - nema internal state
    - Input: round_history (100 poslednje rundi)
    - Output: {'bet_amounts': [...], 'auto_stops': [...], 'current_index': 0}
    - Poziva se od strane BettingAgent-a
    - Svaki bookmaker ima svoj instance

Data Flow:
    Worker Process ’ BettingAgent ’ StrategyExecutor
    BettingAgent.round_history (deque 100) ’ StrategyExecutor.decide()
    ’ decision ’ BettingAgent izvraava

Strategija format:
    - bet_amounts: Lista bet iznosa [10, 20, 40, 70, 120, 200]
    - auto_stops: Lista auto stop multiplikatora [2.20, 2.20, 2.20, 2.50, 3.00, 3.00]
    - current_index: Gde smo u strategiji (0-5)
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class StrategyDecision:
    """Decision returned by strategy executor."""
    bet_amounts: List[float]  # [10, 20, 40, ...]
    auto_stops: List[float]   # [2.20, 2.20, 2.50, ...]
    current_index: int        # Current position in strategy
    strategy_name: str        # "Martingale", "Fibonacci", etc.
    confidence: float = 1.0   # 0.0-1.0, za budue ML modele


class StrategyExecutor:
    """
    Strategy decision engine.

    Analizira istoriju rundi i odluuje o betting strategiji.
    Stateless - sve ato mu treba je u round_history parametru.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize strategy executor.

        Args:
            config: Optional configuration dict
                    {
                        'default_strategy': 'martingale',
                        'base_bet': 10,
                        'max_bet': 200,
                        'progression_factor': 2.0,
                        'auto_stop_conservative': 2.20,
                        'auto_stop_aggressive': 3.00
                    }
        """
        self.config = config or self._default_config()
        self.logger = logging.getLogger("StrategyExecutor")

    def _default_config(self) -> Dict:
        """Default configuration."""
        return {
            'default_strategy': 'martingale',
            'base_bet': 10,
            'max_bet': 200,
            'progression_factor': 2.0,
            'auto_stop_conservative': 2.20,
            'auto_stop_aggressive': 3.00,
            'max_progression_steps': 6
        }

    def decide(self, round_history: List[Dict]) -> Dict:
        """
        Decide betting strategy based on round history.

        Args:
            round_history: List of round dicts from Worker's round_history (deque 100)
                          Each dict contains:
                          {
                              'score': 3.45,
                              'total_players': 1250,
                              'players_left': 320,
                              'total_money': 12500.0,
                              'thresholds': [...],
                              'loading_duration_ms': 850,
                              'timestamp': 1234567890.123
                          }

        Returns:
            Dict with:
                {
                    'bet_amounts': [10, 20, 40, 70, 120, 200],
                    'auto_stops': [2.20, 2.20, 2.20, 2.50, 3.00, 3.00],
                    'current_index': 0,
                    'strategy_name': 'Martingale',
                    'confidence': 1.0
                }
        """
        strategy_name = self.config.get('default_strategy', 'martingale')

        if strategy_name == 'martingale':
            return self._martingale_strategy(round_history)
        elif strategy_name == 'fibonacci':
            return self._fibonacci_strategy(round_history)
        elif strategy_name == 'dalembert':
            return self._dalembert_strategy(round_history)
        else:
            self.logger.warning(f"Unknown strategy: {strategy_name}, using Martingale")
            return self._martingale_strategy(round_history)

    def _martingale_strategy(self, round_history: List[Dict]) -> Dict:
        """
        Martingale strategy - double bet after loss.

        Logic:
        - Start with base_bet
        - After loss, double the bet
        - After win, reset to base_bet
        - Adjust auto_stop based on progression level
        """
        base_bet = self.config['base_bet']
        max_bet = self.config['max_bet']
        factor = self.config['progression_factor']
        max_steps = self.config['max_progression_steps']

        # Generate bet progression
        bet_amounts = []
        auto_stops = []

        current_bet = base_bet
        for step in range(max_steps):
            bet_amounts.append(min(current_bet, max_bet))

            # Conservative auto-stop for first 3 steps, aggressive for last 3
            if step < 3:
                auto_stops.append(self.config['auto_stop_conservative'])
            else:
                auto_stops.append(self.config['auto_stop_aggressive'])

            current_bet *= factor

        # Determine current index based on recent history
        current_index = self._calculate_current_index(round_history, bet_amounts)

        return {
            'bet_amounts': bet_amounts,
            'auto_stops': auto_stops,
            'current_index': current_index,
            'strategy_name': 'Martingale',
            'confidence': 1.0
        }

    def _fibonacci_strategy(self, round_history: List[Dict]) -> Dict:
        """
        Fibonacci strategy - progression based on Fibonacci sequence.

        TODO: Implement Fibonacci logic
        """
        self.logger.warning("Fibonacci strategy not yet implemented, using Martingale")
        return self._martingale_strategy(round_history)

    def _dalembert_strategy(self, round_history: List[Dict]) -> Dict:
        """
        D'Alembert strategy - increase bet by fixed amount after loss.

        TODO: Implement D'Alembert logic
        """
        self.logger.warning("D'Alembert strategy not yet implemented, using Martingale")
        return self._martingale_strategy(round_history)

    def _calculate_current_index(self, round_history: List[Dict], bet_amounts: List[float]) -> int:
        """
        Calculate current position in strategy based on recent wins/losses.

        Logic:
        - If no history, start at 0
        - If last round was win, reset to 0
        - If last round was loss, move to next step
        - Cap at max index (len(bet_amounts) - 1)

        Args:
            round_history: Round history list
            bet_amounts: Bet amounts list

        Returns:
            Current index (0 to len(bet_amounts)-1)
        """
        if not round_history:
            return 0

        # Get last round
        last_round = round_history[-1]
        last_score = last_round.get('score', 0.0)

        # Simple logic: if last score > 2.0, consider it "winnable" ’ reset to 0
        # Otherwise, progress to next step
        # TODO: This needs proper bet result tracking from BettingAgent

        # For now, use dummy logic based on score patterns
        recent_scores = [r.get('score', 0.0) for r in round_history[-10:]]
        low_scores = sum(1 for s in recent_scores if s < 2.0)

        # If many low scores recently, increase index
        index = min(low_scores // 2, len(bet_amounts) - 1)

        return index

    def analyze_history(self, round_history: List[Dict]) -> Dict:
        """
        Analyze round history for statistics and patterns.

        Args:
            round_history: Round history list

        Returns:
            Dict with analysis:
                {
                    'avg_score': 2.34,
                    'low_scores_count': 15,
                    'high_scores_count': 5,
                    'avg_players': 1250,
                    'avg_money': 12500.0,
                    'loading_avg_ms': 850,
                    'pattern': 'volatile'  # 'stable', 'volatile', 'trending_low', 'trending_high'
                }
        """
        if not round_history:
            return {
                'avg_score': 0.0,
                'low_scores_count': 0,
                'high_scores_count': 0,
                'avg_players': 0,
                'avg_money': 0.0,
                'loading_avg_ms': 0,
                'pattern': 'unknown'
            }

        scores = [r.get('score', 0.0) for r in round_history]
        players = [r.get('total_players', 0) for r in round_history]
        money = [r.get('total_money', 0.0) for r in round_history]
        loading_times = [r.get('loading_duration_ms', 0) for r in round_history]

        avg_score = sum(scores) / len(scores) if scores else 0.0
        low_scores = sum(1 for s in scores if s < 2.0)
        high_scores = sum(1 for s in scores if s >= 3.0)

        # Determine pattern
        if len(scores) >= 10:
            recent_avg = sum(scores[-10:]) / 10
            overall_avg = avg_score

            if abs(recent_avg - overall_avg) < 0.3:
                pattern = 'stable'
            elif recent_avg < overall_avg - 0.5:
                pattern = 'trending_low'
            elif recent_avg > overall_avg + 0.5:
                pattern = 'trending_high'
            else:
                pattern = 'volatile'
        else:
            pattern = 'insufficient_data'

        return {
            'avg_score': round(avg_score, 2),
            'low_scores_count': low_scores,
            'high_scores_count': high_scores,
            'avg_players': int(sum(players) / len(players)) if players else 0,
            'avg_money': round(sum(money) / len(money), 2) if money else 0.0,
            'loading_avg_ms': int(sum(loading_times) / len(loading_times)) if loading_times else 0,
            'pattern': pattern
        }


# Example usage / testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    # Create strategy executor
    executor = StrategyExecutor()

    # Mock round history
    mock_history = [
        {'score': 1.50, 'total_players': 1200, 'players_left': 300, 'total_money': 12000, 'thresholds': []},
        {'score': 2.30, 'total_players': 1150, 'players_left': 400, 'total_money': 11500, 'thresholds': []},
        {'score': 1.20, 'total_players': 1300, 'players_left': 250, 'total_money': 13000, 'thresholds': []},
        {'score': 3.45, 'total_players': 1100, 'players_left': 500, 'total_money': 11000, 'thresholds': []},
    ]

    # Get decision
    decision = executor.decide(mock_history)
    print(f"\nStrategy Decision:")
    print(f"  Strategy: {decision['strategy_name']}")
    print(f"  Bet Amounts: {decision['bet_amounts']}")
    print(f"  Auto Stops: {decision['auto_stops']}")
    print(f"  Current Index: {decision['current_index']}")
    print(f"  Confidence: {decision['confidence']}")

    # Analyze history
    analysis = executor.analyze_history(mock_history)
    print(f"\nHistory Analysis:")
    for key, value in analysis.items():
        print(f"  {key}: {value}")
