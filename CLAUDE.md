# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## PROJECT OVERVIEW
AVIATOR - Multi-bookmaker Aviator game tracking system with OCR, ML predictions, and automated betting.

**Core principle:** 1 Bookmaker = 1 Process = 1 CPU Core (parallel OCR execution)

## CRITICAL DEVELOPMENT COMMANDS

### Application Entry Points
```bash
python main.py                              # GUI Control Panel (primary interface)
python utils/region_editor.py               # CRITICAL: Setup screen regions interactively
python utils/region_visualizer.py           # Debug: Visualize current regions with overlays
python utils/diagnostic.py                  # System diagnostic (8-step validation)
python utils/template_generator.py          # Generate OCR templates from screenshots
```

### Testing
```bash
python -m pytest tests/                     # All tests
python -m pytest tests/ocr_performance.py   # OCR speed benchmark (must be < 15ms)
python -m orchestration.bookmaker_worker    # Test single worker in isolation
```

### Dependencies
```bash
pip install -r requirements.txt
# CRITICAL: Tesseract OCR must be installed SEPARATELY
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

---

## 🚨 ABSOLUTE DEVELOPMENT RULES

### RULE #0: NEVER LIE
**You MUST provide concrete evidence for ANY claim about completed work.**

❌ FORBIDDEN:
- "I checked all files" → **MUST list specific files and line numbers**
- "I fixed the errors" → **MUST show exact changes made**
- Giving generic answers without specific details

✅ REQUIRED:
- If unsure → ASK immediately
- If complex → Propose breaking into sub-tasks
- If something doesn't exist → SAY SO and ask for clarification

**Verification:** If you cannot provide file paths and line numbers, you are lying.

---

### RULE #1: NO VERSION SUFFIXES - EVER!
❌ **FORBIDDEN:**
```python
bookmaker_worker_v2.py
BookmakerWorkerV3
my_module_new.py
my_module_backup.py
```

✅ **REQUIRED:**
```python
bookmaker_worker.py  # Edit directly - Git stores history!
```

**Procedure:**
1. `git commit` before changes (backup in Git)
2. Edit existing file DIRECTLY
3. Test changes
4. `git commit` with clear message

---

### RULE #2: NEVER DELETE FUNCTIONALITY WITHOUT VERIFICATION
Before deleting ANY code:

1. **STOP** - Do NOT delete immediately
2. **SEARCH** - Use Glob/Grep to find the class/function
3. **UNDERSTAND** - Read what it does
4. **ASK USER** if not found - Do NOT assume it's obsolete!

**Example from this project:**
```python
# WRONG: Deleted self.coords_manager because I didn't find it
# RIGHT: Search for RegionManager (it was renamed!)
# RIGHT: Ask user: "coords_manager not found - was it renamed to RegionManager?"
```

**Rule:** Better 100 questions than 1 deleted core feature.

---

## ARCHITECTURE: THE BIG PICTURE

### Core Principle: Worker Process Parallelism

```
6 Bookmakers = 6 Processes = 6 CPU Cores = 100ms OCR (not 600ms!)

Main Process (GUI)
├── ProcessManager (spawns workers)
├── EventBus (receives events)
└── Shared BatchWriters (one per TYPE)
    │
    └─> Spawns 6 Worker Processes:
        │
        ├─ Worker 1 (Admiral) ─> Own OCR Reader
        ├─ Worker 2 (Mozzart) ─> Own OCR Reader  } Parallel
        ├─ Worker 3 (Balkan)  ─> Own OCR Reader  } on CPU
        └─ ... (up to 6)                          } cores

        Each Worker contains:
        ├─ local_state dict (in-process, FAST)
        ├─ round_history list (100 rounds for strategy)
        ├─ Collectors (MainCollector, RGBCollector)
        └─ Agents as threads (BettingAgent, SessionKeeper)
```

**Why processes not threads?** Python GIL prevents true parallelism. OCR is CPU-intensive (100ms), so 6 threads = 600ms sequential. 6 processes = 100ms parallel.

---

## KEY ARCHITECTURAL PATTERNS

### Pattern 1: Shared BatchWriter Per TYPE (Not Per Worker!)

```python
# ❌ WRONG - Each worker has own writer
Worker1 → BatchWriter1 → 10 records → flush
Worker2 → BatchWriter2 → 10 records → flush
Total: 2 flushes (inefficient)

# ✅ CORRECT - All workers share ONE writer per TYPE
main_writer = BatchDatabaseWriter('main_game.db', batch_size=100)

