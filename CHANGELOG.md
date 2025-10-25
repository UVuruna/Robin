# Changelog

All notable changes to Aviator Data Collector project.

## [5.1.0] - 2025-10-19 - GUI Control Panel

### 🎨 Added - GUI Control Panel
- **New GUI application** (`main.py`) with PySide6
  - Tab-based layout (Data Collector, RGB Collector, Betting Agent, Session Keeper)
  - Real-time log streaming via threading callbacks
  - DB-polled statistics (every 2-3 sec) with minimal CPU usage
  - Configuration save/load system
  - Setup wizard dialog

### 📦 New Modules
- `gui/app_controller.py` - Process control with live log capture
- `gui/stats_widgets.py` - Database-polling widgets (OPCIJA A)
- `gui/config_manager.py` - JSON config management
- `gui/setup_dialog.py` - Interactive setup wizard

### 🔧 Changes
- **Log streaming:** Apps write to `stdout` → GUI captures via thread
- **Stats polling:** Widgets query DB every 2-3 sec (not real-time queue)
- **Config format:** Centralized JSON config (`config.json`)

### ✅ Technical Details
- **Live logs:** Threading with `subprocess.PIPE` + callback
- **Stats:** DB polling with `QTimer` (2-3 sec intervals)
- **Thread-safe:** Qt signals for cross-thread updates
- **CPU-efficient:** < 1ms per stats query

---

## [5.0.0] - 2025-10-18 - Coordinate System Overhaul

### 🔧 Changed - New Coordinate System
- **Layout-based coordinates:** Base coords + position offsets
- **JSON format change:**
  ```json
  {
    "positions": { "TL": {...}, "TC": {...}, ... },
    "bookmakers": { "BalkanBet": {...}, ... }
  }
  ```

### 📦 New Modules
- `core/coord_manager.py` v5.0 - Layout + bookmaker system
- `utils/region_visualizer.py` - Automatic verification screenshots
- `utils/pre_run_verification.py` - System check before running

### 🔧 Updated Apps
- `apps/main_data_collector.py` v1.0
  - Uses `CoordsManager`
  - Interactive bookmaker + position selection
  - Screenshot verification before start
  
- `apps/rgb_collector.py` v1.0
  - Collects phase + button RGB data
  - Batch insert (100 rows)
  - Unlabeled data (for K-means)
  
- `apps/betting_agent.py` v1.0
  - Basic update to use `CoordsManager`
  - ⚠️ Transaction-safe with Lock

### 🐛 Fixed
- **Type hints:** `Event` instead of `MPEvent` (correct multiprocessing type)
- **Region verification:** Auto-screenshot before starting collection
- **Multi-monitor:** Initial support (manual offset for now)

---

## [4.0.0] - 2025-10-15 - Multiprocessing Architecture

### 🚀 Added
- **Parallel processing:** Each bookmaker runs in separate process
- **Batch database operations:** 50 items per transaction
- **Queue-based data flow:** 10,000 item buffer
- **Phase detection:** K-means RGB clustering

### 📦 New Structure
```
apps/
├── base_app.py              # Base template (optional)
├── main_data_collector.py   # Main data collection
├── rgb_collector.py         # RGB training data
└── betting_agent.py         # Automated betting (DEMO only!)
```

### 🔧 Database Schema
- **main_game_data.db:**
  - `rounds` table (final scores)
  - `threshold_scores` table (snapshots at 1.5x, 2x, etc.)
  
- **rgb_training_data.db:**
  - `phase_rgb` table (phase region colors)
  - `button_rgb` table (button state colors)

### Performance
- **Throughput:** ~20 items/sec (4 bookmakers @ 0.2s)
- **Efficiency:** 99%+
- **Database growth:** ~100MB/day per bookmaker

---

## [3.0.0] - 2025-10-04 - Critical Fixes

### 🐛 Fixed - Major Bugs
1. **Logger not writing:**
   - Added missing `return root_logger` in `logger.py`
   - Now creates per-process log files
   
2. **Low database throughput:**
   - Changed from single inserts to batch (50 items)
   - Performance: 24% → 100% efficiency (4.1x improvement)
   
3. **Poor predictions:**
   - Added 20+ features (was only 3 RGB values)
   - Improved Random Forest + Gradient Boosting

### 📦 New Files
- `database/database_worker.py` - Batch queue worker
- `prediction_analyzer.py` - ML prediction system
- `diagnostic.py` - System diagnostics
- `performance_analyzer.py` - Performance analysis

### 📊 Performance Improvements
- **Before:** 35K records in 2 hours (24% efficiency)
- **After:** 144K records in 2 hours (100% efficiency)
- **Improvement:** 4.1x faster

---

## [2.1.0] - 2025-10-02 - Phase Detection

### 🎨 Added
- **GamePhase detection** via K-means clustering
  - 6 phases: ENDED, LOADING, BETTING, SCORE_LOW, SCORE_MID, SCORE_HIGH
  - RGB-based (not OCR, very fast ~5-10ms)
  
- **K-means model:** `game_phase_kmeans.pkl`

### 🔧 Updated
- `regions/game_phase.py` - Added `GamePhaseDetector` class
- `config.py` - Added `GamePhase` enum

---

## [2.0.0] - 2025-09-30 - Multiprocessing Support

### 🚀 Added
- **Multiprocessing:** Each bookmaker in separate process
- **GUI Controller:** Sequential bet placement (thread-safe)
- **Database Worker:** Separate thread for DB writes

### 📦 New Structure
```
main/
├── bookmaker_orchestrator.py   # Coordinates all processes
├── bookmaker_process.py        # Worker process per bookmaker
└── gui_controller.py           # Betting controller (threading)
```

### 🔧 Architecture
- **Main process:** Coordinator
- **Bookmaker processes:** N parallel workers (multiprocessing)
- **GUI controller:** Sequential betting (threading)
- **DB worker:** Batch writes (threading)

---

## [1.0.0] - 2025-09-25 - Initial Release

### 🎯 Core Features
- **Screen reading:** OCR via Tesseract
- **Coordinate management:** JSON-based configs
- **Single bookmaker:** Basic data collection

### 📦 Initial Modules
- `main/screen_reader.py` - OCR functionality
- `main/coord_manager.py` - Coordinate management
- `regions/` - Screen region handlers
- `database/` - SQLite database layer

### 🔧 Database
- Simple SQLite schema
- Single-insert writes (no batching)

---

## Legend

- 🎨 **Added** - New features
- 🔧 **Changed** - Modifications to existing features
- 🐛 **Fixed** - Bug fixes
- 🚀 **Performance** - Performance improvements
- 📦 **Dependencies** - Dependency updates
- ⚠️ **Deprecated** - Features marked for removal
- ❌ **Removed** - Removed features

---

## Version Format

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR** - Incompatible API changes
- **MINOR** - New features (backward-compatible)
- **PATCH** - Bug fixes (backward-compatible)