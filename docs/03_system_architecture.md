# 🏗️ System Architecture

**Technical overview of Aviator Data Collector system**

---

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│           GUI CONTROL PANEL (main.py)           │
│              PySide6 Application                │
├─────────────────────────────────────────────────┤
│  ConfigManager │ AppController │ StatsWidgets   │
└────────┬────────────────┬───────────────────────┘
         │                │
         │ config.json    │ subprocess + threading
         │                │
    ┌────▼────────────────▼────────────────────┐
    │    APP PROCESSES (multiprocessing)       │
    ├──────────────────────────────────────────┤
    │  Data Collector  │  RGB Collector  │ ... │
    │  (Process 1-6)   │  (Process 1-6)  │     │
    └────────┬─────────────────┬────────────────┘
             │                 │
             │ batch insert    │
             ▼                 ▼
    ┌─────────────────────────────────────┐
    │    SQLite DATABASES (WAL mode)      │
    ├─────────────────────────────────────┤
    │  main_game_data.db                  │
    │  rgb_training_data.db               │
    │  betting_history.db                 │
    └─────────────────────────────────────┘
```

---

## 🎨 GUI Layer

### Components

```python
main.py (QMainWindow)
├── Tabs (QTabWidget)
│   ├── Data Collector Tab
│   ├── RGB Collector Tab
│   ├── Betting Agent Tab
│   └── Session Keeper Tab
│
├── AppController
│   ├── Start/stop processes
│   ├── Capture stdout (threading)
│   └── Real-time log streaming
│
├── StatsWidgets (per tab)
│   ├── QTimer (2-3 sec intervals)
│   ├── SQL queries to DB
│   └── Update UI (Qt signals)
│
└── ConfigManager
    ├── Load/save config.json
    └── Setup dialog
```

### Log Streaming Flow

```
App Process (subprocess)
    │ stdout
    ▼
LogReader Thread
    │ line-by-line reading
    ▼
Callback Function
    │ Qt signal (thread-safe)
    ▼
QTextEdit Widget
    │ append + auto-scroll
    ▼
User sees logs in real-time
```

### Stats Polling Flow

```
QTimer (every 2 sec)
    │
    ▼
fetch_stats()
    │ SQL: SELECT ... WHERE timestamp >= session_start
    ▼
Database
    │ returns results (< 1ms)
    ▼
stats_updated signal
    │ Qt signal (thread-safe)
    ▼
update_display()
    │ update QLabel widgets
    ▼
User sees stats update
```

---

## 🔄 Data Collection Layer

### Main Data Collector

```
MainDataCollector (Main Process)
    │
    ├─► CollectorProcess 1 (Bookmaker 1)
    │   ├── ScreenReader (OCR)
    │   ├── GamePhaseDetector (K-means)
    │   ├── Batch buffer (50 items)
    │   └── Database insert
    │
    ├─► CollectorProcess 2 (Bookmaker 2)
    │   └── ... (same as above)
    │
    └─► CollectorProcess 3-6
        └── ... (same as above)
```

**Key Points:**
- Each bookmaker = separate process (multiprocessing)
- Independent OCR readers
- Individual batch buffers
- Interval: 0.2s between reads (~5 reads/sec)

### Data Flow

```
1. Screen Capture (MSS)
   ↓ 10-20ms
2. Preprocessing (OpenCV)
   - Grayscale
   - Upscale 4x
   - Thresholding
   ↓ 5-10ms
3. OCR (Tesseract)
   - Read text
   - Parse & validate
   ↓ 20-30ms
4. Batch Buffer
   - Collect 50 items
   ↓
5. Database INSERT
   - Single transaction
   ↓ 5-10ms
6. Repeat
```

**Total cycle:** ~40-70ms (leaves 130-160ms idle time per 0.2s interval)

---

## 🎯 Region Readers

### Score Reader

```python
class Score:
    def __init__(self, score_region, ...):
        self.reader = ScreenReader(
            region=score_region,
            ocr_type='score'
        )
    
    def read_current_score(self) -> float:
        img = self.reader.capture_image()
        text = self.reader.read_once()  # "1.86x"
        score = self.parse_score(text)  # 1.86
        return score if self.validate(score) else None
