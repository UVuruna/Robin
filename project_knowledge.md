# PROJECT KNOWLEDGE - AVIATOR System

## Purpose
This file contains project-specific knowledge for AI assistants working on AVIATOR codebase.

---

## 🚨 FOR AI SESSIONS: MANDATORY READING ON START

### Required Files (Read in This Order):
```
1. CLAUDE.md - Core technical principles & patterns
2. ARCHITECTURE.md - Detailed system design
3. README.md - Project overview
4. CHANGELOG.md - Recent changes history
5. This file (project_knowledge.md) - Specific implementation details
```

### Critical: ASK QUESTIONS BEFORE CODING
- **NEVER start implementing without clarifying ambiguities**
- If ANY aspect is unclear → ASK first
- If multiple approaches exist → ASK which to use
- If requirements are missing → ASK for details
- **Only after receiving clear answers → Proceed**

---

## ⚠️ ABSOLUTE RULES (ZERO TOLERANCE)

### RULE #0: NO LYING
**You MUST provide concrete evidence for any claim.**

❌ Forbidden:
- "I checked all files" → **List specific files with line numbers**
- "I fixed errors" → **Show exact changes**
- Generic answers without specifics

✅ Required:
- If unsure → ASK
- If not verified → SAY SO
- If complex → Propose breaking into sub-tasks

**Control:** If you can't provide file:line references, you're lying.

---

### RULE #1: NO VERSION SUFFIXES
❌ Never create: `module_v2.py`, `ClassV3`, `file_new.py`, `file_backup.py`
✅ Always: Edit existing file directly (Git stores history)

**Procedure:**
1. `git commit` before changes
2. Edit existing file DIRECTLY
3. Test
4. `git commit` with clear message

---

### RULE #2: NEVER DELETE WITHOUT VERIFICATION

Before deleting code:
1. STOP - Don't delete immediately
2. SEARCH - Glob/Grep for the class/function
3. UNDERSTAND - Read what it does
4. ASK USER if not found

**Example from this project:**
```python
# ❌ WRONG: Delete self.coords_manager (couldn't find it)
# ✅ RIGHT: Search → Found RegionManager (was renamed!)
# ✅ RIGHT: Ask: "coords_manager not found. Was it renamed?"
```

**Rule:** 100 questions > 1 deleted core feature

---

## CORE ARCHITECTURAL PATTERNS

### Pattern 1: Worker Process Parallelism

**Principle:** 1 Bookmaker = 1 Process = 1 CPU Core

```
6 Bookmakers = 6 Processes = 100ms OCR (not 600ms sequential!)

Main Process (GUI)
└─> Spawns 6 Worker Processes (parallel on CPU cores)
    Each Worker:
    ├─ Own OCR Reader (parallel execution)
    ├─ local_state dict (in-process, fast)
    ├─ round_history list (100 rounds)
    ├─ Collectors (MainCollector, RGBCollector)
    └─ Agents as threads (BettingAgent, SessionKeeper)
```

**Why processes not threads?** Python GIL prevents true parallelism. OCR is CPU-intensive, so 6 threads = 600ms sequential. 6 processes = 100ms parallel.

---

### Pattern 2: Shared BatchWriter Per TYPE

**Critical:** ONE writer per collector/agent TYPE, NOT per bookmaker!

```python
# ❌ WRONG - Each worker has own writer
Worker1 → BatchWriter1 → flush (inefficient)
Worker2 → BatchWriter2 → flush

# ✅ CORRECT - All workers share ONE writer per TYPE
main_writer = BatchDatabaseWriter('main.db', batch_size=100)

Worker1 → main_writer.add() ┐
Worker2 → main_writer.add() ├─> 100 records → ONE flush
Worker3 → main_writer.add() ┘

# Result: 50-100x faster batch operations
```

**Implementation:** [gui/app_controller.py:49-110](gui/app_controller.py)

---

### Pattern 3: Closure Pattern for Agent State Access

**Problem:** Agents (threads) need access to Worker's `local_state`

**Solution:** Pass closure functions, NOT shared memory

```python
# In orchestration/bookmaker_worker.py
class BookmakerWorker:
    def setup_agents(self):
        # Closure captures self
        def get_state_fn():
            return self.local_state.copy()

        # Pass to agent
        self.betting_agent = BettingAgent(get_state_fn=get_state_fn)

# In agents/betting_agent.py
class BettingAgent:
    def __init__(self, get_state_fn):
        self.get_state = get_state_fn  # Store closure

    def _do_work(self):
        state = self.get_state()  # Call closure → instant access!
```

