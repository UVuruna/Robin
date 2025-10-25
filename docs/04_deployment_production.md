# Deployment & Production Guide

**VERSION: 5.2**  
**Taking Aviator from development to 24/7 production**

---

## Pre-Production Checklist

Before deploying to production, verify:

- [ ] All tests passed (run `utils/pre_run_verification.py`)
- [ ] Coordinates verified for all bookmakers
- [ ] 30-minute test run successful (no errors)
- [ ] Database writing correctly
- [ ] Logs show accurate readings
- [ ] GUI stable and responsive
- [ ] Browser CSS injected
- [ ] Backup procedures in place
- [ ] Monitoring configured
- [ ] Recovery procedures documented

---

## Deployment Steps

### 1. Environment Setup

#### A. Production Machine Requirements

**Minimum:**
- 4-core CPU
- 8GB RAM
- 50GB SSD
- Stable internet
- Dual monitor (recommended)

**Optimal:**
- 8-core CPU
- 16GB RAM
- 256GB NVMe SSD
- Gigabit internet
- Dual/triple monitor setup

#### B. OS Configuration

**Windows:**
```powershell
# Disable sleep
powercfg /change standby-timeout-ac 0

# Set high performance power plan
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
```

**Linux:**
```bash
# Disable suspend
sudo systemctl mask sleep.target suspend.target

# Increase file watch limit
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

#### C. Database Optimization

```sql
-- Open database
sqlite3 data/databases/main_game_data.db

-- Enable WAL mode (better concurrency)
PRAGMA journal_mode = WAL;

-- Set synchronous to NORMAL (faster, still safe)
PRAGMA synchronous = NORMAL;

-- Increase cache (64MB)
PRAGMA cache_size = -64000;

-- Verify settings
PRAGMA journal_mode;
PRAGMA synchronous;
```

### 2. Coordinate Setup

#### Create for All Bookmakers

```bash
# Bookmaker 1
python utils/region_editor.py
# Select: BalkanBet
# Draw regions
# Save

# Bookmaker 2
python utils/region_editor.py
# Select: Mozzart
# Draw regions
# Save

# ... repeat for all bookmakers
```

#### Verify Coordinates

```bash
python utils/region_visualizer.py
# Test each bookmaker @ each position
# Verify all regions align correctly
```

### 3. GUI Configuration

```bash
python main.py
```

**Setup Tab:**
1. Add all bookmakers with positions
2. Configure database paths
3. Set log levels
4. Save configuration

**Test:**
- Start Data Collector
- Let run for 5 minutes
- Verify logs and stats

### 4. Production Launch

**Final checks:**
```bash
# 1. Test all apps
python utils/pre_run_verification.py

# 2. Check database
sqlite3 main_game_data.db "SELECT COUNT(*) FROM rounds;"

# 3. Check logs
tail -f logs/main_data_collector.log
```

**Launch:**
1. Start GUI: `python main.py`
2. Start all apps in sequence:
   - Data Collector first (wait 1 min)
   - RGB Collector (optional)
   - Betting Agent (if needed)
3. Monitor logs for 10 minutes
4. Verify database is recording

---

## Monitoring & Maintenance

### 1. Real-Time Monitoring

**GUI Stats Tab:**
- Updates every 2 seconds
- Shows live counts and rates
- Detects stuck processes

**Logs:**
```bash
# Live tail
tail -f logs/main_data_collector.log