Worker1 → main_writer.add(record) ┐
Worker2 → main_writer.add(record) ├─> 100 records → ONE flush
Worker3 → main_writer.add(record) ┘

# Why: 50-100x faster batch operations
# Thread-safe: BatchWriter has internal lock
# SQLite WAL mode: Allows concurrent writes
```

**Implementation:**
```python
# In gui/app_controller.py (lines 49-110)
self.db_writers = {
    'main': BatchDatabaseWriter('main_game_data.db', batch_size=100),
    'betting': BatchDatabaseWriter('betting_history.db', batch_size=50),
    'rgb': BatchDatabaseWriter('rgb_training_data.db', batch_size=100)
}

# Pass SAME instances to ALL workers
worker = BookmakerWorker(db_writers=self.db_writers)  # Shared!
```

---

### Pattern 2: Closure Pattern for Agent Access to local_state

**Problem:** Agents run as threads inside Worker process. How do they access Worker's `local_state`?

**Solution:** Pass closure functions, NOT shared memory.

```python
# In orchestration/bookmaker_worker.py (lines 216-228)
class BookmakerWorker:
    def setup_agents(self):
        # Create closure functions that capture self
        def get_state_fn() -> Dict:
            return self.local_state.copy()

        def get_history_fn() -> List[Dict]:
            return self.round_history.copy()

        # Pass closures to agents (NOT shared memory!)
        self.betting_agent = BettingAgent(
            get_state_fn=get_state_fn,      # Closure
            get_history_fn=get_history_fn   # Closure
        )

# In agents/betting_agent.py (lines 72-73)
class BettingAgent:
    def __init__(self, get_state_fn, get_history_fn):
        self.get_state = get_state_fn  # Store closure

    def _do_work(self):
        state = self.get_state()  # Call closure → instant access!
```

**Why closures?**
- In-process access (no multiprocessing overhead)
- Thread-safe (threads in same process share memory)
- No need for Manager().dict() (expensive)

---

### Pattern 3: Worker Process Initialization Flow

**Complete initialization chain:**

```python
# 1. GUI creates ProcessManager
process_manager = ProcessManager()

# 2. GUI registers workers with WorkerConfig
config = WorkerConfig(
    name='Admiral',
    target_func=worker_entry_point,  # From bookmaker_worker.py
    kwargs={
        'bookmaker_name': 'Admiral',
        'bookmaker_index': 0,
        'coords': coords_dict,
        'db_writers': self.db_writers  # Shared instances!
    }
)
process_manager.register_worker(config)

# 3. ProcessManager wraps with _worker_wrapper
process = Process(
    target=self._worker_wrapper,
    args=(config, self.shutdown_event, self.health_queue)
)

# 4. Wrapper INJECTS shutdown_event into kwargs
def _worker_wrapper(config, shutdown_event, health_queue):
    kwargs = config.kwargs.copy()
    kwargs['shutdown_event'] = shutdown_event  # Injected!
    config.target_func(**kwargs)  # Calls worker_entry_point

# 5. worker_entry_point creates BookmakerWorker and runs
def worker_entry_point(bookmaker_name, coords, db_writers, shutdown_event, ...):
    worker = BookmakerWorker(...)
    worker.run()  # Main OCR loop
```

**Key insight:** `shutdown_event` is NOT in target_func signature - wrapper injects it!

---

### Pattern 4: Adaptive OCR Intervals

Workers adjust OCR speed based on game phase:

```python
# orchestration/bookmaker_worker.py (lines 102-108)
OCR_INTERVALS = {
    GameState.WAITING: 1.0,      # Slow (1 read/sec)
    GameState.BETTING: 0.5,      # Medium (2 reads/sec)
    GameState.LOADING: 0.5,      # Medium
    GameState.PLAYING: 0.15,     # FAST (7 reads/sec) - score changes rapidly!
    GameState.ENDED: 2.0,        # Slow (0.5 reads/sec)
}
```

**Performance impact:** During active play, system reads 7x per second to catch threshold crossings. When idle, reduces to 1 read per 2 seconds (saves 93% CPU).

---

## CRITICAL MODULE DEPENDENCIES

### Core Orchestration (bookmaker_worker.py)
**Primary worker implementation - understand this first!**

```python
class BookmakerWorker:
    def __init__(self,
                 bookmaker_name: str,
                 bookmaker_index: int,           # For SessionKeeper offset
                 coords: Dict[str, Dict],        # Screen regions
                 db_writers: Dict[str, BatchDatabaseWriter],  # Shared!
                 shutdown_event: MPEvent,
                 health_queue: Queue):

        # Local state (in-process, fast)
        self.local_state = {}
        self.round_history = []  # Last 100 rounds

        # Own OCR reader (parallel execution!)
        self.ocr_reader = MultiRegionOCRReader(coords)

        # Collectors (use local_state)
        self.main_collector = MainCollector(db_writers['main'])

        # Agents (use closures to access local_state)
        self.betting_agent = BettingAgent(
            get_state_fn=lambda: self.local_state.copy(),
            get_history_fn=lambda: self.round_history.copy()
        )
