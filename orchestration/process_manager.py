# orchestration/process_manager.py
"""
Process Manager - Centralno upravljanje svim worker procesima.
Automatski health check, restart, graceful shutdown.
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Manager
from multiprocessing.synchronize import Event as MPEvent
import threading
import time
import signal
import psutil
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging


class ProcessState(Enum):
    """Status worker procesa"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"


@dataclass
class WorkerConfig:
    """Konfiguracija za worker proces"""
    name: str
    target_func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    auto_restart: bool = True
    max_restarts: int = 3
    restart_delay: float = 5.0
    health_check_interval: float = 10.0
    memory_limit_mb: int = 500
    cpu_limit_percent: float = 80.0


@dataclass
class WorkerInfo:
    """Informacije o worker procesu"""
    config: WorkerConfig
    process: Optional[Process] = None
    state: ProcessState = ProcessState.STOPPED
    pid: Optional[int] = None
    start_time: Optional[float] = None
    restart_count: int = 0
    last_health_check: Optional[float] = None
    health_status: bool = True
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class ProcessManager:
    """
    Centralni manager za sve worker procese.
    
    Features:
    - Automatski health check
    - Auto-restart crashed procesa
    - Resource monitoring (CPU, Memory)
    - Graceful shutdown
    - Inter-process komunikacija
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize Process Manager.
        
        Args:
            max_workers: Maksimalan broj worker procesa
        """
        self.max_workers = max_workers
        self.workers = {}  # {name: WorkerInfo}
        
        # Multiprocessing components
        self.manager = Manager()
        self.shutdown_event = self.manager.Event()  # Use manager.Event() instead of MPEvent()
        self.health_queue = self.manager.Queue()
        
        # Control
        self.running = False
        self.monitor_thread = None
        
        # Statistics
        self.stats = {
            'total_started': 0,
            'total_crashed': 0,
            'total_restarted': 0,
            'uptime_seconds': 0
        }
        self.start_time = None
        
        # Logging
        self.logger = logging.getLogger("ProcessManager")
        
        # Signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers za graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            self.shutdown_all()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def register_worker(self, config: WorkerConfig) -> bool:
        """
        Registruj novi worker.
        
        Args:
            config: Worker konfiguracija
            
        Returns:
            True ako je uspešno registrovan
        """
        if config.name in self.workers:
            self.logger.warning(f"Worker {config.name} already registered")
            return False
        
        if len(self.workers) >= self.max_workers:
            self.logger.error(f"Max workers limit reached ({self.max_workers})")
            return False
        
        self.workers[config.name] = WorkerInfo(config=config)
        self.logger.info(f"Registered worker: {config.name}")
        return True

    def start_worker(self, name: str) -> bool:
        """
        Pokreni worker proces.
        
        Args:
            name: Ime worker-a
            
        Returns:
            True ako je uspešno pokrenut
        """
        if name not in self.workers:
            self.logger.error(f"Worker {name} not registered")
            return False
        
        worker_info = self.workers[name]
        
        if worker_info.state == ProcessState.RUNNING:
            self.logger.warning(f"Worker {name} already running")
            return False
        
        try:
            # Update state
            worker_info.state = ProcessState.STARTING
            
            # Create process with wrapper function
            process = Process(
                target=self._worker_wrapper,
                args=(worker_info.config, self.shutdown_event, self.health_queue),
                name=name,
                daemon=False
            )
            
            # Start process
            process.start()
            
            # Update info
            worker_info.process = process
            worker_info.pid = process.pid
            worker_info.start_time = time.time()
            worker_info.state = ProcessState.RUNNING
            worker_info.last_health_check = time.time()
            
            # Update stats
            self.stats['total_started'] += 1
            
            self.logger.info(f"Started worker {name} (PID: {process.pid})")
            return True
            
        except Exception as e:
            worker_info.state = ProcessState.CRASHED
            worker_info.error_message = str(e)
            self.logger.error(f"Failed to start worker {name}: {e}", exc_info=True)
            return False

    def stop_worker(self, name: str, timeout: float = 5.0) -> bool:
        """
        Zaustavi worker proces.
        
        Args:
            name: Ime worker-a
            timeout: Timeout za graceful shutdown
            
        Returns:
            True ako je uspešno zaustavljen
        """
        if name not in self.workers:
            return False
        
        worker_info = self.workers[name]
        
        if worker_info.state != ProcessState.RUNNING:
            return False
        
        try:
            worker_info.state = ProcessState.STOPPING
            process = worker_info.process
            
            if process and process.is_alive():
                # Request graceful shutdown
                # (worker should check shutdown_event)
                
                # Wait for process to stop
                process.join(timeout)
                
                if process.is_alive():
                    # Force terminate if still alive
                    self.logger.warning(f"Force terminating worker {name}")
                    process.terminate()
                    process.join(timeout=2.0)
                    
                    if process.is_alive():
                        # Kill if terminate failed
                        process.kill()
                        process.join()
            
            # Update info
            worker_info.state = ProcessState.STOPPED
            worker_info.process = None
            worker_info.pid = None
            
            self.logger.info(f"Stopped worker {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping worker {name}: {e}")
            return False

    def restart_worker(self, name: str) -> bool:
        """
        Restartuj worker proces.
        
        Args:
            name: Ime worker-a
            
        Returns:
            True ako je uspešno restartovan
        """
        if name not in self.workers:
            return False
        
        worker_info = self.workers[name]
        
        # Check restart limit
        if worker_info.restart_count >= worker_info.config.max_restarts:
            self.logger.error(
                f"Worker {name} exceeded max restarts ({worker_info.config.max_restarts})"
            )
            return False
        
        self.logger.info(f"Restarting worker {name}...")
        worker_info.state = ProcessState.RESTARTING
        
        # Stop if running
        if worker_info.process and worker_info.process.is_alive():
            self.stop_worker(name)
        
        # Wait before restart
        time.sleep(worker_info.config.restart_delay)
        
        # Start again
        if self.start_worker(name):
            worker_info.restart_count += 1
            self.stats['total_restarted'] += 1
            return True
        
        return False

    def start_all(self):
        """Pokreni sve registrovane worker-e"""
        self.logger.info("Starting all workers...")
        
        for name in self.workers:
            self.start_worker(name)
        
        # Start monitoring
        self.start_monitoring()

    def stop_all(self, timeout: float = 10.0):
        """Zaustavi sve worker-e"""
        self.logger.info("Stopping all workers...")
        
        # Stop monitoring first
        self.stop_monitoring()
        
        # Stop all workers
        for name in list(self.workers.keys()):
            self.stop_worker(name, timeout)

    def shutdown_all(self):
        """Graceful shutdown svih procesa"""
        self.logger.info("Initiating graceful shutdown...")
        
        # Set shutdown event
        self.shutdown_event.set()
        
        # Stop all workers
        self.stop_all()
        
        self.logger.info("Shutdown complete")

    def start_monitoring(self):
        """Pokreni monitoring thread"""
        if self.running:
            return
        
        self.running = True
        self.start_time = time.time()
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ProcessMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        self.logger.info("Process monitoring started")

    def stop_monitoring(self):
        """Zaustavi monitoring"""
        if not self.running:
            return
        
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        
        self.logger.info("Process monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check all workers
                for name, worker_info in self.workers.items():
                    if worker_info.state == ProcessState.RUNNING:
                        self._check_worker_health(name)
                
                # Update stats
                if self.start_time:
                    self.stats['uptime_seconds'] = time.time() - self.start_time
                
                # Sleep before next check
                time.sleep(5.0)
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}", exc_info=True)

    def _check_worker_health(self, name: str):
        """
        Proveri health worker-a.
        
        Checks:
        1. Process alive
        2. Health queue response
        3. Resource usage (CPU, Memory)
        """
        worker_info = self.workers[name]
        
        try:
            process = worker_info.process
            
            if not process or not process.is_alive():
                # Process crashed
                self._handle_crashed_worker(name)
                return
            
            # Check resource usage
            try:
                proc = psutil.Process(process.pid)
                
                # CPU usage
                cpu_percent = proc.cpu_percent(interval=0.1)
                if cpu_percent > worker_info.config.cpu_limit_percent:
                    self.logger.warning(
                        f"Worker {name} high CPU: {cpu_percent:.1f}%"
                    )
                
                # Memory usage
                memory_mb = proc.memory_info().rss / 1024 / 1024
                if memory_mb > worker_info.config.memory_limit_mb:
                    self.logger.warning(
                        f"Worker {name} high memory: {memory_mb:.1f}MB"
                    )
                    # Could restart if memory leak detected
                
                # Update metrics
                worker_info.metrics['cpu_percent'] = cpu_percent
                worker_info.metrics['memory_mb'] = memory_mb
                
            except psutil.NoSuchProcess:
                # Process ended between checks
                self._handle_crashed_worker(name)
                return
            
            # Update last health check
            worker_info.last_health_check = time.time()
            worker_info.health_status = True
            
        except Exception as e:
            self.logger.error(f"Health check error for {name}: {e}")
            worker_info.health_status = False

    def _handle_crashed_worker(self, name: str):
        """Handle crashed worker"""
        worker_info = self.workers[name]
        
        self.logger.error(f"Worker {name} crashed!")
        
        worker_info.state = ProcessState.CRASHED
        worker_info.process = None
        worker_info.pid = None
        self.stats['total_crashed'] += 1
        
        # Auto restart if configured
        if worker_info.config.auto_restart:
            self.logger.info(f"Auto-restarting {name}...")
            self.restart_worker(name)

    def _worker_wrapper(self, config: WorkerConfig, shutdown_event: MPEvent, health_queue: Queue):
        """
        Wrapper funkcija za worker process.
        Omogućava health monitoring i graceful shutdown.
        """
        try:
            # Setup logging for worker
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger(config.name)
            logger.info(f"Worker {config.name} started (PID: {mp.current_process().pid})")
            
            # Pass shutdown event to worker function
            kwargs = config.kwargs.copy()
            kwargs['shutdown_event'] = shutdown_event
            kwargs['health_queue'] = health_queue
            
            # Run worker function
            config.target_func(*config.args, **kwargs)
            
            logger.info(f"Worker {config.name} finished")
            
        except Exception as e:
            logger = logging.getLogger(config.name)
            logger.error(f"Worker {config.name} crashed: {e}", exc_info=True)
            raise

    def get_worker_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Dobavi status worker-a"""
        if name not in self.workers:
            return None
        
        worker_info = self.workers[name]
        
        return {
            'name': name,
            'state': worker_info.state.value,
            'pid': worker_info.pid,
            'uptime': time.time() - worker_info.start_time if worker_info.start_time else 0,
            'restart_count': worker_info.restart_count,
            'health_status': worker_info.health_status,
            'metrics': worker_info.metrics,
            'error': worker_info.error_message
        }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Dobavi status svih worker-a"""
        status = {}
        for name in self.workers:
            status[name] = self.get_worker_status(name)
        return status

    def get_stats(self) -> Dict[str, Any]:
        """Dobavi statistiku"""
        return self.stats.copy()


