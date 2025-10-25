# 🎰 Robin Project - File Structure
**Aviator Data Collector v5.2 - Multi-Bookmaker System**

---

## 📁 Project Overview

```
Robin/
├── 📄 Root Configuration
├── 🎮 apps/          - Main Applications
├── 🔧 core/          - Core System Logic
├── 👁️  regions/       - Screen Region Readers
├── 💾 database/      - Database Layer
├── 🖥️  gui/           - GUI Control Panel
├── 🤖 ai/            - Machine Learning
├── 🛠️  utils/         - Utility Tools
├── 🧪 tests/         - Testing Suite
├── 📦 data/          - Data Storage
├── 📝 logs/          - Log Files
└── 📚 docs/          - Documentation
```

---

## 📄 Root Files

| File | Status | Description |
|------|--------|-------------|
| `main.py` | ✅ **ACTIVE** | GUI Application Entry Point |
| `config.py` | ✅ **ACTIVE** | Configuration Management |
| `config.json` | ✅ **ACTIVE** | User Configuration File |
| `logger.py` | ✅ **ACTIVE** | Centralized Logging System |
| `requirements.txt` | ✅ **ACTIVE** | Python Dependencies |
| `README.md` | ✅ **ACTIVE** | Project Overview & Quick Start |
| `CHANGELOG.md` | ✅ **ACTIVE** | Version History |
| `javascript.txt` | ✅ **ACTIVE** | CSS Injection Code for Browsers |
| `structure.md` | ✅ **ACTIVE** | This File - Project Structure |
| `project_structure.txt` | 📄 **GENERATED** | Auto-generated File Tree |
| `__init__.py` | ✅ **ACTIVE** | Python Package Marker |

---

## 🎮 apps/ - Main Applications

**Purpose:** Standalone programs that can run independently

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package exports |
| `base_app.py` | ✅ **ACTIVE** | Base template for all apps |
| `main_data_collector.py` | ✅ **ACTIVE** | **Program 1** - Multi-bookmaker data collection |
| `rgb_collector.py` | ✅ **ACTIVE** | **Program 2** - RGB training data collection |
| `betting_agent.py` | ✅ **ACTIVE** | **Program 3** - Automated betting system |
| `session_keeper.py` | ✅ **ACTIVE** | **Program 4** - Keep sessions alive |
| `prediction_agent.py` | ✅ **ACTIVE** | **Program 5** - ML-based predictions |

**Run:** `python apps/<app_name>.py` or via GUI

---

## 🔧 core/ - Core System Logic

**Purpose:** Fundamental system components used across all apps

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package exports |
| `coord_manager.py` | ✅ **ACTIVE** | Coordinate system management (v5.x) |
| `screen_reader.py` | ✅ **ACTIVE** | Screenshot capture & OCR |
| `ocr_processor.py` | ✅ **ACTIVE** | Tesseract OCR wrapper |
| `smart_validator.py` | ✅ **ACTIVE** | OCR result validation & correction |
| `gui_controller.py` | ✅ **ACTIVE** | Mouse & keyboard automation |
| `event_collector.py` | ✅ **ACTIVE** | Event management system |
| `bookmaker_process.py` | ✅ **ACTIVE** | Individual bookmaker process handler |
| `bookmaker_orchestrator.py` | ✅ **ACTIVE** | Multi-bookmaker coordination |

**Key Features:**
- New coordinate system (base coords + position offsets)
- OCR with automatic validation & correction
- Multi-bookmaker parallelization

---

## 👁️ regions/ - Screen Region Readers

**Purpose:** Individual screen region handlers for data extraction

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package exports |
| `base_region.py` | ✅ **ACTIVE** | Base class for all regions |
| `score.py` | ✅ **ACTIVE** | Game score OCR (e.g., "1.50x") |
| `my_money.py` | ✅ **ACTIVE** | User balance OCR |
| `other_money.py` | ✅ **ACTIVE** | Other player balance OCR |
| `other_count.py` | ✅ **ACTIVE** | Player count OCR |
| `game_phase.py` | ✅ **ACTIVE** | Game phase detection (K-means) |

