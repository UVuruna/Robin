"""
Module: RGB Collector
Purpose: Collects RGB data for ML phase detector training
Version: 2.0 (Refactored to use BaseCollector)

This collector:
- Captures raw RGB pixel data from screen regions
- Calculates RGB statistics (mean, std deviation)
- Stores data for ML model training
- Does NOT use OCR (only pixel analysis)
"""

import time
import logging
import cv2
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime

from collectors.base_collector import BaseCollector
from core.capture.screen_capture import ScreenCapture
from core.communication.shared_state import SharedGameState
from core.communication.event_bus import EventPublisher, EventType
from data.database.batch_writer import BatchDatabaseWriter


class RGBCollector(BaseCollector):
    """
    RGB Collector for ML training data.

    Collects raw RGB pixel statistics for training phase detection models.
    Unlike other collectors, this one directly captures screen data
    instead of using SharedGameState.

    Features:
    - Direct screen capture of phase region
    - RGB channel statistics (mean, std)
    - High-frequency sampling (2 Hz)
    - Data for ML clustering and phase detection
    """

    # Collection interval (faster than other collectors)
    COLLECTION_INTERVAL = 0.5  # 2 samples per second

    def __init__(
        self,
        bookmaker: str,
        coords: Dict,
        shared_state: SharedGameState,
        db_writer: BatchDatabaseWriter,
        event_publisher: Optional[EventPublisher] = None
    ):
        """
        Initialize RGB collector.

        Args:
            bookmaker: Name of bookmaker
            coords: Screen region coordinates
            shared_state: SharedGameState (not used, but required for interface)
            db_writer: BatchDatabaseWriter instance
            event_publisher: Optional EventPublisher
        """
        super().__init__(bookmaker, shared_state, db_writer, event_publisher)

        # Screen capture
        self.screen_capture = ScreenCapture()
        self.coords = coords

        # Phase region (main region for RGB extraction)
        self.phase_region = coords.get("phase_region") or coords.get("score_region_small")

        if not self.phase_region:
            raise ValueError(f"No phase region found in coords for {bookmaker}")

        # Timing
        self.last_collection_time = 0.0

        # Statistics
        self.samples_collected = 0

        self.logger.info(f"RGB collector initialized for {bookmaker}")

    def get_collection_name(self) -> str:
        """Get collector name."""
        return "RGBCollector"

    def collect_cycle(self) -> None:
        """
        Perform one RGB collection cycle.

        Captures screen region and extracts RGB statistics.
        """
        current_time = time.time()

        # Check collection interval
        if current_time - self.last_collection_time < self.COLLECTION_INTERVAL:
            return

        # Extract RGB statistics
        rgb_stats = self._extract_rgb_stats()

        if rgb_stats:
            # Save to database
            rgb_data = {
                "bookmaker": self.bookmaker,
                "timestamp": datetime.now().isoformat(),
                **rgb_stats
            }

            if self.write_to_database("rgb_samples", rgb_data):
                self.samples_collected += 1

            # Update timing
            self.last_collection_time = current_time

            # Publish event periodically
            if self.samples_collected % 50 == 0:
                self.publish_event(
                    EventType.DATA_COLLECTED,
                    {
                        "type": "rgb",
                        "count": self.samples_collected
                    },
                    priority=7  # Low priority
                )

            # Log periodically
            if self.samples_collected % 100 == 0:
                self.log_stats()

    def _extract_rgb_stats(self) -> Optional[Dict[str, float]]:
        """
        Extract RGB statistics from phase region.

        Returns:
            Dictionary with r_avg, g_avg, b_avg, r_std, g_std, b_std
        """
        try:
            # Capture region
            img = self.screen_capture.capture_region(self.phase_region)

            if img is None:
                self.logger.warning("Failed to capture screen region")
                return None

            # Convert BGR (OpenCV) to RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Extract channels
            r_channel = img_rgb[:, :, 0].flatten()
            g_channel = img_rgb[:, :, 1].flatten()
            b_channel = img_rgb[:, :, 2].flatten()

            # Calculate statistics
            stats = {
                "r_avg": float(np.mean(r_channel)),
                "g_avg": float(np.mean(g_channel)),
                "b_avg": float(np.mean(b_channel)),
                "r_std": float(np.std(r_channel)),
                "g_std": float(np.std(g_channel)),
                "b_std": float(np.std(b_channel))
            }

            return stats

        except Exception as e:
            self.logger.error(f"Error extracting RGB stats: {e}")
            return None

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate RGB data before writing.

        Args:
            data: RGB data to validate

        Returns:
            True if valid
        """
        required_fields = [
            "bookmaker", "timestamp",
            "r_avg", "g_avg", "b_avg",
            "r_std", "g_std", "b_std"
        ]

        # Check required fields
        for field in required_fields:
            if field not in data:
                self.logger.warning(f"Missing required field: {field}")
                return False

        # Validate RGB values (0-255 range)
        for channel in ["r", "g", "b"]:
            avg = data.get(f"{channel}_avg")
            std = data.get(f"{channel}_std")

            if not isinstance(avg, (int, float)) or not (0 <= avg <= 255):
                self.logger.warning(f"Invalid {channel}_avg: {avg}")
                return False

            if not isinstance(std, (int, float)) or std < 0:
                self.logger.warning(f"Invalid {channel}_std: {std}")
                return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        base_stats = super().get_stats()

        # Add RGB-specific stats
        base_stats.update({
            "samples_collected": self.samples_collected,
            "last_collection": self.last_collection_time,
            "samples_per_minute": (
                self.samples_collected / (self.stats.uptime_seconds() / 60.0)
                if self.stats.uptime_seconds() > 0
                else 0.0
            )
        })

        return base_stats

    def cleanup(self) -> None:
        """Cleanup RGB collector resources."""
        self.logger.info("RGB collector cleanup")

        # Log final sampling stats
        self.logger.info(f"Total RGB samples collected: {self.samples_collected}")

        # Call base cleanup
        super().cleanup()


if __name__ == "__main__":
    # Testing
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )

    from core.communication.shared_state import get_shared_state
    from data.database.batch_writer import BatchConfig

    print("=== RGB Collector Test ===\n")

    # Test coordinates
    test_coords = {
        "score_region_small": {
            "left": 100,
            "top": 100,
            "width": 100,
            "height": 30
        }
    }

    # Create collector
    shared_state = get_shared_state()
    db_config = BatchConfig(batch_size=10, flush_interval=1.0)
    db_writer = BatchDatabaseWriter("test_rgb.db", db_config)
    db_writer.start()

    collector = RGBCollector(
        bookmaker="TestBookmaker",
        coords=test_coords,
        shared_state=shared_state,
        db_writer=db_writer
    )

    print("Collecting RGB samples for 5 seconds...\n")

    # Run for 5 seconds
    start_time = time.time()
    while time.time() - start_time < 5.0:
        collector.run_cycle()
        time.sleep(0.1)

    # Show statistics
    print("\n=== Statistics ===")
    stats = collector.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    # Cleanup
    collector.cleanup()
    db_writer.stop()
