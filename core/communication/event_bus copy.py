# core/communication/event_bus.py
# VERSION: 1.0 - COMPLETE
# PURPOSE: Centralizovana komunikacija između svih komponenti

from multiprocessing import Manager
import threading
import time
import logging
from typing import Dict, List, Callable
from dataclasses import dataclass
from enum import IntEnum
from collections import defaultdict
import queue

class EventType(IntEnum):
    """Event types za komunikaciju."""
    # Game events
    ROUND_START = 1
    ROUND_END = 2
    PHASE_CHANGE = 3
    SCORE_UPDATE = 4
    THRESHOLD_CROSSED = 5
    
    # Betting events
    BET_PLACED = 10
    BET_CASHED = 11
    BET_LOST = 12
    
    # System events
    WORKER_STARTED = 20
    WORKER_STOPPED = 21
    WORKER_ERROR = 22
    WORKER_RESTARTED = 23
    
    # Data events
    DATA_COLLECTED = 30
    DATA_SAVED = 31
    BATCH_FLUSH = 32
    
    # Performance events
    OCR_SLOW = 40
    MEMORY_HIGH = 41
    CPU_HIGH = 42

@dataclass
class Event:
    """Event object."""
    type: EventType
    source: str
    data: dict
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'type': int(self.type),
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'Event':
        """Create from dictionary."""
        return cls(
            type=EventType(d['type']),
            source=d['source'],
            data=d['data'],
            timestamp=d.get('timestamp')
        )

class EventBus:
    """
    Centralni event bus za sve komponente.
    Process-safe i thread-safe.
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_queue_size = max_queue_size
        
        # Process-safe components
        self.manager = Manager()
        self.event_queue = self.manager.Queue(maxsize=max_queue_size)
        self.subscribers = self.manager.dict()
        self.lock = self.manager.Lock()
        
        # Local subscribers (for current process)
        self.local_subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        
        # Processing thread
        self.stop_event = threading.Event()
        self.processor_thread = None
        
        # Statistics
        self.stats = self.manager.dict({
            'events_sent': 0,
            'events_processed': 0,
            'events_failed': 0,
            'events_dropped': 0
        })
        
        # Event history (last 100)
        self.event_history = self.manager.list()
        
        self.start()
    
    def publish(self, event: Event):
        """
        Publish event to bus.
        
        Args:
            event: Event to publish
        """
        try:
            # Add to queue (non-blocking)
            self.event_queue.put_nowait(event.to_dict())
            
            with self.lock:
                self.stats['events_sent'] += 1
            
            # Add to history
            if len(self.event_history) >= 100:
                self.event_history.pop(0)
            self.event_history.append(event.to_dict())
            
        except queue.Full:
            self.logger.warning(f"Event queue full, dropping event: {event.type}")
            with self.lock:
                self.stats['events_dropped'] += 1
        
        except Exception as e:
            self.logger.error(f"Error publishing event: {e}")
            with self.lock:
                self.stats['events_failed'] += 1
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """
        Subscribe to event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
        """
        self.local_subscribers[event_type].append(callback)
        self.logger.debug(f"Subscribed to {event_type.name}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from event type."""
        if callback in self.local_subscribers[event_type]:
            self.local_subscribers[event_type].remove(callback)
            self.logger.debug(f"Unsubscribed from {event_type.name}")
    
    def _process_events(self):
        """Process events from queue (runs in thread)."""
        self.logger.info("Event processor started")
        
        while not self.stop_event.is_set():
            try:
                # Get event with timeout
                event_dict = self.event_queue.get(timeout=0.1)
                event = Event.from_dict(event_dict)
                
                # Process locally
                self._dispatch_event(event)
                
                with self.lock:
                    self.stats['events_processed'] += 1
                
            except queue.Empty:
                continue
            
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                with self.lock:
                    self.stats['events_failed'] += 1
        
        self.logger.info("Event processor stopped")
    
    def _dispatch_event(self, event: Event):
        """Dispatch event to local subscribers."""
        subscribers = self.local_subscribers.get(event.type, [])
        
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Subscriber error: {e}")
    
    def start(self):
        """Start event processing."""
        if self.processor_thread is None or not self.processor_thread.is_alive():
            self.stop_event.clear()
            self.processor_thread = threading.Thread(
                target=self._process_events,
                name="EventProcessor",
                daemon=True
            )
            self.processor_thread.start()
            self.logger.info("Event bus started")
    
    def stop(self, timeout: float = 5.0):
        """Stop event processing."""
        if self.processor_thread and self.processor_thread.is_alive():
            self.stop_event.set()
            self.processor_thread.join(timeout)
            
            if self.processor_thread.is_alive():
                self.logger.warning("Event processor still running")
            
            self.processor_thread = None
            self.logger.info("Event bus stopped")
    
    def get_stats(self) -> dict:
        """Get event bus statistics."""
        with self.lock:
            return dict(self.stats)
    
    def get_history(self, count: int = 10) -> List[dict]:
        """Get recent event history."""
        return list(self.event_history[-count:])
    
    def clear_queue(self):
        """Clear event queue."""
        cleared = 0
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
                cleared += 1
            except:
                break
        
        self.logger.info(f"Cleared {cleared} events from queue")
        return cleared


