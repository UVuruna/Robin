# data/database/batch_writer.py
"""
Batch Database Writer - Optimizovano pisanje u bazu podataka.
Umesto pojedinačnih INSERT-a, koristi batch operacije.
50-100x brže za velike količine podataka.
"""

import sqlite3
import threading
import queue
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging
from contextlib import contextmanager
from collections import defaultdict


@dataclass
class WriteRequest:
    """Zahtev za pisanje u bazu"""
    table: str
    data: Dict[str, Any]
    callback: Optional[Callable] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class BatchConfig:
    """Konfiguracija za batch pisanje"""
    batch_size: int = 50  # Broj rekorda pre flush-a
    flush_interval: float = 2.0  # Sekunde između automatskih flush-ova
    max_queue_size: int = 10000  # Maksimalna veličina queue-a
    retry_on_error: bool = True
    max_retries: int = 3
    connection_pool_size: int = 5


class ConnectionPool:
    """
    Connection pool za SQLite.
    Održava više konekcija za paralelno pisanje.
    """
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self.connections = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self.logger = logging.getLogger("ConnectionPool")
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create initial connections
        for _ in range(pool_size):
            conn = self._create_connection()
            self.connections.put(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        """Kreiraj novu SQLite konekciju"""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-thread access
            isolation_level='DEFERRED',  # Better concurrency
            timeout=30.0
        )
        
        # Optimize for performance
        conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
        conn.execute("PRAGMA synchronous = NORMAL")  # Faster writes
        conn.execute("PRAGMA cache_size = 10000")  # Bigger cache
        conn.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
        
        return conn
    
    @contextmanager
    def get_connection(self, timeout: float = 5.0):
        """
        Context manager za dobijanje konekcije iz pool-a.
        
        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        conn = None
        try:
            conn = self.connections.get(timeout=timeout)
            yield conn
        finally:
            if conn:
                self.connections.put(conn)
    
    def close_all(self):
        """Zatvori sve konekcije"""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                conn.close()
            except queue.Empty:
                break


class BatchDatabaseWriter:
    """
    Glavni batch writer za bazu podataka.
    
    Features:
    - Batch INSERT operacije (50-100x brže)
    - Automatski flush na interval
    - Connection pooling
    - Thread-safe
    - Retry logika
    - Callback support
    """
    
    def __init__(self, 
                 db_path: str,
                 config: Optional[BatchConfig] = None):
        """
        Initialize batch writer.
        
        Args:
            db_path: Putanja do SQLite baze
            config: Konfiguracija za batching
        """
        self.db_path = Path(db_path)
        self.config = config or BatchConfig()
        
        # Connection pool
        self.connection_pool = ConnectionPool(db_path, self.config.connection_pool_size)
        
        # Buffers per table
        self.buffers = defaultdict(list)  # {table_name: [records]}
        self.buffer_lock = threading.Lock()
        
        # Write queue
        self.write_queue = queue.Queue(maxsize=self.config.max_queue_size)
        
        # Control
        self.running = False
        self.writer_thread = None
        self.flush_thread = None
        
        # Statistics
        self.stats = {
            'total_writes': 0,
            'successful_writes': 0,
            'failed_writes': 0,
            'total_flushes': 0,
            'avg_batch_size': 0,
            'last_flush_time': None
        }
        
        # Table schemas cache
        self.table_schemas = {}
        self._cache_table_schemas()
        
        # Logging
        self.logger = logging.getLogger("BatchWriter")
    
    def _cache_table_schemas(self):
        """Keširaj sheme tabela za validaciju"""
        try:
            with self.connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                
                # Get columns for each table
                for (table_name,) in tables:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    self.table_schemas[table_name] = {
                        col[1]: col[2] for col in columns  # name: type
                    }
                
                self.logger.info(f"Cached schemas for {len(self.table_schemas)} tables")
                
        except Exception as e:
            self.logger.error(f"Error caching schemas: {e}")
    
    def start(self):
        """Pokreni batch writer"""
        if self.running:
            self.logger.warning("BatchWriter already running")
            return
        
        self.running = True
        
        # Start writer thread
        self.writer_thread = threading.Thread(
            target=self._writer_loop,
            name="BatchWriter",
            daemon=False
        )
        self.writer_thread.start()
        
        # Start flush thread
        self.flush_thread = threading.Thread(
            target=self._flush_loop,
            name="BatchFlusher",
            daemon=False
        )
        self.flush_thread.start()
        
        self.logger.info("BatchWriter started")
    
    def stop(self, timeout: float = 10.0):
        """Zaustavi batch writer"""
        if not self.running:
            return
        
        self.logger.info("Stopping BatchWriter...")
        self.running = False
        
        # Flush remaining data
        self.flush_all()
        
        # Wait for threads
        if self.writer_thread:
            self.writer_thread.join(timeout)
        
        if self.flush_thread:
            self.flush_thread.join(timeout)
        
        # Close connections
        self.connection_pool.close_all()
        
        self.logger.info(f"BatchWriter stopped. Stats: {self.stats}")
    
    def write(self, 
             table: str, 
             data: Dict[str, Any],
             callback: Optional[Callable] = None):
        """
        Dodaj podatke za pisanje.
        
        Args:
            table: Ime tabele
            data: Dict sa podacima za insert
            callback: Funkcija koja se poziva posle pisanja
        """
        request = WriteRequest(table=table, data=data, callback=callback)
        
        try:
            self.write_queue.put(request, timeout=1.0)
            self.stats['total_writes'] += 1
        except queue.Full:
            self.logger.error("Write queue full, dropping request")
            self.stats['failed_writes'] += 1
    
    def write_many(self, table: str, records: List[Dict[str, Any]]):
        """
        Dodaj više rekorda odjednom.
        
        Args:
            table: Ime tabele
            records: Lista dict-ova sa podacima
        """
        for record in records:
            self.write(table, record)
    
    def _writer_loop(self):
        """Main writer loop - procesira queue"""
        self.logger.info("Writer loop started")
        
        while self.running:
            try:
                # Get request from queue
                request = self.write_queue.get(timeout=0.1)
                
                # Add to buffer
                with self.buffer_lock:
                    self.buffers[request.table].append(request)
                
                # Check if should flush
                if len(self.buffers[request.table]) >= self.config.batch_size:
                    self._flush_table(request.table)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Writer loop error: {e}", exc_info=True)
        
        self.logger.info("Writer loop stopped")
    
    def _flush_loop(self):
        """Flush loop - automatski flush na interval"""
        self.logger.info("Flush loop started")
        
        while self.running:
            try:
                time.sleep(self.config.flush_interval)
                
                # Flush all tables with data
                with self.buffer_lock:
                    tables_to_flush = list(self.buffers.keys())
                
                for table in tables_to_flush:
                    if self.buffers[table]:
                        self._flush_table(table)
                
            except Exception as e:
                self.logger.error(f"Flush loop error: {e}", exc_info=True)
        
        self.logger.info("Flush loop stopped")
    
    def _flush_table(self, table: str):
        """
        Flush buffer za specifičnu tabelu.
        
        Args:
            table: Ime tabele
        """
        with self.buffer_lock:
            if not self.buffers[table]:
                return
            
            # Take all requests from buffer
            requests = self.buffers[table].copy()
            self.buffers[table].clear()
        
        # Group by unique columns
        records = [req.data for req in requests]
        callbacks = [req.callback for req in requests if req.callback]
        
        # Perform batch insert
        success = self._batch_insert(table, records)
        
        if success:
            self.stats['successful_writes'] += len(records)
            self.stats['total_flushes'] += 1
            
            # Update average batch size
            total = self.stats['successful_writes']
            flushes = self.stats['total_flushes']
            self.stats['avg_batch_size'] = total / flushes if flushes > 0 else 0
            
            # Execute callbacks
            for callback in callbacks:
                try:
                    callback()
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")
            
            self.logger.debug(f"Flushed {len(records)} records to {table}")
        else:
            self.stats['failed_writes'] += len(records)
            
            # Re-add to buffer if retry enabled
            if self.config.retry_on_error:
                with self.buffer_lock:
                    self.buffers[table].extend(requests)
        
        self.stats['last_flush_time'] = time.time()
    
    def _batch_insert(self, table: str, records: List[Dict[str, Any]]) -> bool:
        """
        Izvrši batch INSERT.
        
        Args:
            table: Ime tabele
            records: Lista rekorda
            
        Returns:
            True ako je uspešno
        """
        if not records:
            return True
        
        retries = 0
        while retries < self.config.max_retries:
            try:
                with self.connection_pool.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Build insert query
                    columns = list(records[0].keys())
                    placeholders = ','.join(['?' for _ in columns])
                    columns_str = ','.join(columns)
                    
                    query = f"""
                        INSERT OR IGNORE INTO {table} 
                        ({columns_str}) VALUES ({placeholders})
                    """
                    
                    # Prepare values
                    values = []
                    for record in records:
                        row = tuple(record.get(col) for col in columns)
                        values.append(row)
                    
                    # Execute batch insert
                    cursor.executemany(query, values)
                    conn.commit()
                    
                    return True
                    
            except sqlite3.Error as e:
                retries += 1
                self.logger.error(
                    f"Database error (retry {retries}/{self.config.max_retries}): {e}"
                )
                if retries < self.config.max_retries:
                    time.sleep(0.5 * retries)  # Exponential backoff
            except Exception as e:
                self.logger.error(f"Unexpected error in batch insert: {e}", exc_info=True)
                break
        
        return False
    
    def flush_all(self):
        """Flush sve buffere odmah"""
        self.logger.info("Flushing all buffers...")
        
        with self.buffer_lock:
            tables = list(self.buffers.keys())
        
        for table in tables:
            self._flush_table(table)
    
    def get_stats(self) -> Dict[str, Any]:
        """Vrati statistiku"""
        return self.stats.copy()
    
    def get_buffer_size(self, table: Optional[str] = None) -> int:
        """Vrati veličinu buffer-a"""
        with self.buffer_lock:
            if table:
                return len(self.buffers.get(table, []))
            else:
                return sum(len(buf) for buf in self.buffers.values())


class OptimizedDatabaseInterface:
    """
    High-level interface za rad sa bazom.
    Kombinuje batch writing sa čitanjem.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.writer = BatchDatabaseWriter(db_path)
        self.writer.start()
        self.logger = logging.getLogger("DatabaseInterface")
    
    def insert_round(self, bookmaker: str, score: float, **kwargs):
        """Insert round podataka"""
        data = {
            'bookmaker': bookmaker,
            'timestamp': datetime.now().isoformat(),
            'final_score': score,
            **kwargs
        }
        self.writer.write('rounds', data)
    
    def insert_threshold(self, round_id: int, threshold: float, **kwargs):
        """Insert threshold podataka"""
        data = {
            'round_id': round_id,
            'timestamp': datetime.now().isoformat(),
            'threshold': threshold,
            **kwargs
        }
        self.writer.write('threshold_scores', data)
    
    def insert_bet(self, bookmaker: str, amount: float, **kwargs):
        """Insert bet podataka"""
        data = {
            'bookmaker': bookmaker,
            'timestamp': datetime.now().isoformat(),
            'bet_amount': amount,
            **kwargs
        }
        self.writer.write('bets', data)
    
    def query(self, query: str, params: Tuple = ()) -> List[Dict]:
        """
        Izvršava SELECT query.
        
        Returns:
            Lista dict-ova sa rezultatima
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_recent_rounds(self, bookmaker: str, limit: int = 100) -> List[Dict]:
        """Dobavi poslednje runde"""
        return self.query(
            """
            SELECT * FROM rounds 
            WHERE bookmaker = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (bookmaker, limit)
        )
    
    def close(self):
        """Zatvori interface"""
        self.writer.stop()