**How it works:** Each region class handles one specific screen area with specialized OCR preprocessing

---

## 💾 database/ - Database Layer

**Purpose:** SQLite database management and optimization

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package exports |
| `models.py` | ✅ **ACTIVE** | **PRIMARY** - SQLAlchemy models & DB operations |
| `setup.py` | ✅ **ACTIVE** | Database initialization |
| `optimizer.py` | ✅ **ACTIVE** | Performance optimization & cleanup |
| `writer.py` | ✅ **ACTIVE** | Batch writer for high-throughput |
| `worker.py` | ✅ **ACTIVE** | Background worker process |
| `database.py` | ✅ **ACTIVE** | Legacy database utilities |

**Main Database:** `data/databases/main_game_data.db`

---

## 🖥️ gui/ - GUI Control Panel

**Purpose:** PySide6 GUI application for controlling all programs

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package exports |
| `app_controller.py` | ✅ **ACTIVE** | Process control + live log streaming |
| `stats_widgets.py` | ✅ **ACTIVE** | Real-time statistics display (DB polling) |
| `config_manager.py` | ✅ **ACTIVE** | Configuration save/load |
| `setup_dialog.py` | ✅ **ACTIVE** | Setup wizard dialog |
| `log_reader.py` | ✅ **ACTIVE** | Live log file reader |
| `stats_queue.py` | ✅ **ACTIVE** | Stats queue management |

**Features:**
- Start/stop all programs from one interface
- Real-time logs streaming
- Live statistics (updates every 2-3 seconds)
- Configuration management

**Run:** `python main.py`

---

## 🤖 ai/ - Machine Learning

**Purpose:** ML models for game phase prediction and color classification

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package exports |
| `color_collector.py` | ✅ **ACTIVE** | Collect RGB training data |
| `color_selector.py` | ✅ **ACTIVE** | Interactive RGB labeling tool |
| `model_trainer.py` | ✅ **ACTIVE** | Train K-means clustering models |
| `phase_predictor.py` | ✅ **ACTIVE** | Predict game phase from RGB |

**Models:**
- `game_phase_kmeans.pkl` - K-means for game phase (waiting/flying/crashed)
- `bet_button_kmeans.pkl` - K-means for bet button state

---

## 🛠️ utils/ - Utility Tools

**Purpose:** Standalone tools for development, debugging, and maintenance

### 📍 Coordinate Tools
| File | Status | Description |
|------|--------|-------------|
| `region_editor.py` | ✅ **ACTIVE** | Interactive coordinate editor |
| `region_visualizer.py` | ✅ **ACTIVE** | Visualize & verify coordinates |

### 🔍 Debug & Analysis
| File | Status | Description |
|------|--------|-------------|
| `diagnostic.py` | ✅ **ACTIVE** | System diagnostics |
| `debug_monitor.py` | ✅ **ACTIVE** | Real-time debug monitor |
| `performance_analyzer.py` | ✅ **ACTIVE** | Performance metrics |
| `data_analyzer.py` | ✅ **ACTIVE** | Database data analysis |

### ✅ Testing & Verification
| File | Status | Description |
|------|--------|-------------|
| `pre_run_verification.py` | ✅ **ACTIVE** | Pre-run system check |
| `quick_test.py` | ✅ **ACTIVE** | Quick system test |

### 📹 Video Processing Tools
| File | Status | Description |
|------|--------|-------------|
| `video_log/batch_video_processor.py` | 🗂️ **ARCHIVE** | Batch video processing |
| `video_log/mkv_to_mp4.py` | 🗂️ **ARCHIVE** | Video format conversion |
| `video_log/video_region_editor.py` | 🗂️ **ARCHIVE** | Video region editor |
| `video_log/video_screenshot_extractor.py` | 🗂️ **ARCHIVE** | Extract frames from video |

**Note:** Video tools are archived but available if needed for future video analysis features

### 🔧 Other
| File | Status | Description |
|------|--------|-------------|
| `list_structure.py` | ✅ **ACTIVE** | Generate project structure tree |

---

## 🧪 tests/ - Testing Suite

