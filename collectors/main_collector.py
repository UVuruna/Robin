# collectors/main_collector.py
"""
Main Data Collector V2 - Koristi Shared Reader za OCR.
Fokusira se samo na logiku praćenja, ne na OCR.
"""

import time
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from config import GamePhase
from core.communication.event_bus import EventPublisher


class MainDataCollectorV2:
    """
    Main data collector koji koristi shared reader.
    
    Prednosti:
    - Ne radi OCR (shared reader to radi)
    - Instant pristup podacima
    - Fokus na business logiku
    """
    
    # Pragovi koje pratimo
    THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]
    THRESHOLD_TOLERANCE = 0.08  # ±0.08x tolerancija
    
    def __init__(self,
                 bookmaker: str,
                 shared_reader,
                 db_writer,
                 event_publisher: Optional[EventPublisher] = None):
        """
        Initialize collector.
        
        Args:
            bookmaker: Ime kladionice
            shared_reader: SharedGameStateReader instanca
            db_writer: BatchDatabaseWriter instanca
            event_publisher: EventPublisher za slanje eventova
        """
        self.bookmaker = bookmaker
        self.shared_reader = shared_reader
        self.db_writer = db_writer
        self.event_publisher = event_publisher or EventPublisher(f"MainCollector-{bookmaker}")
        
        # Round tracking
        self.current_round_id = None
        self.round_start_time = None
        self.thresholds_crossed = set()
        self.threshold_data = []
        
        # State tracking
        self.last_phase = GamePhase.UNKNOWN
        self.last_score = None
        
        # Statistics
        self.rounds_collected = 0
        self.thresholds_collected = 0
        
        self.logger = logging.getLogger(f"MainCollector-{bookmaker}")
    
    def collect_cycle(self):
        """
        Jedan ciklus prikupljanja podataka.
        Poziva se u loop-u iz worker procesa.
        """
        # Get current state from shared reader (INSTANT - 0ms!)
        state = self.shared_reader.get_state(self.bookmaker)
        
        if not state:
            return
        
        current_phase = GamePhase(state.get('phase', GamePhase.UNKNOWN.value))
        current_score = state.get('score')
        
        # Handle phase changes
        if current_phase != self.last_phase:
            self._handle_phase_change(self.last_phase, current_phase, state)
        
        # Track during active game
        if current_phase in [GamePhase.SCORE_LOW, GamePhase.SCORE_MID, GamePhase.SCORE_HIGH]:
            self._track_active_game(current_score, state)
        
        # Update tracking
        self.last_phase = current_phase
        self.last_score = current_score
    
    def _handle_phase_change(self, old_phase: GamePhase, new_phase: GamePhase, state: Dict):
        """Handle phase transitions"""
        self.logger.debug(f"Phase change: {old_phase.name} → {new_phase.name}")
        
        # Round started
        if new_phase in [GamePhase.START, GamePhase.SCORE_LOW]:
            if old_phase in [GamePhase.BETTING, GamePhase.LOADING, GamePhase.UNKNOWN]:
                self._handle_round_start(state)
        
        # Round ended
        elif new_phase == GamePhase.ENDED:
            if old_phase in [GamePhase.SCORE_LOW, GamePhase.SCORE_MID, GamePhase.SCORE_HIGH]:
                self._handle_round_end(state)
    
    def _handle_round_start(self, state: Dict):
        """Handle round start"""
        self.logger.info(f"🎬 Round started for {self.bookmaker}")
        
        # Reset round data
        self.round_start_time = time.time()
        self.thresholds_crossed.clear()
        self.threshold_data.clear()
        
        # Publish event
        self.event_publisher.round_start(self.bookmaker)
    
    def _handle_round_end(self, state: Dict):
        """Handle round end and save to database"""
        final_score = state.get('score') or self.last_score
        
        if not final_score:
            self.logger.warning("Round ended without final score")
            return
        
        self.logger.info(f"🔴 Round ended: {final_score:.2f}x")
        
        # Calculate round duration
        duration = None
        if self.round_start_time:
            duration = time.time() - self.round_start_time
        
        # Save round to database
        round_data = {
            'bookmaker': self.bookmaker,
            'timestamp': datetime.now().isoformat(),
            'final_score': final_score,
            'total_players': state.get('total_players'),
            'players_left': state.get('players_left'),
            'total_money': state.get('total_money'),
            'duration_seconds': duration,
            'loading_duration_ms': state.get('loading_duration_ms')  # NOVO!
        }
        
        # Write to database (batch writer će handle-ovati)
        self.db_writer.write('rounds', round_data)
        
        # Save threshold data
        for threshold in self.threshold_data:
            threshold['bookmaker'] = self.bookmaker
            self.db_writer.write('threshold_scores', threshold)
        
        # Update statistics
        self.rounds_collected += 1
        self.thresholds_collected += len(self.threshold_data)
        
        # Publish event
        self.event_publisher.round_end(self.bookmaker, final_score)
        
        # Log stats periodically
        if self.rounds_collected % 10 == 0:
            self._log_statistics()
    
    def _track_active_game(self, current_score: Optional[float], state: Dict):
        """Track thresholds during active game"""
        if not current_score or not self.last_score:
            return
        
        # Check if score is rising
        if current_score > self.last_score:
            # Check for threshold crossing
            threshold = self._check_threshold_crossed(self.last_score, current_score)
            
            if threshold and threshold not in self.thresholds_crossed:
                self._handle_threshold_crossed(current_score, threshold, state)
    
    def _check_threshold_crossed(self, prev_score: float, current_score: float) -> Optional[float]:
        """Check if threshold was crossed"""
        for threshold in self.THRESHOLDS:
            if threshold in self.thresholds_crossed:
                continue
            
            if prev_score < threshold <= current_score:
                # Check tolerance
                distance = abs(current_score - threshold)
                
                if distance <= self.THRESHOLD_TOLERANCE:
                    self.logger.info(f"✓ Threshold {threshold}x crossed at {current_score:.2f}x")
                else:
                    self.logger.warning(f"⚠ Threshold {threshold}x crossed far at {current_score:.2f}x")
                
                return threshold
        
        return None
    
    def _handle_threshold_crossed(self, score: float, threshold: float, state: Dict):
        """Handle threshold crossing"""
        # Mark as crossed
        self.thresholds_crossed.add(threshold)
        
        # Create threshold record
        threshold_record = {
            'timestamp': datetime.now().isoformat(),
            'threshold': threshold,
            'actual_score': score,
            'players_left': state.get('players_left'),
            'total_money': state.get('total_money')
        }
        
        self.threshold_data.append(threshold_record)
        
        # Publish event
        self.event_publisher.publish(
            EventType.THRESHOLD_CROSSED,
            {
                'bookmaker': self.bookmaker,
                'threshold': threshold,
                'score': score,
                'players_left': state.get('players_left'),
                'total_money': state.get('total_money')
            }
        )
        
        self.logger.debug(f"Threshold {threshold}x data collected")
    
    def _log_statistics(self):
        """Log collection statistics"""
        self.logger.info("=" * 60)
        self.logger.info(f"📊 STATISTICS for {self.bookmaker}")
        self.logger.info(f"Rounds collected: {self.rounds_collected}")
        self.logger.info(f"Thresholds collected: {self.thresholds_collected}")
        
        if self.rounds_collected > 0:
            avg_thresholds = self.thresholds_collected / self.rounds_collected
            self.logger.info(f"Avg thresholds/round: {avg_thresholds:.1f}")
        
        self.logger.info("=" * 60)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            'bookmaker': self.bookmaker,
            'rounds_collected': self.rounds_collected,
            'thresholds_collected': self.thresholds_collected,
            'current_phase': self.last_phase.name if self.last_phase else 'UNKNOWN',
            'last_score': self.last_score
        }


