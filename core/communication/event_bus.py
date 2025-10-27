# core/communication/event_bus.py
"""
Event Bus - Centralizovan sistem za komunikaciju između procesa.
Koristi multiprocessing Queue i Manager za thread-safe i process-safe komunikaciju.
"""

import time
import threading
import multiprocessing as mp
from multiprocessing import Process
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging


class EventType(Enum):
    """Tipovi eventova u sistemu"""
    
    # Game events
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    SCORE_UPDATE = "score_update"
    THRESHOLD_CROSSED = "threshold_crossed"
    PHASE_CHANGE = "phase_change"
    
    # Betting events
    BET_PLACED = "bet_placed"
    BET_WON = "bet_won"
    BET_LOST = "bet_lost"
    CASH_OUT = "cash_out"
    
    # System events
    PROCESS_START = "process_start"
    PROCESS_STOP = "process_stop"
    PROCESS_ERROR = "process_error"
    HEALTH_CHECK = "health_check"
    
    # Data events
    DATA_COLLECTED = "data_collected"
    BATCH_READY = "batch_ready"
    DATABASE_WRITE = "database_write"
    
    # Control events
    SHUTDOWN = "shutdown"
    PAUSE = "pause"
    RESUME = "resume"
    CONFIG_UPDATE = "config_update"


@dataclass
class Event:
    """Event objekat koji se šalje kroz bus"""
    
    type: EventType
    source: str  # Ko šalje event (e.g., "MainCollector-Admiral")
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 5  # 1-10, 1 je najviši prioritet
    id: str = field(default_factory=lambda: f"{time.time()}_{mp.current_process().pid}")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'type': self.type.value,
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp,
            'priority': self.priority,
            'id': self.id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Event':
        """Create from dictionary"""
        return cls(
            type=EventType(data['type']),
            source=data['source'],
            data=data['data'],
            timestamp=data['timestamp'],
            priority=data.get('priority', 5),
            id=data.get('id', '')
        )