# Example worker functions for testing
def example_worker(worker_id: int, shutdown_event: MPEvent, health_queue: Queue, **kwargs):
    """Example worker function"""
    logger = logging.getLogger(f"Worker-{worker_id}")
    logger.info(f"Worker {worker_id} started")
    
    while not shutdown_event.is_set():
        # Do work
        time.sleep(1)
        logger.debug(f"Worker {worker_id} working...")
        
        # Send health signal
        try:
            health_queue.put_nowait({'worker_id': worker_id, 'status': 'healthy'})
        except:
            pass
    
    logger.info(f"Worker {worker_id} stopping")


def test_process_manager():
    """Test process manager"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s'
    )
    
    # Create manager
    manager = ProcessManager(max_workers=5)
    
    # Register workers
    for i in range(3):
        config = WorkerConfig(
            name=f"Worker-{i}",
            target_func=example_worker,
            args=(i,),
            auto_restart=True,
            max_restarts=2,
            memory_limit_mb=100,
            cpu_limit_percent=50.0
        )
        manager.register_worker(config)
    
    # Start all
    manager.start_all()
    
    try:
        # Run for 20 seconds
        for i in range(20):
            time.sleep(1)
            
            # Print status every 5 seconds
            if i % 5 == 0:
                print("\n" + "="*60)
                print("WORKER STATUS:")
                for name, status in manager.get_all_status().items():
                    print(f"  {name}: {status['state']} (PID: {status['pid']}, Uptime: {status['uptime']:.1f}s)")
                
                print("\nSTATS:")
                stats = manager.get_stats()
                for key, value in stats.items():
                    print(f"  {key}: {value}")
                print("="*60)
        
        # Test restart
        print("\nTesting restart of Worker-0...")
        manager.restart_worker("Worker-0")
        time.sleep(5)
        
    finally:
        # Shutdown
        print("\nShutting down...")
        manager.shutdown_all()
        print("Test complete!")


if __name__ == "__main__":
    test_process_manager()