**Purpose:** Unit tests and integration tests

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ **ACTIVE** | Package marker |
| `quick_check.py` | ✅ **ACTIVE** | Quick system check |
| `test_betting.py` | ✅ **ACTIVE** | Betting agent tests |
| `test_ocr_accuracy.py` | ✅ **ACTIVE** | OCR accuracy tests |
| `test_reader.py` | ✅ **ACTIVE** | Screen reader tests |
| `screenshots/` | 📸 **DATA** | Test screenshots |

**Run:** `python tests/<test_name>.py`

---

## 📦 data/ - Data Storage

### 📍 coordinates/
**Coordinate configuration files**
- `bookmaker_coords.json` - Main coordinate file (v5.x format)
- `video_regions.json` - Video processing regions (archived)

### 💾 databases/
**SQLite databases**
- `main_game_data.db` - **PRIMARY** - All game data (rounds, bets)
- `game_phase.db` - Game phase training data
- `bet_button.db` - Bet button training data

### 🤖 models/
**Trained ML models**
- `game_phase_kmeans.pkl` - Game phase classifier
- `game_phase_weighted.pkl` - Weighted phase classifier
- `bet_button_kmeans.pkl` - Bet button classifier
- `bet_button_weighted.pkl` - Weighted button classifier
- `model_mapping.json` - Model metadata

### 📸 video_screenshots/
**Screenshot storage for video processing** (archived feature)

---

## 📝 logs/ - Log Files

**Purpose:** Application logs (auto-rotated: 10MB × 5 backups)

| File | Description |
|------|-------------|
| `main.log` | Main application logs |
| `error.log` | Error-only logs |
| `main_data_collector.log` | Data collector logs |
| `rgb_collector.log` | RGB collector logs |
| `betting_agent.log` | Betting agent logs |

**Retention:** 5 rotated backups per log file

---

## 📚 docs/ - Documentation

**Purpose:** Complete project documentation

| File | Description |
|------|-------------|
| `01_quick_start.md` | Installation & first run (5 minutes) |
| `02_gui_guide.md` | GUI control panel usage |
| `03_coordinate_system.md` | Coordinate system guide |
| `03_system_architecture.md` | System design & architecture |
| `04_deployment_production.md` | Production deployment guide |
| `05_troubleshooting.md` | Common issues & solutions |

**Start here:** `01_quick_start.md`

---

## 📊 analysis/ - Analysis Tools & Data

**Purpose:** Data analysis scripts and exported data

| File | Status | Description |
|------|--------|-------------|
| `analysis_readme.md` | ✅ **ACTIVE** | Analysis guide |
| `betting_stats.py` | ✅ **ACTIVE** | Betting statistics analyzer |
| `data_extractor.py` | ✅ **ACTIVE** | Extract data from databases |
| `log_processor.py` | ✅ **ACTIVE** | Process log files |
| `style_getter.py` | ✅ **ACTIVE** | Extract styling patterns |

**Data folders:** (not tracked in git)
- `csv/` - Exported CSV data
- `txt/` - Exported TXT data

---

## 🎯 Quick Navigation

### For Users
1. **Getting Started:** `docs/01_quick_start.md`
2. **Run GUI:** `python main.py`
3. **Configuration:** Edit `config.json`

### For Developers
1. **System Architecture:** `docs/03_system_architecture.md`
2. **Core Logic:** `core/` folder
3. **Add New App:** Extend `apps/base_app.py`

### For Troubleshooting
1. **Common Issues:** `docs/05_troubleshooting.md`
2. **Check Logs:** `logs/` folder
3. **Run Diagnostics:** `python utils/diagnostic.py`

---

## 📈 Project Stats

- **Total Python Files:** ~60 active files
- **Lines of Code:** ~15,000+ lines
- **Version:** 5.2
- **Last Updated:** 2025-10-19

---

## 🔄 File Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ **ACTIVE** | Currently used in production |
| 📄 **GENERATED** | Auto-generated file |
| 🗂️ **ARCHIVE** | Archived but available |
| 📸 **DATA** | Data storage folder |
| ⚠️ **DEPRECATED** | Will be removed in future |

---

**Generated:** 2025-10-19  
**Structure Version:** 2.0