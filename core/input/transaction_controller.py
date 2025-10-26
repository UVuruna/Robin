# core/input/transaction_controller.py
"""
Transaction Controller - Atomski GUI kontroler
Garantuje da se svaka betting operacija izvršava u celosti ili uopšte ne.
"""

import threading
import queue
import time
import uuid
from typing import Tuple, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
import pyautogui
from enum import Enum
import logging

# Configure pyautogui for safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


class TransactionStatus(Enum):
    """Status transakcije"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Transaction:
    """Transakcija za GUI operaciju"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    bookmaker: str = ""
    action_type: str = ""  # 'place_bet', 'cash_out', 'click'
    params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, 1 je najveći prioritet
    status: TransactionStatus = TransactionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None


class TransactionController:
    """
    Centralizovan kontroler za sve GUI operacije.
    Garantuje atomske transakcije i thread-safety.
    """

    # Singleton pattern
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            
            # Transaction queue (priority queue)
            self.transaction_queue = queue.PriorityQueue()
            
            # Active transactions tracking
            self.active_transactions = {}
            self.completed_transactions = {}
            
            # Thread control
            self.running = False
            self.worker_thread = None
            self.transaction_lock = threading.RLock()  # Reentrant lock
            
            # Statistics
            self.stats = {
                'total_transactions': 0,
                'successful': 0,
                'failed': 0,
                'avg_execution_time': 0,
                'last_error': None
            }
            
            # Logging
            self.logger = logging.getLogger("TransactionController")
            
            # Action delays (customizable)
            self.delays = {
                'click': 0.05,
                'type': 0.02,  # per character
                'key_combo': 0.1,
                'after_action': 0.1,
                'between_retries': 1.0
            }

    def start(self):
        """Pokreni controller"""
        if self.running:
            self.logger.warning("Controller already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(
            target=self._process_transactions,
            name="TransactionWorker",
            daemon=False
        )
        self.worker_thread.start()
        self.logger.info("Transaction Controller started")

    def stop(self, timeout: float = 5.0):
        """Zaustavi controller"""
        if not self.running:
            return
        
        self.logger.info("Stopping Transaction Controller...")
        self.running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout)
            if self.worker_thread.is_alive():
                self.logger.warning("Worker thread did not stop gracefully")
        
        self.logger.info(f"Controller stopped. Stats: {self.stats}")

    def submit_transaction(self, transaction: Transaction) -> str:
        """
        Podnesi transakciju za izvršavanje.
        
        Returns:
            Transaction ID
        """
        # Priority queue expects (priority, item) tuple
        # Lower number = higher priority
        self.transaction_queue.put((transaction.priority, transaction))
        self.active_transactions[transaction.id] = transaction
        self.stats['total_transactions'] += 1
        
        self.logger.debug(f"Transaction {transaction.id} submitted: {transaction.action_type}")
        return transaction.id

    def place_bet(
        self,
        bookmaker: str,
        amount: float,
        auto_stop: float,
        amount_coords: Tuple[int, int],
        auto_stop_coords: Tuple[int, int],
        play_button_coords: Tuple[int, int],
        priority: int = 5,
        callback: Optional[Callable] = None
    ) -> str:
        """
        Postavi bet - atomska operacija.
        
        Returns:
            Transaction ID
        """
        transaction = Transaction(
            bookmaker=bookmaker,
            action_type="place_bet",
            params={
                'amount': amount,
                'auto_stop': auto_stop,
                'amount_coords': amount_coords,
                'auto_stop_coords': auto_stop_coords,
                'play_button_coords': play_button_coords
            },
            priority=priority,
            callback=callback
        )
        
        return self.submit_transaction(transaction)

    def click(
        self,
        coords: Tuple[int, int],
        bookmaker: str = "unknown",
        priority: int = 5,
        callback: Optional[Callable] = None
    ) -> str:
        """Klikni na koordinate"""
        transaction = Transaction(
            bookmaker=bookmaker,
            action_type="click",
            params={'coords': coords},
            priority=priority,
            callback=callback
        )
        
        return self.submit_transaction(transaction)

    def get_transaction_status(self, transaction_id: str) -> Optional[TransactionStatus]:
        """Proveri status transakcije"""
        if transaction_id in self.active_transactions:
            return self.active_transactions[transaction_id].status
        elif transaction_id in self.completed_transactions:
            return self.completed_transactions[transaction_id].status
        return None

    def cancel_transaction(self, transaction_id: str) -> bool:
        """
        Otkaži transakciju ako još nije počela.
        
        Returns:
            True ako je uspešno otkazana
        """
        if transaction_id in self.active_transactions:
            transaction = self.active_transactions[transaction_id]
            if transaction.status == TransactionStatus.PENDING:
                transaction.status = TransactionStatus.CANCELLED
                self.completed_transactions[transaction_id] = transaction
                del self.active_transactions[transaction_id]
                self.logger.info(f"Transaction {transaction_id} cancelled")
                return True
        return False

    def _process_transactions(self):
        """Worker thread - procesira transakcije iz queue-a"""
        self.logger.info("Transaction worker started")
        
        while self.running:
            try:
                # Get transaction with timeout
                priority, transaction = self.transaction_queue.get(timeout=0.1)
                
                # Skip if cancelled
                if transaction.status == TransactionStatus.CANCELLED:
                    self.transaction_queue.task_done()
                    continue
                
                # Process transaction
                self._execute_transaction(transaction)
                
                # Mark as done
                self.transaction_queue.task_done()
                
                # Small pause between transactions
                time.sleep(self.delays['after_action'])
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in worker thread: {e}", exc_info=True)
                time.sleep(0.5)
        
        self.logger.info("Transaction worker stopped")

    def _execute_transaction(self, transaction: Transaction):
        """
        Izvrši pojedinačnu transakciju.
        CRITICAL: Ovo mora biti atomsko!
        """
        with self.transaction_lock:
            try:
                # Update status
                transaction.status = TransactionStatus.PROCESSING
                transaction.started_at = time.time()
                
                self.logger.info(f"Executing {transaction.action_type} for {transaction.bookmaker}")
                
                # Route to appropriate handler
                if transaction.action_type == "place_bet":
                    success = self._execute_place_bet(transaction)
                elif transaction.action_type == "click":
                    success = self._execute_click(transaction)
                else:
                    raise ValueError(f"Unknown action type: {transaction.action_type}")
                
                # Handle result
                if success:
                    transaction.status = TransactionStatus.COMPLETED
                    transaction.completed_at = time.time()
                    self.stats['successful'] += 1
                    
                    # Update average execution time
                    exec_time = transaction.completed_at - transaction.started_at
                    self.stats['avg_execution_time'] = (
                        (self.stats['avg_execution_time'] * (self.stats['successful'] - 1) + exec_time) 
                        / self.stats['successful']
                    )
                    
                    self.logger.info(
                        f"Transaction {transaction.id} completed in {exec_time:.2f}s"
                    )
                else:
                    # Retry logic
                    if transaction.retry_count < transaction.max_retries:
                        transaction.retry_count += 1
                        transaction.status = TransactionStatus.PENDING
                        self.logger.warning(
                            f"Transaction {transaction.id} failed, retry {transaction.retry_count}/{transaction.max_retries}"
                        )
                        time.sleep(self.delays['between_retries'])
                        # Re-queue for retry
                        self.transaction_queue.put((transaction.priority, transaction))
                    else:
                        transaction.status = TransactionStatus.FAILED
                        transaction.completed_at = time.time()
                        self.stats['failed'] += 1
                        self.logger.error(f"Transaction {transaction.id} failed after {transaction.max_retries} retries")
                
                # Move to completed if finished
                if transaction.status in [TransactionStatus.COMPLETED, TransactionStatus.FAILED]:
                    self.completed_transactions[transaction.id] = transaction
                    del self.active_transactions[transaction.id]
                    
                    # Execute callback if provided
                    if transaction.callback:
                        try:
                            transaction.callback(transaction)
                        except Exception as e:
                            self.logger.error(f"Callback error: {e}")
                
            except Exception as e:
                transaction.status = TransactionStatus.FAILED
                transaction.error = str(e)
                transaction.completed_at = time.time()
                self.stats['failed'] += 1
                self.stats['last_error'] = str(e)
                
                self.completed_transactions[transaction.id] = transaction
                if transaction.id in self.active_transactions:
                    del self.active_transactions[transaction.id]
                
                self.logger.error(f"Transaction {transaction.id} error: {e}", exc_info=True)

    def _execute_place_bet(self, transaction: Transaction) -> bool:
        """
        Izvrši place_bet transakciju.
        
        ATOMSKA OPERACIJA - sve ili ništa!
        """
        try:
            params = transaction.params
            
            # Step 1: Click amount field
            pyautogui.click(params['amount_coords'])
            time.sleep(self.delays['click'])
            
            # Step 2: Select all and type amount
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(self.delays['key_combo'])
            
            amount_str = str(params['amount'])
            for char in amount_str:
                pyautogui.press(char)
                time.sleep(self.delays['type'])
            
            # Step 3: Click auto-stop field
            pyautogui.click(params['auto_stop_coords'])
            time.sleep(self.delays['click'])
            
            # Step 4: Select all and type auto-stop
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(self.delays['key_combo'])
            
            auto_stop_str = str(params['auto_stop'])
            for char in auto_stop_str:
                pyautogui.press(char)
                time.sleep(self.delays['type'])
            
            # Step 5: Click play button
            pyautogui.click(params['play_button_coords'])
            time.sleep(self.delays['click'])
            
            self.logger.info(
                f"Bet placed: {params['amount']} @ {params['auto_stop']}x for {transaction.bookmaker}"
            )
            
            return True
            
        except pyautogui.FailSafeException:
            self.logger.warning("Fail-safe triggered - mouse moved to corner")
            return False
        except Exception as e:
            self.logger.error(f"Error placing bet: {e}")
            transaction.error = str(e)
            return False

    def _execute_click(self, transaction: Transaction) -> bool:
        """Izvrši click transakciju"""
        try:
            coords = transaction.params['coords']
            pyautogui.click(coords)
            time.sleep(self.delays['click'])
            return True
        except Exception as e:
            self.logger.error(f"Error clicking: {e}")
            transaction.error = str(e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Vrati statistiku"""
        return self.stats.copy()

    def clear_completed_transactions(self):
        """Obriši završene transakcije (za čišćenje memorije)"""
        count = len(self.completed_transactions)
        self.completed_transactions.clear()
        self.logger.info(f"Cleared {count} completed transactions")


# Singleton instance
transaction_controller = TransactionController()


def test_transaction_controller():
    """Test funkcija"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    controller = TransactionController()
    controller.start()
    
    try:
        # Test bet placement
        trans_id = controller.place_bet(
            bookmaker="TestBookmaker",
            amount=10.0,
            auto_stop=2.0,
            amount_coords=(100, 200),
            auto_stop_coords=(100, 250),
            play_button_coords=(150, 300),
            priority=1,
            callback=lambda t: print(f"Transaction {t.id} completed with status {t.status}")
        )
        
        print(f"Submitted transaction: {trans_id}")
        
        # Wait for completion
        time.sleep(3)
        
        # Check status
        status = controller.get_transaction_status(trans_id)
        print(f"Final status: {status}")
        
        # Print stats
        print(f"Stats: {controller.get_stats()}")
        
    finally:
        controller.stop()


if __name__ == "__main__":
    test_transaction_controller()