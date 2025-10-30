# orchestration/bookmaker_worker.py
"""
Bookmaker Worker - v3.0 Architecture Compliant
===============================================

Worker Process za praćenje jedne kladionice.

**v3.0 ARCHITECTURE:**
1. WORKER PROCESS PATTERN - 1 Bookmaker = 1 Process = 1 CPU Core (PARALLELISM!)
2. LOCAL STATE - Worker ima local_state dict (fast in-process access)
3. CLOSURE PATTERN - Agents pristupaju local_state preko closure funkcija
4. SHARED BATCH WRITER - ONE per collector/agent TYPE (shared across workers)
5. AGENTS AS THREADS - BettingAgent i SessionKeeper run as threads
6. PARALLEL OCR - Each Worker has own OCR (Template + Tesseract)

**FLOW:**
Worker Process
 ├─ OCR Components (Template + Tesseract) - PARALLEL!
 ├─ local_state (fast dict) - PRIMARY data source
 ├─ round_history (list of 100 rounds) - For StrategyExecutor
 ├─ MainCollector (thread) → reads local_state via closure
 ├─ RGBCollector (thread) → reads local_state via closure
 ├─ BettingAgent (thread) → reads local_state + history via closure
 └─ SessionKeeper (thread) → reads local_state via closure

Version: 3.0
"""

import multiprocessing as mp
from multiprocessing import Queue
from multiprocessing.synchronize import Event as MPEvent
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path

# Core components
from core.capture.screen_capture import ScreenCapture
from core.ocr.engine import OCREngine
from config.settings import OCR
from core.communication.event_bus import EventPublisher, EventSubscriber, EventType, Event
from core.communication.shared_state import get_shared_state, BookmakerState, GamePhase
from data.database.batch_writer import BatchDatabaseWriter, BatchConfig


class GameState(Enum):
    """Internal game state tracking"""
    UNKNOWN = "unknown"
    WAITING = "waiting"
    BETTING = "betting"
    LOADING = "loading"
    PLAYING = "playing"
    ENDED = "ended"


@dataclass
class RoundRecord:
    """Single round record for history"""
    round_id: int
    bookmaker: str
    timestamp: str
    final_score: float
    duration_seconds: Optional[float] = None
    total_players: Optional[int] = None
    players_left: Optional[int] = None
    total_money: Optional[float] = None
    thresholds_crossed: List[float] = field(default_factory=list)


@dataclass
class WorkerMetrics:
    """Worker metrics tracking"""
    rounds_collected: int = 0
    ocr_operations: int = 0
    ocr_failures: int = 0
    total_ocr_time_ms: float = 0
    errors: int = 0
    uptime_seconds: float = 0
    start_time: float = field(default_factory=time.time)