class EventPublisher:
    """
    Helper class for publishing events.
    Svaka komponenta kreira svoju instancu.
    """
    
    def __init__(self, source: str):
        self.source = source
        self.bus = get_event_bus()
    
    def publish(self, event_type: EventType, data: dict = None):
        """Publish event."""
        event = Event(
            type=event_type,
            source=self.source,
            data=data or {}
        )
        self.bus.publish(event)
    
    # Convenience methods
    def round_start(self, bookmaker: str):
        """Publish round start event."""
        self.publish(EventType.ROUND_START, {'bookmaker': bookmaker})
    
    def round_end(self, bookmaker: str, final_score: float):
        """Publish round end event."""
        self.publish(EventType.ROUND_END, {
            'bookmaker': bookmaker,
            'final_score': final_score
        })
    
    def phase_change(self, bookmaker: str, old_phase: int, new_phase: int):
        """Publish phase change event."""
        self.publish(EventType.PHASE_CHANGE, {
            'bookmaker': bookmaker,
            'old_phase': old_phase,
            'new_phase': new_phase
        })
    
    def score_update(self, bookmaker: str, score: float):
        """Publish score update event."""
        self.publish(EventType.SCORE_UPDATE, {
            'bookmaker': bookmaker,
            'score': score
        })
    
    def threshold_crossed(self, bookmaker: str, threshold: float, actual: float):
        """Publish threshold crossed event."""
        self.publish(EventType.THRESHOLD_CROSSED, {
            'bookmaker': bookmaker,
            'threshold': threshold,
            'actual_score': actual
        })
    
    def bet_placed(self, bookmaker: str, amount: float, auto_stop: float):
        """Publish bet placed event."""
        self.publish(EventType.BET_PLACED, {
            'bookmaker': bookmaker,
            'amount': amount,
            'auto_stop': auto_stop
        })
    
    def worker_error(self, error: str, details: dict = None):
        """Publish worker error event."""
        self.publish(EventType.WORKER_ERROR, {
            'error': error,
            'details': details or {}
        })
    
    def data_collected(self, bookmaker: str, count: int, data_type: str):
        """Publish data collected event."""
        self.publish(EventType.DATA_COLLECTED, {
            'bookmaker': bookmaker,
            'count': count,
            'type': data_type
        })


class EventSubscriber:
    """
    Helper class for subscribing to events.
    Svaka komponenta kreira svoju instancu.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.bus = get_event_bus()
        self.logger = logging.getLogger(f"EventSubscriber-{name}")
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to event type."""
        # Wrap callback with logging
        def wrapped_callback(event: Event):
            self.logger.debug(f"Received {event.type.name} from {event.source}")
            callback(event)
        
        self.bus.subscribe(event_type, wrapped_callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from event type."""
        self.bus.unsubscribe(event_type, callback)


# Singleton instance
_event_bus_instance = None

def get_event_bus() -> EventBus:
    """Get singleton event bus instance."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance

def init_event_bus(max_queue_size: int = 10000) -> EventBus:
    """Initialize event bus singleton."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus(max_queue_size)
    return _event_bus_instance