# Search for errors
grep "ERROR" logs/*.log

# Check last hour
tail -100 logs/main_data_collector.log
```

### 2. Database Monitoring

```sql
-- Check record counts
SELECT bookmaker, COUNT(*) as rounds
FROM rounds
GROUP BY bookmaker
ORDER BY rounds DESC;

-- Check recent activity
SELECT bookmaker, timestamp, final_score
FROM rounds
ORDER BY timestamp DESC
LIMIT 10;

-- Check for gaps
SELECT bookmaker, 
       MIN(timestamp) as first_record,
       MAX(timestamp) as last_record,
       COUNT(*) as total_rounds
FROM rounds
GROUP BY bookmaker;
```

### 3. Performance Monitoring

```bash
# CPU usage
top -p $(pgrep -f main_data_collector)

# Memory usage
ps aux | grep python

# Disk I/O
iostat -x 1

# Database size
du -h data/databases/*.db
```

### 4. Automated Monitoring Script

Save as `monitor.sh`:

```bash
#!/bin/bash
# monitor.sh - Production monitoring script

LOG_DIR="logs"
DB_FILE="data/databases/main_game_data.db"
ALERT_EMAIL="your@email.com"

# Check if processes running
if ! pgrep -f "main_data_collector" > /dev/null; then
    echo "WARNING: Data collector not running!" | mail -s "Aviator Alert" $ALERT_EMAIL
fi

# Check database size
DB_SIZE=$(du -m $DB_FILE | cut -f1)
if [ $DB_SIZE -gt 10000 ]; then  # Alert if > 10GB
    echo "WARNING: Database size is ${DB_SIZE}MB" | mail -s "Aviator Alert" $ALERT_EMAIL
fi

# Check for recent errors
ERROR_COUNT=$(grep -c "ERROR" $LOG_DIR/*.log)
if [ $ERROR_COUNT -gt 10 ]; then
    echo "WARNING: ${ERROR_COUNT} errors found in logs" | mail -s "Aviator Alert" $ALERT_EMAIL
fi

# Check last record timestamp
LAST_RECORD=$(sqlite3 $DB_FILE "SELECT MAX(timestamp) FROM rounds;")
CURRENT_TIME=$(date +%s)
LAST_RECORD_TIME=$(date -d "$LAST_RECORD" +%s)
TIME_DIFF=$((CURRENT_TIME - LAST_RECORD_TIME))

if [ $TIME_DIFF -gt 300 ]; then  # Alert if no records in 5 minutes
    echo "WARNING: No records in last 5 minutes" | mail -s "Aviator Alert" $ALERT_EMAIL
fi
```

**Schedule with cron:**
```bash
crontab -e
# Add line:
*/5 * * * * /path/to/monitor.sh
```

---

## Backup & Recovery

### 1. Automated Backup

**Daily Backup Script** (`backup.sh`):

```bash
#!/bin/bash
# backup.sh - Daily database backup

BACKUP_DIR="backups"
DB_FILE="data/databases/main_game_data.db"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# Create backup
cp $DB_FILE "$BACKUP_DIR/main_game_data_$DATE.db"

# Compress old backups (> 7 days)
find $BACKUP_DIR -name "*.db" -mtime +7 -exec gzip {} \;

# Delete very old backups (> 30 days)
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

**Schedule:**
```bash
crontab -e
# Add line:
0 2 * * * /path/to/backup.sh  # Daily at 2 AM
```

### 2. Recovery Procedures

**Restore from Backup:**
```bash
# Stop all apps first!
# In GUI, stop all processes

# Restore database
cp backups/main_game_data_20241019.db data/databases/main_game_data.db

# Restart apps
python main.py
```

**Recover from Corruption:**
```bash
# Export data
sqlite3 main_game_data.db ".dump" > backup.sql

# Create new database
rm main_game_data.db
python database/setup.py

# Import data
sqlite3 main_game_data.db < backup.sql
```

### 3. Backup Best Practices

- **Frequency:** Daily at minimum, hourly for critical production
- **Location:** Separate disk/server, cloud storage
- **Retention:** Keep 30 days of daily backups
- **Verification:** Test restore monthly
- **Documentation:** Document restore procedures

---

## Scaling to 6 Bookmakers

### Incremental Rollout

**Day 1: Single Bookmaker**
- Start with 1 bookmaker
- Monitor for 24 hours
- Verify data quality
- Check for errors

**Day 2: Three Bookmakers**
- Add 2 more bookmakers
- Monitor resource usage
- Verify all recording correctly
- Check performance

