# orchestration/shared_reader.py
# VERSION: 1.0 - COMPLETE
# PURPOSE: Shared OCR reader - čita jednom, deli svima

import multiprocessing as mp
from multiprocessing import shared_memory
import time
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from core.capture.screen_capture import ScreenCapture
from core.ocr.engine import OCREngine
from config import GamePhase

@dataclass
class GameState:
    """Shared game state for a bookmaker."""
    score: float = 0.0
    phase: int = GamePhase.ENDED
    my_money: float = 0.0
    other_money: float = 0.0
    total_players: int = 0
    left_players: int = 0
    loading_duration_ms: int = 0  # Trajanje loading faze
    timestamp: float = 0.0
    is_valid: bool = False
    error_count: int = 0

class SharedGameStateReader:
    """
    Deljeni reader koji čita game state jednom i deli svima preko shared memory.
    Ovo drastično smanjuje CPU usage jer samo jedan proces čita OCR.
    """
    
    def __init__(self, bookmakers: List[str], regions_config: Dict):
        self.bookmakers = bookmakers
        self.regions_config = regions_config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Screen capture & OCR
        self.screen_capture = ScreenCapture()
        self.ocr_engine = OCREngine()
        
        # Shared memory
        self.shared_states: Dict[str, dict] = {}
        self.shared_memories: Dict[str, shared_memory.SharedMemory] = {}
        self.locks: Dict[str, mp.Lock] = {}
        
        # Control
        self.stop_event = mp.Event()
        self.process: Optional[mp.Process] = None
        
        # Loading phase tracking
        self.loading_start_times: Dict[str, float] = {}
        self.previous_phases: Dict[str, int] = {}
        
        # Metrics
        self.read_times: List[float] = []
        self.error_counts: Dict[str, int] = {bm: 0 for bm in bookmakers}
        
        self._setup_shared_memory()
    
    def _setup_shared_memory(self):
        """Setup shared memory for each bookmaker."""
        for bookmaker in self.bookmakers:
            # Create 2KB shared memory per bookmaker
            shm = shared_memory.SharedMemory(create=True, size=2048)
            self.shared_memories[bookmaker] = shm
            self.locks[bookmaker] = mp.Lock()
            
            # Initialize
            self._write_state(bookmaker, GameState())
            self.previous_phases[bookmaker] = GamePhase.ENDED
            
            self.logger.info(f"Shared memory created for {bookmaker}: {shm.name}")
    
    def _write_state(self, bookmaker: str, state: GameState):
        """Write state to shared memory - thread-safe."""
        try:
            with self.locks[bookmaker]:
                state_dict = asdict(state)
                state_bytes = json.dumps(state_dict).encode('utf-8')
                
                # Write with null terminator
                shm = self.shared_memories[bookmaker]
                shm.buf[:len(state_bytes)] = state_bytes
                shm.buf[len(state_bytes):len(state_bytes)+1] = b'\0'
                
        except Exception as e:
            self.logger.error(f"Error writing state for {bookmaker}: {e}")
    
    def get_state(self, bookmaker: str) -> Optional[GameState]:
        """
        Get current state for bookmaker.
        Ovu metodu zovu drugi procesi (collectors, agents).
        """
        try:
            with self.locks[bookmaker]:
                shm = self.shared_memories[bookmaker]
                
                # Find null terminator
                null_idx = shm.buf.tobytes().find(b'\0')
                if null_idx == -1:
                    return None
                
                # Parse JSON
                state_bytes = bytes(shm.buf[:null_idx])
                state_dict = json.loads(state_bytes.decode('utf-8'))
                
                return GameState(**state_dict)
                
        except Exception as e:
            self.logger.error(f"Error reading state for {bookmaker}: {e}")
            return None
    
    def _read_bookmaker_state(self, bookmaker: str) -> GameState:
        """Read all regions for one bookmaker."""
        state = GameState()
        state.timestamp = time.time()
        
        try:
            regions = self.regions_config.get(bookmaker, {})
            
            # Read score
            if 'score' in regions:
                score_img = self.screen_capture.capture_region(regions['score'])
                if score_img is not None:
                    score_text = self.ocr_engine.read_score(score_img)
                    if score_text:
                        # Clean score (remove 'x' suffix)
                        clean = score_text.replace('x', '').replace('X', '').strip()
                        try:
                            state.score = float(clean)
                        except:
                            pass
            
            # Read game phase
            if 'phase' in regions:
                phase_img = self.screen_capture.capture_region(regions['phase'])
                if phase_img is not None:
                    state.phase = self.ocr_engine.detect_phase(phase_img)
                    
                    # Track loading duration
                    prev_phase = self.previous_phases.get(bookmaker, GamePhase.ENDED)
                    
                    # Start tracking when entering LOADING
                    if state.phase == GamePhase.LOADING and prev_phase != GamePhase.LOADING:
                        self.loading_start_times[bookmaker] = time.time()
                    
                    # Calculate duration when exiting LOADING
                    elif prev_phase == GamePhase.LOADING and state.phase != GamePhase.LOADING:
                        if bookmaker in self.loading_start_times:
                            duration = (time.time() - self.loading_start_times[bookmaker]) * 1000
                            state.loading_duration_ms = int(duration)
                            del self.loading_start_times[bookmaker]
                    
                    self.previous_phases[bookmaker] = state.phase
            
            # Read money values
            if 'my_money' in regions:
                money_img = self.screen_capture.capture_region(regions['my_money'])
                if money_img is not None:
                    money_text = self.ocr_engine.read_money(money_img)
                    if money_text:
                        # Parse money format (1,234.56)
                        try:
                            clean = money_text.replace(',', '')
                            state.my_money = float(clean)
                        except:
                            pass
            
            if 'other_money' in regions:
                money_img = self.screen_capture.capture_region(regions['other_money'])
                if money_img is not None:
                    money_text = self.ocr_engine.read_money(money_img)
                    if money_text:
                        try:
                            clean = money_text.replace(',', '')
                            state.other_money = float(clean)
                        except:
                            pass
            
            # Read player count
            if 'other_count' in regions:
                count_img = self.screen_capture.capture_region(regions['other_count'])
                if count_img is not None:
                    count_text = self.ocr_engine.read_player_count(count_img)
                    if count_text and '/' in count_text:
                        parts = count_text.split('/')
                        if len(parts) == 2:
                            try:
                                state.left_players = int(parts[0].strip())
                                state.total_players = int(parts[1].strip())
                            except:
                                pass
            
            state.is_valid = True
            state.error_count = 0
            
        except Exception as e:
            self.logger.error(f"Error reading {bookmaker}: {e}")
            state.is_valid = False
            state.error_count = self.error_counts.get(bookmaker, 0) + 1
            self.error_counts[bookmaker] = state.error_count
        
        return state
    
    def _reader_loop(self):
        """Main reader loop - runs in separate process."""
        self.logger.info("Shared reader started")
        
        while not self.stop_event.is_set():
            start_time = time.time()
            
            # Read all bookmakers
            for bookmaker in self.bookmakers:
                if self.stop_event.is_set():
                    break
                    
                state = self._read_bookmaker_state(bookmaker)
                self._write_state(bookmaker, state)
            
            # Track performance
            read_time = time.time() - start_time
            self.read_times.append(read_time)
            
            # Keep last 100 measurements
            if len(self.read_times) > 100:
                self.read_times.pop(0)
            
            # Sleep to maintain ~10 reads/second
            sleep_time = max(0, 0.1 - read_time)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.logger.info("Shared reader stopped")
    
    def start(self):
        """Start the reader process."""
        if self.process is None or not self.process.is_alive():
            self.stop_event.clear()
            self.process = mp.Process(target=self._reader_loop, name="SharedReader")
            self.process.start()
            self.logger.info("SharedReader process started")
    
    def stop(self, timeout: float = 5.0):
        """Stop the reader process."""
        if self.process and self.process.is_alive():
            self.stop_event.set()
            self.process.join(timeout)
            
            if self.process.is_alive():
                self.logger.warning("Force terminating SharedReader")
                self.process.terminate()
                self.process.join()
            
            self.process = None
            self.logger.info("SharedReader process stopped")
    
    def cleanup(self):
        """Cleanup shared memory."""
        self.stop()
        
        for bookmaker, shm in self.shared_memories.items():
            try:
                shm.close()
                shm.unlink()
                self.logger.info(f"Cleaned up shared memory for {bookmaker}")
            except:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reader statistics."""
        avg_read_time = sum(self.read_times) / len(self.read_times) if self.read_times else 0
        
        return {
            'is_running': self.process.is_alive() if self.process else False,
            'bookmakers_count': len(self.bookmakers),
            'avg_read_time_ms': avg_read_time * 1000,
            'reads_per_second': 1.0 / avg_read_time if avg_read_time > 0 else 0,
            'error_counts': self.error_counts,
            'total_errors': sum(self.error_counts.values())
        }
    
    def __del__(self):
        """Cleanup on destruction."""
        self.cleanup()


# Singleton instance
_shared_reader_instance = None

def get_shared_reader() -> SharedGameStateReader:
    """Get singleton shared reader instance."""
    global _shared_reader_instance
    if _shared_reader_instance is None:
        raise RuntimeError("Shared reader not initialized. Call init_shared_reader first.")
    return _shared_reader_instance

def init_shared_reader(bookmakers: List[str], regions_config: Dict) -> SharedGameStateReader:
    """Initialize shared reader singleton."""
    global _shared_reader_instance
    if _shared_reader_instance is None:
        _shared_reader_instance = SharedGameStateReader(bookmakers, regions_config)
    return _shared_reader_instance