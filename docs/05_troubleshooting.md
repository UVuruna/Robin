# Troubleshooting Guide

**VERSION: 5.2**  
**Common issues and solutions for Aviator project**

---

## Installation Issues

### Issue: pip install fails

**Symptom:** Errors during `pip install -r requirements.txt`

**Solutions:**

#### 1. Upgrade pip
```bash
python -m pip install --upgrade pip
```

#### 2. Install with verbose
```bash
pip install -r requirements.txt -v
```

#### 3. Install individually
```bash
# If one package fails, install others first
pip install PySide6
pip install pytesseract
pip install Pillow
pip install pyautogui
# ... etc
```

#### 4. Use virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

---

### Issue: Tesseract not found

**Symptom:** `TesseractNotFoundError`

**Solutions:**

#### Windows:
```bash
# 1. Install Tesseract from:
# https://github.com/UB-Mannheim/tesseract/wiki

# 2. Add to PATH, or update config.py:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

#### Linux:
```bash
sudo apt update
sudo apt install tesseract-ocr
```

#### macOS:
```bash
brew install tesseract
```

**Verify:**
```bash
tesseract --version
# Should show: tesseract 4.x.x or higher
```

---

## GUI Issues

### Issue: GUI doesn't start

**Symptom:** `ModuleNotFoundError: No module named 'PySide6'`

**Solutions:**

#### 1. Install/Upgrade PySide6
```bash
pip install --upgrade PySide6
```

#### 2. Check Python version
```bash
python --version
# Should be 3.8 or higher
```

#### 3. Reinstall all dependencies
```bash
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

---

### Issue: GUI freezes/hangs

**Symptom:** GUI becomes unresponsive

**Solutions:**

#### 1. Check Process Status
- Click "Check Status" button in GUI
- Look for ZOMBIE processes

#### 2. Kill Stuck Processes
```bash
# Linux/Mac:
pkill -9 -f main_data_collector

# Windows:
taskkill /F /IM python.exe /T
```

#### 3. Restart GUI
```bash
# Close GUI completely
# Re-launch:
python main.py
```

---

## Coordinate Issues

### Issue: OCR reads "ERROR" or wrong values

**Symptom:** Score shows "ERROR", wrong numbers, or gibberish

**Solutions:**

#### 1. Verify Browser State
- Fullscreen (F11)
- 100% zoom (Ctrl+0)
- CSS injected (check console)