class BookmakerWorker:
    """
    Worker Process - v3.0 Architecture.

    **KEY FEATURES:**
    - Parallel OCR (each worker has own OCR components)
    - local_state dict for fast in-process access
    - round_history list (100 recent rounds for StrategyExecutor)
    - Closure pattern for agents
    - Shared BatchWriter per TYPE
    - Agents run as threads
    """

    # Thresholds to track
    THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]

    # OCR intervals based on state
    OCR_INTERVALS = {
        GameState.WAITING: 1.0,
        GameState.BETTING: 0.5,
        GameState.LOADING: 0.5,
        GameState.PLAYING: 0.15,  # FAST during game!
        GameState.ENDED: 2.0,
    }

    def __init__(self,
                 bookmaker_name: str,
                 bookmaker_index: int,
                 coords: Dict[str, Dict],
                 db_writers: Dict[str, BatchDatabaseWriter],
                 shutdown_event: MPEvent,
                 health_queue: Queue,
                 image_saving_config: Optional[Dict[str, bool]] = None):
        """
        Initialize Worker.

        Args:
            bookmaker_name: Bookmaker name (e.g., "Admiral")
            bookmaker_index: Index for offset calculation (0-5)
            coords: Region coordinates dict
            db_writers: Shared BatchWriter instances per TYPE
                       {'main': main_writer, 'betting': betting_writer, 'rgb': rgb_writer}
            shutdown_event: Multiprocessing Event for shutdown
            health_queue: Queue for health signals
            image_saving_config: Dict with regions to save for CNN training
                                 {'score': True, 'my_money': False, 'player_count': True}
        """
        self.bookmaker_name = bookmaker_name
        self.bookmaker_index = bookmaker_index
        self.coords = coords
        self.db_writers = db_writers  # SHARED writers per TYPE!
        self.shutdown_event = shutdown_event
        self.health_queue = health_queue
        self.image_saving_config = image_saving_config or {'score': True}  # Default: only score

        # ===== LOCAL STATE (FAST!) =====
        self.local_state: Dict[str, Any] = {
            'bookmaker': bookmaker_name,
            'phase': GamePhase.UNKNOWN,
            'score': None,
            'previous_score': None,
            'round_start_time': None,
            'round_end_time': None,
            'loading_start_time': None,
            'loading_duration': None,
            'player_count_current': None,
            'player_count_total': None,
            'money_total': None,
            'my_money': None,
            'last_update_time': time.time(),
            'read_count': 0,
            'error_count': 0
        }

        # ===== ROUND HISTORY (for StrategyExecutor) =====
        self.round_history: List[Dict] = []  # Last 100 rounds
        self.round_counter = 0

        # ===== INTERNAL STATE =====
        self.current_state = GameState.UNKNOWN
        self.previous_state = GameState.UNKNOWN
        self.last_score = None
        self.same_score_count = 0

        # Current round tracking
        self.current_round = {
            'round_id': None,
            'start_time': None,
            'end_time': None,
            'final_score': None,
            'thresholds_crossed': []
        }

        # ===== COMPONENTS (created in setup) =====
        self.screen_capture = None
        self.ocr_engine = None  # Unified OCR Engine (Template/Tesseract/CNN)
        self.shared_game_state = None  # For GUI monitoring only
        self.event_publisher = None
        self.event_subscriber = None

        # ===== COLLECTORS & AGENTS (threads) =====
        self.collectors = []
        self.agents = []
        self.threads = []

        # ===== METRICS =====
        self.metrics = WorkerMetrics()

        # ===== LOGGING =====
        self.logger = logging.getLogger(f"Worker-{bookmaker_name}")

    def setup(self):
        """Setup all components"""
        self.logger.info(f"Setting up Worker for {self.bookmaker_name}")

        # Screen Capture
        self.screen_capture = ScreenCapture()

        # OCR Engine - PARALLEL (each worker has own!)
        # Method selected from config.settings.OCR.method
        self.ocr_engine = OCREngine(method=OCR.method)
        self.logger.info(f"OCR Engine initialized (method: {OCR.method.name}, parallel mode)")

        # Shared State (for GUI monitoring only)
        self.shared_game_state = get_shared_state()

        # Event Bus
        self.event_publisher = EventPublisher(f"Worker-{self.bookmaker_name}")
        self.event_subscriber = EventSubscriber(f"Worker-{self.bookmaker_name}")

        # Subscribe to control events
        self.event_subscriber.subscribe(EventType.PAUSE, self.on_pause_event)
        self.event_subscriber.subscribe(EventType.CONFIG_UPDATE, self.on_config_update)

        # ===== CREATE CLOSURE FUNCTIONS FOR AGENTS =====
        def get_state_fn() -> Dict:
            """Closure: Returns current local_state"""
            return self.local_state.copy()

        def get_history_fn() -> List[Dict]:
            """Closure: Returns round_history"""
            return self.round_history.copy()

        self.get_state = get_state_fn
        self.get_history = get_history_fn

        self.logger.info("Closure functions created for agents")

        # ===== INITIALIZE COLLECTORS & AGENTS =====
        self.init_collectors()
        self.init_agents()

        self.logger.info("Worker setup complete")

    def init_collectors(self):
        """Initialize collectors (as threads)"""
        from collectors.main_collector import MainDataCollector
        from collectors.rgb_collector import RGBCollector
        from collectors.phase_collector import PhaseCollector

        # Main Data Collector
        main_collector = MainDataCollector(
            bookmaker=self.bookmaker_name,
            shared_state=self.shared_game_state,
            db_writer=self.db_writers['main'],
            event_publisher=self.event_publisher,
            image_saving_config=self.image_saving_config
        )
        self.collectors.append(main_collector)

        # RGB Collector
        rgb_collector = RGBCollector(
            bookmaker=self.bookmaker_name,
            shared_state=self.shared_game_state,
            db_writer=self.db_writers['rgb'],
            event_publisher=self.event_publisher,
            screen_capture=self.screen_capture,
            coords=self.coords
        )
        self.collectors.append(rgb_collector)

        # Phase Collector
        phase_collector = PhaseCollector(
            bookmaker=self.bookmaker_name,
            shared_state=self.shared_game_state,
            db_writer=self.db_writers['main'],
            event_publisher=self.event_publisher
        )
        self.collectors.append(phase_collector)

        # NOTE: Collectors are NOT threaded! They're called via run_cycle() from main loop.
        self.logger.info(f"Initialized {len(self.collectors)} collectors")

    def init_agents(self):
        """Initialize agents (as threads)"""
        from agents.betting_agent import BettingAgent
        from agents.session_keeper import SessionKeeper
        import threading

        # Betting Agent
        betting_agent = BettingAgent(
            bookmaker=self.bookmaker_name,
            bookmaker_index=self.bookmaker_index,
            get_state_fn=self.get_state,
            get_history_fn=self.get_history,
            db_writer=self.db_writers['betting'],
            coords=self.coords,
            event_publisher=self.event_publisher
        )
        self.agents.append(betting_agent)

        # Session Keeper
        session_keeper = SessionKeeper(
            bookmaker=self.bookmaker_name,
            bookmaker_index=self.bookmaker_index,
            get_state_fn=self.get_state,
            coords=self.coords,
            event_publisher=self.event_publisher
        )
        self.agents.append(session_keeper)

        # Start agent threads
        for agent in self.agents:
            thread = threading.Thread(
                target=agent.run,
                daemon=True,
                name=f"{self.bookmaker_name}-{agent.__class__.__name__}"
            )
            thread.start()
            self.threads.append(thread)
            self.logger.info(f"Started agent: {agent.__class__.__name__}")

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

        # Graceful shutdown state
        graceful_shutdown = False

        try:
            while not self.shutdown_event.is_set() or graceful_shutdown:
                loop_start = time.time()

                # ===== CHECK GRACEFUL SHUTDOWN =====
                if self.shutdown_event.is_set() and not graceful_shutdown:
                    # Shutdown requested - check if we need to wait for round end
                    if self.current_state == GameState.PLAYING:
                        self.logger.info("Graceful shutdown: Waiting for round to end...")
                        graceful_shutdown = True
                    else:
                        # Not in active round, exit immediately
                        break

                # ===== EXIT IF GRACEFUL SHUTDOWN COMPLETE =====
                if graceful_shutdown and self.current_state == GameState.ENDED:
                    self.logger.info("Graceful shutdown: Round ended, exiting...")
                    break

                # ===== MAIN OCR CYCLE =====
                self.ocr_cycle()

                # ===== RUN COLLECTORS =====
                for collector in self.collectors:
                    collector.run_cycle()

                # ===== UPDATE SHARED STATE (for GUI) =====
                self.update_shared_state()

                # ===== SEND HEALTH SIGNAL =====
                self.send_health_signal()

                # ===== UPDATE METRICS =====
                self.metrics.uptime_seconds = time.time() - self.metrics.start_time

                # ===== ADAPTIVE SLEEP =====
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

    def ocr_cycle(self):
        """
        OCR Cycle - Read game state using OCR.

        This is where Worker does parallel OCR.
        Results are stored in local_state (PRIMARY).
        """
        start_time = time.time()

        try:
            # ===== READ SCORE =====
            score = self.read_score()

            # ===== UPDATE LOCAL STATE =====
            if score is not None:
                self.local_state['previous_score'] = self.local_state['score']
                self.local_state['score'] = score
                self.local_state['last_update_time'] = time.time()
                self.local_state['read_count'] += 1

            # ===== DETERMINE STATE =====
            new_state = self.determine_state(score)

            # ===== HANDLE STATE CHANGES =====
            if new_state != self.current_state:
                self.handle_state_change(new_state)

            # ===== UPDATE PHASE IN LOCAL STATE =====
            phase = self.game_state_to_phase(self.current_state)
            self.local_state['phase'] = phase

            # ===== PROCESS BASED ON STATE =====
            if self.current_state == GameState.PLAYING:
                self.process_playing_state(score)
            elif self.current_state == GameState.ENDED:
                self.process_ended_state()

            # ===== TRACK SCORE =====
            if score != self.last_score:
                self.last_score = score

            # ===== METRICS =====
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.ocr_operations += 1
            self.metrics.total_ocr_time_ms += elapsed_ms

            if elapsed_ms > 50:
                self.logger.warning(f"Slow OCR: {elapsed_ms:.1f}ms")

        except Exception as e:
            self.logger.error(f"OCR cycle error: {e}")
            self.local_state['error_count'] += 1
            self.metrics.errors += 1
            self.metrics.ocr_failures += 1

    def read_score(self) -> Optional[float]:
        """
        Read score using OCREngine (Template/Tesseract/CNN).

        Also saves screenshot for CNN training data (zero overhead).

        Returns:
            Score or None
        """
        # Determine region based on last score
        if self.last_score is None or self.last_score < 10:
            region_name = "score_region_small"
        elif self.last_score < 100:
            region_name = "score_region_medium"
        else:
            region_name = "score_region_large"

        region = self.coords.get(region_name)
        if not region:
            return None

        # Capture image ONCE (used for both OCR and screenshot saving)
        image = self.screen_capture.capture_region(region)
        if image is None:
            return None

        # Read using OCREngine (method selected from config)
        score_str = self.ocr_engine.read_score(image)

        if score_str:
            try:
                # Remove 'x' suffix if present
                score_str = score_str.replace('x', '').replace('X', '').strip()
                score = float(score_str)

                # Save screenshot for CNN training (if main collector exists)
                if self.collectors:
                    for collector in self.collectors:
                        if hasattr(collector, 'save_score_screenshot'):
                            collector.save_score_screenshot(score, image)
                            break

                return score
            except (ValueError, TypeError):
                self.logger.debug(f"Failed to parse score: {score_str}")
                return None

        return None

    def determine_state(self, score: Optional[float]) -> GameState:
        """Determine current game state based on score"""
        if score is None:
            if self.current_state == GameState.PLAYING:
                return GameState.ENDED
            else:
                return GameState.WAITING

        elif score == self.last_score and self.last_score is not None:
            self.same_score_count += 1

            if self.same_score_count >= 3:
                return GameState.ENDED
            else:
                return self.current_state

        else:
            self.same_score_count = 0
            return GameState.PLAYING

    def game_state_to_phase(self, game_state: GameState) -> GamePhase:
        """Convert GameState to GamePhase"""
        mapping = {
            GameState.UNKNOWN: GamePhase.UNKNOWN,
            GameState.WAITING: GamePhase.BETTING,
            GameState.BETTING: GamePhase.BETTING,
            GameState.LOADING: GamePhase.LOADING,
            GameState.PLAYING: GamePhase.SCORE_LOW,  # TODO: Refine based on score
            GameState.ENDED: GamePhase.ENDED
        }
        return mapping.get(game_state, GamePhase.UNKNOWN)

    def handle_state_change(self, new_state: GameState):
        """Handle state transitions"""
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
            self.handle_round_start()

        elif new_state == GameState.ENDED and old_state == GameState.PLAYING:
            self.handle_round_end()

    def handle_round_start(self):
        """Handle round start"""
        self.logger.info(f"Round started for {self.bookmaker_name}")

        # Update local_state
        self.local_state['round_start_time'] = time.time()
        self.local_state['round_end_time'] = None

        # Reset tracking
        self.same_score_count = 0
        self.round_counter += 1

        # Reset current round
        self.current_round = {
            'round_id': self.round_counter,
            'start_time': time.time(),
            'end_time': None,
            'final_score': None,
            'thresholds_crossed': []
        }

        # Publish event
        self.event_publisher.publish(EventType.ROUND_START, {
            'bookmaker': self.bookmaker_name,
            'timestamp': datetime.now().isoformat()
        })

        self.metrics.rounds_collected += 1

    def handle_round_end(self):
        """Handle round end"""
        final_score = self.last_score
        self.logger.info(f"Round ended for {self.bookmaker_name}: {final_score:.2f}x")

        # Update local_state
        self.local_state['round_end_time'] = time.time()

        # Update current round
        self.current_round['end_time'] = time.time()
        self.current_round['final_score'] = final_score

        # Read additional data
        self.read_ended_data()

        # Save round to database
        self.save_round()

        # Create round record for history
        round_record = {
            'round_id': self.round_counter,
            'bookmaker': self.bookmaker_name,
            'timestamp': datetime.now().isoformat(),
            'final_score': final_score,
            'duration_seconds': (
                self.current_round['end_time'] - self.current_round['start_time']
                if self.current_round['start_time'] else None
            ),
            'thresholds_crossed': self.current_round['thresholds_crossed']
        }

        # Add to history (keep last 100)
        self.round_history.append(round_record)
        if len(self.round_history) > 100:
            self.round_history.pop(0)

        # Publish event
        self.event_publisher.publish(EventType.ROUND_END, {
            'bookmaker': self.bookmaker_name,
            'final_score': final_score,
            'round_id': self.round_counter
        })

    def process_playing_state(self, score: Optional[float]):
        """Process during active game"""
        if score is None:
            return

        # Check for threshold crossing
        if self.last_score and score > self.last_score:
            threshold = self.check_threshold_crossed(self.last_score, score)

            if threshold:
                self.handle_threshold_crossed(score, threshold)

        # Publish score update (lower priority)
        if score != self.last_score:
            self.event_publisher.publish(EventType.SCORE_UPDATE, {
                'bookmaker': self.bookmaker_name,
                'score': score
            }, priority=7)

    def process_ended_state(self):
        """Process after round end"""
        # Wait a bit for new round
        time.sleep(2.0)

    def check_threshold_crossed(self, prev: float, current: float) -> Optional[float]:
        """
        Check if threshold was crossed.

        Returns:
            Threshold value or None
        """
        for threshold in self.THRESHOLDS:
            if threshold in self.current_round['thresholds_crossed']:
                continue

            if prev < threshold <= current:
                return threshold

        return None

    def handle_threshold_crossed(self, score: float, threshold: float):
        """Handle threshold crossing"""
        self.logger.info(f"Threshold {threshold}x crossed at {score:.2f}x")

        # Mark as crossed
        self.current_round['thresholds_crossed'].append(threshold)

        # Read additional data
        players_left = self.read_players_left()
        total_money = self.read_total_money()

        # Publish event
        self.event_publisher.publish(EventType.THRESHOLD_CROSSED, {
            'bookmaker': self.bookmaker_name,
            'threshold': threshold,
            'score': score,
            'players_left': players_left,
            'total_money': total_money
        })

    def read_ended_data(self):
        """Read data from ENDED screen"""
        try:
            # Read total players
            if "other_count_region" in self.coords:
                image = self.screen_capture.capture_region(self.coords["other_count_region"])
                if image is not None:
                    player_count = self.tesseract_ocr.read_player_count(image)

                    if player_count:
                        self.local_state['player_count_current'] = player_count[0]
                        self.local_state['player_count_total'] = player_count[1]

                        # Save screenshot if enabled
                        if self.collectors:
                            for collector in self.collectors:
                                if hasattr(collector, 'save_region_screenshot'):
                                    value = f"{player_count[0]}_{player_count[1]}"
                                    collector.save_region_screenshot('player_count', value, image)
                                    break

            # Read total money
            if "other_money_region" in self.coords:
                image = self.screen_capture.capture_region(self.coords["other_money_region"])
                if image is not None:
                    money_value = self.tesseract_ocr.read_money(image)

                    if money_value is not None:
                        self.local_state['money_total'] = money_value

                        # Save screenshot if enabled
                        if self.collectors:
                            for collector in self.collectors:
                                if hasattr(collector, 'save_region_screenshot'):
                                    collector.save_region_screenshot('player_money', str(money_value), image)
                                    break

        except Exception as e:
            self.logger.error(f"Error reading ended data: {e}")

    def read_players_left(self) -> Optional[int]:
        """Read number of players left"""
        if "other_count_region" not in self.coords:
            return None

        image = self.screen_capture.capture_region(self.coords["other_count_region"])
        if image is None:
            return None

        player_count = self.tesseract_ocr.read_player_count(image)

        if player_count:
            return player_count[0]  # Current players

        return None

    def read_total_money(self) -> Optional[float]:
        """Read total money"""
        if "other_money_region" not in self.coords:
            return None

        image = self.screen_capture.capture_region(self.coords["other_money_region"])
        if image is None:
            return None

        money_value = self.tesseract_ocr.read_money(image)
        return money_value

    def save_round(self):
        """Save round to database"""
        try:
            # Prepare round data
            round_data = {
                'bookmaker': self.bookmaker_name,
                'timestamp': datetime.now().isoformat(),
                'final_score': self.current_round['final_score'],
                'total_players': self.local_state.get('player_count_total'),
                'players_left': self.local_state.get('player_count_current'),
                'total_money': self.local_state.get('money_total'),
                'duration_seconds': (
                    self.current_round['end_time'] - self.current_round['start_time']
                    if self.current_round['start_time'] else None
                )
            }

            # Write to shared BatchWriter
            if 'main' in self.db_writers:
                self.db_writers['main'].write('rounds', round_data)

        except Exception as e:
            self.logger.error(f"Error saving round: {e}")
            self.metrics.errors += 1

    def update_shared_state(self):
        """
        Update SharedGameState for GUI monitoring.

        NOTE: local_state is PRIMARY, SharedGameState is SECONDARY (GUI only)!
        """
        try:
            state = BookmakerState(
                bookmaker_name=self.bookmaker_name,
                phase=self.local_state['phase'],
                score=self.local_state['score'],
                previous_score=self.local_state['previous_score'],
                round_start_time=self.local_state['round_start_time'],
                round_end_time=self.local_state['round_end_time'],
                loading_start_time=self.local_state['loading_start_time'],
                loading_duration=self.local_state['loading_duration'],
                player_count_current=self.local_state['player_count_current'],
                player_count_total=self.local_state['player_count_total'],
                money_total=self.local_state['money_total'],
                my_money=self.local_state['my_money'],
                last_update_time=self.local_state['last_update_time'],
                read_count=self.local_state['read_count'],
                error_count=self.local_state['error_count']
            )

            self.shared_game_state.set_state(self.bookmaker_name, state)

        except Exception as e:
            self.logger.error(f"Error updating shared state: {e}")

    def send_health_signal(self):
        """Send health signal to process manager"""
        try:
            health_data = {
                'bookmaker': self.bookmaker_name,
                'state': self.current_state.value,
                'metrics': {
                    'rounds': self.metrics.rounds_collected,
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
            pass  # Queue full

    def on_pause_event(self, event: Event):
        """Handle pause event"""
        if event.data.get('bookmaker') in [self.bookmaker_name, 'all']:
            self.logger.info("Pausing worker...")
            # TODO: Implement pause logic

    def on_config_update(self, event: Event):
        """Handle config update event"""
        if event.data.get('bookmaker') in [self.bookmaker_name, 'all']:
            self.logger.info("Updating configuration...")

            new_config = event.data.get('config', {})

            if 'thresholds' in new_config:
                self.THRESHOLDS = new_config['thresholds']

            if 'ocr_intervals' in new_config:
                self.OCR_INTERVALS.update(new_config['ocr_intervals'])

    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up worker...")

        # Stop agents (threads)
        for agent in self.agents:
            if hasattr(agent, 'stop'):
                agent.stop()

        # Wait for threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2.0)

        # Flush batch writers to ensure all data is saved
        self.logger.info("Flushing batch writers...")
        for writer_type, writer in self.db_writers.items():
            try:
                if hasattr(writer, 'flush'):
                    writer.flush()
                    self.logger.info(f"Flushed {writer_type} batch writer")
            except Exception as e:
                self.logger.error(f"Failed to flush {writer_type} writer: {e}")

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
        """Get worker metrics"""
        return {
            'rounds_collected': self.metrics.rounds_collected,
            'ocr_operations': self.metrics.ocr_operations,
            'ocr_failures': self.metrics.ocr_failures,
            'ocr_avg_ms': (
                self.metrics.total_ocr_time_ms / self.metrics.ocr_operations
                if self.metrics.ocr_operations > 0 else 0
            ),
            'errors': self.metrics.errors,
            'uptime_seconds': self.metrics.uptime_seconds,
            'success_rate': (
                (self.metrics.ocr_operations - self.metrics.ocr_failures)
                / self.metrics.ocr_operations * 100
                if self.metrics.ocr_operations > 0 else 0
            )
        }


def worker_entry_point(
    bookmaker_name: str,
    bookmaker_index: int,
    coords: Dict[str, Dict],
    db_writers: Dict[str, BatchDatabaseWriter],
    shutdown_event: MPEvent,
    health_queue: Queue,
    **kwargs
):
    """Entry point for Worker process"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s | {bookmaker_name:12s} | %(levelname)-8s | %(message)s'
    )

    # Extract optional config from kwargs
    image_saving_config = kwargs.get('image_saving_config', None)

    # Create and run worker
    worker = BookmakerWorker(
        bookmaker_name=bookmaker_name,
        bookmaker_index=bookmaker_index,
        coords=coords,
        db_writers=db_writers,
        shutdown_event=shutdown_event,
        health_queue=health_queue,
        image_saving_config=image_saving_config
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

    # Create shared BatchWriter
    db_path = Path("data/databases/test.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    main_writer = BatchDatabaseWriter(db_path, BatchConfig(batch_size=50))
    main_writer.start()

    db_writers = {'main': main_writer}

    # Create multiprocessing components
    shutdown_event = mp.Event()
    health_queue = mp.Queue()

    # Start worker process
    process = mp.Process(
        target=worker_entry_point,
        args=(
            "TestBookmaker",
            0,
            coords,
            db_writers,
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

    # Stop BatchWriter
    main_writer.stop()

    print("Test complete!")


if __name__ == "__main__":
    test_worker()
