# agents/betting_agent.py
# VERSION: 3.0 - REFAKTORISAN SA NOVOM ARHITEKTUROM
# PURPOSE: Automatizovan betting agent sa novom arhitekturom

import time
import logging
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass
from enum import IntEnum

from core.input.transaction_controller import TransactionController
from core.communication.event_bus import EventPublisher, EventSubscriber, EventType
from data.database.batch_writer import BatchDatabaseWriter
from config import GamePhase, BettingConfig
from strategies.base_strategy import BaseStrategy
from agents.strategy_executor import StrategyExecutor

class BetStatus(IntEnum):
    """Status of current bet."""
    NO_BET = 0
    BET_PLACED = 1
    BET_WON = 2
    BET_LOST = 3
    BET_CASHED = 4

@dataclass
class BetInfo:
    """Information about current bet."""
    amount: float
    auto_stop: float
    entry_score: float
    exit_score: float = 0.0
    profit: float = 0.0
    status: BetStatus = BetStatus.NO_BET
    placed_at: float = 0.0
    ended_at: float = 0.0

class BettingAgent:
    """
    Refaktorisan betting agent koji koristi novu arhitekturu.

    Features:
    - Koristi closure funkcije za pristup Worker's local_state i round_history
    - Transaction Controller za atomske bet operacije
    - Event Bus za komunikaciju
    - Batch Writer za database (shared instance)
    - Strategy pattern za betting logiku (via StrategyExecutor)

    Runtime: Thread u Worker procesu
    Exclusivity: Kad je aktivan, SessionKeeper je PAUSED
    """

    def __init__(
        self,
        bookmaker: str,
        strategy: BaseStrategy,
        coords: Dict,
        config: BettingConfig,
        get_state_fn: Callable[[], Dict],
        get_history_fn: Callable[[], List[Dict]],
        db_writer: BatchDatabaseWriter,
        transaction_controller: Optional[TransactionController] = None,
        strategy_executor: Optional['StrategyExecutor'] = None
    ):
        """
        Initialize BettingAgent.

        Args:
            bookmaker: Bookmaker name
            strategy: Strategy instance (legacy, will be replaced by strategy_executor)
            coords: Screen coordinates
            config: Betting configuration
            get_state_fn: Closure za pristup Worker's local_state
            get_history_fn: Closure za pristup Worker's round_history
            db_writer: Shared BatchDatabaseWriter instance
            transaction_controller: Optional TransactionController
            strategy_executor: Optional StrategyExecutor for decision making
        """
        self.bookmaker = bookmaker
        self.strategy = strategy
        self.coords = coords
        self.config = config
        self.get_state = get_state_fn  # Closure za local_state
        self.get_history = get_history_fn  # Closure za round_history
        self.logger = logging.getLogger(f"BettingAgent-{bookmaker}")

        # Components
        self.tx_controller = transaction_controller or TransactionController()
        self.event_publisher = EventPublisher(f"BettingAgent-{bookmaker}")
        self.event_subscriber = EventSubscriber(f"BettingAgent-{bookmaker}")
        self.db_writer = db_writer  # Shared instance from Worker Process
        self.strategy_executor = strategy_executor  # Optional, for future use
        
        # State tracking
        self.current_bet: Optional[BetInfo] = None
        self.previous_phase = GamePhase.ENDED
        self.balance_start = 0.0
        self.balance_current = 0.0
        self.total_bets = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_profit = 0.0

        # Control
        self.running = False
        self.active = True  # Can be paused when session keeper is active
        self.paused = False  # Paused via pause() method
        
        # Subscribe to events
        self._setup_event_subscriptions()
        
        self.logger.info(f"Initialized with strategy: {strategy.__class__.__name__}")
    
    def _setup_event_subscriptions(self):
        """Setup event subscriptions."""
        # Listen for manual stop signals
        self.event_subscriber.subscribe(
            EventType.WORKER_STOPPED,
            self._on_stop_signal
        )
    
    def _on_stop_signal(self, event):
        """Handle stop signal."""
        if event.data.get('bookmaker') == self.bookmaker:
            self.logger.info("Received stop signal")
            self.stop()
    
    def run(self):
        """Main betting loop."""
        self.logger.info("Starting betting agent")
        self.running = True

        # Get initial balance via closure
        state = self.get_state()
        if state:
            self.balance_start = state.get('my_money', 0.0)
            self.balance_current = state.get('my_money', 0.0)

        while self.running:
            try:
                if self.paused:
                    time.sleep(0.1)
                    continue

                # Get current game state via closure (Worker's local_state)
                state = self.get_state()
                if not state or not state.get('is_valid', False):
                    time.sleep(0.1)
                    continue

                # Update balance
                self.balance_current = state.get('my_money', self.balance_current)

                # Process based on phase
                self._process_phase(state)

                # Track phase changes
                current_phase = state.get('phase')
                if current_phase != self.previous_phase:
                    self.event_publisher.publish(
                        EventType.PHASE_CHANGE,
                        {
                            'bookmaker': self.bookmaker,
                            'from_phase': self.previous_phase,
                            'to_phase': current_phase
                        }
                    )
                    self.previous_phase = current_phase
                
                # Small delay
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.event_publisher.worker_error(
                    str(e),
                    {'bookmaker': self.bookmaker}
                )
                time.sleep(1)
        
        self.logger.info("Betting agent stopped")
    
    def _process_phase(self, state: Dict):
        """
        Process game state based on phase.

        Args:
            state: Dict from Worker's local_state
        """

        current_phase = state.get('phase')
        current_score = state.get('score', 0.0)

        # BETTING phase - Place bet if strategy says so
        if current_phase == GamePhase.BETTING.value:
            if not self.current_bet:
                # Get history via closure (Worker's round_history)
                history = self.get_history()

                # Use StrategyExecutor if available, otherwise legacy strategy
                if self.strategy_executor:
                    decision = self.strategy_executor.decide(history)
                    # decision = {'bet_amounts': [...], 'auto_stops': [...], 'current_index': 0}
                    if decision.get('bet_amounts'):
                        idx = decision.get('current_index', 0)
                        self._place_bet(
                            amount=decision['bet_amounts'][idx],
                            auto_stop=decision['auto_stops'][idx]
                        )
                else:
                    # Legacy strategy
                    decision = self.strategy.should_bet(
                        balance=self.balance_current,
                        history=history
                    )

                    if decision.get('place_bet'):
                        self._place_bet(
                            amount=decision['amount'],
                            auto_stop=decision['auto_stop']
                        )

        # SCORE phases - Monitor and potentially cash out
        elif current_phase in [GamePhase.SCORE_LOW.value, GamePhase.SCORE_MID.value, GamePhase.SCORE_HIGH.value]:
            if self.current_bet and self.current_bet.status == BetStatus.BET_PLACED:
                # Check if should cash out
                if self.strategy.should_cash_out(
                    current_score=current_score,
                    bet_info=self.current_bet
                ):
                    self._cash_out(current_score)
        
        # ENDED phase - Record result
        elif current_phase == GamePhase.ENDED.value:
            if self.current_bet and self.current_bet.status == BetStatus.BET_PLACED:
                self._record_loss(current_score)
    
    def _place_bet(self, amount: float, auto_stop: float):
        """Place a bet."""
        try:
            # Validate amount
            amount = max(self.config.min_bet_amount, 
                        min(amount, self.config.max_bet_amount))
            
            # Validate auto-stop
            auto_stop = max(self.config.min_auto_stop,
                           min(auto_stop, self.config.max_auto_stop))
            
            # Execute transaction
            success = self.tx_controller.place_bet(
                bookmaker=self.bookmaker,
                amount=amount,
                auto_stop=auto_stop,
                coords=self.coords,
                priority=3  # HIGH priority (1=CRITICAL, 3=HIGH, 5=NORMAL, 7=LOW, 10=LOWEST)
            )
            
            if success:
                # Create bet info
                self.current_bet = BetInfo(
                    amount=amount,
                    auto_stop=auto_stop,
                    entry_score=1.0,
                    placed_at=time.time(),
                    status=BetStatus.BET_PLACED
                )
                
                self.total_bets += 1
                
                # Publish event
                self.event_publisher.bet_placed(
                    self.bookmaker, amount, auto_stop
                )
                
                self.logger.info(f"Bet placed: {amount} @ {auto_stop}x")
            else:
                self.logger.error("Failed to place bet")
                
        except Exception as e:
            self.logger.error(f"Error placing bet: {e}")
    
    def _cash_out(self, current_score: float):
        """Cash out current bet."""
        try:
            success = self.tx_controller.cash_out(
                bookmaker=self.bookmaker,
                coords=self.coords,
                priority=1  # CRITICAL priority (cash out is time-sensitive!)
            )
            
            if success and self.current_bet:
                self.current_bet.exit_score = current_score
                self.current_bet.profit = self.current_bet.amount * (current_score - 1)
                self.current_bet.status = BetStatus.BET_CASHED
                self.current_bet.ended_at = time.time()
                
                self.total_wins += 1
                self.total_profit += self.current_bet.profit
                
                # Save to database
                self._save_bet_to_db()
                
                # Publish event
                self.event_publisher.publish(
                    EventType.BET_CASHED,
                    {
                        'bookmaker': self.bookmaker,
                        'score': current_score,
                        'profit': self.current_bet.profit
                    }
                )
                
                self.logger.info(f"Cashed out at {current_score}x, profit: {self.current_bet.profit:.2f}")
                
                # Clear current bet
                self.current_bet = None
                
        except Exception as e:
            self.logger.error(f"Error cashing out: {e}")
    
    def _record_loss(self, final_score: float):
        """Record lost bet."""
        if not self.current_bet:
            return
        
        self.current_bet.exit_score = final_score
        self.current_bet.profit = -self.current_bet.amount
        self.current_bet.status = BetStatus.BET_LOST
        self.current_bet.ended_at = time.time()
        
        self.total_losses += 1
        self.total_profit -= self.current_bet.amount
        
        # Save to database
        self._save_bet_to_db()
        
        # Publish event
        self.event_publisher.publish(
            EventType.BET_LOST,
            {
                'bookmaker': self.bookmaker,
                'score': final_score,
                'loss': self.current_bet.amount
            }
        )
        
        self.logger.info(f"Bet lost at {final_score}x, loss: {self.current_bet.amount:.2f}")
        
        # Update strategy with loss
        self.strategy.on_loss(self.current_bet)
        
        # Clear current bet
        self.current_bet = None
    
    def _save_bet_to_db(self):
        """Save bet to database."""
        if not self.current_bet:
            return
        
        record = {
            'bookmaker': self.bookmaker,
            'amount': self.current_bet.amount,
            'auto_stop': self.current_bet.auto_stop,
            'entry_score': self.current_bet.entry_score,
            'exit_score': self.current_bet.exit_score,
            'profit': self.current_bet.profit,
            'status': int(self.current_bet.status),
            'strategy': self.strategy.__class__.__name__,
            'balance_before': self.balance_current - self.current_bet.profit,
            'balance_after': self.balance_current,
            'placed_at': self.current_bet.placed_at,
            'ended_at': self.current_bet.ended_at,
            'duration': self.current_bet.ended_at - self.current_bet.placed_at
        }
        
        self.db_writer.add(record)
    
    def pause(self):
        """Pause betting (finish current bet)."""
        self.paused = True
        self.logger.info("Betting paused")
    
    def resume(self):
        """Resume betting."""
        self.paused = False
        self.logger.info("Betting resumed")
    
    def stop(self):
        """Stop betting agent."""
        self.running = False
        
        # Flush database
        self.db_writer.flush()
        
        # Final stats
        self.logger.info(f"Final stats: Bets: {self.total_bets}, "
                        f"Wins: {self.total_wins}, Losses: {self.total_losses}, "
                        f"Profit: {self.total_profit:.2f}")
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        win_rate = (self.total_wins / self.total_bets * 100) if self.total_bets > 0 else 0
        
        return {
            'bookmaker': self.bookmaker,
            'strategy': self.strategy.__class__.__name__,
            'balance_start': self.balance_start,
            'balance_current': self.balance_current,
            'total_profit': self.total_profit,
            'total_bets': self.total_bets,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'win_rate': win_rate,
            'current_bet': self.current_bet is not None,
            'status': 'paused' if self.paused else 'running' if self.running else 'stopped'
        }