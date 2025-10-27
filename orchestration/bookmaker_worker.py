# orchestration/bookmaker_worker.py
"""
Bookmaker Worker - Optimizovan worker process za praćenje jedne kladionice.
Koristi sve nove komponente: Fast OCR, Event Bus, Batch Writer.
"""

import multiprocessing as mp
from multiprocessing import Event as MPEvent, Queue
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path

# Import Phase 1 components
from core.capture.screen_capture import ScreenCapture
from core.ocr.tesseract_ocr import TesseractOCR
from core.ocr.template_ocr import TemplateOCR
from core.communication.event_bus import EventPublisher, EventSubscriber, EventType, Event
from core.communication.shared_state import get_shared_state
from data_layer.database.batch_writer import BatchDatabaseWriter, BatchConfig


class GameState(Enum):
    """Stanje igre"""
    UNKNOWN = "unknown"
    WAITING = "waiting"  # Čeka početak runde
    BETTING = "betting"  # Betting window otvoren
    LOADING = "loading"  # Loading između rundi
    PLAYING = "playing"  # Runda u toku
    ENDED = "ended"     # Runda završena


@dataclass
class RoundData:
    """Podaci o trenutnoj rundi"""
    round_id: Optional[int] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    final_score: Optional[float] = None
    total_players: Optional[int] = None
    players_left: Optional[int] = None
    total_money: Optional[float] = None
    thresholds_crossed: List[float] = field(default_factory=list)
    threshold_data: List[Dict] = field(default_factory=list)


@dataclass
class WorkerMetrics:
    """Metrike worker-a"""
    rounds_collected: int = 0
    thresholds_collected: int = 0
    ocr_operations: int = 0
    ocr_failures: int = 0
    total_ocr_time_ms: float = 0
    events_published: int = 0
    db_writes: int = 0
    errors: int = 0
    uptime_seconds: float = 0
    start_time: float = field(default_factory=time.time)


