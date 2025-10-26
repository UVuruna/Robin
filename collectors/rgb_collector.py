# collectors/rgb_collector.py
"""
RGB Collector V2 - Prikuplja RGB podatke za treniranje phase detectora.
Ne koristi shared reader jer mu ne treba OCR, samo RGB vrednosti.
"""

import time
import cv2
import numpy as np
import mss
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from core.communication.event_bus import EventPublisher, EventType


class RGBCollectorV2:
    """
    RGB Collector za prikupljanje podataka za treniranje game phase modela.
    
    Prikuplja:
    - Prosečne RGB vrednosti
    - Standardnu devijaciju RGB
    - Score (ako je vidljiv) za labelovanje
    """
    
    # Interval prikupljanja (brže jer je samo RGB extraction)
    COLLECTION_INTERVAL = 0.5  # 2 puta po sekundi
    
    def __init__(self,
                 bookmaker: str,
                 coords: Dict,
                 db_writer,
                 event_publisher: Optional[EventPublisher] = None):
        """
        Initialize RGB collector.
        
        Args:
            bookmaker: Ime kladionice
            coords: Koordinate regiona
            db_writer: BatchDatabaseWriter instanca
            event_publisher: EventPublisher za slanje eventova
        """
        self.bookmaker = bookmaker
        self.coords = coords
        self.db_writer = db_writer
        self.event_publisher = event_publisher or EventPublisher(f"RGBCollector-{bookmaker}")
        
        # Screen capture
        self.sct = mss.mss()
        
        # Phase region (glavni region za RGB)
        self.phase_region = coords.get('phase_region') or coords.get('score_region_small')
        
        # Statistics
        self.samples_collected = 0
        self.last_collection_time = 0
        
        self.logger = logging.getLogger(f"RGBCollector-{bookmaker}")
    
    def collect_cycle(self):
        """
        Jedan ciklus prikupljanja RGB podataka.
        """
        current_time = time.time()
        
        # Check interval
        if current_time - self.last_collection_time < self.COLLECTION_INTERVAL:
            return
        
        # Capture and extract RGB
        rgb_stats = self._extract_rgb_stats()
        
        if rgb_stats:
            # Save to database
            self._save_rgb_sample(rgb_stats)
            
            # Update stats
            self.samples_collected += 1
            self.last_collection_time = current_time
            
            # Log periodically
            if self.samples_collected % 100 == 0:
                self._log_statistics()
    
    def _extract_rgb_stats(self) -> Optional[Dict[str, float]]:
        """
        Extract RGB statistics from phase region.
        
        Returns:
            Dict with r_avg, g_avg, b_avg, r_std, g_std, b_std
        """
        try:
            # Capture region
            monitor = {
                "left": self.phase_region["left"],
                "top": self.phase_region["top"],
                "width": self.phase_region["width"],
                "height": self.phase_region["height"]
            }
            
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)[:, :, :3]  # Remove alpha
            
            # Convert BGR to RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Calculate statistics for each channel
            r_channel = img_rgb[:, :, 0].flatten()
            g_channel = img_rgb[:, :, 1].flatten()
            b_channel = img_rgb[:, :, 2].flatten()
            
            stats = {
                'r_avg': float(np.mean(r_channel)),
                'g_avg': float(np.mean(g_channel)),
                'b_avg': float(np.mean(b_channel)),
                'r_std': float(np.std(r_channel)),
                'g_std': float(np.std(g_channel)),
                'b_std': float(np.std(b_channel))
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error extracting RGB: {e}")
            return None
    
    def _save_rgb_sample(self, rgb_stats: Dict[str, float]):
        """Save RGB sample to database"""
        sample = {
            'bookmaker': self.bookmaker,
            'timestamp': datetime.now().isoformat(),
            'r_avg': rgb_stats['r_avg'],
            'g_avg': rgb_stats['g_avg'],
            'b_avg': rgb_stats['b_avg'],
            'r_std': rgb_stats['r_std'],
            'g_std': rgb_stats['g_std'],
            'b_std': rgb_stats['b_std']
            # phase će biti određena kasnije kroz clustering
        }
        
        self.db_writer.write('rgb_samples', sample)
        
        # Publish event periodically
        if self.samples_collected % 50 == 0:
            self.event_publisher.publish(
                EventType.DATA_COLLECTED,
                {
                    'bookmaker': self.bookmaker,
                    'type': 'rgb',
                    'count': 50
                }
            )
    
    def _log_statistics(self):
        """Log collection statistics"""
        self.logger.info(f"RGB samples collected: {self.samples_collected}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            'bookmaker': self.bookmaker,
            'samples_collected': self.samples_collected,
            'last_collection': self.last_collection_time
        }
    
    def cleanup(self):
        """Cleanup resources"""
        if self.sct:
            self.sct.close()


def rgb_collector_worker(bookmaker: str,
                         coords: Dict,
                         shared_reader,  # Not used but kept for interface consistency
                         shutdown_event,
                         db_writer,
                         event_bus,
                         **kwargs):
    """
    Worker function za RGB Collector.
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(f"Worker-RGBCollector-{bookmaker}")
    
    logger.info(f"Starting RGB Collector for {bookmaker}")
    
    # Create event publisher
    event_publisher = EventPublisher(f"RGBCollector-{bookmaker}")
    
    # Create collector
    collector = RGBCollectorV2(
        bookmaker=bookmaker,
        coords=coords,
        db_writer=db_writer,
        event_publisher=event_publisher
    )
    
    # Main loop
    loop_count = 0
    try:
        while not shutdown_event.is_set():
            # Collect RGB data
            collector.collect_cycle()
            
            # Small sleep
            time.sleep(0.05)
            
            loop_count += 1
            
            # Log alive status periodically
            if loop_count % 1200 == 0:  # Every ~60 seconds
                stats = collector.get_stats()
                logger.info(f"Alive - Stats: {stats}")
    
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
    finally:
        # Cleanup
        collector.cleanup()
        
        # Final statistics
        stats = collector.get_stats()
        logger.info(f"Stopping - Final stats: {stats}")
        
        # Publish stop event
        event_publisher.publish(
            EventType.PROCESS_STOP,
            {
                'bookmaker': bookmaker,
                'stats': stats
            }
        )