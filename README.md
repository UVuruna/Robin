# 🎰 Aviator Data Collector v5.0

**Multi-bookmaker data collection system with GUI control panel, ML predictions, and automated workflows.**

---

## ⚡ Quick Start (5 minutes)

```bash
# 1. Install dependencies
pip install PySide6 mss pytesseract pillow numpy scikit-learn joblib

# 2. Install Tesseract OCR
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr

# 3. Launch GUI
python main.py

# 4. Setup & Run
# - Click "⚙️ Setup Config"
# - Add bookmakers & positions
# - Click "▶️ START" on any tab
```

**That's it!** 🎉

For detailed instructions, see [Quick Start Guide](docs/01_quick_start.md)

---

## 🎯 What Can It Do?

### 📊 **Data Collection** (Main Feature)
```python
# Collects game statistics from 1-6 bookmakers simultaneously
- Round scores (final multipliers)
- Player counts & money totals
- Threshold snapshots (1.5x, 2x, 3x, 5x, 10x)
- Phase detection (BETTING → FLYING → ENDED)

# Database: SQLite with batch inserts (~20 records/sec)
```

### 🎨 **RGB Training Data** (ML Support)
```python
# Collects RGB samples for ML model training
- Phase region colors (every 500ms)
- Button state colors (red/orange/green)
- Automatic K-means clustering

# Database: Separate RGB database for training
```

### 💰 **Betting Agent** (⚠️ DEMO ONLY!)
```python
# Automated bet placement with configurable strategy
⚠️ WARNING: Uses real money! Test in DEMO mode only!

Features:
- Transaction-safe (lock mechanism)
- Configurable bet amounts & auto cash-out
- Multiple betting strategies
```

### 🕐 **Session Keeper** (Background)
```python
# Keeps sessions alive by periodic activity
- Prevents auto-logout
- Configurable check interval
- Minimal interference
```

---

## 🖥️ GUI Control Panel

```
┌─────────────────────────────────────────────────┐
│  🎰 Aviator Control Panel                       │
├─────────────────────────────────────────────────┤
│  [⚙️ Setup] [🔄 Load] [💾 Save]                │
├─────────────────────────────────────────────────┤
│  📊 Data Collector │ 🎨 RGB Collector │ ...    │
│  ┌───────────────┬─────────────────────────┐    │
│  │ STATS         │  LIVE LOGS              │    │
│  │ • Rounds: 245 │  [2025-10-19 15:30:45]  │    │
│  │ • Avg: 2.34x  │  Round ended: 3.45x     │    │
│  │ • Efficiency  │  Threshold 2x reached   │    │
│  │   [████░░] 95%│  Batch insert: 50 rows  │    │
│  └───────────────┴─────────────────────────┘    │
│  [▶️ START]  [⏹️ STOP]                         │
└─────────────────────────────────────────────────┘
```

**Features:**
- ✅ Real-time logs streaming (via threading)
- ✅ DB-polled stats (every 2-3 sec, minimal CPU)
- ✅ Tab-based layout (Data, RGB, Agent, Keeper)
- ✅ Save/load configurations

---

## 📂 Project Structure

```
Aviator/
├── main.py                   # GUI Control Panel
├── config.py                 # Configuration
├── logger.py                 # Logging system
│
├── apps/                     # Main applications
│   ├── main_data_collector.py
│   ├── rgb_collector.py
│   ├── betting_agent.py
│   └── session_keeper.py
│
├── gui/                      # GUI components
│   ├── app_controller.py     # Process control + live logs
│   ├── stats_widgets.py      # DB-polled statistics
│   ├── config_manager.py     # Config save/load
│   └── setup_dialog.py       # Setup wizard
│
├── core/                     # Core functionality
│   ├── coord_manager.py      # Coordinate system
│   ├── screen_reader.py      # OCR via Tesseract
│   ├── gui_controller.py     # Mouse/keyboard
│   └── event_collector.py    # Event handling
│
├── regions/                  # Screen region readers
│   ├── score.py              # Score OCR
│   ├── my_money.py           # Balance OCR
│   ├── other_count.py        # Player count OCR
│   └── game_phase.py         # Phase detection (K-means)
│
├── database/                 # Database layer
│   └── models.py             # SQLite schemas
│
└── docs/                     # Documentation
    ├── 01_quick_start.md
    ├── 02_gui_guide.md
    ├── 03_system_architecture.md
    └── 04_deployment.md
```