class EventBus:
    """
    Centralni event bus za komunikaciju između procesa.
    Thread-safe i process-safe.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern sa thread-safe inicijalizacijom"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            
            # Multiprocessing components
            self.manager = Manager()
            self.event_queue = self.manager.Queue()
            self.subscribers = self.manager.dict()  # {event_type: [subscriber_ids]}
            self.callbacks = {}  # Local callbacks (not shared between processes)
            
            # Control
            self.running = False
            self.dispatcher_thread = None
            self.dispatcher_process = None
            
            # Statistics
            self.stats = self.manager.dict({
                'events_sent': 0,
                'events_processed': 0,
                'events_failed': 0,
                'last_event_time': None
            })
            
            # Logging
            self.logger = logging.getLogger("EventBus")
            
            # Event history (circular buffer)
            self.history_size = 1000
            self.event_history = self.manager.list()
            
            # Rate limiting
            self.rate_limits = {}  # {source: {'count': 0, 'reset_time': time}}
            self.rate_limit_window = 60  # seconds
            self.rate_limit_max = 1000  # max events per window

    def start(self, use_process: bool = True):
        """
        Pokreni event bus.
        
        Args:
            use_process: Ako je True, koristi Process za dispatcher (za multiprocessing)
                        Ako je False, koristi Thread (za single process)
        """
        if self.running:
            self.logger.warning("EventBus already running")
            return
        
        self.running = True
        
        if use_process:
            # Use separate process for dispatcher (multiprocessing mode)
            self.dispatcher_process = Process(
                target=self._dispatcher_loop,
                name="EventBusDispatcher",
                daemon=True
            )
            self.dispatcher_process.start()
            self.logger.info("EventBus started in multiprocessing mode")
        else:
            # Use thread for dispatcher (single process mode)
            self.dispatcher_thread = threading.Thread(
                target=self._dispatcher_loop,
                name="EventBusDispatcher",
                daemon=True
            )
            self.dispatcher_thread.start()
            self.logger.info("EventBus started in threading mode")

    def stop(self, timeout: float = 5.0):
        """Zaustavi event bus"""
        if not self.running:
            return
        
        self.logger.info("Stopping EventBus...")
        self.running = False
        
        # Send shutdown event
        self.publish(Event(EventType.SHUTDOWN, source="EventBus"))
        
        # Wait for dispatcher to stop
        if self.dispatcher_process and self.dispatcher_process.is_alive():
            self.dispatcher_process.join(timeout)
            if self.dispatcher_process.is_alive():
                self.dispatcher_process.terminate()
        
        if self.dispatcher_thread and self.dispatcher_thread.is_alive():
            self.dispatcher_thread.join(timeout)
        
        self.logger.info(f"EventBus stopped. Stats: {dict(self.stats)}")

    def subscribe(self, 
                 event_type: EventType,
                 callback: Callable[[Event], None],
                 subscriber_id: Optional[str] = None) -> str:
        """
        Pretplati se na event type.
        
        Args:
            event_type: Tip eventa
            callback: Funkcija koja se poziva za event
            subscriber_id: Jedinstveni ID subscriber-a
            
        Returns:
            Subscriber ID
        """
        if not subscriber_id:
            subscriber_id = f"{mp.current_process().name}_{id(callback)}"
        
        # Store callback locally
        if event_type not in self.callbacks:
            self.callbacks[event_type] = {}
        self.callbacks[event_type][subscriber_id] = callback
        
        # Register in shared dict
        if event_type.value not in self.subscribers:
            self.subscribers[event_type.value] = []
        
        subscribers_list = list(self.subscribers[event_type.value])
        if subscriber_id not in subscribers_list:
            subscribers_list.append(subscriber_id)
            self.subscribers[event_type.value] = subscribers_list
        
        self.logger.debug(f"Subscribed {subscriber_id} to {event_type.value}")
        return subscriber_id

    def unsubscribe(self, event_type: EventType, subscriber_id: str):
        """Otkaži pretplatu"""
        # Remove from local callbacks
        if event_type in self.callbacks:
            self.callbacks[event_type].pop(subscriber_id, None)
        
        # Remove from shared dict
        if event_type.value in self.subscribers:
            subscribers_list = list(self.subscribers[event_type.value])
            if subscriber_id in subscribers_list:
                subscribers_list.remove(subscriber_id)
                self.subscribers[event_type.value] = subscribers_list
        
        self.logger.debug(f"Unsubscribed {subscriber_id} from {event_type.value}")

    def publish(self, event: Event):
        """
        Objavi event.
        
        Args:
            event: Event za objavljivanje
        """
        # Rate limiting
        if not self._check_rate_limit(event.source):
            self.logger.warning(f"Rate limit exceeded for {event.source}")
            return
        
        # Add to queue
        self.event_queue.put((event.priority, event.to_dict()))
        
        # Update stats
        self.stats['events_sent'] = self.stats['events_sent'] + 1
        self.stats['last_event_time'] = time.time()
        
        # Add to history
        self._add_to_history(event)
        
        self.logger.debug(f"Published {event.type.value} from {event.source}")

    def publish_async(self, event: Event):
        """Asinhrono objavljivanje (non-blocking)"""
        thread = threading.Thread(target=self.publish, args=(event,))
        thread.daemon = True
        thread.start()

    def _dispatcher_loop(self):
        """Dispatcher loop - procesira eventove iz queue-a"""
        self.logger.info("EventBus dispatcher started")
        
        while self.running:
            try:
                # Get event from queue with timeout
                priority, event_dict = self.event_queue.get(timeout=0.1)
                event = Event.from_dict(event_dict)
                
                # Process event
                self._process_event(event)
                
            except Exception as e:
                self.logger.error(f"Dispatcher error: {e}", exc_info=True)
                self.stats['events_failed'] = self.stats['events_failed'] + 1
            except:
                # Timeout or empty queue
                continue
        
        self.logger.info("EventBus dispatcher stopped")

    def _process_event(self, event: Event):
        """Procesira pojedinačni event"""
        try:
            # Get subscribers
            subscribers = self.subscribers.get(event.type.value, [])
            
            # Call callbacks
            if event.type in self.callbacks:
                for subscriber_id, callback in self.callbacks[event.type].items():
                    if subscriber_id in subscribers:
                        try:
                            callback(event)
                        except Exception as e:
                            self.logger.error(
                                f"Callback error for {subscriber_id}: {e}",
                                exc_info=True
                            )
            
            # Update stats
            self.stats['events_processed'] = self.stats['events_processed'] + 1
            
        except Exception as e:
            self.logger.error(f"Error processing event: {e}", exc_info=True)
            self.stats['events_failed'] = self.stats['events_failed'] + 1

    def _check_rate_limit(self, source: str) -> bool:
        """Proveri rate limit za source"""
        current_time = time.time()
        
        if source not in self.rate_limits:
            self.rate_limits[source] = {
                'count': 0,
                'reset_time': current_time + self.rate_limit_window
            }
        
        limit_info = self.rate_limits[source]
        
        # Reset if window expired
        if current_time > limit_info['reset_time']:
            limit_info['count'] = 0
            limit_info['reset_time'] = current_time + self.rate_limit_window
        
        # Check limit
        if limit_info['count'] >= self.rate_limit_max:
            return False
        
        limit_info['count'] += 1
        return True

    def _add_to_history(self, event: Event):
        """Dodaj event u istoriju (circular buffer)"""
        history = list(self.event_history)
        history.append(event.to_dict())
        
        # Keep only last N events
        if len(history) > self.history_size:
            history = history[-self.history_size:]
        
        # Update shared list
        self.event_history[:] = history

    def get_history(self, 
                   event_type: Optional[EventType] = None,
                   source: Optional[str] = None,
                   limit: int = 100) -> List[Event]:
        """
        Dobavi istoriju eventova.
        
        Args:
            event_type: Filter po tipu
            source: Filter po source-u
            limit: Maksimalan broj rezultata
            
        Returns:
            Lista eventova
        """
        history = list(self.event_history)
        events = [Event.from_dict(e) for e in history]
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        if source:
            events = [e for e in events if e.source == source]
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        
        return events[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Dobavi statistiku"""
        return dict(self.stats)

    def broadcast(self, event: Event):
        """
        Broadcast event svim procesima.
        Koristi se za globalne eventove kao što su SHUTDOWN.
        """
        event.priority = 1  # Highest priority
        self.publish(event)
        self.logger.info(f"Broadcasted {event.type.value}")