```

### Phase Detector (K-means)

```python
class GamePhaseDetector:
    def __init__(self, phase_region):
        self.model = load_model('game_phase_kmeans.pkl')
    
    def detect_phase(self) -> GamePhase:
        img = self.capture(phase_region)
        rgb = self.get_avg_rgb(img)  # (r, g, b)
        cluster = self.model.predict([rgb])  # K-means
        phase = self.map_cluster_to_phase(cluster)
        return phase  # BETTING, SCORE_LOW, ENDED, etc.
```

**Performance:** ~5-10ms (no OCR, pure RGB math)

---

## 💾 Database Layer

### Schema Design

```sql
-- main_game_data.db

CREATE TABLE rounds (
    id INTEGER PRIMARY KEY,
    bookmaker TEXT,
    timestamp DATETIME,
    final_score REAL,
    total_players INTEGER,
    left_players INTEGER,
    total_money REAL
);

CREATE TABLE threshold_scores (
    id INTEGER PRIMARY KEY,
    bookmaker TEXT,
    timestamp DATETIME,
    threshold REAL,  -- 1.5, 2.0, 3.0, 5.0, 10.0
    current_players INTEGER,
    current_money REAL
);

CREATE INDEX idx_rounds_bookmaker 
ON rounds(bookmaker, timestamp DESC);
```

### Batch Insert Mechanism

```python
# OLD (slow):
for item in items:
    cursor.execute("INSERT ...")
    conn.commit()  # 50 commits = slow

# NEW (fast):
items_batch = []  # Collect 50 items

with conn:  # Single transaction
    cursor.executemany("INSERT ...", items_batch)
    # 1 commit = fast

# Performance: 10x faster
```

### WAL Mode

```sql
PRAGMA journal_mode = WAL;  -- Write-Ahead Logging
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  -- 64MB cache
```

**Benefits:**
- Concurrent reads during writes
- Better performance (~10x faster writes)
- Crash recovery

---

## 🔧 Coordinate System

### Layout + Bookmaker Model

```
Base Coordinates (per bookmaker)
    │ saved in bookmaker_coords.json
    ▼
Position Offset (TL, TC, TR, BL, BC, BR)
    │ from positions dict
    ▼
CoordsManager.calculate_coords()
    │ base + offset
    ▼
Final Coordinates
    │ where to actually read screen
    ▼
ScreenReader uses these coords
```

**Example Calculation:**
```python
base = {"left": 615, "top": 420, ...}  # BalkanBet
offset = {"left": 1030, "top": 0}      # TC position

final = {
    "left": 615 + 1030 = 1645,
    "top": 420 + 0 = 420,
    ...
}
```

---

## ⚡ Performance Optimizations

### 1. Batch Processing
- **Before:** 1 transaction per item = 20 transactions/sec
- **After:** 1 transaction per 50 items = 0.4 transactions/sec
- **Improvement:** 50x reduction in I/O

### 2. Multiprocessing
- **Benefit:** Each bookmaker runs independently
- **CPU:** Parallelized across cores
- **No GIL:** True parallel processing (not threading)

### 3. Queue Buffering
- **Size:** Batch buffer of 50 items
- **Prevents:** Data loss during bursts
- **Flush:** On shutdown (graceful)

### 4. K-means Phase Detection
- **Instead of:** OCR (30-50ms)
- **Uses:** RGB clustering (5-10ms)
- **Improvement:** 3-5x faster

### 5. Preprocessing Cache
- **Grayscale:** Once per capture
- **Upscale:** Reused for all regions
- **Result:** 20-30% faster overall

---

## 🔒 Thread Safety

### GUI Threading

```python
# BAD (crashes):
def some_thread():
    widget.setText("...")  # ❌ Not thread-safe

# GOOD:
class Worker(QThread):
    signal = Signal(str)
    
    def run(self):
        self.signal.emit("...")  # ✅ Thread-safe
        
worker.signal.connect(widget.setText)
```

**Rule:** Always use Qt Signals for cross-thread UI updates

### Multiprocessing Safety

```python
# Shared data (read-only):
shutdown_event = multiprocessing.Event()