**Day 3: Six Bookmakers (Full Scale)**
- Add remaining 3
- Monitor CPU/RAM usage
- Verify database performance
- Check for bottlenecks

### Resource Management

**CPU Usage:**
- Each bookmaker process: ~10-15% CPU
- 6 bookmakers: ~60-90% CPU usage
- Leave headroom for GUI and system

**RAM Usage:**
- Each process: ~200-300MB RAM
- 6 processes: ~1.5-2GB total
- Plus OS and GUI: 3-4GB total

**Disk I/O:**
- Batch inserts minimize I/O
- SSD recommended for production
- Monitor write latency

**Network:**
- Minimal network usage
- Screenshots are local
- Database writes are local

---

## Troubleshooting Production Issues

### Issue: App Crashes Overnight

**Check:**
1. Memory leaks (RAM usage over time)
2. Disk space (database growing too large)
3. System logs (OS-level issues)
4. Error logs (application errors)

**Solutions:**
- Increase RAM if needed
- Rotate/compress old logs
- Check for memory leaks in code
- Implement graceful restart

### Issue: Database Locking

**Symptoms:**
- "Database is locked" errors
- Slow writes
- Timeouts

**Solutions:**
```sql
-- Enable WAL mode
PRAGMA journal_mode = WAL;

-- Increase busy timeout
PRAGMA busy_timeout = 5000;
```

### Issue: Coordinate Drift

**Symptoms:**
- OCR accuracy decreases over time
- Regions no longer align

**Causes:**
- Browser window moved
- Resolution changed
- OS scaling changed

**Solutions:**
- Re-verify coordinates with region_visualizer
- Re-create coordinates if needed
- Lock browser windows in place

### Issue: High CPU Usage

**Check:**
```bash
# Top processes
top -p $(pgrep -f python)

# Process details
ps aux | grep python | awk '{print $2, $3, $11}'
```

**Solutions:**
- Increase batch size (fewer DB transactions)
- Reduce screenshot frequency
- Optimize OCR regions (smaller = faster)
- Upgrade CPU if bottleneck

---

## Production Best Practices

### 1. Start Small, Scale Gradually

- Day 1: 1 bookmaker
- Day 2: 3 bookmakers
- Day 3: 6 bookmakers

### 2. Monitor First Week Closely

- Check logs daily
- Verify data quality
- Adjust settings as needed
- Watch for errors/warnings

### 3. Automate Maintenance

- Daily backups (cron/Task Scheduler)
- Weekly database optimization
- Monthly log cleanup
- Automated monitoring alerts

### 4. Document Your Setup

- Note bookmaker positions
- Save coordinate backups
- Document custom configs
- Track changes over time

### 5. Test Recovery Procedures

- Practice restoring from backup
- Test process restart
- Verify data integrity after restore
- Document recovery time

---

## Related Documentation

- [Quick Start](01_quick_start.md) - Initial setup
- [GUI Guide](02_gui_guide.md) - GUI usage
- [Coordinate System](03_coordinate_system.md) - Coordinates
- [System Architecture](03_system_architecture.md) - How it works
- [Troubleshooting](05_troubleshooting.md) - Common issues

---

## Production Launch Checklist

Final check before going live:

**Pre-Launch:**
- [ ] All tests passed
- [ ] Coordinates verified for all bookmakers
- [ ] 30-minute test run successful
- [ ] Database configured and optimized
- [ ] Backups configured and tested
- [ ] Monitoring scripts deployed
- [ ] Resource usage acceptable (CPU, RAM, disk)
- [ ] No errors in logs

**Post-Launch (First Hour):**
- [ ] All processes running
- [ ] Database recording correctly
- [ ] Stats updating in GUI
- [ ] No errors in logs
- [ ] Resource usage normal

**Post-Launch (First 24 Hours):**
- [ ] Data quality verified
- [ ] Backup created successfully
- [ ] No crashes or restarts
- [ ] Performance stable

**All checked? You're ready for 24/7 production!**

---

**Deploy with confidence!**