# Global instance
event_bus = EventBus()


class EventPublisher:
    """Helper klasa za lakše publikovanje eventova"""
    
    def __init__(self, source: str):
        self.source = source
        self.bus = event_bus
    
    def publish(self, event_type: EventType, data: Dict[str, Any] = None, priority: int = 5):
        """Publish event sa predefinisanim source-om"""
        event = Event(
            type=event_type,
            source=self.source,
            data=data or {},
            priority=priority
        )
        self.bus.publish(event)
    
    def round_start(self, bookmaker: str):
        """Shortcut za ROUND_START event"""
        self.publish(EventType.ROUND_START, {'bookmaker': bookmaker})
    
    def round_end(self, bookmaker: str, final_score: float):
        """Shortcut za ROUND_END event"""
        self.publish(EventType.ROUND_END, {
            'bookmaker': bookmaker,
            'final_score': final_score
        })
    
    def score_update(self, bookmaker: str, score: float):
        """Shortcut za SCORE_UPDATE event"""
        self.publish(EventType.SCORE_UPDATE, {
            'bookmaker': bookmaker,
            'score': score
        }, priority=7)  # Lower priority for frequent events


class EventSubscriber:
    """Helper klasa za lakše subscribovanje na eventove"""
    
    def __init__(self, subscriber_id: str):
        self.subscriber_id = subscriber_id
        self.bus = event_bus
        self.subscriptions = {}
    
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """Subscribe na event"""
        sub_id = self.bus.subscribe(event_type, callback, f"{self.subscriber_id}_{event_type.value}")
        self.subscriptions[event_type] = sub_id
    
    def unsubscribe(self, event_type: EventType):
        """Unsubscribe od eventa"""
        if event_type in self.subscriptions:
            self.bus.unsubscribe(event_type, self.subscriptions[event_type])
            del self.subscriptions[event_type]
    
    def unsubscribe_all(self):
        """Unsubscribe od svih eventova"""
        for event_type in list(self.subscriptions.keys()):
            self.unsubscribe(event_type)


def test_event_bus():
    """Test event bus functionality"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Start event bus
    bus = EventBus()
    bus.start(use_process=False)  # Use threading for test
    
    # Create publisher and subscriber
    publisher = EventPublisher("TestPublisher")
    subscriber = EventSubscriber("TestSubscriber")
    
    # Define callback
    def on_round_start(event: Event):
        print(f"Round started: {event.data}")
    
    def on_round_end(event: Event):
        print(f"Round ended: {event.data}")
    
    # Subscribe
    subscriber.subscribe(EventType.ROUND_START, on_round_start)
    subscriber.subscribe(EventType.ROUND_END, on_round_end)
    
    # Publish events
    publisher.round_start("TestBookmaker")
    time.sleep(0.1)
    
    publisher.round_end("TestBookmaker", 2.34)
    time.sleep(0.1)
    
    # Check stats
    print(f"Stats: {bus.get_stats()}")
    
    # Check history
    history = bus.get_history(limit=10)
    print(f"History: {[e.type.value for e in history]}")
    
    # Cleanup
    subscriber.unsubscribe_all()
    bus.stop()


if __name__ == "__main__":
    test_event_bus()