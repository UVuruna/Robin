# gui/app_controller.py
"""
App Controller v3.0 - v3.0 Architecture Compliant
==================================================

Kontroler za Aviator aplikacije sa Worker Process Pattern.

**v3.0 ARCHITECTURE:**
- NO Shared Reader (OBSOLETE!)
- Workers use bookmaker_worker.py with parallel OCR
- Shared BatchWriter per TYPE (not per worker!)
- EventBus for real-time GUI updates

Version: 3.0
"""

from typing import Dict, Optional, Callable, Any
from collections import deque
import logging
from pathlib import Path

from config.settings import PATH
from orchestration.process_manager import ProcessManager, WorkerConfig
from orchestration.bookmaker_worker import worker_entry_point
from core.communication.event_bus import EventBus, EventSubscriber, EventType, Event
from data_layer.database.batch_writer import BatchDatabaseWriter, BatchConfig


class AppController:
    """
    App Controller v3.0 - Worker Process Pattern.

    **KEY FEATURES:**
    - Process manager for worker processes
    - Shared BatchWriter per TYPE (main, betting, rgb)
    - Event bus for real-time communication
    - NO Shared Reader (workers have own OCR!)
    """

    def __init__(self):
        self.logger = logging.getLogger("AppController")

        # Process management
        self.process_manager = ProcessManager(max_workers=30)  # 6 bookmakers * 5 apps

        # Event handling
        self.event_bus = EventBus()
        self.event_subscriber = EventSubscriber("AppController")

        # ===== SHARED BATCH WRITERS (per TYPE!) =====
        self.db_writers = {}  # {type_name: BatchWriter}
        self._init_shared_writers()

        # App states
        self.app_states = {
            "data_collector": {"running": False, "workers": []},
            "rgb_collector": {"running": False, "workers": []},
            "betting_agent": {"running": False, "workers": []},
            "session_keeper": {"running": False, "workers": []},
        }

        # Log callbacks from GUI
        self.log_callbacks = {}  # {app_name: callback_func}

        # Log buffers
        self.log_buffers = {
            "data_collector": deque(maxlen=1000),
            "rgb_collector": deque(maxlen=1000),
            "betting_agent": deque(maxlen=1000),
            "session_keeper": deque(maxlen=1000),
        }

        self._setup_event_handlers()

        self.logger.info("AppController v3.0 initialized")

    def _init_shared_writers(self):
        """
        Initialize SHARED BatchWriter instances per TYPE.

        v3.0: ONE writer per TYPE, shared across all workers!
        """
        writer_configs = {
            'main': {
                'path': PATH.main_game_db,
                'batch_size': 100
            },
            'betting': {
                'path': PATH.betting_history_db,
                'batch_size': 50
            },
            'rgb': {
                'path': PATH.rgb_training_db,
                'batch_size': 100
            }
        }

        for writer_type, config_data in writer_configs.items():
            db_path = Path(config_data['path'])
            db_path.parent.mkdir(parents=True, exist_ok=True)

            config = BatchConfig(
                batch_size=config_data['batch_size'],
                flush_interval=2.0,
                max_queue_size=10000
            )

            self.db_writers[writer_type] = BatchDatabaseWriter(db_path, config)
            self.db_writers[writer_type].start()

            self.logger.info(f"Started SHARED BatchWriter: {writer_type}")

    def _setup_event_handlers(self):
        """Setup event subscriptions"""
        # Subscribe to important events
        self.event_subscriber.subscribe(EventType.PROCESS_START, self._on_process_start)
        self.event_subscriber.subscribe(EventType.PROCESS_STOP, self._on_process_stop)
        self.event_subscriber.subscribe(EventType.PROCESS_ERROR, self._on_process_error)

        # Log events
        self.event_subscriber.subscribe(EventType.DATA_COLLECTED, self._on_data_collected)
        self.event_subscriber.subscribe(EventType.ROUND_END, self._on_round_end)

    def start_app(
        self,
        app_name: str,
        config: Dict,
        log_callback: Optional[Callable[[str, str], None]] = None
    ) -> bool:
        """
        Start application with multiple workers (one per bookmaker).

        v3.0: Uses bookmaker_worker.py with parallel OCR!

        Args:
            app_name: Name of app (data_collector, rgb_collector, etc)
            config: Configuration with bookmakers list
            log_callback: Callback for log streaming

        Returns:
            True if started successfully
        """
        if self.app_states[app_name]["running"]:
            self.logger.warning(f"{app_name} already running")
            return False

        # Store log callback
        if log_callback:
            self.log_callbacks[app_name] = log_callback

        # Get bookmakers from config
        bookmakers = config.get('bookmakers', [])
        if not bookmakers:
            self.logger.error(f"No bookmakers configured for {app_name}")
            return False

        # Start event bus if not running
        if not self.event_bus.running:
            self.event_bus.start(use_process=False)  # Use threading in main process

        # Start worker for each bookmaker
        workers_started = []
        for index, bookmaker_config in enumerate(bookmakers):
            worker_name = f"{app_name}-{bookmaker_config['name']}"

            if self._start_worker(app_name, bookmaker_config, worker_name, index):
                workers_started.append(worker_name)
                self._send_log(app_name, f"✓ Started {bookmaker_config['name']}")
            else:
                self._send_log(app_name, f"✗ Failed to start {bookmaker_config['name']}")

        if workers_started:
            self.app_states[app_name]["running"] = True
            self.app_states[app_name]["workers"] = workers_started
            self._send_log(app_name, f"=== {app_name.upper()} STARTED ({len(workers_started)} workers) ===")
            self._send_log(app_name, "Architecture: Worker Process Pattern (v3.0)")
            return True

        return False

    def _start_worker(
        self,
        app_name: str,
        bookmaker_config: Dict,
        worker_name: str,
        bookmaker_index: int
    ) -> bool:
        """
        Start individual worker process using bookmaker_worker.py.

        v3.0: All apps use the SAME BookmakerWorker with different configs!
        """
        try:
            # v3.0: Use worker_entry_point from bookmaker_worker.py
            target_func = worker_entry_point

            # Prepare shared BatchWriter dict for this worker
            db_writers_dict = {
                'main': self.db_writers['main'],
                'betting': self.db_writers['betting'],
                'rgb': self.db_writers['rgb']
            }

            # Create worker config
            worker_config = WorkerConfig(
                name=worker_name,
                target_func=target_func,
                args=(
                    bookmaker_config['name'],      # bookmaker_name
                    bookmaker_index,                # bookmaker_index (for offset)
                    bookmaker_config['coords'],     # coords
                    db_writers_dict,                # db_writers (SHARED!)
                ),
                kwargs={
                    # Add app-specific kwargs if needed
                    'app_type': app_name
                },
                auto_restart=True,
                max_restarts=3,
                restart_delay=5.0,
                health_check_interval=10.0,
                memory_limit_mb=300,
                cpu_limit_percent=25.0
            )

            # Register and start worker
            if self.process_manager.register_worker(worker_config):
                return self.process_manager.start_worker(worker_name)

            return False

        except Exception as e:
            self.logger.error(f"Error starting worker {worker_name}: {e}", exc_info=True)
            return False

    def stop_app(self, app_name: str, force: bool = False) -> bool:
        """
        Stop application and all its workers.

        Args:
            app_name: Name of app to stop
            force: If True, kill immediately

        Returns:
            True if stopped successfully
        """
        if not self.app_states[app_name]["running"]:
            self.logger.warning(f"{app_name} not running")
            return False

        # Stop all workers for this app
        workers = self.app_states[app_name]["workers"]
        for worker_name in workers:
            self.process_manager.stop_worker(worker_name, timeout=5.0 if not force else 1.0)
            self._send_log(app_name, f"Stopped {worker_name}")

        # Flush shared database writers
        for writer_type, writer in self.db_writers.items():
            writer.flush_all()
            self.logger.info(f"Flushed shared writer: {writer_type}")

        # Update state
        self.app_states[app_name]["running"] = False
        self.app_states[app_name]["workers"] = []

        self._send_log(app_name, f"=== {app_name.upper()} STOPPED ===")

        return True

    def _send_log(self, app_name: str, message: str):
        """Send log to GUI and buffer"""
        # Add to buffer
        self.log_buffers[app_name].append(message)

        # Send to GUI callback if registered
        if app_name in self.log_callbacks:
            callback = self.log_callbacks[app_name]
            try:
                callback(app_name, message)
            except Exception as e:
                self.logger.error(f"Log callback error: {e}")

    # Event handlers
    def _on_process_start(self, event: Event):
        """Handle process start event"""
        app_name = self._get_app_from_worker(event.source)
        if app_name:
            self._send_log(app_name, f"[{event.source}] Process started")

    def _on_process_stop(self, event: Event):
        """Handle process stop event"""
        app_name = self._get_app_from_worker(event.source)
        if app_name:
            metrics = event.data.get('metrics', {})
            self._send_log(app_name, f"[{event.source}] Process stopped")
            if metrics:
                self._send_log(app_name, f"  Metrics: {metrics}")

    def _on_process_error(self, event: Event):
        """Handle process error event"""
        app_name = self._get_app_from_worker(event.source)
        if app_name:
            error = event.data.get('error', 'Unknown error')
            self._send_log(app_name, f"⚠️ [{event.source}] Error: {error}")

    def _on_data_collected(self, event: Event):
        """Handle data collected event"""
        app_name = self._get_app_from_worker(event.source)
        if app_name:
            bookmaker = event.data.get('bookmaker')
            count = event.data.get('count', 0)
            self._send_log(app_name, f"[{bookmaker}] Collected {count} samples")

    def _on_round_end(self, event: Event):
        """Handle round end event"""
        bookmaker = event.data.get('bookmaker')
        score = event.data.get('final_score')

        # Log to data collector
        self._send_log('data_collector', f"[{bookmaker}] Round ended: {score:.2f}x")

    def _get_app_from_worker(self, worker_name: str) -> Optional[str]:
        """Extract app name from worker name"""
        for app_name in self.app_states:
            if worker_name.startswith(app_name):
                return app_name
        return None

    def is_running(self, app_name: str) -> bool:
        """Check if app is running"""
        return self.app_states[app_name]["running"]

    def get_worker_status(self, app_name: str) -> Dict[str, Any]:
        """Get status of all workers for an app"""
        if not self.app_states[app_name]["running"]:
            return {"running": False}

        workers = self.app_states[app_name]["workers"]
        worker_status = {}

        for worker_name in workers:
            status = self.process_manager.get_worker_status(worker_name)
            if status:
                worker_status[worker_name] = status

        return {
            "running": True,
            "workers": worker_status
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        stats = {
            'process_manager': self.process_manager.get_stats(),
            'event_bus': self.event_bus.get_stats()
        }

        # Add shared BatchWriter stats
        for writer_type, writer in self.db_writers.items():
            stats[f'db_writer_{writer_type}'] = writer.get_stats()

        return stats

    def stop_all(self):
        """Stop all running apps"""
        self.logger.info("Stopping all apps...")

        for app_name in self.app_states:
            if self.is_running(app_name):
                self.stop_app(app_name, force=True)

        # Stop event bus
        self.event_bus.stop()

        # Stop shared DB writers
        for writer_type, writer in self.db_writers.items():
            self.logger.info(f"Stopping shared writer: {writer_type}")
            writer.stop()

        # Stop process manager
        self.process_manager.stop_all()

        self.logger.info("All apps stopped (v3.0)")