# Process-specific data (no sharing):
each_process_has_own_ScreenReader()
each_process_has_own_batch_buffer()
```

**Rule:** Minimize shared state, use Events for signaling

---

## 🛡️ Error Handling

### Graceful Shutdown

```python
try:
    while not shutdown_event.is_set():
        # Collection loop
        ...
except KeyboardInterrupt:
    pass
finally:
    # Flush batch buffer
    if batch_buffer:
        insert_batch(batch_buffer)
    # Close connections
    conn.close()
```

### OCR Validation

```python
def parse_score(text):
    try:
        score = float(text.replace('x', ''))
        if 1.0 <= score <= 1000.0:
            return score
        else:
            return None  # Invalid range
    except ValueError:
        return None  # Parse error
```

### Database Retry

```python
for attempt in range(3):
    try:
        conn.execute(...)
        break
    except sqlite3.OperationalError as e:
        if "locked" in str(e) and attempt < 2:
            time.sleep(0.1)
        else:
            raise
```

---

## 📈 Expected Throughput

### Single Bookmaker
- **Interval:** 0.2s (5 reads/sec)
- **Rounds/hour:** ~150 (25 sec/round avg)
- **Thresholds/hour:** ~300-750 (2-5 per round)
- **Total inserts/hour:** ~450-900

### Six Bookmakers
- **Reads/sec:** 30 (6 × 5)
- **Rounds/hour:** ~900
- **Thresholds/hour:** ~1,800-4,500
- **Total inserts/hour:** ~2,700-5,400
- **Batch inserts/hour:** ~54-108 (50 items each)

### Resource Usage
- **CPU:** 30-50% (6 processes)
- **RAM:** ~1.5GB (6 × 250MB)
- **Disk I/O:** ~10MB/hour (SQLite writes)
- **Network:** 0 (local only)

---

## 🔗 Component Dependencies

```
main.py
├── gui/
│   ├── PySide6
│   ├── config_manager → json
│   ├── app_controller → subprocess, threading
│   └── stats_widgets → sqlite3, QTimer
│
├── apps/
│   ├── multiprocessing
│   ├── core/
│   ├── regions/
│   └── database/
│
├── core/
│   ├── mss (screen capture)
│   ├── pytesseract (OCR)
│   ├── PIL (image processing)
│   └── cv2 (preprocessing)
│
├── regions/
│   ├── core.screen_reader
│   └── scikit-learn (K-means)
│
└── database/
    └── sqlite3
```

---

## 🎯 Key Design Decisions

### Why Multiprocessing (not Threading)?
- **GIL limitation:** Threading doesn't parallelize CPU-bound work
- **True parallelism:** Each process uses separate CPU core
- **Isolation:** Crash in one process doesn't affect others

### Why Batch Inserts?
- **I/O bottleneck:** Disk writes are slow
- **Transaction overhead:** Each commit takes time
- **Solution:** Batch 50 items = 50x less I/O

### Why K-means for Phase?
- **OCR unreliable:** Phase text can be tiny/unclear
- **RGB stable:** Phase colors are consistent
- **Fast:** No OCR overhead (~5ms)

### Why GUI Separate from Apps?
- **Decoupling:** Apps can run without GUI
- **Flexibility:** CLI or GUI - user choice
- **Stability:** GUI crash doesn't stop apps

---

## 🔧 Extension Points

Want to add features? Here's where:

### New Region Type
1. Create `regions/new_region.py`
2. Inherit from `Region`
3. Implement `read_value()`
4. Update `bookmaker_coords.json`

### New App
1. Create `apps/new_app.py`
2. Use `CoordsManager` for coords
3. Add to GUI tabs
4. Update `AppController.APP_COMMANDS`

### New Database Table
1. Update `database/models.py`
2. Add schema in `DatabaseModel`
3. Create batch insert method
4. Update stats widgets

### New ML Model
1. Train model (scikit-learn)
2. Save to `data/models/`
3. Load in relevant region reader
4. Use predictions in logic

---

## 📚 Further Reading

- [GUI Guide](02_gui_guide.md) - GUI usage details
- [Coordinate System](03_coordinate_system.md) - Coord management
- [Deployment](04_deployment_production.md) - Production setup
- [Troubleshooting](05_troubleshooting.md) - Common issues

---

**Understanding the architecture helps extend the system!** 🏗️