---

## 🎓 Documentation

| Doc | Description |
|-----|-------------|
| [Quick Start](docs/01_quick_start.md) | Installation & first run |
| [GUI Guide](docs/02_gui_guide.md) | GUI control panel usage |
| [Architecture](docs/03_system_architecture.md) | System design & data flow |
| [Deployment](docs/04_deployment.md) | Production deployment |
| [Troubleshooting](docs/05_troubleshooting.md) | Common issues & solutions |

---

## 🚀 Key Features

### Performance
- **Multi-bookmaker:** 1-6 bookmakers in parallel (multiprocessing)
- **Batch inserts:** 50 records per transaction (~20 records/sec)
- **Efficient:** 99%+ efficiency, minimal data loss
- **Real-time logs:** Live streaming via threading

### Reliability
- **Graceful shutdown:** Saves all pending data on Ctrl+C
- **Error handling:** Robust try-catch blocks
- **Transaction safety:** Lock mechanism for betting
- **Queue buffering:** Large buffers prevent data loss

### ML Support
- **K-means clustering:** Phase detection via RGB analysis
- **Training data:** Automatic RGB sample collection
- **Feature-ready:** Easy to extend with new ML models

---

## 📊 Expected Performance

**With 4 bookmakers @ 0.2s interval:**

| Metric | Value |
|--------|-------|
| Records/second | ~20 |
| Records/hour | ~72,000 |
| CPU usage | 30-50% |
| RAM usage | ~1.5GB |
| Database growth | ~100MB/day per bookmaker |

---

## 🛠️ System Requirements

**Minimum:**
- Python 3.8+
- 4GB RAM
- 4-core CPU
- 10GB disk space

**Recommended:**
- Python 3.10+
- 8GB+ RAM
- 8-core+ CPU
- SSD for database

**Software:**
- Tesseract OCR 5.0+
- PySide6 (GUI)
- SQLite 3.x

---

## ⚙️ Configuration

Edit `config.py` for:

```python
# Paths
paths.main_game_db = "data/databases/main_game_data.db"

# OCR
ocr_config.min_confidence = 60
ocr_config.char_whitelist = "0123456789.,x/"

# Collection
collection_config.score_thresholds = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
collection_config.batch_size_rounds = 50

# Betting (⚠️ DEMO ONLY!)
betting_config.default_bet_amount = 10.0
betting_config.default_auto_stop = 2.0
```

---

## 🔧 Troubleshooting

### Issue: Logs not appearing in GUI
**Solution:** Logs stream via threading - they should appear in real-time. If not, check `logs/` folder.

### Issue: Stats not updating
**Solution:** Stats poll DB every 2-3 sec. If frozen, restart the app.

### Issue: OCR errors
**Solution:**
1. Verify Tesseract is installed: `tesseract --version`
2. Check coordinate alignment (use region verification)
3. Ensure browser is fullscreen (F11) and zoom is 100%

For more solutions, see [Troubleshooting Guide](docs/05_troubleshooting.md)

---

## 📈 Roadmap

- [x] Multi-bookmaker data collection
- [x] GUI control panel
- [x] Real-time logs & stats
- [x] RGB training data collection
- [x] K-means phase detection
- [ ] Advanced ML predictions (in progress)
- [ ] Video processing tools
- [ ] Data analysis dashboard
- [ ] Cloud sync & backup

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

Private project for educational and research purposes.

---

## ⚠️ Disclaimer

This tool is for data collection and analysis. Betting features are for DEMO mode only. Use responsibly and in accordance with applicable terms of service.

---

## 🎯 Quick Links

- 📖 [Full Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/aviator/issues)
- 💬 [Discussions](https://github.com/yourusername/aviator/discussions)

---

**Made with ❤️ for data science and ML research**

🎰 **Good luck!** 🚀