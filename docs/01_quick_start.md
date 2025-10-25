# Quick Start Guide

**VERSION: 5.2**  
**Get up and running in 10 minutes**

---

## System Requirements

- **OS:** Windows 10/11, Linux, macOS
- **Python:** 3.8+
- **RAM:** 4GB minimum, 8GB recommended
- **CPU:** 4+ cores recommended (for multiprocessing)
- **Disk:** SSD recommended (faster database writes)
- **Tesseract:** 4.0+ for OCR

---

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Key packages:**
- PySide6 (GUI)
- pytesseract (OCR)
- Pillow (screenshots)
- pyautogui (mouse/keyboard)
- scikit-learn (K-means for phase detection)

### 2. Install Tesseract OCR

**Windows:**
```bash
# Download installer from:
# https://github.com/UB-Mannheim/tesseract/wiki

# Add to PATH or update config.py
```

**Linux:**
```bash
sudo apt install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Verify:**
```bash
tesseract --version
# Should show: tesseract 4.x.x or higher
```

### 3. Inject CSS into Browsers

**Open browser console (F12) and paste:**

```javascript
// Inject custom CSS for better OCR
const style = document.createElement('style');
style.textContent = `
  /* Dark theme + larger numbers for OCR */
  body { background: #000 !important; }
  .score { font-size: 120px !important; color: #fff !important; }
  .money { font-size: 36px !important; color: #fff !important; }
`;
document.head.appendChild(style);
```

**Do this for EACH bookmaker browser.**

---

## First Run (5 Steps)

### Step 1: Launch GUI

```bash
python main.py
```

### Step 2: Setup Configuration

1. Click **"Setup Config"** tab
2. Click **"+ Add Bookmaker"**
3. Enter:
   - Name: e.g., "BalkanBet"
   - Position: e.g., "TL" (Top-Left)
   - Monitor Offset: 0 (or 1920 if second monitor)
4. Click **"Save Setup"**

### Step 3: Create Coordinates

```bash
# Run region editor
python utils/region_editor.py

# 1. Select bookmaker name (must match setup config)
# 2. Position browser at TL (fullscreen with F11)
# 3. Draw 8 regions with mouse:
#    - SCORE (center display)
#    - PHASE (around score)
#    - MY_MONEY (top-right)
#    - PLAYER_COUNT (left sidebar)
#    - OTHER_MONEY (left sidebar)
#    - PLAY_BUTTON (green button)
#    - BET_AMOUNT (bet input)
#    - AUTO_PLAY (auto cashout input)
# 4. Press 's' to save
```

### Step 4: Start Data Collection

In GUI:
1. Go to **"Data Collector"** tab
2. Click **"START"**
3. Watch:
   - **Logs** (right side) - Real-time activity
   - **Stats** (left side) - Updates every 2 seconds

**Let it run for 5 minutes** to verify it's working.

### Step 5: Check Results

```bash
# Check database
sqlite3 data/databases/main_game_data.db "SELECT COUNT(*) FROM rounds;"

# Should show ~5-10 rounds after 5 minutes
```

---

## What's Next?

### Option A: Production Run (Overnight)

Once verified working:
1. Start all needed apps in GUI
2. Let it run overnight
3. Check results in morning

### Option B: Multiple Bookmakers

1. Add more bookmakers in Setup Config
2. Position browser windows accordingly
3. Create coordinates for each (region editor)
4. Start Data Collector

**Grid Layout (6 bookmakers):**
```
TL     TC     TR
BL     BC     BR
```

### Option C: Betting Agent (WARNING: DEMO ONLY!)

**CAUTION:** Uses real money! Test thoroughly first!

1. Configure in Setup Dialog
2. Set bet amount & auto cashout
3. Test in DEMO mode
4. Monitor closely

---

## Quick Troubleshooting

### Issue: GUI doesn't start

```bash
pip install --upgrade PySide6
```

### Issue: Tesseract not found

```bash
# Windows: Add to PATH or update config.py
# Linux: sudo apt install tesseract-ocr
```

### Issue: OCR not reading correctly

1. Check browser is fullscreen (F11)
2. Check zoom is 100% (Ctrl+0)
3. Check CSS is injected
4. Re-create coordinates with region editor

### Issue: No data in database

1. Check logs for errors
2. Verify coordinates are correct
3. Check game is actually running
4. Verify bookmaker name matches config

---

## Documentation

- **[GUI Guide](02_gui_guide.md)** - Detailed GUI usage
- **[Coordinate System](03_coordinate_system.md)** - How coordinates work
- **[System Architecture](03_system_architecture.md)** - Technical details
- **[Deployment](04_deployment_production.md)** - Production setup
- **[Troubleshooting](05_troubleshooting.md)** - Common issues

---

## Success Checklist

After first run, verify:
- [ ] GUI launches without errors
- [ ] Tesseract installed and working
- [ ] Browser positioned correctly
- [ ] CSS injected
- [ ] Coordinates created for all regions
- [ ] Data collector runs for 5+ minutes
- [ ] Logs show successful readings
- [ ] Database has records
- [ ] Values match actual game

**All checked? You're ready for production!**

---

## Tips

1. **Start with 1 bookmaker** - Scale to 6 later
2. **Monitor logs** - Check for errors/warnings daily
3. **Backup data** - Copy databases regularly
4. **Use SSD** - Faster database writes
5. **Check stats** - Compare with actual game data
6. **Test coordinates** - Use region_visualizer.py
7. **Document setup** - Note which bookmaker goes where

---

## Getting Help

If stuck:
1. Check [Troubleshooting Guide](05_troubleshooting.md)
2. Review logs in `logs/` folder
3. Check `config.json` for errors
4. Run `utils/pre_run_verification.py`

---

**Ready to collect data!**
