"""
Module: Health Monitor
Purpose: Process health monitoring and auto-recovery
Version: 2.0

This module provides:
- Worker process health monitoring
- Heartbeat tracking
- Auto-recovery of failed workers
- Performance metrics tracking
- Resource usage monitoring
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from multiprocessing import Process
from enum import Enum


class HealthStatus(Enum):
    """Worker health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DEAD = "dead"
    RECOVERING = "recovering"


@dataclass
class WorkerHealth:
    """
    Health information for a single worker process.

    Tracks heartbeats, resource usage, and error counts to determine
    if a worker is functioning properly or needs recovery.
    """

    worker_name: str
    process: Optional[Process] = None

    # Health tracking
    status: HealthStatus = HealthStatus.HEALTHY
    last_heartbeat: Optional[float] = None
    consecutive_failures: int = 0
    total_failures: int = 0
    recovery_attempts: int = 0

    # Performance metrics
    avg_cycle_time: float = 0.0
    last_cycle_time: float = 0.0
    cycles_completed: int = 0

    # Resource tracking
    cpu_percent: float = 0.0
    memory_mb: float = 0.0

    # Timing
    start_time: float = field(default_factory=time.time)
    last_recovery_time: Optional[float] = None

    def is_alive(self) -> bool:
        """Check if worker process is alive."""
        if self.process is None:
            return False
        return self.process.is_alive()

    def uptime_seconds(self) -> float:
        """Get worker uptime in seconds."""
        return time.time() - self.start_time

    def time_since_heartbeat(self) -> Optional[float]:
        """Get seconds since last heartbeat."""
        if self.last_heartbeat is None:
            return None
        return time.time() - self.last_heartbeat