def main_collector_worker(bookmaker: str,
                          coords: Dict,
                          shared_reader,
                          shutdown_event,
                          db_writer,
                          event_bus,
                          **kwargs):
    """
    Worker function za Main Data Collector.
    Pokreće se kao zaseban proces za svaku kladionicu.
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(f"Worker-MainCollector-{bookmaker}")
    
    logger.info(f"Starting Main Collector for {bookmaker}")
    
    # Create event publisher
    event_publisher = EventPublisher(f"MainCollector-{bookmaker}")
    
    # Create collector
    collector = MainDataCollectorV2(
        bookmaker=bookmaker,
        shared_reader=shared_reader,
        db_writer=db_writer,
        event_publisher=event_publisher
    )
    
    # Main loop
    loop_count = 0
    try:
        while not shutdown_event.is_set():
            # Collect data
            collector.collect_cycle()
            
            # Small sleep (shared reader does the heavy OCR work)
            time.sleep(0.1)
            
            loop_count += 1
            
            # Log alive status periodically
            if loop_count % 600 == 0:  # Every ~60 seconds
                stats = collector.get_stats()
                logger.info(f"Alive - Stats: {stats}")
    
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
    finally:
        # Final statistics
        stats = collector.get_stats()
        logger.info(f"Stopping - Final stats: {stats}")
        
        # Publish stop event
        event_publisher.publish(
            EventType.PROCESS_STOP,
            {
                'bookmaker': bookmaker,
                'stats': stats
            }
        )


# Test function
if __name__ == "__main__":
    import multiprocessing as mp
    from orchestration.shared_reader import SharedGameStateReader
    from data_layer.database.batch_writer import BatchDatabaseWriter, BatchConfig
    
    # Test configuration
    test_bookmaker = "TestBookmaker"
    test_coords = {
        'score_region_small': {'left': 100, 'top': 100, 'width': 100, 'height': 30},
        # ... other regions
    }
    
    # Create shared components
    shared_reader = SharedGameStateReader([{
        'name': test_bookmaker,
        'coords': test_coords
    }])
    
    db_writer = BatchDatabaseWriter(
        "data/databases/test.db",
        BatchConfig(batch_size=10, flush_interval=5.0)
    )
    
    shutdown = mp.Event()
    
    # Start shared reader
    shared_reader.start()
    db_writer.start()
    
    try:
        # Run worker for 30 seconds
        print("Testing Main Collector for 30 seconds...")
        
        worker_thread = mp.Process(
            target=main_collector_worker,
            args=(test_bookmaker, test_coords, shared_reader, shutdown, db_writer, None)
        )
        worker_thread.start()
        
        time.sleep(30)
        
    finally:
        shutdown.set()
        worker_thread.join()
        shared_reader.stop()
        db_writer.stop()
        
        print("Test complete!")