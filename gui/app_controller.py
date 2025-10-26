# gui/app_controller.py
"""
App Controller V2 - Koristi novu arhitekturu sa ProcessManager i EventBus.
Integrisan sa GUI za real-time logs i stats.
"""

from typing import Dict, Optional, Callable, List, Any
from collections import deque
import logging

from orchestration.process_manager import ProcessManager, WorkerConfig
from orchestration.shared_reader import SharedGameStateReader
from core.communication.event_bus import EventBus, EventSubscriber, EventType, Event
from data_layer.database.batch_writer import BatchDatabaseWriter, BatchConfig


class AppController:
    """
    Kontroler za Aviator aplikacije - V2 sa novom arhitekturom.
    
    Features:
    - Process manager za worker procese
    - Shared reader za deljeni OCR
    - Event bus za komunikaciju
    - Batch writer za bazu
    - Real-time log streaming
    """
    
    def __init__(self):
        self.logger = logging.getLogger("AppController")
        
        # Process management
        self.process_manager = ProcessManager(max_workers=30)  # 6 bookmakers * 5 apps
        self.shared_reader = None
        
        # Event handling
        self.event_bus = EventBus()
        self.event_subscriber = EventSubscriber("AppController")
        
        # Database
        self.db_writers = {}  # {app_name: BatchWriter}
        
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
        
        # Start shared reader if needed (for data_collector and betting_agent)
        if app_name in ['data_collector', 'betting_agent']:
            if not self.shared_reader:
                self._start_shared_reader(bookmakers)
        
        # Start event bus if not running
        if not self.event_bus.running:
            self.event_bus.start(use_process=False)  # Use threading in main process
        
        # Setup database writer
        self._setup_db_writer(app_name)
        
        # Start worker for each bookmaker
        workers_started = []
        for bookmaker_config in bookmakers:
            worker_name = f"{app_name}-{bookmaker_config['name']}"
            
            if self._start_worker(app_name, bookmaker_config, worker_name):
                workers_started.append(worker_name)
                self._send_log(app_name, f"✓ Started {bookmaker_config['name']}")
            else:
                self._send_log(app_name, f"✗ Failed to start {bookmaker_config['name']}")
        
        if workers_started:
            self.app_states[app_name]["running"] = True
            self.app_states[app_name]["workers"] = workers_started
            self._send_log(app_name, f"=== {app_name.upper()} STARTED ({len(workers_started)} workers) ===")
            return True
        
        return False
    
    def _start_worker(self, app_name: str, bookmaker_config: Dict, worker_name: str) -> bool:
        """Start individual worker process"""
        try:
            # Import appropriate worker function
            if app_name == "data_collector":
                from collectors.main_collector import main_collector_worker
                target_func = main_collector_worker
            elif app_name == "rgb_collector":
                from collectors.rgb_collector import rgb_collector_worker
                target_func = rgb_collector_worker
            elif app_name == "betting_agent":
                from agents.betting_agent import betting_agent_worker
                target_func = betting_agent_worker
            elif app_name == "session_keeper":
                from agents.session_keeper import session_keeper_worker
                target_func = session_keeper_worker
            else:
                self.logger.error(f"Unknown app: {app_name}")
                return False
            
            # Create worker config
            worker_config = WorkerConfig(
                name=worker_name,
                target_func=target_func,
                args=(
                    bookmaker_config['name'],
                    bookmaker_config['coords'],
                    self.shared_reader if app_name in ['data_collector', 'betting_agent'] else None
                ),
                kwargs={
                    'db_writer': self.db_writers.get(app_name),
                    'event_bus': self.event_bus
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
            self.logger.error(f"Error starting worker {worker_name}: {e}")
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
        
        # Flush database
        if app_name in self.db_writers:
            self.db_writers[app_name].flush_all()
        
        # Update state
        self.app_states[app_name]["running"] = False
        self.app_states[app_name]["workers"] = []
        
        self._send_log(app_name, f"=== {app_name.upper()} STOPPED ===")
        
        # Stop shared reader if no apps using it
        if app_name in ['data_collector', 'betting_agent']:
            if not self._any_app_using_shared_reader():
                self._stop_shared_reader()
        
        return True
    
    def _start_shared_reader(self, bookmakers: List[Dict]):
        """Start shared OCR reader"""
        if self.shared_reader:
            return
        
        bookmaker_configs = [
            {
                'name': bm['name'],
                'coords': bm['coords']
            }
            for bm in bookmakers
        ]
        
        self.shared_reader = SharedGameStateReader(bookmaker_configs)
        self.shared_reader.start()
        self.logger.info(f"Started shared reader for {len(bookmakers)} bookmakers")
    
    def _stop_shared_reader(self):
        """Stop shared OCR reader"""
        if not self.shared_reader:
            return
        
        self.shared_reader.stop()
        self.shared_reader = None
        self.logger.info("Stopped shared reader")
    
    def _any_app_using_shared_reader(self) -> bool:
        """Check if any app is using shared reader"""
        return (
            self.app_states["data_collector"]["running"] or
            self.app_states["betting_agent"]["running"]
        )
    
    def _setup_db_writer(self, app_name: str):
        """Setup batch database writer for app"""
        db_paths = {
            'data_collector': 'data/databases/main_game_data.db',
            'rgb_collector': 'data/databases/rgb_training_data.db',
            'betting_agent': 'data/databases/betting_history.db',
            'session_keeper': None  # No database
        }
        
        db_path = db_paths.get(app_name)
        if not db_path:
            return
        
        if app_name not in self.db_writers:
            config = BatchConfig(
                batch_size=50,
                flush_interval=2.0,
                max_queue_size=10000
            )
            
            self.db_writers[app_name] = BatchDatabaseWriter(db_path, config)
            self.db_writers[app_name].start()
            self.logger.info(f"Started DB writer for {app_name}")
    
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
            "workers": worker_status,
            "shared_reader": self.shared_reader is not None
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        stats = {
            'process_manager': self.process_manager.get_stats(),
            'event_bus': self.event_bus.get_stats()
        }
        
        if self.shared_reader:
            stats['shared_reader'] = self.shared_reader.get_stats()
        
        for app_name, writer in self.db_writers.items():
            stats[f'db_writer_{app_name}'] = writer.get_stats()
        
        return stats
    
    def stop_all(self):
        """Stop all running apps"""
        self.logger.info("Stopping all apps...")
        
        for app_name in self.app_states:
            if self.is_running(app_name):
                self.stop_app(app_name, force=True)
        
        # Stop shared components
        if self.shared_reader:
            self._stop_shared_reader()
        
        # Stop event bus
        self.event_bus.stop()
        
        # Stop DB writers
        for writer in self.db_writers.values():
            writer.stop()
        
        # Stop process manager
        self.process_manager.stop_all()
        
        self.logger.info("All apps stopped")