class HealthMonitor:
    """
    Monitors health of all worker processes and handles recovery.

    Features:
    - Heartbeat monitoring with configurable timeout
    - Performance metrics tracking
    - Automatic recovery of failed workers
    - Resource usage monitoring
    - Health statistics
    """

    def __init__(
        self,
        heartbeat_timeout: float = 10.0,
        heartbeat_warning: float = 5.0,
        max_recovery_attempts: int = 3,
        recovery_cooldown: float = 60.0
    ):
        """
        Initialize health monitor.

        Args:
            heartbeat_timeout: Seconds without heartbeat before worker considered dead
            heartbeat_warning: Seconds without heartbeat before warning status
            max_recovery_attempts: Maximum automatic recovery attempts
            recovery_cooldown: Seconds to wait between recovery attempts
        """
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_warning = heartbeat_warning
        self.max_recovery_attempts = max_recovery_attempts
        self.recovery_cooldown = recovery_cooldown

        # Worker tracking
        self.workers: Dict[str, WorkerHealth] = {}

        # Statistics
        self.total_recoveries = 0
        self.failed_recoveries = 0
        self.monitoring_start_time = time.time()

        # Logging
        self.logger = logging.getLogger("HealthMonitor")
        self.logger.setLevel(logging.INFO)

    def register_worker(self, worker_name: str, process: Process) -> None:
        """
        Register a new worker for monitoring.

        Args:
            worker_name: Name identifier for worker
            process: Worker's Process object
        """
        self.workers[worker_name] = WorkerHealth(
            worker_name=worker_name,
            process=process
        )
        self.logger.info(f"Registered worker: {worker_name}")

    def update_heartbeat(
        self,
        worker_name: str,
        cycle_time: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None
    ) -> None:
        """
        Update worker heartbeat and metrics.

        Args:
            worker_name: Name of worker
            cycle_time: Time taken for last cycle
            cpu_percent: CPU usage percentage
            memory_mb: Memory usage in MB
        """
        if worker_name not in self.workers:
            self.logger.warning(f"Heartbeat from unknown worker: {worker_name}")
            return

        worker = self.workers[worker_name]
        worker.last_heartbeat = time.time()
        worker.cycles_completed += 1

        # Update performance metrics
        if cycle_time is not None:
            worker.last_cycle_time = cycle_time
            # Calculate moving average
            if worker.avg_cycle_time == 0.0:
                worker.avg_cycle_time = cycle_time
            else:
                worker.avg_cycle_time = (worker.avg_cycle_time * 0.9) + (cycle_time * 0.1)

        # Update resource metrics
        if cpu_percent is not None:
            worker.cpu_percent = cpu_percent
        if memory_mb is not None:
            worker.memory_mb = memory_mb

        # Reset failure counter on successful heartbeat
        if worker.consecutive_failures > 0:
            self.logger.info(f"Worker {worker_name} recovered from {worker.consecutive_failures} failures")
            worker.consecutive_failures = 0

    def check_health(self) -> Dict[str, HealthStatus]:
        """
        Check health status of all workers.

        Returns:
            Dictionary mapping worker name to health status
        """
        health_status = {}

        for worker_name, worker in self.workers.items():
            status = self._determine_health_status(worker)

            # Update status if changed
            if status != worker.status:
                self.logger.info(f"Worker {worker_name} status changed: {worker.status.value} -> {status.value}")
                worker.status = status

            health_status[worker_name] = status

        return health_status

    def _determine_health_status(self, worker: WorkerHealth) -> HealthStatus:
        """
        Determine health status of a worker.

        Args:
            worker: Worker health data

        Returns:
            Current health status
        """
        # Check if process is alive
        if not worker.is_alive():
            return HealthStatus.DEAD

        # Check if recovering
        if worker.status == HealthStatus.RECOVERING:
            time_since_recovery = time.time() - (worker.last_recovery_time or 0)
            if time_since_recovery < self.recovery_cooldown:
                return HealthStatus.RECOVERING

        # Check heartbeat timing
        time_since_heartbeat = worker.time_since_heartbeat()

        if time_since_heartbeat is None:
            # No heartbeat yet (just started)
            return HealthStatus.HEALTHY

        if time_since_heartbeat >= self.heartbeat_timeout:
            # Dead - no heartbeat for too long
            worker.consecutive_failures += 1
            worker.total_failures += 1
            return HealthStatus.CRITICAL

        if time_since_heartbeat >= self.heartbeat_warning:
            # Warning - heartbeat delayed
            return HealthStatus.WARNING

        # Check consecutive failures
        if worker.consecutive_failures > 0:
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    def get_unhealthy_workers(self) -> List[str]:
        """
        Get list of workers that need attention.

        Returns:
            List of worker names with critical or dead status
        """
        unhealthy = []

        for worker_name, worker in self.workers.items():
            if worker.status in (HealthStatus.CRITICAL, HealthStatus.DEAD):
                unhealthy.append(worker_name)

        return unhealthy

    def should_recover_worker(self, worker_name: str) -> bool:
        """
        Determine if worker should be recovered.

        Args:
            worker_name: Name of worker

        Returns:
            True if worker should be recovered
        """
        if worker_name not in self.workers:
            return False

        worker = self.workers[worker_name]

        # Don't recover if already recovering
        if worker.status == HealthStatus.RECOVERING:
            return False

        # Don't recover if max attempts reached
        if worker.recovery_attempts >= self.max_recovery_attempts:
            self.logger.error(
                f"Worker {worker_name} exceeded max recovery attempts ({self.max_recovery_attempts})"
            )
            return False

        # Check cooldown period
        if worker.last_recovery_time is not None:
            time_since_recovery = time.time() - worker.last_recovery_time
            if time_since_recovery < self.recovery_cooldown:
                return False

        # Recover if critical or dead
        return worker.status in (HealthStatus.CRITICAL, HealthStatus.DEAD)

    def mark_recovering(self, worker_name: str) -> None:
        """
        Mark worker as recovering.

        Args:
            worker_name: Name of worker being recovered
        """
        if worker_name not in self.workers:
            return

        worker = self.workers[worker_name]
        worker.status = HealthStatus.RECOVERING
        worker.recovery_attempts += 1
        worker.last_recovery_time = time.time()
        self.total_recoveries += 1

        self.logger.info(
            f"Recovering worker {worker_name} (attempt {worker.recovery_attempts}/{self.max_recovery_attempts})"
        )

    def mark_recovery_success(self, worker_name: str, new_process: Process) -> None:
        """
        Mark worker recovery as successful.

        Args:
            worker_name: Name of recovered worker
            new_process: New Process object
        """
        if worker_name not in self.workers:
            return

        worker = self.workers[worker_name]
        worker.process = new_process
        worker.status = HealthStatus.HEALTHY
        worker.start_time = time.time()
        worker.last_heartbeat = time.time()
        worker.consecutive_failures = 0

        self.logger.info(f"Worker {worker_name} recovered successfully")

    def mark_recovery_failure(self, worker_name: str) -> None:
        """
        Mark worker recovery as failed.

        Args:
            worker_name: Name of worker that failed recovery
        """
        if worker_name not in self.workers:
            return

        self.failed_recoveries += 1
        self.logger.error(f"Failed to recover worker {worker_name}")

    def unregister_worker(self, worker_name: str) -> None:
        """
        Remove worker from monitoring.

        Args:
            worker_name: Name of worker to remove
        """
        if worker_name in self.workers:
            del self.workers[worker_name]
            self.logger.info(f"Unregistered worker: {worker_name}")

    def get_stats(self) -> Dict:
        """
        Get health monitoring statistics.

        Returns:
            Dictionary with monitoring statistics
        """
        total_workers = len(self.workers)
        healthy_count = sum(1 for w in self.workers.values() if w.status == HealthStatus.HEALTHY)
        warning_count = sum(1 for w in self.workers.values() if w.status == HealthStatus.WARNING)
        critical_count = sum(1 for w in self.workers.values() if w.status == HealthStatus.CRITICAL)
        dead_count = sum(1 for w in self.workers.values() if w.status == HealthStatus.DEAD)
        recovering_count = sum(1 for w in self.workers.values() if w.status == HealthStatus.RECOVERING)

        total_cycles = sum(w.cycles_completed for w in self.workers.values())
        total_failures = sum(w.total_failures for w in self.workers.values())

        uptime = time.time() - self.monitoring_start_time

        return {
            "total_workers": total_workers,
            "healthy": healthy_count,
            "warning": warning_count,
            "critical": critical_count,
            "dead": dead_count,
            "recovering": recovering_count,
            "total_cycles": total_cycles,
            "total_failures": total_failures,
            "total_recoveries": self.total_recoveries,
            "failed_recoveries": self.failed_recoveries,
            "recovery_success_rate": (
                (self.total_recoveries - self.failed_recoveries) / self.total_recoveries * 100
                if self.total_recoveries > 0 else 0.0
            ),
            "uptime_seconds": uptime,
            "uptime_hours": uptime / 3600.0
        }

    def get_worker_details(self, worker_name: str) -> Optional[Dict]:
        """
        Get detailed information about a worker.

        Args:
            worker_name: Name of worker

        Returns:
            Dictionary with worker details or None if not found
        """
        if worker_name not in self.workers:
            return None

        worker = self.workers[worker_name]

        return {
            "name": worker.worker_name,
            "status": worker.status.value,
            "is_alive": worker.is_alive(),
            "uptime_seconds": worker.uptime_seconds(),
            "last_heartbeat": worker.last_heartbeat,
            "time_since_heartbeat": worker.time_since_heartbeat(),
            "consecutive_failures": worker.consecutive_failures,
            "total_failures": worker.total_failures,
            "recovery_attempts": worker.recovery_attempts,
            "cycles_completed": worker.cycles_completed,
            "avg_cycle_time": worker.avg_cycle_time,
            "last_cycle_time": worker.last_cycle_time,
            "cpu_percent": worker.cpu_percent,
            "memory_mb": worker.memory_mb
        }

    def get_all_worker_details(self) -> Dict[str, Dict]:
        """
        Get detailed information about all workers.

        Returns:
            Dictionary mapping worker names to their details
        """
        return {
            worker_name: self.get_worker_details(worker_name)
            for worker_name in self.workers.keys()
        }

    def log_status_summary(self) -> None:
        """Log a summary of all worker statuses."""
        stats = self.get_stats()

        self.logger.info(
            f"Health Monitor Status: "
            f"{stats['healthy']} healthy, "
            f"{stats['warning']} warning, "
            f"{stats['critical']} critical, "
            f"{stats['dead']} dead, "
            f"{stats['recovering']} recovering"
        )

        # Log unhealthy workers
        for worker_name, worker in self.workers.items():
            if worker.status != HealthStatus.HEALTHY:
                details = self.get_worker_details(worker_name)
                self.logger.warning(
                    f"Worker {worker_name}: {worker.status.value} - "
                    f"Heartbeat: {details['time_since_heartbeat']:.1f}s ago, "
                    f"Failures: {worker.consecutive_failures}/{worker.total_failures}, "
                    f"Recovery attempts: {worker.recovery_attempts}"
                )

    def cleanup(self) -> None:
        """Clean up health monitor resources."""
        self.logger.info("Health monitor cleanup started")

        # Log final statistics
        stats = self.get_stats()
        self.logger.info(f"Final statistics: {stats}")

        # Clear worker tracking
        self.workers.clear()

        self.logger.info("Health monitor cleanup completed")


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    from multiprocessing import Process
    import time

    def dummy_worker(name: str):
        """Dummy worker for testing."""
        time.sleep(5)

    # Create health monitor
    monitor = HealthMonitor(
        heartbeat_timeout=3.0,
        heartbeat_warning=2.0,
        max_recovery_attempts=3
    )

    # Create and register workers
    workers = []
    for i in range(3):
        worker_name = f"Worker-{i+1}"
        process = Process(target=dummy_worker, args=(worker_name,))
        process.start()
        monitor.register_worker(worker_name, process)
        workers.append(process)

    # Simulate monitoring
    print("\n=== Simulating Monitoring ===")
    for cycle in range(5):
        print(f"\nCycle {cycle + 1}:")

        # Simulate heartbeats for some workers
        if cycle < 3:  # First 3 cycles
            monitor.update_heartbeat("Worker-1", cycle_time=0.5, cpu_percent=25.0, memory_mb=100.0)
            monitor.update_heartbeat("Worker-2", cycle_time=0.6, cpu_percent=30.0, memory_mb=110.0)
        # Worker-3 never sends heartbeat (to test failure detection)

        # Check health
        health_status = monitor.check_health()
        monitor.log_status_summary()

        time.sleep(1)

    # Print final statistics
    print("\n=== Final Statistics ===")
    stats = monitor.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    print("\n=== Worker Details ===")
    for worker_name in ["Worker-1", "Worker-2", "Worker-3"]:
        details = monitor.get_worker_details(worker_name)
        if details:
            print(f"\n{worker_name}:")
            for key, value in details.items():
                print(f"  {key}: {value}")

    # Cleanup
    monitor.cleanup()
    for worker in workers:
        if worker.is_alive():
            worker.terminate()
            worker.join()
