# gui/log_reader.py
# VERSION: 1.0
# PURPOSE: Thread for reading logs from subprocess stdout in real-time

import threading
import queue
from typing import Callable
from subprocess import Popen

from utils.logger import AviatorLogger


class LogReaderThread(threading.Thread):
    """
    Thread that reads stdout from subprocess and emits log lines.

    Non-blocking, runs in background, automatically stops when process ends.
    """

    def __init__(
        self, process: Popen, app_name: str, callback: Callable[[str, str], None]
    ):
        """
        Initialize log reader thread.

        Args:
            process: Subprocess to read from
            app_name: Name of app (for identification)
            callback: Function to call with (app_name, log_line)
        """
        super().__init__(daemon=True, name=f"LogReader-{app_name}")

        self.process = process
        self.app_name = app_name
        self.callback = callback
        self.logger = AviatorLogger.get_logger(f"LogReader-{app_name}")
        self._stop_event = threading.Event()

    def run(self):
        """Main thread loop - reads stdout line by line."""
        try:
            self.logger.info(f"Started reading logs for {self.app_name}")

            # Read stdout line by line
            for line in iter(self.process.stdout.readline, ""):
                if self._stop_event.is_set():
                    break

                if line:
                    # Strip newline and send to callback
                    log_line = line.rstrip("\n")
                    self.callback(self.app_name, log_line)

            self.logger.info(f"Stopped reading logs for {self.app_name}")

        except Exception as e:
            self.logger.error(f"Error reading logs: {e}")

    def stop(self):
        """Stop the thread gracefully."""
        self._stop_event.set()


class LogManager:
    """
    Manages log reader threads for multiple apps.

    Centralizes log collection from all running apps.
    """

    def __init__(self):
        self.logger = AviatorLogger.get_logger("LogManager")
        self.readers: dict[str, LogReaderThread] = {}
        self.log_queue = queue.Queue(maxsize=10000)  # Buffer for logs

    def start_reader(self, app_name: str, process: Popen):
        """
        Start log reader for an app.

        Args:
            app_name: Name of app
            process: Subprocess to read from
        """
        if app_name in self.readers:
            self.logger.warning(f"Log reader already exists for {app_name}")
            return

        reader = LogReaderThread(
            process=process, app_name=app_name, callback=self._on_log_line
        )
        reader.start()

        self.readers[app_name] = reader
        self.logger.info(f"Started log reader for {app_name}")

    def stop_reader(self, app_name: str):
        """
        Stop log reader for an app.

        Args:
            app_name: Name of app
        """
        reader = self.readers.get(app_name)
        if reader:
            reader.stop()
            del self.readers[app_name]
            self.logger.info(f"Stopped log reader for {app_name}")

    def stop_all_readers(self):
        """Stop all log readers."""
        for app_name in list(self.readers.keys()):
            self.stop_reader(app_name)

    def _on_log_line(self, app_name: str, log_line: str):
        """
        Callback when new log line is received.

        Args:
            app_name: Name of app
            log_line: Log line text
        """
        try:
            self.log_queue.put_nowait((app_name, log_line))
        except queue.Full:
            # Queue is full, drop oldest logs
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait((app_name, log_line))
            except queue.Empty:
                pass

    def get_logs(self, max_count: int = 100) -> list[tuple[str, str]]:
        """
        Get pending logs from queue.

        Args:
            max_count: Maximum number of logs to retrieve

        Returns:
            List of (app_name, log_line) tuples
        """
        logs = []

        for _ in range(max_count):
            try:
                log_entry = self.log_queue.get_nowait()
                logs.append(log_entry)
            except queue.Empty:
                break

        return logs