class BookmakerWorker:
    """
    Glavni worker za praćenje jedne kladionice.
    
    Features:
    - Fast OCR (10ms)
    - State machine za game tracking
    - Event publishing
    - Batch database writing
    - Health monitoring
    - Performance metrics
    """
    
    # Pragovi koje pratimo
    THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]
    
    # OCR intervali bazirani na stanju
    OCR_INTERVALS = {
        GameState.WAITING: 1.0,      # Sporo kada čeka
        GameState.BETTING: 0.5,      # Srednje tokom betting-a
        GameState.LOADING: 0.5,      # Srednje tokom loading-a
        GameState.PLAYING: 0.15,     # Brzo tokom igre
        GameState.ENDED: 2.0,        # Sporo posle kraja
    }
    
    def __init__(self,
                 bookmaker_name: str,
                 coords: Dict[str, Dict],
                 db_path: str,
                 shutdown_event: MPEvent,
                 health_queue: Queue):
        """
        Initialize worker.
        
        Args:
            bookmaker_name: Ime kladionice (e.g., "Admiral")
            coords: Koordinate svih regiona
            db_path: Putanja do baze
            shutdown_event: Event za shutdown
            health_queue: Queue za health signale
        """
        self.bookmaker_name = bookmaker_name
        self.coords = coords
        self.db_path = Path(db_path)
        self.shutdown_event = shutdown_event
        self.health_queue = health_queue
        
        # State
        self.current_state = GameState.UNKNOWN
        self.previous_state = GameState.UNKNOWN
        self.current_round = RoundData()
        
        # Components
        self.screen_capture = None
        self.tesseract_ocr = None
        self.template_ocr = None
        self.shared_state = None
        self.event_publisher = None
        self.event_subscriber = None
        self.db_writer = None
        
        # Tracking
        self.last_score = None
        self.same_score_count = 0
        self.metrics = WorkerMetrics()
        
        # Logging
        self.logger = logging.getLogger(f"Worker-{bookmaker_name}")
    
    def setup(self):
        """Setup komponenti"""
        self.logger.info(f"Setting up worker for {self.bookmaker_name}")

        # Screen Capture
        self.screen_capture = ScreenCapture()

        # OCR Components - Use Template OCR primarily, Tesseract as fallback
        self.template_ocr = TemplateOCR()
        self.tesseract_ocr = TesseractOCR()

        # Shared State
        self.shared_state = get_shared_state()

        # Event Bus
        self.event_publisher = EventPublisher(f"Worker-{self.bookmaker_name}")
        self.event_subscriber = EventSubscriber(f"Worker-{self.bookmaker_name}")

        # Subscribe to control events
        self.event_subscriber.subscribe(EventType.PAUSE, self.on_pause_event)
        self.event_subscriber.subscribe(EventType.CONFIG_UPDATE, self.on_config_update)

        # Database Writer
        db_config = BatchConfig(
            batch_size=50,
            flush_interval=2.0
        )
        self.db_writer = BatchDatabaseWriter(self.db_path, db_config)
        self.db_writer.start()

        self.logger.info("Worker setup complete")
    
    def run(self):
        """Main worker loop"""
        self.logger.info(f"Worker started for {self.bookmaker_name}")
        
        # Setup
        self.setup()
        
        # Announce start
        self.event_publisher.publish(EventType.PROCESS_START, {
            'bookmaker': self.bookmaker_name,
            'pid': mp.current_process().pid
        })
        
        try:
            while not self.shutdown_event.is_set():
                loop_start = time.time()
                
                # Main processing
                self.process_cycle()
                
                # Send health signal
                self.send_health_signal()
                
                # Update metrics
                self.metrics.uptime_seconds = time.time() - self.metrics.start_time
                
                # Adaptive sleep based on state
                interval = self.OCR_INTERVALS.get(self.current_state, 0.5)
                elapsed = time.time() - loop_start
                sleep_time = max(0, interval - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            self.logger.error(f"Worker crashed: {e}", exc_info=True)
            self.metrics.errors += 1
            
            # Announce error
            self.event_publisher.publish(EventType.PROCESS_ERROR, {
                'bookmaker': self.bookmaker_name,
                'error': str(e)
            }, priority=1)
            
        finally:
            self.cleanup()
    
    def process_cycle(self):
        """Jedan ciklus procesiranja"""
        try:
            # Read score
            score = self.read_score()
            
            # Determine state
            new_state = self.determine_state(score)
            
            # Handle state change
            if new_state != self.current_state:
                self.handle_state_change(new_state)
            
            # Process based on current state
            if self.current_state == GameState.PLAYING:
                self.process_playing_state(score)
            elif self.current_state == GameState.ENDED:
                self.process_ended_state()
            elif self.current_state == GameState.BETTING:
                self.process_betting_state()
                
        except Exception as e:
            self.logger.error(f"Process cycle error: {e}")
            self.metrics.errors += 1
    
    def read_score(self) -> Optional[float]:
        """
        Čitaj score koristeći Template/Tesseract OCR.

        Returns:
            Score ili None
        """
        start_time = time.time()

        # Determine which region to use
        if self.last_score is None or self.last_score < 10:
            region_name = "score_region_small"
        elif self.last_score < 100:
            region_name = "score_region_medium"
        else:
            region_name = "score_region_large"

        region = self.coords.get(region_name)
        if not region:
            return None

        # Capture region
        image = self.screen_capture.capture_region(region)
        if image is None:
            self.metrics.ocr_failures += 1
            return None

        # Try Template OCR first (faster)
        score_str = self.template_ocr.read_digits(image, category="score", allow_decimal=True)

        # Fallback to Tesseract if template fails
        if score_str is None:
            score = self.tesseract_ocr.read_score(image)
        else:
            try:
                score = float(score_str)
            except (ValueError, TypeError):
                score = None

        # Update metrics
        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.ocr_operations += 1
        self.metrics.total_ocr_time_ms += elapsed_ms

        if score is None:
            self.metrics.ocr_failures += 1
            return None

        # Log if slow
        if elapsed_ms > 50:
            self.logger.warning(
                f"Slow OCR: {elapsed_ms:.1f}ms for {region_name}"
            )

        return score
    
    def determine_state(self, score: Optional[float]) -> GameState:
        """
        Odredi trenutno stanje igre.
        
        Args:
            score: Trenutni score ili None
            
        Returns:
            GameState
        """
        if score is None:
            # No score visible
            if self.current_state == GameState.PLAYING:
                # Lost score during play - probably ended
                return GameState.ENDED
            else:
                # Could be betting or waiting
                return GameState.WAITING
        
        elif score == self.last_score and self.last_score is not None:
            # Same score multiple times
            self.same_score_count += 1
            
            if self.same_score_count >= 3:
                # Score frozen - game ended
                return GameState.ENDED
            else:
                return self.current_state
        
        else:
            # Score changing - game is playing
            self.same_score_count = 0
            return GameState.PLAYING
    
    def handle_state_change(self, new_state: GameState):
        """Handle promenu stanja"""
        old_state = self.current_state
        self.current_state = new_state
        self.previous_state = old_state
        
        self.logger.info(f"State change: {old_state.value} → {new_state.value}")
        
        # Publish event
        self.event_publisher.publish(EventType.PHASE_CHANGE, {
            'bookmaker': self.bookmaker_name,
            'old_state': old_state.value,
            'new_state': new_state.value
        })
        
        # Handle specific transitions
        if new_state == GameState.PLAYING and old_state != GameState.PLAYING:
            # Round started
            self.handle_round_start()
        
        elif new_state == GameState.ENDED and old_state == GameState.PLAYING:
            # Round ended
            self.handle_round_end()
    
    def handle_round_start(self):
        """Handle početak runde"""
        self.logger.info(f"🎬 Round started for {self.bookmaker_name}")
        
        # Reset round data
        self.current_round = RoundData()
        self.current_round.start_time = time.time()
        
        # Reset tracking
        self.same_score_count = 0
        
        # Publish event
        self.event_publisher.publish(EventType.ROUND_START, {
            'bookmaker': self.bookmaker_name,
            'timestamp': datetime.now().isoformat()
        })
        
        self.metrics.rounds_collected += 1
    
    def handle_round_end(self):
        """Handle kraj runde"""
        self.logger.info(
            f"🔴 Round ended for {self.bookmaker_name}: {self.last_score:.2f}x"
        )
        
        # Update round data
        self.current_round.end_time = time.time()
        self.current_round.final_score = self.last_score
        
        # Read additional data
        self.read_ended_data()
        
        # Save to database
        self.save_round()
        
        # Publish event
        self.event_publisher.publish(EventType.ROUND_END, {
            'bookmaker': self.bookmaker_name,
            'final_score': self.last_score,
            'total_players': self.current_round.total_players,
            'players_left': self.current_round.players_left,
            'total_money': self.current_round.total_money,
            'thresholds_collected': len(self.current_round.thresholds_crossed)
        })
    
    def process_playing_state(self, score: Optional[float]):
        """Procesiranje tokom igre"""
        if score is None:
            return
        
        # Check for threshold crossing
        if self.last_score and score > self.last_score:
            threshold = self.check_threshold_crossed(self.last_score, score)
            
            if threshold:
                self.handle_threshold_crossed(score, threshold)
        
        # Update score
        if score != self.last_score:
            self.last_score = score
            
            # Publish score update (lower priority)
            self.event_publisher.publish(EventType.SCORE_UPDATE, {
                'bookmaker': self.bookmaker_name,
                'score': score
            }, priority=7)
    
    def process_ended_state(self):
        """Procesiranje nakon kraja"""
        # Wait a bit then check for new round
        time.sleep(2.0)
        
        # Check if new round started
        score = self.read_score()
        if score and score != self.last_score:
            # New round detected
            self.current_state = GameState.PLAYING
            self.handle_round_start()
            self.last_score = score
    
    def process_betting_state(self):
        """Procesiranje tokom betting window-a"""
        # Could place bets here if betting agent is active
        pass
    
    def check_threshold_crossed(self, prev: float, current: float) -> Optional[float]:
        """
        Proveri da li je pređen threshold.
        
        Returns:
            Threshold vrednost ili None
        """
        for threshold in self.THRESHOLDS:
            if threshold in self.current_round.thresholds_crossed:
                continue
            
            if prev < threshold <= current:
                return threshold
        
        return None
    
    def handle_threshold_crossed(self, score: float, threshold: float):
        """Handle prelazak threshold-a"""
        self.logger.info(
            f"✓ Threshold {threshold}x crossed at {score:.2f}x"
        )
        
        # Mark as crossed
        self.current_round.thresholds_crossed.append(threshold)
        
        # Read additional data
        players_left = self.read_players_left()
        total_money = self.read_total_money()
        
        # Store threshold data
        self.current_round.threshold_data.append({
            'threshold': threshold,
            'actual_score': score,
            'players_left': players_left,
            'total_money': total_money,
            'timestamp': datetime.now().isoformat()
        })
        
        # Publish event
        self.event_publisher.publish(EventType.THRESHOLD_CROSSED, {
            'bookmaker': self.bookmaker_name,
            'threshold': threshold,
            'score': score,
            'players_left': players_left,
            'total_money': total_money
        })
        
        self.metrics.thresholds_collected += 1
    
    def read_ended_data(self):
        """Čitaj podatke sa ENDED ekrana"""
        try:
            # Read total players
            if "other_count_region" in self.coords:
                image = self.screen_capture.capture_region(self.coords["other_count_region"])
                if image is not None:
                    player_count_text = self.tesseract_ocr.read_player_count(image)

                    if player_count_text and '/' in player_count_text:
                        parts = player_count_text.split('/')
                        try:
                            self.current_round.players_left = int(parts[0].strip())
                            self.current_round.total_players = int(parts[1].strip())
                        except (ValueError, IndexError):
                            pass

            # Read total money
            if "other_money_region" in self.coords:
                image = self.screen_capture.capture_region(self.coords["other_money_region"])
                if image is not None:
                    money_value = self.tesseract_ocr.read_money(image)

                    if money_value is not None:
                        self.current_round.total_money = money_value

        except Exception as e:
            self.logger.error(f"Error reading ended data: {e}")
    
    def read_players_left(self) -> Optional[int]:
        """Čitaj broj preostalih igrača"""
        if "other_count_region" not in self.coords:
            return None

        image = self.screen_capture.capture_region(self.coords["other_count_region"])
        if image is None:
            return None

        player_count_text = self.tesseract_ocr.read_player_count(image)

        if player_count_text:
            # Parse "123/456" or just "123"
            value_str = player_count_text.split('/')[0].strip()
            try:
                return int(value_str)
            except ValueError:
                return None

        return None
    
    def read_total_money(self) -> Optional[float]:
        """Čitaj ukupan novac"""
        if "other_money_region" not in self.coords:
            return None

        image = self.screen_capture.capture_region(self.coords["other_money_region"])
        if image is None:
            return None

        money_value = self.tesseract_ocr.read_money(image)
        return money_value
    
    def save_round(self):
        """Sačuvaj rundu u bazu"""
        try:
            # Save main round data
            round_data = {
                'bookmaker': self.bookmaker_name,
                'timestamp': datetime.now().isoformat(),
                'final_score': self.current_round.final_score,
                'total_players': self.current_round.total_players,
                'players_left': self.current_round.players_left,
                'total_money': self.current_round.total_money,
                'duration_seconds': (
                    self.current_round.end_time - self.current_round.start_time
                    if self.current_round.start_time else None
                )
            }
            
            self.db_writer.write('rounds', round_data)
            
            # Save threshold data
            # (would need round_id from database for foreign key)
            for threshold in self.current_round.threshold_data:
                threshold['bookmaker'] = self.bookmaker_name
                self.db_writer.write('threshold_scores', threshold)
            
            self.metrics.db_writes += 1
            
        except Exception as e:
            self.logger.error(f"Error saving round: {e}")
            self.metrics.errors += 1
    
    def send_health_signal(self):
        """Pošalji health signal"""
        try:
            health_data = {
                'bookmaker': self.bookmaker_name,
                'state': self.current_state.value,
                'metrics': {
                    'rounds': self.metrics.rounds_collected,
                    'thresholds': self.metrics.thresholds_collected,
                    'ocr_ops': self.metrics.ocr_operations,
                    'ocr_avg_ms': (
                        self.metrics.total_ocr_time_ms / self.metrics.ocr_operations
                        if self.metrics.ocr_operations > 0 else 0
                    ),
                    'errors': self.metrics.errors,
                    'uptime': self.metrics.uptime_seconds
                },
                'timestamp': time.time()
            }
            
            self.health_queue.put_nowait(health_data)
            
        except:
            # Queue full, skip
            pass
    
    def on_pause_event(self, event: Event):
        """Handle pause event"""
        if event.data.get('bookmaker') in [self.bookmaker_name, 'all']:
            self.logger.info("Pausing worker...")
            # Implementation depends on requirements
    
    def on_config_update(self, event: Event):
        """Handle config update"""
        if event.data.get('bookmaker') in [self.bookmaker_name, 'all']:
            self.logger.info("Updating configuration...")
            # Update thresholds, intervals, etc.
            new_config = event.data.get('config', {})
            
            if 'thresholds' in new_config:
                self.THRESHOLDS = new_config['thresholds']
            
            if 'ocr_intervals' in new_config:
                self.OCR_INTERVALS.update(new_config['ocr_intervals'])
    
    def cleanup(self):
        """Cleanup resursa"""
        self.logger.info("Cleaning up worker...")
        
        # Stop database writer
        if self.db_writer:
            self.db_writer.stop()
        
        # Unsubscribe from events
        if self.event_subscriber:
            self.event_subscriber.unsubscribe_all()
        
        # Announce stop
        if self.event_publisher:
            self.event_publisher.publish(EventType.PROCESS_STOP, {
                'bookmaker': self.bookmaker_name,
                'metrics': self.get_metrics()
            })
        
        self.logger.info("Worker cleanup complete")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Vrati metrike"""
        return {
            'rounds_collected': self.metrics.rounds_collected,
            'thresholds_collected': self.metrics.thresholds_collected,
            'ocr_operations': self.metrics.ocr_operations,
            'ocr_failures': self.metrics.ocr_failures,
            'ocr_avg_ms': (
                self.metrics.total_ocr_time_ms / self.metrics.ocr_operations
                if self.metrics.ocr_operations > 0 else 0
            ),
            'events_published': self.metrics.events_published,
            'db_writes': self.metrics.db_writes,
            'errors': self.metrics.errors,
            'uptime_seconds': self.metrics.uptime_seconds,
            'success_rate': (
                (self.metrics.ocr_operations - self.metrics.ocr_failures) 
                / self.metrics.ocr_operations * 100
                if self.metrics.ocr_operations > 0 else 0
            )
        }


def worker_entry_point(bookmaker_name: str,
                       coords: Dict[str, Dict],
                       db_path: str,
                       shutdown_event: MPEvent,
                       health_queue: Queue,
                       **kwargs):
    """Entry point za worker process"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s | {bookmaker_name:12s} | %(levelname)-8s | %(message)s'
    )
    
    # Create and run worker
    worker = BookmakerWorker(
        bookmaker_name=bookmaker_name,
        coords=coords,
        db_path=db_path,
        shutdown_event=shutdown_event,
        health_queue=health_queue
    )
    
    worker.run()