**Why?** In-process access (no multiprocessing overhead), thread-safe, fast.

---

### Pattern 4: Worker Process Initialization Flow

```python
1. GUI creates ProcessManager
2. GUI registers worker with WorkerConfig
   config = WorkerConfig(
       name='Admiral',
       target_func=worker_entry_point,
       kwargs={'bookmaker_name': 'Admiral', 'db_writers': {...}}
   )
3. ProcessManager wraps with _worker_wrapper
4. Wrapper INJECTS shutdown_event into kwargs
5. worker_entry_point creates BookmakerWorker
6. BookmakerWorker.run() starts OCR loop
```

**Key insight:** `shutdown_event` NOT in target_func signature - wrapper injects it!

**Code:** [orchestration/process_manager.py:137-189](orchestration/process_manager.py)

---

## DATA FLOW: local_state vs SharedGameState

```python
# PRIMARY: local_state (in-process dict)
Worker:
    OCR → local_state → Collectors (read)
                     → Agents (closure access)

# OPTIONAL: SharedGameState (for GUI only)
Worker:
    local_state → Periodically copy to SharedGameState

GUI:
    SharedGameState → Read for stats display
```

**Key difference:**
- `local_state`: Primary, fast in-process
- `SharedGameState`: GUI monitoring only (slower)

**Why both?** Workers avoid multiprocessing overhead. GUI gets monitoring data.

---

## ADDING NEW COMPONENTS

### Adding a New Collector

**Collectors run in Worker process, access local_state.**

Steps:
1. Extend `BaseCollector` ([collectors/base_collector.py](collectors/base_collector.py))
2. Implement:
   ```python
   def collect(self, state: Dict) -> Optional[Dict]:
       # Process state, return data or None

   def validate(self, data: Dict) -> bool:
       # Validate before DB write
   ```
3. Use shared `BatchWriter` (passed in constructor)
4. Register in `BookmakerWorker.setup()` ([orchestration/bookmaker_worker.py](orchestration/bookmaker_worker.py))

---

### Adding a New Agent

**Agents run as THREADS inside Worker process.**

Template:
```python
class YourAgent:
    def __init__(self, bookmaker: str, get_state_fn, config: Dict):
        self.bookmaker = bookmaker
        self.get_state = get_state_fn  # Closure
        self.running = False
        self.active = True  # Can be paused

    def run(self):
        """Main loop - runs in thread."""
        self.running = True
        while self.running:
            if self.active:
                state = self.get_state()  # Access via closure
                self._do_work(state)
            time.sleep(1)

    def pause(self):
        self.active = False

    def stop(self):
        self.running = False
```

Integration:
1. Create `agents/your_agent.py`
2. Add to `BookmakerWorker.setup_agents()`
3. Start as thread: `threading.Thread(target=agent.run, daemon=False)`

**Communication between agents:**
```python
# Mutual exclusivity (e.g., BettingAgent vs SessionKeeper)
def start_betting(self):
    self.session_keeper.pause()  # Pause other agent
    self.betting_agent.resume()
```

---

## PERFORMANCE REQUIREMENTS

| Metric | Target | Critical |
|--------|--------|----------|
| OCR Speed | < 15ms | ✅ YES |
| Batch Write | > 5000 records/sec | ✅ YES |
| Memory/Worker | < 100MB | ⚠️ Monitor |
| CPU/Worker | < 10% idle | ⚠️ Adjust intervals |

**Priority:** Data Accuracy > Speed

---

## WORKFLOW CHECKLIST

### After Completing ANY Work:

#### 1. Update Documentation
- [ ] `CHANGELOG.md` - **MUST** add entry
- [ ] `ARCHITECTURE.md` - If structure changed
- [ ] `README.md` - If functionality added
- [ ] `__init__.py` - Update exports if needed

#### 2. Check Dependency Chain
```python
# Example: If changed core/ocr/engine.py
Check → collectors/* (uses OCR)
Check → orchestration/bookmaker_worker.py (uses OCR)
Check → tests/test_ocr.py (tests OCR)
```

