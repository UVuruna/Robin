# apps/rgb_collector.py
# VERSION: 3.0 - HIGH-SPEED RGB+STD COLLECTOR
# PURPOSE: Collect RGB statistics for NEW ML model training
# TARGET: 30 samples/sec per bookmaker = 180/sec total (6 bookmakers)
# OPTIMIZED: Fast capture, batch insert, minimal overhead

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import sqlite3
import numpy as np
import mss
from typing import Dict, Optional, List
from multiprocessing import Process, Queue
from multiprocessing.synchronize import Event as EventType
from datetime import datetime
from queue import Empty

from apps.base_app import BaseAviatorApp
from utils.logger import AviatorLogger


class RGBCollectorV3(BaseAviatorApp):
    """
    HIGH-SPEED RGB+STD data collector for ML training.
    
    Performance targets:
    - 30 samples/sec per bookmaker
    - 180 samples/sec total (6 bookmakers)
    - ~650k samples/hour
    - Region: 360x120px
    
    Features:
    - Only collects phase_region (game phase detection)
    - Fast 33ms collection interval
    - Large batch inserts (500-1000 samples)
    - Async database writer process
    - Performance monitoring
    """

    def __init__(self):
        super().__init__(
            app_name="RGBCollectorV3", 
            database_name="phase_rgb_training.db"
        )
        self.db_queue = None  # Shared queue for DB writes

    def setup_database(self):
        """Create optimized database tables."""
        self.logger.info("Setting up high-speed RGB database...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Phase RGB table - ONLY THIS ONE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phase_rgb (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bookmaker TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                r_avg REAL NOT NULL,
                g_avg REAL NOT NULL,
                b_avg REAL NOT NULL,
                r_std REAL NOT NULL,
                g_std REAL NOT NULL,
                b_std REAL NOT NULL
            )
        """)

        # Optimized indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase_bookmaker_time 
            ON phase_rgb(bookmaker, timestamp DESC)
        """)

        # Performance stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                bookmaker TEXT,
                samples_collected INTEGER,
                avg_interval_ms REAL,
                batch_insert_time_ms REAL
            )
        """)

        conn.commit()
        conn.close()

        self.logger.info(f"Database ready: {self.db_path}")

    def create_worker_process(self, bookmaker_name: str, coords: Dict):
        """Create high-speed RGB collector process."""
        return HighSpeedRGBProcess(
            bookmaker_name=bookmaker_name,
            coords=coords,
            db_queue=self.db_queue,
            shutdown_event=self.shutdown_event,
        )

    def run(self):
        """Main run method."""
        print("\n" + "=" * 70)
        print("🚀 RGB COLLECTOR v3.0 - HIGH-SPEED MODE")
        print("=" * 70)
        print("\nPerformance targets:")
        print("  • 30 samples/sec per bookmaker")
        print("  • 180 samples/sec total (6 bookmakers)")
        print("  • ~650,000 samples/hour")
        print("  • Region: 360x120px (phase_region only)")
        print("\nFeatures:")
        print("  • 33ms collection interval")
        print("  • Large batch inserts (500-1000)")
        print("  • Async database writer")
        print("  • Real-time performance monitoring")
        print("=" * 70)

        self.setup_database()

        # Create shared database queue
        self.db_queue = Queue(maxsize=10000)

        # Start database writer process
        db_writer = DatabaseWriterProcess(
            db_path=self.db_path,
            db_queue=self.db_queue,
            shutdown_event=self.shutdown_event,
        )
        db_writer.start()

        while True:
            try:
                num = int(input("\nHow many bookmakers to track? (1-6): "))
                if 1 <= num <= 6:
                    break
                print("❌ Please enter 1-6")
            except ValueError:
                print("❌ Invalid input")

        bookmakers_config = self.select_bookmakers_interactive(num)

        if not bookmakers_config:
            print("\n❌ No bookmakers configured!")
            return

        if not self.verify_regions(bookmakers_config):
            print("\n❌ User cancelled. Fix regions and try again.")
            return

        # Start collector processes
        self.start_processes(bookmakers_config)

        print("\n🚀 Collecting RGB data at HIGH SPEED... (Ctrl+C to stop)")
        print("💡 Tip: Monitor logs/RGBCollectorV3.log for performance stats")
        
        self.wait_for_processes()

        # Wait for DB queue to empty
        print("\n⏳ Flushing remaining data...")
        while not self.db_queue.empty():
            time.sleep(0.5)
        
        # Stop DB writer
        db_writer.terminate()
        db_writer.join(timeout=5)

        print("\n✅ RGB collection stopped")


class HighSpeedRGBProcess(Process):
    """
    High-speed worker process for RGB collection.
    
    Optimizations:
    - Fast 33ms interval (30 fps)
    - Numpy vectorized operations
    - Large batch size
    - Async queue-based DB writes
    - Performance monitoring
    """

    # Performance settings
    TARGET_INTERVAL = 0.033  # 33ms = 30 samples/sec
    BATCH_SIZE = 500  # Increased for high-speed collection
    STATS_INTERVAL = 30  # Report stats every 30 seconds

    def __init__(
        self,
        bookmaker_name: str,
        coords: Dict,
        db_queue: Queue,
        shutdown_event: EventType,
    ):
        super().__init__(name=f"RGBCollectorV3-{bookmaker_name}")
        self.bookmaker_name = bookmaker_name
        self.coords = coords
        self.db_queue = db_queue
        self.shutdown_event = shutdown_event

        # Data buffer
        self.buffer: List[Dict] = []

        # Performance tracking
        self.samples_collected = 0
        self.last_stats_time = None
        self.interval_times = []

        self.logger = None
        self._sct = None

    def run(self):
        """Main high-speed collection loop."""
        self.logger = AviatorLogger.get_logger(
            f"RGBCollectorV3-{self.bookmaker_name}"
        )
        self.logger.info("🚀 High-speed process started")
        self.logger.info(f"Target: {1/self.TARGET_INTERVAL:.1f} samples/sec")

        try:
            self._sct = mss.mss()
            self.last_stats_time = time.time()
            last_collect_time = time.time()

            while not self.shutdown_event.is_set():
                loop_start = time.time()

                # Collect RGB stats
                rgb_stats = self.calculate_rgb_stats_fast(
                    self.coords["phase_region"]
                )

                if rgb_stats:
                    self.buffer.append(
                        {
                            "bookmaker": self.bookmaker_name,
                            "timestamp": datetime.now().isoformat(),
                            **rgb_stats,
                        }
                    )
                    self.samples_collected += 1

                    # Track interval
                    interval = loop_start - last_collect_time
                    self.interval_times.append(interval * 1000)  # ms
                    last_collect_time = loop_start

                # Batch send to DB queue
                if len(self.buffer) >= self.BATCH_SIZE:
                    self.send_to_db_queue()

                # Report stats
                if time.time() - self.last_stats_time >= self.STATS_INTERVAL:
                    self.report_stats()

                # Precise timing control
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.TARGET_INTERVAL - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # Warning if we can't keep up
                    if elapsed > self.TARGET_INTERVAL * 1.2:
                        self.logger.warning(
                            f"Collection took {elapsed*1000:.1f}ms "
                            f"(target: {self.TARGET_INTERVAL*1000:.1f}ms)"
                        )

            # Final flush
            self.send_to_db_queue()
            self.report_stats()

        except Exception as e:
            self.logger.critical(f"Critical error: {e}", exc_info=True)
        finally:
            if self._sct:
                self._sct.close()
            self.logger.info("Process stopped")

    def calculate_rgb_stats_fast(self, region: Dict) -> Optional[Dict]:
        """
        OPTIMIZED: Fast RGB statistics calculation.
        
        Optimizations:
        - Direct numpy operations (no intermediate copies)
        - Vectorized mean/std calculations
        - BGR to RGB indexing
        
        Args:
            region: Dict with 'left', 'top', 'width', 'height'
            
        Returns:
            Dict with r_avg, g_avg, b_avg, r_std, g_std, b_std or None
        """
        try:
            bbox = {
                "left": region["left"],
                "top": region["top"],
                "width": region["width"],
                "height": region["height"],
            }

            # Capture (mss returns BGRA)
            img = np.array(self._sct.grab(bbox))[:, :, :3]  # Drop alpha

            # Vectorized stats calculation (BGR order from mss)
            # Index 2=R, 1=G, 0=B in BGR format
            b_channel = img[:, :, 0]
            g_channel = img[:, :, 1]
            r_channel = img[:, :, 2]

            return {
                "r_avg": float(r_channel.mean()),
                "g_avg": float(g_channel.mean()),
                "b_avg": float(b_channel.mean()),
                "r_std": float(r_channel.std()),
                "g_std": float(g_channel.std()),
                "b_std": float(b_channel.std()),
            }

        except Exception as e:
            self.logger.error(f"Error calculating RGB stats: {e}")
            return None

    def send_to_db_queue(self):
        """Send batch to database queue."""
        if not self.buffer:
            return

        try:
            # Non-blocking put with timeout
            self.db_queue.put(self.buffer.copy(), timeout=1.0)
            self.logger.debug(f"Queued {len(self.buffer)} samples for DB insert")
            self.buffer.clear()

        except Exception as e:
            self.logger.error(f"Error queuing data: {e}")

    def report_stats(self):
        """Report performance statistics."""
        if not self.interval_times:
            return

        elapsed = time.time() - self.last_stats_time
        actual_rate = self.samples_collected / elapsed if elapsed > 0 else 0
        target_rate = 1 / self.TARGET_INTERVAL

        avg_interval = np.mean(self.interval_times)
        min_interval = np.min(self.interval_times)
        max_interval = np.max(self.interval_times)

        self.logger.info("=" * 60)
        self.logger.info(f"📊 PERFORMANCE STATS ({elapsed:.1f}s window)")
        self.logger.info(f"Samples collected: {self.samples_collected}")
        self.logger.info(
            f"Collection rate: {actual_rate:.1f}/s (target: {target_rate:.1f}/s)"
        )
        self.logger.info(f"Rate achieved: {actual_rate/target_rate*100:.1f}%")
        self.logger.info(
            f"Interval: avg={avg_interval:.1f}ms, "
            f"min={min_interval:.1f}ms, max={max_interval:.1f}ms"
        )
        self.logger.info(f"Queue size: {self.db_queue.qsize()}")
        self.logger.info("=" * 60)

        # Reset for next interval
        self.samples_collected = 0
        self.interval_times.clear()
        self.last_stats_time = time.time()


class DatabaseWriterProcess(Process):
    """
    Async database writer process.
    
    Handles all database writes in a separate process to avoid
    blocking the collector processes.
    """

    def __init__(
        self,
        db_path: Path,
        db_queue: Queue,
        shutdown_event: EventType,
    ):
        super().__init__(name="DatabaseWriter")
        self.db_path = db_path
        self.db_queue = db_queue
        self.shutdown_event = shutdown_event
        self.logger = None

        # Stats
        self.total_inserted = 0
        self.batch_times = []

    def run(self):
        """Main database writer loop."""
        self.logger = AviatorLogger.get_logger("DatabaseWriter")
        self.logger.info("Database writer started")

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA synchronous = NORMAL")  # Faster writes
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency

        try:
            while not self.shutdown_event.is_set() or not self.db_queue.empty():
                try:
                    # Get batch from queue (timeout 1s)
                    batch = self.db_queue.get(timeout=1.0)

                    # Insert batch
                    insert_start = time.time()
                    self.insert_batch(conn, batch)
                    insert_time = (time.time() - insert_start) * 1000  # ms

                    self.total_inserted += len(batch)
                    self.batch_times.append(insert_time)

                    # Log every 10 batches
                    if len(self.batch_times) % 10 == 0:
                        avg_time = np.mean(self.batch_times[-10:])
                        self.logger.info(
                            f"Inserted {len(batch)} samples in {insert_time:.1f}ms "
                            f"(avg: {avg_time:.1f}ms, total: {self.total_inserted:,})"
                        )

                except Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error inserting batch: {e}", exc_info=True)

        finally:
            conn.close()
            self.logger.info(f"Database writer stopped. Total inserted: {self.total_inserted:,}")

    def insert_batch(self, conn: sqlite3.Connection, batch: List[Dict]):
        """Insert batch of samples."""
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT INTO phase_rgb 
            (bookmaker, timestamp, r_avg, g_avg, b_avg, r_std, g_std, b_std)
            VALUES 
            (:bookmaker, :timestamp, :r_avg, :g_avg, :b_avg, :r_std, :g_std, :b_std)
        """,
            batch,
        )

        conn.commit()


def main():
    collector = RGBCollectorV3()
    collector.run()


if __name__ == "__main__":
    main() 