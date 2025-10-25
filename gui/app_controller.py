# gui/app_controller.py
# VERSION: 2.0 - WITH LIVE LOG STREAMING
# PURPOSE: Control starting/stopping of Aviator apps with real-time log capture

import subprocess
import threading
from pathlib import Path
from typing import Dict, Optional, Callable
from collections import deque

from utils.logger import AviatorLogger


class AppController:
    """
    Controller for Aviator applications.

    Manages:
    - Starting apps as subprocesses
    - Stopping apps (graceful/instant)
    - Real-time log streaming via threads
    - Tracking app status
    """

    APP_COMMANDS = {
        "data_collector": ["python", "apps/main_data_collector.py"],
        "rgb_collector": ["python", "apps/rgb_collector.py"],
        "betting_agent": ["python", "apps/betting_agent.py"],
        "session_keeper": ["python", "apps/session_keeper.py"],
    }

    MAX_LOGS_PER_APP = 1000  # Keep last 1000 log lines in memory

    def __init__(self):
        self.logger = AviatorLogger.get_logger("AppController")

        # Running processes
        self.processes: Dict[str, Optional[subprocess.Popen]] = {
            "data_collector": None,
            "rgb_collector": None,
            "betting_agent": None,
            "session_keeper": None,
        }

        # Log reader threads
        self.log_threads: Dict[str, Optional[threading.Thread]] = {
            "data_collector": None,
            "rgb_collector": None,
            "betting_agent": None,
            "session_keeper": None,
        }

        # Log queues for each app (in-memory cache)
        self.log_queues: Dict[str, deque] = {
            "data_collector": deque(maxlen=self.MAX_LOGS_PER_APP),
            "rgb_collector": deque(maxlen=self.MAX_LOGS_PER_APP),
            "betting_agent": deque(maxlen=self.MAX_LOGS_PER_APP),
            "session_keeper": deque(maxlen=self.MAX_LOGS_PER_APP),
        }

    def start_app(
        self,
        app_name: str,
        config: Dict,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """
        Start an application as subprocess with live log streaming.

        Args:
            app_name: Name of the app to start
            config: Configuration dict (not used yet, for future)
            log_callback: Optional callback(app_name, log_line) for real-time logs

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running(app_name):
            self.logger.warning(f"{app_name} already running")
            return False

        try:
            cmd = self.APP_COMMANDS[app_name].copy()

            # Start process with stdout/stderr capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                cwd=Path(__file__).parent.parent,
            )

            self.processes[app_name] = process

            # Start log reader thread
            if log_callback:
                log_thread = threading.Thread(
                    target=self._read_logs,
                    args=(app_name, process, log_callback),
                    daemon=True,
                    name=f"LogReader-{app_name}",
                )
                log_thread.start()
                self.log_threads[app_name] = log_thread

            self.logger.info(f"Started {app_name} (PID: {process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start {app_name}: {e}", exc_info=True)
            return False

    def _read_logs(
        self,
        app_name: str,
        process: subprocess.Popen,
        callback: Callable[[str, str], None],
    ):
        """
        Read logs from subprocess stdout in background thread.

        Args:
            app_name: Name of the app
            process: Subprocess object
            callback: Callback function to send logs to GUI
        """
        try:
            for line in iter(process.stdout.readline, ""):
                if line:
                    clean_line = line.rstrip()

                    # Store in memory queue
                    self.log_queues[app_name].append(clean_line)

                    # Send to GUI callback
                    callback(app_name, clean_line)

                # Check if process ended
                if process.poll() is not None:
                    break

            # Process ended
            self.logger.info(f"Log reader for {app_name} finished")

        except Exception as e:
            self.logger.error(f"Log reader error for {app_name}: {e}", exc_info=True)

    def stop_app(self, app_name: str, force: bool = False) -> bool:
        """
        Stop an application.

        Args:
            app_name: Name of the app to stop
            force: If True, kill immediately. If False, terminate gracefully.

        Returns:
            True if stopped successfully, False otherwise
        """
        process = self.processes.get(app_name)

        if not process:
            self.logger.warning(f"{app_name} not running")
            return False

        try:
            if force:
                process.kill()
                self.logger.info(f"Killed {app_name} (PID: {process.pid})")
            else:
                process.terminate()
                self.logger.info(f"Terminated {app_name} (PID: {process.pid})")

            # Wait for process to finish
            process.wait(timeout=5)

            # Clear process reference
            self.processes[app_name] = None
            self.log_threads[app_name] = None

            return True

        except subprocess.TimeoutExpired:
            # Force kill if graceful stop failed
            self.logger.warning(f"{app_name} didn't stop gracefully, killing...")
            process.kill()
            process.wait()
            self.processes[app_name] = None
            self.log_threads[app_name] = None
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop {app_name}: {e}", exc_info=True)
            return False

    def is_running(self, app_name: str) -> bool:
        """Check if app is running."""
        process = self.processes.get(app_name)

        if not process:
            return False

        # Check if process is still alive
        return process.poll() is None

    def get_logs(self, app_name: str, last_n: int = 100) -> list:
        """
        Get last N logs from memory queue.

        Args:
            app_name: Name of the app
            last_n: Number of last logs to retrieve

        Returns:
            List of log lines
        """
        queue = self.log_queues.get(app_name, deque())

        # Return last N items
        if len(queue) <= last_n:
            return list(queue)
        else:
            return list(queue)[-last_n:]

    def stop_all(self):
        """Stop all running apps."""
        self.logger.info("Stopping all apps...")

        for app_name in list(self.processes.keys()):
            if self.is_running(app_name):
                self.stop_app(app_name, force=True)

        self.logger.info("All apps stopped")