```

---

### Data Flow: local_state vs SharedGameState

```python
# PRIMARY: local_state (in-process dict)
Worker Process:
    OCR → local_state → Collectors (read local_state)
                     → Agents (closure to local_state)

# OPTIONAL: SharedGameState (for GUI monitoring)
Worker Process:
    local_state → Periodically copy to SharedGameState

GUI Process:
    SharedGameState → Read for statistics display
```

**Key difference:**
- **local_state**: Primary data, fast in-process access
- **SharedGameState**: Optional copy for GUI, slower (multiprocessing overhead)

**Why both?** Workers work with local_state (no overhead). GUI reads SharedGameState (monitoring only).

---

### Agents Architecture

```python
agents/
├── betting_agent.py        → Betting execution (thread)
│   - Stores round_history (deque 100)
│   - Calls StrategyExecutor for decisions
│   - Executes via TransactionController
│   - When active → SessionKeeper PAUSED
│
├── session_keeper.py       → Session maintenance (thread)
│   - Sends fake clicks to keep session alive
│   - Interval: 250-350s random
│   - First click: 300s + (30s × bookmaker_index) offset
│   - When active → BettingAgent PAUSED
│
└── strategy_executor.py    → Strategy decision engine (object)
    - Input: round_history (100 rounds)
    - Output: {bet_amounts: [...], auto_stops: [...], current_index: 0}
    - Stateless - pure function
```

**CRITICAL:** BettingAgent and SessionKeeper NEVER run simultaneously for same bookmaker!

---

### Collectors Architecture

```python
collectors/
├── base_collector.py       → Abstract base
│   - Unified interface for all collectors
│   - Statistics tracking (cycles, errors, rate)
│   - Data validation before DB writes
│
├── main_collector.py       → Round & threshold tracking
│   - Monitors game phases
│   - Detects round end
│   - Tracks threshold crossings (1.5x, 2.0x, 3.0x, etc.)
│
├── rgb_collector.py        → ML training data
│   - Direct screen capture (no OCR)
│   - 2 Hz sampling (500ms intervals)
│   - Extracts RGB statistics (mean, std)
│
└── phase_collector.py      → Phase transition tracking
    - Tracks BETTING → PLAYING → ENDED transitions
    - Records phase durations
    - Pattern analysis for ML
```

**Difference: PhaseCollector vs RGBCollector**
- **PhaseCollector**: Logical phase changes (from OCR results) - infrequent
- **RGBCollector**: Raw RGB pixels (direct capture) - frequent (2 Hz)
- Both needed for different purposes (flow analysis vs ML training)

---

## PERFORMANCE REQUIREMENTS

| Metric | Target | Critical? |
|--------|--------|-----------|
| OCR Speed | < 15ms | ✅ YES - template matching |
| Batch Write | > 5000 records/sec | ✅ YES - buffer 50-100 |
| Memory/Worker | < 100MB | ⚠️ Monitor with psutil |
| CPU/Worker | < 10% idle | ⚠️ Adjust OCR intervals |

**Priority:** Data Accuracy > Speed
- Better to skip data than record wrong data
- Validate ALL data before database writes
- Implement retry mechanisms for critical operations

---

## COMMON DEVELOPMENT PATTERNS

### Adding a New Collector

1. **Extend BaseCollector** (`collectors/base_collector.py`)
2. **Implement required methods:**
   ```python
   def collect(self, state: Dict) -> Optional[Dict]:
       # Process state, return data or None

   def validate(self, data: Dict) -> bool:
       # Validate before DB write
   ```
3. **Use shared BatchWriter** (passed in constructor)
4. **Register in BookmakerWorker.setup()** (`orchestration/bookmaker_worker.py`)

---

### Adding a New Agent

**Agents run as THREADS inside Worker process.**

Template structure:
```python
class YourAgent:
    def __init__(self, bookmaker: str, get_state_fn, config: Dict):
        self.bookmaker = bookmaker
        self.get_state = get_state_fn  # Closure to Worker's local_state
        self.running = False
        self.active = True  # Can be paused

    def run(self):
        """Main agent loop - runs in thread."""
        self.running = True
        while self.running:
            if self.active:
                state = self.get_state()  # Access Worker's local_state
                self._do_work(state)
            time.sleep(1)

    def pause(self):
        """Pause when another agent is active."""
        self.active = False

    def stop(self):
        """Stop gracefully."""
        self.running = False
