# 🖥️ GUI Control Panel - User Guide

**Version:** 2.0  
**Last Updated:** 2025-10-19

---

## 📋 Overview

The GUI Control Panel is a PySide6-based application for managing all Aviator data collection apps from a single interface.

**Features:**
- ✅ Tab-based layout (one tab per app)
- ✅ Real-time log streaming
- ✅ Database-polled statistics
- ✅ Configuration save/load
- ✅ Multi-app support (run multiple apps simultaneously)

---

## 🚀 Installation

### Prerequisites
```bash
# Install PySide6
pip install PySide6

# Verify installation
python -c "import PySide6; print('✅ PySide6 installed')"
```

### Launch
```bash
python main.py
```

---

## 🎮 Using the GUI

### First Time Setup

#### 1. **Open Setup Dialog**
Click **⚙️ Setup Config** button

#### 2. **Configure Dual Monitor** (if applicable)
- Check "Use dual monitor setup" if you have 2 monitors
- This adjusts coordinate offsets automatically

#### 3. **Add Bookmakers**
Click **Add Bookmaker** button:
- **Name:** BalkanBet, Mozzart, etc.
- **Position:** TL, TC, TR, BL, BC, BR
  - TL = Top-Left
  - TC = Top-Center
  - TR = Top-Right
  - BL = Bottom-Left
  - BC = Bottom-Center
  - BR = Bottom-Right

Repeat for up to 6 bookmakers.

#### 4. **Configure Betting Agent** (optional)
- **Bet Amount:** Default bet size (e.g., 10.0)
- **Auto Cashout:** Multiplier to auto cash-out (e.g., 2.0)

⚠️ **WARNING:** Betting Agent uses real money! Test in DEMO mode only!

#### 5. **Configure Session Keeper** (optional)
- **Check Interval:** How often to keep session alive (seconds)

#### 6. **Save Configuration**
- Click **OK** to close setup dialog
- Click **💾 Save Setup** to save to `config.json`

---

### Running Applications

#### Data Collector Tab

**Purpose:** Collect game statistics (scores, player counts, money totals)

**Steps:**
1. Go to **📊 Data Collector** tab
2. Click **▶️ START**
3. Watch logs on the right
4. Watch stats on the left (updates every 2 sec)
5. Click **⏹️ STOP** to stop

**Stats Displayed:**
- Total Rounds
- Average Score
- Score Distribution (1.0-1.5x, 1.5-2.0x, etc.)

---

#### RGB Collector Tab

**Purpose:** Collect RGB training data for ML models

**Steps:**
1. Go to **🎨 RGB Collector** tab
2. Click **▶️ START**
3. Let it collect samples (every 500ms)
4. Click **⏹️ STOP** to stop

**Stats Displayed:**
- Total Samples
- Phase Samples
- Button Samples

---

#### Betting Agent Tab

**Purpose:** Automated bet placement (⚠️ DEMO ONLY!)

**Steps:**
1. ⚠️ **Ensure you're in DEMO mode!**
2. Go to **💰 Betting Agent** tab
3. Click **▶️ START**
4. Stop options:
   - **🛑 GRACEFUL STOP:** Finishes current cycle
   - **⚡ INSTANT STOP:** Kills immediately

**Stats Displayed:**
- Current Balance
- Total Bets
- Win Rate
- Net Profit (green/red)

---

#### Session Keeper Tab

**Purpose:** Keep sessions alive by periodic activity

**Steps:**
1. Go to **⏰ Session Keeper** tab
2. Click **▶️ START**
3. It will check every X seconds (from config)
4. Click **⏹️ STOP** to stop

**Stats Displayed:**
- Status
- Check Interval
- Last Check Time

---

### Loading Saved Configuration

Click **🔄 Load Last Setup** to load `config.json`

---

## 📊 Understanding the Interface

### Layout

```
┌─────────────────────────────────────────────────┐
│  🎰 Aviator Control Panel                      │
├─────────────────────────────────────────────────┤
│  [⚙️ Setup] [🔄 Load] [💾 Save]                │
├─────────────────────────────────────────────────┤
│  📊 Data │ 🎨 RGB │ 💰 Agent │ ⏰ Keeper        │
│  ┌───────────────┬─────────────────────────┐   │
│  │ STATS (30%)   │  LIVE LOGS (70%)        │   │
│  │               │                         │   │
│  │ • Total: 245  │  [Scroll area]          │   │
│  │ • Avg: 2.34x  │  Real-time logs appear  │   │
│  │ • Chart...    │  here as app runs       │   │
│  │               │                         │   │
│  └───────────────┴─────────────────────────┘   │
│  [▶️ START]  [⏹️ STOP]                         │
└─────────────────────────────────────────────────┘
```

### Stats Panel (Left)
- Updates every 2-3 seconds
- Polls database for current session data
- Shows key metrics for each app type