def test_worker():
    """Test worker functionality"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test coordinates (dummy)
    coords = {
        'score_region_small': {'left': 100, 'top': 100, 'width': 100, 'height': 30},
        'score_region_medium': {'left': 100, 'top': 100, 'width': 120, 'height': 30},
        'score_region_large': {'left': 100, 'top': 100, 'width': 140, 'height': 30},
        'other_count_region': {'left': 200, 'top': 100, 'width': 100, 'height': 30},
        'other_money_region': {'left': 300, 'top': 100, 'width': 100, 'height': 30},
    }
    
    # Create multiprocessing components
    shutdown_event = mp.Event()
    health_queue = mp.Queue()
    
    # Start worker process
    process = mp.Process(
        target=worker_entry_point,
        args=(
            "TestBookmaker",
            coords,
            "data/databases/test.db",
            shutdown_event,
            health_queue
        ),
        name="TestWorker"
    )
    
    process.start()
    print(f"Worker started with PID: {process.pid}")
    
    # Monitor for 30 seconds
    try:
        for i in range(30):
            time.sleep(1)
            
            # Check health signals
            try:
                health = health_queue.get_nowait()
                print(f"\nHealth signal: {health['state']}")
                print(f"  Metrics: {health['metrics']}")
            except:
                pass
                
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    # Shutdown
    shutdown_event.set()
    process.join(timeout=5.0)
    
    if process.is_alive():
        process.terminate()
        process.join()
    
    print("Test complete!")


if __name__ == "__main__":
    test_worker()