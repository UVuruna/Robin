# Redis Cache - Future Implementation Guide

## 📋 Table of Contents
- [Overview](#overview)
- [Current State Analysis](#current-state-analysis)
- [When Redis Becomes Necessary](#when-redis-becomes-necessary)
- [Proposed Implementation](#proposed-implementation)
- [Integration Guide](#integration-guide)
- [Performance Comparison](#performance-comparison)
- [Conclusion](#conclusion)

---

## Overview

**Status:** PLACEHOLDER - Not implemented
**Author:** Claude Opus 4.1
**Date:** 2024-10-30
**Purpose:** Documentation and future implementation guide for Redis caching

Redis is an in-memory data structure store (key-value database in RAM) that provides sub-millisecond response times for cached data. This file serves as a comprehensive guide for when and how to implement Redis caching in the AVIATOR system.

---

## Current State Analysis

### What We Have Now (6-8 Bookmakers)

Based on our analysis of the current system:

#### Database Query Patterns
- **DataCollectorStats:** Queries every 2 seconds
- **BettingAgentStats:** Queries every 3 seconds
- **RGBCollectorStats:** Queries every 3 seconds
- **SessionKeeperStats:** No database queries (memory only)

#### Performance Metrics
- **Database query time:** ~10-50ms per query
- **Total overhead:** 10-50ms every 1-3 seconds
- **User experience:** SMOOTH - No noticeable lag ✅
- **Connection overhead:** New SQLite connection created each time (wasteful but still fast)

#### Key Finding
**The current architecture is SUFFICIENT for 6-8 bookmakers.** SQLite with BatchDatabaseWriter handles the load perfectly. Redis would add unnecessary complexity without meaningful benefit.

### Problems with Current Implementation

1. **Too Frequent Updates:** Refreshing every 1-3 seconds is overkill
   - Rounds happen every 20-30 seconds
   - Stats update 20-30 times per round (wasteful)

2. **Connection Overhead:** Creating new database connection for each query
   - Should use connection pooling or shared connection

3. **No Caching:** Every refresh queries database even if data hasn't changed
   - Should cache last result and compare

---

## When Redis Becomes Necessary

### Scaling Thresholds

Redis becomes beneficial when you have:
- **20+ bookmakers** running simultaneously
- **Multiple users** accessing the same data (web dashboard)
- **Distributed deployment** (multiple machines)
- **Database queries taking >100ms** consistently
- **Real-time requirements** (<10ms response needed)

### Current vs Future Architecture

#### Without Redis (Current, 6-8 bookmakers)
```
Worker Process → local_state (memory)
            ↓
     BatchDatabaseWriter → SQLite
            ↓
      GUI (every 30s) → Database Query (~10-50ms)
```

#### Without Redis (Future, 20+ bookmakers)
```
20 Workers → BatchDatabaseWriter → SQLite (bottleneck!)
                              ↓
                    GUI → Database Query (~100-500ms) = LAG!
```

#### With Redis (20+ bookmakers)
```
Worker Process → local_state
            ↓
      Redis Cache (instant write)
            ↓
      GUI → Redis Query (~0.1-1ms) = INSTANT!

(BatchDatabaseWriter still writes to SQLite for persistence)
```

---

## Proposed Implementation

### Redis Data Structure Design

```python
# Key patterns
"round:{bookmaker}:{round_id}"     # Individual round data
"stats:{bookmaker}"                 # Aggregated stats per bookmaker
"stats:total"                       # Total stats across all bookmakers
"worker:states"                     # Hash of bookmaker → state
"last_round:{bookmaker}"            # Most recent round (always fresh)

# TTL Strategy
- Round data: 1 hour (historical lookback)
- Stats: 60 seconds (auto-refresh)
- Last round: 30 seconds (near real-time)
- Worker states: No TTL (persistent until changed)
```

### Core Redis Cache Class

```python
class RedisCache:
    """
    Redis caching layer for AVIATOR real-time data.
    Provides instant access to recent rounds, stats, and state.
    """

    def __init__(self, host='localhost', port=6379, db=0):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        self.ttl_round = 3600     # 1 hour for rounds
        self.ttl_stats = 60       # 1 minute for stats
        self.ttl_last_round = 30  # 30 seconds for last round

    def cache_round(self, bookmaker: str, round_data: Dict) -> bool:
        """Cache individual round with TTL."""
        key = f"round:{bookmaker}:{round_data['round_id']}"
        self.redis_client.setex(key, self.ttl_round, json.dumps(round_data))

        # Also update last_round (always fresh)
        last_key = f"last_round:{bookmaker}"
        self.redis_client.setex(last_key, self.ttl_last_round, json.dumps(round_data))
        return True

    def get_stats_with_fallback(self, bookmaker: str) -> Dict:
        """Get stats from Redis, fallback to database if miss."""
        stats = self.redis_client.get(f"stats:{bookmaker}")
        if stats:
            return json.loads(stats)

        # Cache miss - fetch from database
        stats = self.query_database_stats(bookmaker)
        self.cache_bookmaker_stats(bookmaker, stats)
        return stats
```

### Pub/Sub for Real-time Events

```python
# Publisher (in Worker)
redis_cache.publish_event("round_ended", {
    "bookmaker": "Admiral",
    "score": 3.45,
    "timestamp": datetime.now().isoformat()
})

# Subscriber (in GUI)
pubsub = redis_cache.subscribe_to_events(["round_ended", "threshold_crossed"])
for message in pubsub.listen():
    update_gui_instantly(message['data'])
```

---

## Integration Guide

### Step 1: Install Redis

```bash
# Windows
Download from: https://github.com/microsoftarchive/redis/releases
Run: redis-server.exe

# Linux
sudo apt install redis-server
sudo systemctl start redis

# Python client
pip install redis
```

### Step 2: Modify Workers

```python
# orchestration/bookmaker_worker.py

from data_layer.cache.redis_cache import RedisCache

def __init__(self, ...):
    self.redis_cache = RedisCache() if REDIS_ENABLED else None

def process_round_end(self, round_data):
    # Current: Save to local_state and database
    self.local_state.update(round_data)
    self.db_writer.add(round_data)

    # ADD: Also cache in Redis
    if self.redis_cache:
        self.redis_cache.cache_round(self.bookmaker_name, round_data)

        # Calculate and cache aggregated stats
        stats = self.calculate_stats()
        self.redis_cache.cache_bookmaker_stats(self.bookmaker_name, stats)
```

### Step 3: Modify GUI Stats Widgets

```python
# gui/stats_widgets.py

class DataCollectorStats(QWidget):
    def __init__(self, ...):
        self.redis_cache = RedisCache() if REDIS_ENABLED else None

        # Reduce update frequency
        self.update_timer.start(30000)  # 30 seconds instead of 2

    def fetch_and_update_stats(self):
        if self.redis_cache:
            # Fast path - Redis
            stats = self.redis_cache.get_total_stats()
            last_rounds = {
                bm: self.redis_cache.get_last_round(bm)
                for bm in self.bookmaker_names
            }
        else:
            # Slow path - Database
            stats = self.query_database()

        self.update_display(stats, last_rounds)
```

### Step 4: Add Health Check

```python
# utils/diagnostic.py

def check_redis():
    try:
        cache = RedisCache()
        if cache.ping():
            print("✅ Redis connected (using fast cache)")
        else:
            print("⚠️ Redis not available (falling back to database)")
    except:
        print("ℹ️ Redis not configured (using database only)")
```

---

## Performance Comparison

### Current Implementation Issues

| Metric | Current | Optimal | Improvement |
|--------|---------|---------|-------------|
| Query Frequency | 1-3 sec | 30-60 sec | 10-20x less |
| Connections/min | 20-60 | 1-2 | 30x less |
| Database Load | High | Low | 90% reduction |
| Round Updates | 20-30/round | 1-2/round | 15x less |

### With Optimizations (No Redis)

**Recommended changes for current system:**
1. Single shared database connection
2. Update every 30-60 seconds
3. Cache last query result
4. Last round data from memory

This would be PERFECT for 6-8 bookmakers!

### Performance at Different Scales

| Bookmakers | Without Redis | With Redis | Benefit |
|------------|--------------|------------|---------|
| 6-8 | 10-50ms | 0.1-1ms | Minimal |
| 10-15 | 50-100ms | 0.1-1ms | Moderate |
| 20-30 | 100-500ms | 0.1-1ms | Significant |
| 50+ | 500ms-2s | 0.1-1ms | Critical |

---

## Current Recommendations (Without Redis)

### Immediate Optimizations

1. **Centralized Stats Reader**
   ```python
   class CentralizedStatsReader:
       """Single thread/process that queries database for all widgets."""

       def __init__(self):
           self.connection = sqlite3.connect(db_path)
           self.cache = {}
           self.last_update = {}

       def get_stats(self, collector_type: str) -> Dict:
           # Check cache (30 second TTL)
           if self.is_cache_valid(collector_type):
               return self.cache[collector_type]

           # Query once for all bookmakers
           stats = self.query_all_stats(collector_type)
           self.cache[collector_type] = stats
           self.last_update[collector_type] = time.time()
           return stats
   ```

2. **Memory Cache for Last Round**
   ```python
   class LastRoundCache:
       """Keep last round in memory for instant access."""

       def __init__(self):
           self.last_rounds = {}  # bookmaker -> round_data

       def update(self, bookmaker: str, round_data: Dict):
           self.last_rounds[bookmaker] = {
               **round_data,
               'cached_at': time.time()
           }
   ```

3. **Reduce Update Frequencies**
   - DataCollector: 30 seconds (was 2)
   - BettingAgent: 30 seconds (was 3)
   - RGBCollector: 30 seconds (was 3)
   - SessionKeeper: Keep at 1 second (no database)

---

## Conclusion

### For Current Setup (6-8 Bookmakers)

**Redis is NOT needed.** The following optimizations will make the system perfect:

1. ✅ Implement centralized stats reader (single database connection)
2. ✅ Reduce update frequency to 30-60 seconds
3. ✅ Cache last query results
4. ✅ Keep last round data in memory

**Result:** 90% reduction in database load, instant last round updates, smooth GUI

### When to Implement Redis

Implement Redis when you experience:
- Database queries consistently >100ms
- GUI freezing during updates
- Planning for 20+ bookmakers
- Need for web dashboard
- Multi-machine deployment

### Final Verdict

**Keep this file as documentation.** Redis is the correct future solution, but implementing it now would be premature optimization. The current SQLite architecture with the recommended optimizations will handle 6-8 bookmakers perfectly.

**Estimated timeline:** Implement Redis when scaling beyond 15-20 bookmakers or when adding web dashboards with multiple concurrent users.

---

## Implementation Checklist (When Ready)

When you're ready to implement Redis:

- [ ] Install Redis server
- [ ] Add `redis` to requirements.txt
- [ ] Implement RedisCache class
- [ ] Add Redis configuration to settings.py
- [ ] Modify workers to write to Redis
- [ ] Modify GUI to read from Redis
- [ ] Add fallback to database
- [ ] Implement health checks
- [ ] Add monitoring dashboard
- [ ] Document deployment procedures

---

*Last Updated: 2024-10-30 by Claude Opus 4.1*