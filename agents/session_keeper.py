# agents/session_keeper.py
# VERSION: 3.0 - REFAKTORISAN SA NOVOM ARHITEKTUROM
# PURPOSE: Održava sesiju kada betting agent nije aktivan

import time
import logging
import random
from typing import Dict, List, Callable, Optional
import pyautogui

from core.communication.event_bus import EventPublisher, EventType
from core.input.transaction_controller import TransactionController
from config import GamePhase

class SessionKeeper:
    """
    Agent koji održava sesiju sa povremenim klikovima.
    Sprečava timeout i logout zbog neaktivnosti.

    Runtime: Thread u Worker procesu
    Exclusivity: Kad je aktivan, BettingAgent je PAUSED

    Timing:
    - Prvi klik: 300s + offset (30s * bookmaker_index)
    - Interval: random(250, 350) sekundi
    - Razmak između bookmaker-a: 30s offset pri inicijalizaciji
    """

    def __init__(
        self,
        bookmaker: str,
        coords: Dict,
        get_state_fn: Callable[[], Dict],
        bookmaker_index: int = 0,
        transaction_controller: Optional[TransactionController] = None
    ):
        """
        Initialize SessionKeeper.

        Args:
            bookmaker: Bookmaker name
            coords: Screen coordinates
            get_state_fn: Closure funkcija za pristup Worker's local_state
            bookmaker_index: Index kladionice (0-5) za offset calculation
            transaction_controller: Optional TransactionController za akcije
        """
        self.bookmaker = bookmaker
        self.coords = coords
        self.get_state = get_state_fn  # Closure za local_state
        self.tx_controller = transaction_controller or TransactionController()
        self.logger = logging.getLogger(f"SessionKeeper-{bookmaker}")

        # Components
        self.event_publisher = EventPublisher(f"SessionKeeper-{bookmaker}")

        # Click regions - mesta gde može bezbedno da klikne
        self.safe_click_zones = self._setup_safe_zones()

        # Action sequences (fake transactions)
        self.action_sequences = self._setup_action_sequences()

        # Timing configuration
        self.click_interval_min = 250  # 250 sekundi
        self.click_interval_max = 350  # 350 sekundi
        self.initial_delay = 300 + (bookmaker_index * 30)  # 300s + offset

        # State
        self.last_click_time = 0
        self.next_click_time = time.time() + self.initial_delay  # Prvi klik nakon delay

        # Control
        self.running = False
        self.active = True  # Can be paused when betting agent is active

        # Stats
        self.total_clicks = 0
        self.total_actions = 0
        self.session_start = time.time()

        self.logger.info(
            f"Initialized for {bookmaker} (index={bookmaker_index}, "
            f"first_click_in={self.initial_delay}s, interval={self.click_interval_min}-{self.click_interval_max}s)"
        )
    
    def _setup_safe_zones(self) -> List[Dict]:
        """Setup safe click zones based on bookmaker layout."""
        zones = []
        
        # Add safe zones around non-interactive areas
        if 'score' in self.coords:
            # Area around score display (but not on it)
            score = self.coords['score']
            zones.append({
                'x': score['left'] - 50,
                'y': score['top'] - 50,
                'width': 40,
                'height': 40,
                'name': 'near_score'
            })
        
        if 'phase' in self.coords:
            # Area near phase indicator
            phase = self.coords['phase']
            zones.append({
                'x': phase['left'] + phase['width'] + 10,
                'y': phase['top'],
                'width': 30,
                'height': 30,
                'name': 'near_phase'
            })
        
        # Add some random areas in the game window
        if 'window' in self.coords:
            window = self.coords['window']
            # Top-left corner area
            zones.append({
                'x': window['left'] + 10,
                'y': window['top'] + 10,
                'width': 50,
                'height': 50,
                'name': 'top_left'
            })
            # Bottom-right corner area
            zones.append({
                'x': window['left'] + window['width'] - 60,
                'y': window['top'] + window['height'] - 60,
                'width': 50,
                'height': 50,
                'name': 'bottom_right'
            })
        
        return zones

    def _setup_action_sequences(self) -> List[List[str]]:
        """
        Setup fake action sequences to simulate activity.
        Random sequence is chosen each time to avoid robotic behavior.
        """
        return [
            ['click_safe_zone', 'pause_short'],
            ['click_safe_zone', 'pause_medium', 'click_safe_zone'],
            ['type_fake_amount', 'pause_short', 'clear_amount'],
            ['type_fake_autostop', 'pause_short', 'clear_autostop'],
            ['click_safe_zone', 'scroll', 'pause_short'],
        ]

    def run(self):
        """Main session keeper loop."""
        self.logger.info("Starting session keeper")
        self.running = True
        self.session_start = time.time()

        while self.running:
            try:
                # Check if should perform action
                current_time = time.time()

                if self.active and current_time >= self.next_click_time:
                    # Get game state via closure (Worker's local_state)
                    state = self.get_state()

                    # Only act during safe phases
                    if state and state.get('phase') in [GamePhase.ENDED.value, GamePhase.BETTING.value]:
                        # Randomly choose: simple click or action sequence
                        if random.random() < 0.7:  # 70% simple click
                            self._perform_click()
                        else:  # 30% action sequence
                            self._perform_action_sequence()

                        self._schedule_next_click()
                    else:
                        # Postpone if in critical phase
                        self.next_click_time = current_time + 10
                
                # Small sleep
                time.sleep(1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error in session keeper: {e}")
                time.sleep(5)
        
        self.logger.info("Session keeper stopped")
    
    def _perform_click(self):
        """Perform a safe click."""
        if not self.safe_click_zones:
            self.logger.warning("No safe click zones defined")
            return
        
        try:
            # Choose random safe zone
            zone = random.choice(self.safe_click_zones)
            
            # Random position within zone
            x = zone['x'] + random.randint(0, zone.get('width', 10))
            y = zone['y'] + random.randint(0, zone.get('height', 10))
            
            # Perform click
            pyautogui.click(x, y, duration=0.1)
            
            self.total_clicks += 1
            self.last_click_time = time.time()
            
            self.logger.debug(f"Clicked at ({x}, {y}) in zone '{zone.get('name', 'unnamed')}'")
            
            # Publish event
            self.event_publisher.publish(
                EventType.DATA_COLLECTED,
                {
                    'bookmaker': self.bookmaker,
                    'type': 'session_click',
                    'zone': zone.get('name', 'unnamed'),
                    'position': {'x': x, 'y': y}
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error performing click: {e}")
    
    def _perform_action_sequence(self):
        """Perform a random action sequence."""
        if not self.action_sequences:
            self.logger.warning("No action sequences defined")
            return

        try:
            # Choose random sequence
            sequence = random.choice(self.action_sequences)

            self.logger.debug(f"Executing action sequence: {sequence}")

            for action in sequence:
                self._execute_action(action)
                time.sleep(random.uniform(0.3, 0.8))  # Random pause between actions

            self.total_actions += 1

            # Publish event
            self.event_publisher.publish(
                EventType.DATA_COLLECTED,
                {
                    'bookmaker': self.bookmaker,
                    'type': 'session_action_sequence',
                    'sequence': sequence
                }
            )

        except Exception as e:
            self.logger.error(f"Error performing action sequence: {e}")

    def _execute_action(self, action: str):
        """Execute single action."""
        try:
            if action == 'click_safe_zone':
                self._perform_click()
            elif action == 'pause_short':
                time.sleep(random.uniform(0.2, 0.5))
            elif action == 'pause_medium':
                time.sleep(random.uniform(0.5, 1.0))
            elif action == 'type_fake_amount':
                amount = random.choice([10, 20, 50, 100])
                self.tx_controller.type_text(str(amount), clear_first=False)
            elif action == 'type_fake_autostop':
                autostop = random.choice([1.5, 2.0, 2.5, 3.0])
                self.tx_controller.type_text(str(autostop), clear_first=False)
            elif action == 'clear_amount':
                self.tx_controller.clear_field()
            elif action == 'clear_autostop':
                self.tx_controller.clear_field()
            elif action == 'scroll':
                pyautogui.scroll(random.choice([-3, -2, -1, 1, 2, 3]))
            else:
                self.logger.warning(f"Unknown action: {action}")

        except Exception as e:
            self.logger.error(f"Error executing action '{action}': {e}")

    def _schedule_next_click(self):
        """Schedule next click with random interval."""
        interval = random.uniform(self.click_interval_min, self.click_interval_max)
        self.next_click_time = time.time() + interval
        self.logger.debug(f"Next action scheduled in {interval:.1f} seconds ({interval/60:.1f} minutes)")
    
    def pause(self):
        """Pause session keeper (when betting agent is active)."""
        self.active = False
        self.logger.info("Session keeper paused")
    
    def resume(self):
        """Resume session keeper."""
        self.active = True
        self._schedule_next_click()
        self.logger.info("Session keeper resumed")
    
    def stop(self):
        """Stop session keeper."""
        self.running = False
        
        # Log final stats
        session_duration = time.time() - self.session_start
        clicks_per_hour = (self.total_clicks / session_duration) * 3600 if session_duration > 0 else 0
        
        self.logger.info(f"Session stats: Duration: {session_duration:.0f}s, "
                        f"Total clicks: {self.total_clicks}, "
                        f"Rate: {clicks_per_hour:.1f} clicks/hour")
    
    def set_interval(self, min_interval: int, max_interval: int):
        """Update click interval."""
        self.min_interval = max(10, min_interval)  # At least 10 seconds
        self.max_interval = max(self.min_interval + 10, max_interval)
        self.logger.info(f"Interval updated: {self.min_interval}-{self.max_interval}s")
    
    def add_safe_zone(self, zone: Dict):
        """Add new safe click zone."""
        self.safe_click_zones.append(zone)
        self.logger.info(f"Added safe zone: {zone.get('name', 'unnamed')}")
    
    def get_stats(self) -> Dict:
        """Get session keeper statistics."""
        uptime = time.time() - self.session_start
        time_until_next = max(0, self.next_click_time - time.time())
        
        return {
            'bookmaker': self.bookmaker,
            'status': 'active' if self.active else 'paused' if self.running else 'stopped',
            'uptime_seconds': uptime,
            'total_clicks': self.total_clicks,
            'clicks_per_hour': (self.total_clicks / uptime) * 3600 if uptime > 0 else 0,
            'time_until_next_click': time_until_next,
            'safe_zones_count': len(self.safe_click_zones)
        }