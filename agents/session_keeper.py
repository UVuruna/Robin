# agents/session_keeper.py
# VERSION: 2.0 - REFAKTORISAN
# PURPOSE: Održava sesiju kada betting agent nije aktivan

import time
import logging
import random
from typing import Dict, List
import pyautogui

from orchestration.shared_reader import get_shared_reader
from core.communication.event_bus import EventPublisher
from config import GamePhase

class SessionKeeper:
    """
    Agent koji održava sesiju sa povremenim klikovima.
    Sprečava timeout i logout zbog neaktivnosti.
    """
    
    def __init__(self, bookmaker: str, coords: Dict):
        self.bookmaker = bookmaker
        self.coords = coords
        self.logger = logging.getLogger(f"SessionKeeper-{bookmaker}")
        
        # Components
        self.shared_reader = get_shared_reader()
        self.event_publisher = EventPublisher(f"SessionKeeper-{bookmaker}")
        
        # Click regions - mesta gde može bezbedno da klikne
        self.safe_click_zones = self._setup_safe_zones()
        
        # Timing
        self.min_interval = 30  # Minimum seconds between clicks
        self.max_interval = 120  # Maximum seconds between clicks
        self.last_click_time = 0
        self.next_click_time = time.time() + random.uniform(self.min_interval, self.max_interval)
        
        # Control
        self.running = False
        self.active = True  # Can be paused when betting agent is active
        
        # Stats
        self.total_clicks = 0
        self.session_start = time.time()
        
        self.logger.info(f"Initialized for {bookmaker}")
    
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
    
    def run(self):
        """Main session keeper loop."""
        self.logger.info("Starting session keeper")
        self.running = True
        self.session_start = time.time()
        
        while self.running:
            try:
                # Check if should perform click
                current_time = time.time()
                
                if self.active and current_time >= self.next_click_time:
                    # Get game state to avoid clicking during critical moments
                    state = self.shared_reader.get_state(self.bookmaker)
                    
                    # Only click during safe phases
                    if state and state.phase in [GamePhase.ENDED, GamePhase.BETTING]:
                        self._perform_click()
                        self._schedule_next_click()
                    else:
                        # Postpone click if in critical phase
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
    
    def _schedule_next_click(self):
        """Schedule next click with random interval."""
        interval = random.uniform(self.min_interval, self.max_interval)
        self.next_click_time = time.time() + interval
        self.logger.debug(f"Next click scheduled in {interval:.1f} seconds")
    
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