```

**Integration:**
1. Create agent file in `agents/your_agent.py`
2. Add to BookmakerWorker.setup_agents()
3. Start as thread: `threading.Thread(target=agent.run, daemon=False)`

---

## WORKFLOW FOR NEW SESSIONS

### On Session Start - ALWAYS Read These Files FIRST:
```
1. CLAUDE.md (this file) - Core principles
2. ARCHITECTURE.md - Detailed system design
3. README.md - Project overview
4. CHANGELOG.md - Recent changes
5. project_knowledge.md - Project-specific patterns
```

### Critical: ASK BEFORE CODING
- If ANY aspect is unclear → ASK first
- If multiple approaches exist → ASK which to use
- If requirements are missing → ASK for details
- Only after clear answers → Proceed with implementation

### After Completing Work:
1. **Update documentation:**
   - `CHANGELOG.md` - **MUST** add entry
   - `ARCHITECTURE.md` - If structure changed
   - `README.md` - If functionality added

2. **Check dependency impact:**
   ```python
   # Example: If changing core/ocr/engine.py
   Check → collectors/* (uses OCR)
   Check → orchestration/bookmaker_worker.py (uses OCR)
   Check → tests/test_ocr.py (tests OCR)
   ```

3. **Performance verification:**
   - OCR changes → Run `tests/ocr_performance.py`
   - ML changes → Run `tests/ml_phase_performance.py`
   - Database changes → Check write speed

---

## NO-GO ZONES

### ❌ NEVER
- Single database inserts (always batch)
- Sequential OCR reading (must be parallel!)
- Direct process-to-process communication (use EventBus for GUI)
- Block main GUI thread with I/O operations
- Hardcode coordinates or paths
- Use global state without locks
- Skip error handling
- Read from database inside Workers (INSERT only, no SELECT!)

### ❌ DON'T CHANGE WITHOUT DISCUSSION
- Worker Process per Bookmaker architecture
- Shared BatchWriter per TYPE pattern
- EventBus communication
- Closure pattern for agent state access
- Transaction atomicity (TransactionController)

---

## DEBUGGING & TROUBLESHOOTING

### OCR Not Reading Correctly
1. Check browser zoom is exactly 100%
2. Verify Tesseract: `tesseract --version`
3. Use region visualizer: `python utils/region_visualizer.py`
4. Check screen resolution and monitor setup

### Worker Process Crashes
1. Check logs in GUI log widgets
2. Look for unhandled exceptions in worker loop
3. Verify shared memory access is defensive (use `.get()`)
4. Check EventBus queue depth
5. Memory leak - check with `psutil`

### Performance Issues
```bash
python tests/ocr_performance.py         # OCR speed benchmark
python tests/ml_phase_performance.py    # ML model speed
python -m cProfile -o output.prof main.py
```

---

## IMPORTANT CONSTRAINTS

### Platform
- **Windows Only** (uses pywin32 for GUI automation)
- **Tesseract Required** (must install separately)
- **Python 3.11+** required

### Performance Limits
- **Max Bookmakers**: 6 (current layout)
- **OCR Speed Target**: < 15ms
- **Memory Budget**: < 100MB per worker
- **Batch Size**: 50-100 records (optimal)

### Safety
- **NEVER** run on real money without explicit confirmation
- **ALWAYS** use DEMO mode for testing
- **NEVER** ignore validation errors
- **ALWAYS** flush buffers on shutdown

---

## REMEMBER ALWAYS

1. **Data Accuracy > Speed** - Better slow and correct than fast and wrong
2. **Worker Process Parallelism** - 1 Bookmaker = 1 Process = 1 CPU Core
3. **Batch Everything** - Never single operations (50-100x faster)
4. **Shared Writers per TYPE** - Not per worker (massive efficiency gain)
5. **Closure Pattern** - Agents access local_state via closures (no multiprocessing overhead)
6. **Event-Driven GUI** - EventBus for loose coupling
7. **Atomic Transactions** - All-or-nothing for betting
8. **Update Docs** - Always update CHANGELOG.md after work
9. **Verify Dependencies** - Check impact on related files
10. **ASK When Unsure** - Better 100 questions than 1 broken feature