#### 2. Re-inject CSS
```javascript
// Open browser console (F12), paste:
const style = document.createElement('style');
style.textContent = `
  body { background: #000 !important; }
  .score { font-size: 120px !important; color: #fff !important; }
  .money { font-size: 36px !important; color: #fff !important; }
`;
document.head.appendChild(style);
```

#### 3. Re-create Coordinates
```bash
python utils/region_editor.py
# Draw regions more accurately
# Make regions slightly larger if text is cut off
```

#### 4. Test Coordinates
```bash
python utils/region_visualizer.py
# Check if regions align with screen elements
```

---

### Issue: Regions don't align with screen

**Symptom:** Colored borders don't match game elements

**Solutions:**

#### 1. Check Resolution
- Verify monitor resolution unchanged
- Check OS scaling (should be 100%)

#### 2. Check Browser Position
- Browser should be at exact position used when creating coords
- Use fullscreen (F11) for consistency

#### 3. Re-verify Coordinates
```bash
python utils/region_visualizer.py
# Visually inspect each region
```

#### 4. Re-create if Needed
```bash
python utils/region_editor.py
# Create fresh coordinates
```

---

### Issue: All bookmakers read same values

**Symptom:** 6 bookmakers showing identical data

**Causes:**
- Position offsets not applied
- All bookmakers using same coordinates

**Solutions:**

#### 1. Check Config
```json
// config.json should have different positions:
{
  "bookmakers": [
    {"name": "BalkanBet", "position": "TL"},
    {"name": "Mozzart", "position": "TC"},
    {"name": "Soccer", "position": "TR"}
  ]
}
```

#### 2. Verify Position Offsets
```bash
# Check bookmaker_coords.json
cat data/coordinates/bookmaker_coords.json | grep -A 3 "positions"

# Should show:
# "TL": {"left": 0, "top": 0}
# "TC": {"left": 1030, "top": 0}
# "TR": {"left": 2060, "top": 0}
```

#### 3. Test Calculations
```bash
python utils/quick_test.py
# Will test coordinate calculations
```

---

## Database Issues

### Issue: Database locked

**Symptom:** `sqlite3.OperationalError: database is locked`

**Solutions:**

#### 1. Enable WAL Mode
```sql
sqlite3 data/databases/main_game_data.db
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
.quit
```

#### 2. Close Other Connections
- Close any SQLite browser/viewer
- Stop duplicate app instances

#### 3. Restart Apps
- Stop all apps in GUI
- Wait 10 seconds
- Restart

---

### Issue: No data in database

**Symptom:** `SELECT COUNT(*) FROM rounds` returns 0

**Solutions:**

#### 1. Check Logs
```bash
tail -100 logs/main_data_collector.log
# Look for errors or "No score detected"
```

#### 2. Verify Coordinates
```bash
python utils/region_visualizer.py
# Check if regions capture correct areas
```

#### 3. Check OCR
- Verify Tesseract installed
- Test with: `tesseract --version`
- Check CSS injected in browser

#### 4. Verify Bookmaker Names Match
```bash
# Config.json:
{"name": "BalkanBet"}

# bookmaker_coords.json:
"bookmakers": {
  "BalkanBet": { ... }  # Must match exactly!
}
```

---

## Performance Issues

### Issue: High CPU usage

**Symptom:** CPU at 100%, system slow

**Solutions:**

#### 1. Check Process Count
```bash
# Linux/Mac:
ps aux | grep python | wc -l

# Windows:
tasklist | find /c "python.exe"

# Should be 1 process per bookmaker + 1 for GUI
```

#### 2. Reduce Batch Size
```python
# In database/writer.py
BATCH_SIZE = 20  # Lower = less CPU, more frequent writes
```

#### 3. Increase Sleep Time
```python
# In apps/main_data_collector.py
time.sleep(0.5)  # Increase from 0.1 to 0.5
```

#### 4. Check for Leaks
```bash
# Monitor memory over time
watch -n 1 'ps aux | grep python | awk "{print \$6}"'
```

---

### Issue: High memory usage

**Symptom:** RAM usage grows over time

**Solutions:**

#### 1. Check Memory Leaks
```bash
# Monitor RAM growth
watch -n 60 'free -h'  # Linux
watch -n 60 'vm_stat'  # macOS
```

#### 2. Restart Processes Periodically
```bash
# In cron (Linux) or Task Scheduler (Windows)
# Restart apps every 12 hours:
0 */12 * * * pkill -f main_data_collector && python main.py &
```

#### 3. Clear Image Caches
- Screenshots stored temporarily
- Cleared after OCR
- Check `temp/` folder

---

## Process Issues

### Issue: Process hangs on shutdown

**Symptom:** Ctrl+C doesn't work, process won't stop

**Solutions:**

#### 1. Wait 10-15 Seconds
- Graceful shutdown takes time
- Processes need to flush data

#### 2. Force Kill
```bash
# Linux/Mac:
pkill -9 -f main_data_collector

# Windows:
taskkill /F /IM python.exe /T
```

#### 3. Check Logs
```bash
tail -50 logs/main_data_collector.log
# Look for shutdown messages
```

---

### Issue: App crashes silently

**Symptom:** Process disappears with no error

**Check:**

#### 1. Error Log
```bash
tail -100 logs/error.log
```

#### 2. System Logs
- **Linux:** `dmesg | tail`
- **Windows:** Event Viewer → Application Logs
- **macOS:** Console.app

#### 3. Memory (OOM Kill?)
```bash
free -h  # Linux
vm_stat  # macOS

# If memory full, OS may have killed process
```

#### 4. Check Core Dumps
```bash
# Linux:
ls -lh /var/crash/
ls -lh core*
```

---

## Logging Issues

### Issue: Log files empty

**Symptom:** Files exist but 0 bytes

**Solutions:**

#### 1. Check Logger Setup
```bash
grep "return root_logger" logger.py
# Should return the logger, not None
```

#### 2. Check File Permissions
```bash
ls -lh logs/
# Should be writable by current user
```

#### 3. Test Logger
```python
from logger import setup_logger

logger = setup_logger("test")
logger.info("Test message")

# Check logs/test.log
```

---

### Issue: Log files too large

**Symptom:** `logs/` folder > 1GB

**Solutions:**

#### 1. Check Rotation Settings
```python
# In logger.py
handler = RotatingFileHandler(
    file_path,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5            # Keep 5 backups
)
```

#### 2. Manual Cleanup
```bash
# Delete old rotated logs
find logs/ -name "*.log.*" -mtime +7 -delete

# Compress old logs
gzip logs/*.log.* 2>/dev/null
```

#### 3. Adjust Log Level
```python
# In config.py or logger.py
logging.INFO   # Normal (recommended)
logging.WARNING  # Less verbose
logging.ERROR    # Only errors
```

---

## Best Practices to Avoid Issues

### 1. Regular Backups

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
cp data/databases/main_game_data.db backups/backup_$DATE.db
```

### 2. Monitor Logs

```bash
# Check for errors daily
grep "ERROR" logs/*.log | tail -20
```

### 3. Test Coordinates

```bash
# Before production run
python utils/region_visualizer.py
```

### 4. Keep Software Updated

```bash
pip list --outdated
pip install --upgrade -r requirements.txt
```

### 5. Start Small

- 1 bookmaker first
- Verify for 1 hour
- Then scale to 6

---

## Still Stuck?

### Debugging Checklist

- [ ] Ran `utils/pre_run_verification.py`
- [ ] Checked logs in `logs/` folder
- [ ] Verified coordinates with `region_visualizer.py`
- [ ] Tested Tesseract: `tesseract --version`
- [ ] Checked database: `sqlite3 main_game_data.db ".tables"`
- [ ] Restarted computer (seriously!)

### Gather Debug Info

```bash
# 1. System info
python --version
tesseract --version
uname -a  # Linux/Mac
systeminfo  # Windows

# 2. Last 100 log lines
tail -100 logs/main_data_collector.log > debug_logs.txt

# 3. Database status
sqlite3 main_game_data.db <<EOF
.tables
SELECT COUNT(*) FROM rounds;
SELECT bookmaker, COUNT(*) FROM rounds GROUP BY bookmaker;
EOF

# 4. Process status
ps aux | grep python >> debug_logs.txt

# 5. Resource usage
top -b -n 1 | head -20 >> debug_logs.txt
```

---

## Related Documentation

- [Quick Start](01_quick_start.md) - Initial setup
- [GUI Guide](02_gui_guide.md) - GUI usage
- [Coordinate System](03_coordinate_system.md) - Coordinates
- [System Architecture](03_system_architecture.md) - How it works
- [Deployment](04_deployment_production.md) - Production

---

## Emergency Procedures

### Complete System Reset

If everything fails:

```bash
# 1. Stop all processes
pkill -9 -f python  # Linux/Mac
taskkill /F /IM python.exe /T  # Windows

# 2. Backup current data
cp -r data/databases backups/emergency_$(date +%Y%m%d)

# 3. Reset logs
rm logs/*.log

# 4. Recreate databases
python database/setup.py

# 5. Verify coordinates
python utils/region_visualizer.py

# 6. Test run
python utils/quick_test.py

# 7. Start fresh
python main.py
```

---

**Most issues have simple solutions!**