def test_batch_writer():
    """Test batch writer performanse"""
    import logging
    import random
    
    logging.basicConfig(level=logging.INFO)
    
    # Create test database
    db_path = "data/databases/test_batch.db"
    
    # Setup table
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bookmaker TEXT,
            score REAL,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    # Test batch writer
    config = BatchConfig(
        batch_size=100,
        flush_interval=1.0
    )
    
    writer = BatchDatabaseWriter(db_path, config)
    writer.start()
    
    print("\n" + "="*60)
    print("BATCH WRITER PERFORMANCE TEST")
    print("="*60)
    
    # Write test data
    start_time = time.time()
    num_records = 10000
    
    for i in range(num_records):
        writer.write('test_data', {
            'bookmaker': random.choice(['Admiral', 'BalkanBet', 'Merkur']),
            'score': random.uniform(1.0, 100.0),
            'timestamp': datetime.now().isoformat()
        })
        
        if i % 1000 == 0:
            print(f"Written {i}/{num_records} records...")
    
    # Wait for flush
    writer.flush_all()
    time.sleep(0.5)
    
    elapsed = time.time() - start_time
    rate = num_records / elapsed
    
    print("\nResults:")
    print(f"  Records written: {num_records}")
    print(f"  Time elapsed: {elapsed:.2f}s")
    print(f"  Write rate: {rate:.0f} records/second")
    print(f"\nStats: {writer.get_stats()}")
    
    # Compare with direct writes
    print("\n" + "-"*60)
    print("COMPARING WITH DIRECT WRITES...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    start_time = time.time()
    for i in range(1000):  # Only 1000 for direct
        cursor.execute(
            "INSERT INTO test_data (bookmaker, score, timestamp) VALUES (?, ?, ?)",
            ('Direct', random.uniform(1.0, 100.0), datetime.now().isoformat())
        )
        conn.commit()
    
    elapsed_direct = time.time() - start_time
    rate_direct = 1000 / elapsed_direct
    
    print("\nDirect write results:")
    print("  Records written: 1000")
    print(f"  Time elapsed: {elapsed_direct:.2f}s")
    print(f"  Write rate: {rate_direct:.0f} records/second")
    
    improvement = rate / rate_direct
    print(f"\n🚀 Batch writer is {improvement:.1f}x faster!")
    
    conn.close()
    writer.stop()
    
    # Cleanup
    Path(db_path).unlink()
    
    print("\n" + "="*60)


if __name__ == "__main__":
    test_batch_writer()