### Logs Panel (Right)
- Real-time streaming via threading
- Auto-scrolls to latest entry
- Color-coded by log level
- Limited to last 1000 lines in memory

### Control Buttons (Bottom)
- **START:** Launch app in background process
- **STOP:** Gracefully terminate app
- **GRACEFUL/INSTANT:** Betting Agent only

---

## 🔧 Technical Details

### How Live Logs Work

```python
App Process (subprocess)
    ↓ stdout
Thread (LogReader)
    ↓ callback
GUI Widget (QTextEdit)
```

- Apps write to `stdout`
- `subprocess.PIPE` captures output
- Background thread reads line-by-line
- Callback sends to GUI (thread-safe via Qt)

**Also logs to files:** `logs/` folder for persistence

---

### How Stats Work

```python
Stats Widget (QTimer every 2 sec)
    ↓ SQL query
Database (session data)
    ↓ results
Widget Update (display)
```

- Stats poll database every 2-3 seconds
- Query: `SELECT ... WHERE timestamp >= session_start`
- Very fast (< 1ms per query)
- Minimal CPU usage

**Why not real-time queue?**
- DB polling is simpler
- No multiprocessing.Queue complexity
- Still feels real-time (2 sec refresh)

---

## 🎨 Themes

### Dark Theme (Default)
Automatically applied. Uses Fusion style with dark palette.

### Light Theme
To disable dark theme, comment out in `main.py`:
```python
# self.apply_dark_theme()  # Comment this line
```

---

## ⚙️ Configuration File

`config.json` structure:
```json
{
  "dual_monitor": false,
  "bookmakers": [
    {
      "name": "BalkanBet",
      "position": "TL"
    },
    {
      "name": "Mozzart",
      "position": "TC"
    }
  ],
  "betting_agent": {
    "bet_amount": 10.0,
    "auto_stop": 2.0
  },
  "session_keeper": {
    "interval": 600
  }
}
```

**Fields:**
- `dual_monitor`: Adds coordinate offset for 2nd monitor
- `bookmakers`: List of configured bookmakers
- `betting_agent`: Betting parameters
- `session_keeper`: Check interval in seconds

---

## 🛠️ Troubleshooting

### Issue: GUI doesn't start

**Check PySide6:**
```bash
pip install --upgrade PySide6
```

### Issue: Apps don't start from GUI

**Check app files exist:**
```bash
ls apps/main_data_collector.py
ls apps/rgb_collector.py
ls apps/betting_agent.py
ls apps/session_keeper.py
```

### Issue: Logs not appearing

**Logs stream in real-time.** If frozen:
1. Check `logs/` folder - files should still be written
2. Restart GUI
3. Check app process is running (Task Manager)

### Issue: Stats not updating

**Stats poll DB every 2-3 sec.** If frozen:
1. Check if app is actually collecting data
2. Check database file exists: `data/databases/main_game_data.db`
3. Restart GUI

### Issue: "No config found" error

**Create config first:**
1. Click **⚙️ Setup Config**
2. Add at least 1 bookmaker
3. Click **💾 Save Setup**

---

## 🔐 Safety Features

### Graceful Shutdown
When closing GUI:
- Prompts to stop all running apps
- Waits for processes to finish cleanly
- Saves any pending data

### Error Handling
- Try-catch blocks for all operations
- Logs errors to `logs/` folder
- Shows error dialogs for critical issues

### Transaction Safety (Betting Agent)
- Lock mechanism prevents concurrent bets
- Each bet is atomic (all-or-nothing)
- Queue system for sequential processing

---

## 📈 Performance

**Resource Usage:**
- **CPU:** 5-10% (GUI idle) + app processes
- **RAM:** ~100MB (GUI) + ~200MB per app process
- **Disk:** Logs grow ~1MB/hour per app

**Recommended:**
- 8GB+ RAM for 6 apps
- Quad-core+ CPU
- SSD for faster database access

---

## 🎓 Tips & Best Practices

### 1. **Start Small**
Test with 1 bookmaker first, then scale to 6

### 2. **Monitor Logs**
Check logs regularly for errors or warnings

### 3. **Save Configs Often**
Click **💾 Save Setup** after each config change

### 4. **Use Dual Monitor**
Run GUI on one monitor, bookmakers on the other

### 5. **Check Stats Accuracy**
Compare stats with actual game data periodically

### 6. **Backup Data**
Backup `data/databases/` folder regularly

---

## 🔗 Related Documentation

- [Quick Start Guide](01_quick_start.md) - Installation & first run
- [System Architecture](03_system_architecture.md) - How it works
- [Deployment Guide](04_deployment_production.md) - Production setup
- [Troubleshooting](05_troubleshooting.md) - Common issues

---

## 📞 Getting Help

If you encounter issues:
1. Check [Troubleshooting Guide](05_troubleshooting.md)
2. Check `logs/` folder for error messages
3. Review app configuration in `config.json`

---

**Enjoy the GUI!** 🎮