#### 3. Verify Performance
- OCR changes → Run `tests/ocr_performance.py`
- ML changes → Run `tests/ml_phase_performance.py`
- Database changes → Check write speed

---

## CRITICAL MODULE DEPENDENCIES

### Core Files to Understand Together

**Worker Implementation:**
- [orchestration/bookmaker_worker.py](orchestration/bookmaker_worker.py) - Primary worker
- [orchestration/process_manager.py](orchestration/process_manager.py) - Lifecycle management

**Communication:**
- [core/communication/event_bus.py](core/communication/event_bus.py) - Process-safe pub/sub
- [core/communication/shared_state.py](core/communication/shared_state.py) - Optional shared memory

**Database:**
- [data_layer/database/batch_writer.py](data_layer/database/batch_writer.py) - Buffered writes

**Agents:**
- [agents/betting_agent.py](agents/betting_agent.py) - Closure pattern consumer
- [agents/session_keeper.py](agents/session_keeper.py) - Closure pattern consumer
- [agents/strategy_executor.py](agents/strategy_executor.py) - Stateless decision engine

**Collectors:**
- [collectors/base_collector.py](collectors/base_collector.py) - Abstract base
- [collectors/main_collector.py](collectors/main_collector.py) - Round tracking
- [collectors/rgb_collector.py](collectors/rgb_collector.py) - ML training data
- [collectors/phase_collector.py](collectors/phase_collector.py) - Phase transitions

---

## COMMON IMPORT PATTERNS

**Frequently imported in 5+ files:**
- `BatchDatabaseWriter` - AppController, BookmakerWorker, all Collectors, BettingAgent
- `EventPublisher/Subscriber` - BookmakerWorker, Collectors, Agents, AppController
- `GamePhase enum` - BookmakerWorker, Collectors, Agents, shared_state

---

## TESTING REQUIREMENTS

### Before Considering Module Complete:
1. Unit tests for public methods
2. Integration test with related modules
3. Performance benchmark (meet targets)
4. Memory leak check (psutil)
5. Error recovery test

---

## DEBUGGING COMMANDS

```bash
# OCR speed benchmark (must be < 15ms)
python tests/ocr_performance.py

# ML model speed
python tests/ml_phase_performance.py

# Profile code
python -m cProfile -o output.prof main.py

# Test single worker
python -m orchestration.bookmaker_worker

# Region setup and debugging
python utils/region_editor.py        # Interactive setup
python utils/region_visualizer.py    # Visual debug
python utils/diagnostic.py           # System validation (8 steps)
```

---

## NO-GO ZONES

### ❌ NEVER
- Single database inserts (always batch)
- Sequential OCR (must be parallel!)
- Direct process communication (use EventBus for GUI)
- Block main GUI thread with I/O
- Hardcode coordinates/paths
- Global state without locks
- Skip error handling
- Read from DB inside Workers (INSERT only!)

### ❌ DON'T CHANGE WITHOUT DISCUSSION
- Worker Process per Bookmaker architecture
- Shared BatchWriter per TYPE pattern
- EventBus communication
- Closure pattern for agent state access
- TransactionController atomicity

---

## PRIORITY HIERARCHY

When making decisions:
1. **Data Accuracy** - Never compromise
2. **System Stability** - Must run 24/7
3. **Performance** - Meet targets
4. **Features** - Add incrementally
5. **UI/UX** - Polish last

---

## QUESTIONS TO ASK YOURSELF

Before implementing:
1. Does this follow Worker Process per Bookmaker pattern?
2. Am I using batch operations for database?
3. Is this loosely coupled (EventBus for GUI, closures for agents)?
4. Have I handled all error cases?
5. Will this scale to 6+ bookmakers?
6. Am I using local_state (fast) or SharedGameState (GUI only)?

---

## RED FLAGS TO STOP AND ASK

Stop immediately if:
- Writing sequential OCR code (must be parallel!)
- Doing single database inserts (must batch!)
- Reading from database in Workers (only INSERT!)
- Creating direct inter-process calls (use EventBus for GUI)
- Hardcoding values
- Skipping error handling
- Not writing tests

---

## REMEMBER

This is a **long-term project** focused on:
- **Reliability over features**
- **Data quality over quantity**
- **Maintainability over cleverness**
- **Safety over aggressive profit**

Goal: System runs 24/7 with minimal intervention, collecting accurate data.
