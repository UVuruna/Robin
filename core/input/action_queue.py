"""
Module: ActionQueue
Purpose: FIFO queue for betting transactions with atomic execution
Version: 2.0

This module provides:
- FIFO queue for betting actions (no priorities - simple queue)
- Thread-safe operation
- Integration with TransactionController
- Action tracking and statistics
- Timeout handling
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional
from datetime import datetime


class ActionStatus(Enum):
    """Action execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Action:
    """
    Represents a betting action to be executed.

    Attributes:
        action_id: Unique action identifier
        bookmaker: Bookmaker name
        bet_amount: Bet amount
        auto_stop: Auto cash-out multiplier
        callback: Optional callback function after execution
        timeout: Maximum execution time in seconds (default: 30s)
        created_at: Timestamp when action was created
        started_at: Timestamp when execution started
        completed_at: Timestamp when execution completed
        status: Current action status
        result: Execution result data
        error: Error message if failed
    """
    action_id: str
    bookmaker: str
    bet_amount: float
    auto_stop: float
    callback: Optional[Callable[[Dict], None]] = None
    timeout: float = 30.0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ActionStatus = ActionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def duration(self) -> Optional[float]:
        """Get action duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def wait_time(self) -> float:
        """Get wait time before execution in seconds."""
        if self.started_at:
            return (self.started_at - self.created_at).total_seconds()
        return (datetime.now() - self.created_at).total_seconds()


class ActionQueue:
    """
    FIFO queue for betting transactions.

    Features:
    - Thread-safe FIFO queue
    - No action limit (must process all)
    - Timeout handling per action
    - Statistics tracking
    - Action cancellation support
    """

    def __init__(self, transaction_controller: Optional[Any] = None):
        """
        Initialize ActionQueue.

        Args:
            transaction_controller: TransactionController instance for executing actions
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Queue storage
        self._queue: deque[Action] = deque()
        self._lock = threading.RLock()

        # Transaction controller
        self.transaction_controller = transaction_controller

        # Action tracking
        self._actions_by_id: Dict[str, Action] = {}
        self._action_counter = 0

        # Statistics
        self.stats = {
            "total_queued": 0,
            "total_executed": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_timeout": 0,
            "total_cancelled": 0,
            "avg_wait_time": 0.0,
            "avg_execution_time": 0.0
        }

        self.logger.info("ActionQueue initialized")

    def _generate_action_id(self) -> str:
        """Generate unique action ID."""
        with self._lock:
            self._action_counter += 1
            return f"action_{self._action_counter}_{int(time.time() * 1000)}"

    def enqueue(
        self,
        bookmaker: str,
        bet_amount: float,
        auto_stop: float,
        callback: Optional[Callable[[Dict], None]] = None,
        timeout: float = 30.0
    ) -> str:
        """
        Add betting action to queue.

        Args:
            bookmaker: Bookmaker name
            bet_amount: Bet amount
            auto_stop: Auto cash-out multiplier
            callback: Optional callback after execution
            timeout: Maximum execution time

        Returns:
            Action ID for tracking

        Example:
            >>> queue = ActionQueue()
            >>> action_id = queue.enqueue("Mozzart", 100.0, 2.0)
            >>> print(f"Queued: {action_id}")
        """
        with self._lock:
            # Create action
            action = Action(
                action_id=self._generate_action_id(),
                bookmaker=bookmaker,
                bet_amount=bet_amount,
                auto_stop=auto_stop,
                callback=callback,
                timeout=timeout
            )

            # Add to queue
            self._queue.append(action)
            self._actions_by_id[action.action_id] = action

            # Update stats
            self.stats["total_queued"] += 1

            self.logger.info(
                f"Queued action {action.action_id}: {bookmaker} "
                f"bet={bet_amount}, stop={auto_stop} (queue size: {len(self._queue)})"
            )

            return action.action_id

    def dequeue(self) -> Optional[Action]:
        """
        Remove and return next action from queue (FIFO).

        Returns:
            Next Action or None if queue is empty
        """
        with self._lock:
            if self._queue:
                action = self._queue.popleft()
                action.status = ActionStatus.EXECUTING
                action.started_at = datetime.now()
                self.stats["total_executed"] += 1

                self.logger.debug(f"Dequeued action {action.action_id}")
                return action
            return None

    def execute_next(self) -> bool:
        """
        Execute next action in queue.

        Returns:
            True if action was executed, False if queue is empty

        Example:
            >>> queue = ActionQueue(transaction_controller)
            >>> while queue.execute_next():
            ...     time.sleep(0.1)
        """
        action = self.dequeue()

        if not action:
            return False

        # Check if transaction controller is available
        if not self.transaction_controller:
            self.logger.error("No TransactionController available")
            self._mark_failed(action, "No TransactionController")
            return False

        try:
            # Execute transaction
            success = self.transaction_controller.place_bet(
                bookmaker=action.bookmaker,
                bet_amount=action.bet_amount,
                auto_stop=action.auto_stop,
                timeout=action.timeout
            )

            if success:
                self._mark_completed(action, {"success": True})
            else:
                self._mark_failed(action, "Transaction returned False")

        except Exception as e:
            self.logger.error(f"Action {action.action_id} failed: {e}")
            self._mark_failed(action, str(e))

        return True

    def _mark_completed(self, action: Action, result: Dict[str, Any]):
        """Mark action as completed successfully."""
        with self._lock:
            action.status = ActionStatus.COMPLETED
            action.completed_at = datetime.now()
            action.result = result

            # Update stats
            self.stats["total_completed"] += 1
            self._update_timing_stats(action)

            self.logger.info(
                f"Action {action.action_id} completed in {action.duration():.2f}s"
            )

            # Call callback if provided
            if action.callback:
                try:
                    action.callback(result)
                except Exception as e:
                    self.logger.error(f"Callback failed for {action.action_id}: {e}")

    def _mark_failed(self, action: Action, error: str):
        """Mark action as failed."""
        with self._lock:
            action.status = ActionStatus.FAILED
            action.completed_at = datetime.now()
            action.error = error

            # Update stats
            self.stats["total_failed"] += 1
            self._update_timing_stats(action)

            self.logger.error(f"Action {action.action_id} failed: {error}")

            # Call callback with error
            if action.callback:
                try:
                    action.callback({"success": False, "error": error})
                except Exception as e:
                    self.logger.error(f"Callback failed for {action.action_id}: {e}")

    def _update_timing_stats(self, action: Action):
        """Update timing statistics."""
        # Update average wait time
        wait_time = action.wait_time()
        total = self.stats["total_executed"]
        current_avg = self.stats["avg_wait_time"]
        self.stats["avg_wait_time"] = (current_avg * (total - 1) + wait_time) / total

        # Update average execution time
        if action.duration():
            exec_time = action.duration()
            completed = self.stats["total_completed"] + self.stats["total_failed"]
            if completed > 0:
                current_exec_avg = self.stats["avg_execution_time"]
                self.stats["avg_execution_time"] = (
                    current_exec_avg * (completed - 1) + exec_time
                ) / completed

    def get_action_status(self, action_id: str) -> Optional[ActionStatus]:
        """
        Get status of specific action.

        Args:
            action_id: Action identifier

        Returns:
            ActionStatus or None if not found
        """
        with self._lock:
            action = self._actions_by_id.get(action_id)
            return action.status if action else None

    def get_action(self, action_id: str) -> Optional[Action]:
        """Get action by ID."""
        with self._lock:
            return self._actions_by_id.get(action_id)

    def cancel_action(self, action_id: str) -> bool:
        """
        Cancel pending action.

        Args:
            action_id: Action identifier

        Returns:
            True if cancelled, False if not found or already executing
        """
        with self._lock:
            action = self._actions_by_id.get(action_id)

            if not action:
                return False

            if action.status != ActionStatus.PENDING:
                self.logger.warning(
                    f"Cannot cancel action {action_id} - status: {action.status}"
                )
                return False

            # Remove from queue
            try:
                self._queue.remove(action)
                action.status = ActionStatus.CANCELLED
                action.completed_at = datetime.now()
                self.stats["total_cancelled"] += 1

                self.logger.info(f"Cancelled action {action_id}")
                return True

            except ValueError:
                return False

    def clear_queue(self) -> int:
        """
        Clear all pending actions.

        Returns:
            Number of actions cleared
        """
        with self._lock:
            count = len(self._queue)

            for action in self._queue:
                action.status = ActionStatus.CANCELLED
                action.completed_at = datetime.now()
                self.stats["total_cancelled"] += 1

            self._queue.clear()

            self.logger.warning(f"Cleared {count} pending actions from queue")
            return count

    def size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self.size() == 0

    def get_pending_actions(self) -> list[Action]:
        """Get list of all pending actions."""
        with self._lock:
            return list(self._queue)

    def get_stats(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                **self.stats,
                "current_queue_size": len(self._queue),
                "total_tracked": len(self._actions_by_id)
            }

    def cleanup(self):
        """Cleanup resources."""
        with self._lock:
            cleared = self.clear_queue()
            self._actions_by_id.clear()

            self.logger.info(
                f"ActionQueue cleanup - Cleared {cleared} actions. "
                f"Stats: {self.get_stats()}"
            )


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    queue = ActionQueue()

    # Add some test actions
    id1 = queue.enqueue("Mozzart", 100.0, 2.0)
    id2 = queue.enqueue("BalkanBet", 50.0, 1.5)
    id3 = queue.enqueue("Soccer", 200.0, 3.0)

    print(f"Queue size: {queue.size()}")
    print(f"Pending actions: {len(queue.get_pending_actions())}")
    print(f"Stats: {queue.get_stats()}")

    # Cancel one
    queue.cancel_action(id2)
    print(f"After cancel, queue size: {queue.size()}")
