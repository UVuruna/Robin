# orchestration/shared_reader.py
"""
Shared Game State Reader - Centralizovano čitanje za sve procese.
Čita jednom, deli sa svima preko shared memory.
"""

from multiprocessing import Manager, Process, Event
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from core.ocr.screen_reader import ScreenReader
from config import GamePhase


@dataclass
class GameState:
    """Trenutno stanje igre za jednu kladionicu"""
    bookmaker: str
    score: Optional[float] = None
    phase: GamePhase = GamePhase.UNKNOWN
    players_left: Optional[int] = None
    total_players: Optional[int] = None
    total_money: Optional[float] = None
    timestamp: float = 0.0
    last_score: Optional[float] = None
    same_score_count: int = 0
    round_start_time: Optional[float] = None
    loading_start_time: Optional[float] = None
    loading_duration_ms: Optional[int] = None


class SharedGameStateReader:
    """
    Deljeni reader koji čita game state jednom i deli sa svim procesima.
    
    Prednosti:
    - Samo jedan OCR po kladionici (umesto 2-3)
    - Instant pristup podacima preko shared memory
    - Sinhronizovano stanje između collector-a i agent-a
    """
    
    # Intervali čitanja bazirani na fazi
    READ_INTERVALS = {
        GamePhase.UNKNOWN: 0.5,
        GamePhase.BETTING: 0.3,
        GamePhase.LOADING: 0.2,
        GamePhase.START: 0.15,
        GamePhase.SCORE_LOW: 0.15,
        GamePhase.SCORE_MID: 0.2,
        GamePhase.SCORE_HIGH: 0.3,
        GamePhase.ENDED: 1.0,
    }
    
    def __init__(self, bookmaker_configs: List[Dict[str, Any]]):
        """
        Initialize shared reader.
        
        Args:
            bookmaker_configs: Lista sa konfiguracijom za svaku kladionicu
                              [{'name': 'Admiral', 'coords': {...}}, ...]
        """
        self.bookmaker_configs = bookmaker_configs
        self.logger = logging.getLogger("SharedReader")
        
        # Multiprocessing components
        self.manager = Manager()
        self.shared_state = self.manager.dict()  # Shared memory dict
        self.shutdown_event = Event()
        self.reader_process = None
        
        # Initialize state for each bookmaker
        for config in bookmaker_configs:
            name = config['name']
            self.shared_state[name] = self._create_initial_state(name)
        
        # Screen readers (will be created in process)
        self.readers = {}
        
        # Statistics
        self.stats = self.manager.dict({
            'total_reads': 0,
            'successful_reads': 0,
            'failed_reads': 0,
            'avg_read_time_ms': 0.0,
            'start_time': time.time()
        })
    
    def _create_initial_state(self, bookmaker: str) -> Dict:
        """Create initial state dict for bookmaker"""
        return {
            'bookmaker': bookmaker,
            'score': None,
            'phase': GamePhase.UNKNOWN.value,
            'players_left': None,
            'total_players': None,
            'total_money': None,
            'timestamp': 0.0,
            'last_score': None,
            'same_score_count': 0,
            'round_start_time': None,
            'loading_start_time': None,
            'loading_duration_ms': None
        }
    
    def start(self):
        """Start shared reader process"""
        if self.reader_process and self.reader_process.is_alive():
            self.logger.warning("Reader already running")
            return
        
        self.reader_process = Process(
            target=self._reader_loop,
            name="SharedGameReader",
            daemon=False
        )
        self.reader_process.start()
        self.logger.info(f"Started shared reader for {len(self.bookmaker_configs)} bookmakers")
    
    def stop(self, timeout: float = 5.0):
        """Stop shared reader"""
        if not self.reader_process:
            return
        
        self.logger.info("Stopping shared reader...")
        self.shutdown_event.set()
        
        self.reader_process.join(timeout)
        if self.reader_process.is_alive():
            self.logger.warning("Force terminating reader")
            self.reader_process.terminate()
            self.reader_process.join()
        
        self.logger.info("Shared reader stopped")
    
    def _reader_loop(self):
        """Main reader loop - runs in separate process"""
        # Setup logging for subprocess
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("SharedReader-Process")
        
        # Create screen readers for each bookmaker
        self._setup_readers()
        
        logger.info("Reader loop started")
        last_read_times = {cfg['name']: 0 for cfg in self.bookmaker_configs}
        
        while not self.shutdown_event.is_set():
            try:
                current_time = time.time()
                
                # Read each bookmaker
                for config in self.bookmaker_configs:
                    bookmaker = config['name']
                    state = self.shared_state[bookmaker]
                    
                    # Get appropriate interval based on phase
                    phase = GamePhase(state.get('phase', GamePhase.UNKNOWN.value))
                    interval = self.READ_INTERVALS.get(phase, 0.3)
                    
                    # Check if it's time to read
                    if current_time - last_read_times[bookmaker] >= interval:
                        self._read_bookmaker_state(bookmaker, config['coords'])
                        last_read_times[bookmaker] = current_time
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Reader loop error: {e}", exc_info=True)
                time.sleep(0.1)
        
        logger.info("Reader loop stopped")
        self._cleanup_readers()
    
    def _setup_readers(self):
        """Setup screen readers for each bookmaker"""
        for config in self.bookmaker_configs:
            bookmaker = config['name']
            coords = config['coords']
            
            # Create readers for different regions
            self.readers[bookmaker] = {
                'score_small': ScreenReader(coords.get('score_region_small')),
                'score_medium': ScreenReader(coords.get('score_region_medium')),
                'score_large': ScreenReader(coords.get('score_region_large')),
                'other_count': ScreenReader(coords.get('other_count_region')),
                'other_money': ScreenReader(coords.get('other_money_region')),
            }
    
    def _cleanup_readers(self):
        """Cleanup all screen readers"""
        for bookmaker_readers in self.readers.values():
            for reader in bookmaker_readers.values():
                try:
                    reader.close()
                except:
                    pass
    
    def _read_bookmaker_state(self, bookmaker: str, coords: Dict):
        """
        Read and update state for single bookmaker.
        
        This is where the magic happens - one read, shared by all!
        """
        start_time = time.perf_counter()
        
        try:
            # Get current state
            current_state = dict(self.shared_state[bookmaker])
            
            # Read score (smart selection based on last score)
            score = self._read_score_smart(bookmaker, current_state.get('last_score'))
            
            # Determine phase
            new_phase = self._determine_phase(current_state, score)
            
            # Handle phase transitions
            if new_phase != current_state['phase']:
                self._handle_phase_change(current_state, new_phase, score)
            
            # Update state
            current_state['score'] = score
            current_state['phase'] = new_phase.value
            current_state['timestamp'] = time.time()
            
            # Track same score for ENDED detection
            if score and score == current_state.get('last_score'):
                current_state['same_score_count'] += 1
            else:
                current_state['same_score_count'] = 0
            
            current_state['last_score'] = score
            
            # Read additional data if in ENDED phase
            if new_phase == GamePhase.ENDED:
                self._read_ended_data(bookmaker, current_state)
            
            # Update shared state (atomic operation)
            self.shared_state[bookmaker] = current_state
            
            # Update stats
            read_time_ms = (time.perf_counter() - start_time) * 1000
            self._update_stats(True, read_time_ms)
            
        except Exception as e:
            self.logger.error(f"Error reading {bookmaker}: {e}")
            self._update_stats(False, 0)
    
    def _read_score_smart(self, bookmaker: str, last_score: Optional[float]) -> Optional[float]:
        """Smart score reading - chooses appropriate region"""
        readers = self.readers[bookmaker]
        
        # Determine which reader to use
        if last_score is None or last_score < 10:
            reader = readers['score_small']
        elif last_score < 100:
            reader = readers['score_medium']
        else:
            reader = readers['score_large']
        
        return reader.read_score()
    
    def _determine_phase(self, state: Dict, score: Optional[float]) -> GamePhase:
        """Determine game phase based on score and state"""
        last_phase = GamePhase(state['phase'])
        
        if score is None:
            # No score visible
            if last_phase in [GamePhase.SCORE_LOW, GamePhase.SCORE_MID, GamePhase.SCORE_HIGH]:
                # Lost score during game - probably ended
                return GamePhase.ENDED
            elif state.get('loading_start_time'):
                # In loading
                return GamePhase.LOADING
            else:
                # Betting or unknown
                return GamePhase.BETTING
        
        elif score == 1.00:
            # Game just started
            return GamePhase.START
        
        elif score < 10.0:
            # Low score
            return GamePhase.SCORE_LOW
        
        elif score < 100.0:
            # Mid score
            return GamePhase.SCORE_MID
        
        else:
            # High score
            return GamePhase.SCORE_HIGH
    
    def _handle_phase_change(self, state: Dict, new_phase: GamePhase, score: Optional[float]):
        """Handle phase transitions"""
        old_phase = GamePhase(state['phase'])
        
        # Track loading duration
        if old_phase == GamePhase.LOADING and new_phase == GamePhase.START:
            if state.get('loading_start_time'):
                duration_ms = int((time.time() - state['loading_start_time']) * 1000)
                state['loading_duration_ms'] = duration_ms
                self.logger.info(f"Loading duration: {duration_ms}ms")
        
        elif new_phase == GamePhase.LOADING:
            state['loading_start_time'] = time.time()
        
        # Track round start
        if new_phase in [GamePhase.START, GamePhase.SCORE_LOW]:
            if old_phase in [GamePhase.BETTING, GamePhase.LOADING]:
                state['round_start_time'] = time.time()
    
    def _read_ended_data(self, bookmaker: str, state: Dict):
        """Read additional data when round ends"""
        readers = self.readers[bookmaker]
        
        # Read player count
        count_text = readers['other_count'].read_text()
        if count_text and '/' in count_text:
            parts = count_text.split('/')
            try:
                state['players_left'] = int(parts[0].strip())
                state['total_players'] = int(parts[1].strip())
            except (ValueError, IndexError):
                pass
        
        # Read total money
        money_text = readers['other_money'].read_text()
        if money_text:
            try:
                state['total_money'] = float(money_text.replace(',', '').strip())
            except ValueError:
                pass
    
    def _update_stats(self, success: bool, read_time_ms: float):
        """Update statistics"""
        stats = dict(self.stats)
        stats['total_reads'] += 1
        
        if success:
            stats['successful_reads'] += 1
            # Update average
            if stats['successful_reads'] > 0:
                avg = stats['avg_read_time_ms']
                stats['avg_read_time_ms'] = (
                    (avg * (stats['successful_reads'] - 1) + read_time_ms) 
                    / stats['successful_reads']
                )
        else:
            stats['failed_reads'] += 1
        
        self.stats.update(stats)
    
    def get_state(self, bookmaker: str) -> Optional[Dict]:
        """
        Get current state for bookmaker.
        
        This is what collectors/agents call to get instant data!
        """
        return dict(self.shared_state.get(bookmaker, {}))
    
    def get_all_states(self) -> Dict[str, Dict]:
        """Get states for all bookmakers"""
        return {k: dict(v) for k, v in self.shared_state.items()}
    
    def get_stats(self) -> Dict:
        """Get reader statistics"""
        return dict(self.stats)


# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test configuration
    configs = [
        {
            'name': 'TestBookmaker',
            'coords': {
                'score_region_small': {'left': 100, 'top': 100, 'width': 100, 'height': 30},
                'score_region_medium': {'left': 100, 'top': 100, 'width': 120, 'height': 30},
                'score_region_large': {'left': 100, 'top': 100, 'width': 140, 'height': 30},
                'other_count_region': {'left': 200, 'top': 100, 'width': 100, 'height': 30},
                'other_money_region': {'left': 300, 'top': 100, 'width': 100, 'height': 30},
            }
        }
    ]
    
    # Create and start reader
    reader = SharedGameStateReader(configs)
    reader.start()
    
    # Monitor for 10 seconds
    try:
        for i in range(10):
            time.sleep(1)
            state = reader.get_state('TestBookmaker')
            print(f"State: {state}")
            
            if i % 5 == 0:
                stats = reader.get_stats()
                print(f"Stats: {stats}")
    
    finally:
        reader.stop()
        print("Test complete!")