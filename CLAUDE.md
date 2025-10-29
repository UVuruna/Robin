# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## PROJECT OVERVIEW
AVIATOR - Multi-bookmaker Aviator game tracking system with OCR, ML predictions, and automated betting.

**Core Architecture:** v3.0 - Worker Process Pattern
**Core Principle:** 1 Bookmaker = 1 Process = 1 CPU Core (parallel OCR execution)

---

## 🔄 MANDATORY WORKFLOW

**CRITICAL:** This is the WORKFLOW you MUST follow for EVERY task. Not following this workflow is unacceptable.

### PHASE 1: BEFORE STARTING WORK - ASK QUESTIONS

Before writing ANY code or making ANY changes, you MUST:

1. **Read the task carefully** - Understand what is being asked
2. **Identify ambiguities** - What is unclear? What could be interpreted multiple ways?
3. **Ask questions** - NEVER assume, ALWAYS verify:
   - "Should I modify existing file X or create new one?"
   - "You mentioned Y - did you mean Z or something else?"
   - "I see three approaches (A, B, C) - which one do you prefer?"
   - "Should I update tests/docs as well?"
4. **Propose approach** - Explain HOW you will solve it, get confirmation
5. **Only after user confirms** → Start work

**Why this matters:**
- Prevents wasted work on wrong assumptions
- Catches misunderstandings early
- Ensures we're solving the RIGHT problem

**Example:**
```
User: "Fix the layout logic"

WRONG Response:
✗ "I'll refactor the layout code..." [starts coding immediately]

CORRECT Response:
✓ "Before I start, let me clarify:
   1. Do you want me to remove hardcoded if/elif checks?
   2. Should I centralize layout config in one place?
   3. Are you planning to add new layouts (layout_10, layout_12)?
   4. Should I update all 15 files that reference layout, or focus on core logic first?
   [waits for answers before starting]"
```

---

### PHASE 2: AFTER COMPLETING WORK - VERIFY COMPLIANCE

After finishing ANY task, you MUST perform explicit **Rule Compliance Check**:

#### Compliance Checklist:

**✅ RULE #0: NEVER LIE**
- [ ] Did I provide specific file paths and line numbers?
- [ ] Did I show actual before/after code changes?
- [ ] Did I give concrete evidence for all claims?

**✅ RULE #1: NO VERSION SUFFIXES**
- [ ] Did I edit existing files directly (not create _v2, _new, _backup)?
- [ ] Are all filenames clean without version numbers?

**✅ RULE #2: NEVER DELETE WITHOUT VERIFICATION**
- [ ] If I deleted code, did I search/verify it's not used elsewhere?
- [ ] Did I ask user before removing seemingly obsolete code?

**✅ RULE #3: NO HARDCODED VALUES**
- [ ] Did I check for hardcoded dimensions, paths, colors, timeouts?
- [ ] Are all config values loaded from JSON or settings.py?
- [ ] Did I use PATH constants instead of string literals?

**✅ RULE #4: NO BACKWARD COMPATIBILITY**
- [ ] Did I update ALL callers when refactoring?
- [ ] Did I avoid creating wrapper methods "for compatibility"?

**✅ RULE #5: NO DEFENSIVE PROGRAMMING FOR IMPOSSIBLE SCENARIOS**
- [ ] Did I add checks only for REAL threats (external input, I/O)?
- [ ] Did I avoid checking for impossible scenarios (data validated in __init__)?

**⚠️ SUSPICIOUS ITEMS - ASK USER:**
- List anything that seems questionable
- Example: "I added a new method X - is this the right design?"
- Example: "I noticed Y is duplicated in 3 places - should we refactor?"

**📊 FINAL REPORT FORMAT:**
```
## 🔍 RULE COMPLIANCE VERIFICATION

✅ RULE #0: [Compliant/Issue found]
✅ RULE #1: [Compliant/Issue found]
✅ RULE #2: [Compliant/Issue found]
✅ RULE #3: [Compliant/Issue found]
✅ RULE #4: [Compliant/Issue found]
✅ RULE #5: [Compliant/Issue found]

⚠️ QUESTIONS FOR USER:
1. [Any suspicious items]
2. [Any design concerns]

✅ OVERALL STATUS: [COMPLIANT / ISSUES FOUND]
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

### RULE #3: NO HARDCODED VALUES - ALWAYS USE CONFIGURATION

**CRITICAL:** Before hardcoding ANY value, ASK: "Will this be used in multiple places? Should this be configurable?"

❌ **FORBIDDEN:**
```python
# WRONG - Hardcoded colors
REGION_COLORS = {
    "score_region": (0, 255, 0),
    "my_money": (255, 0, 0)
}

# WRONG - Hardcoded paths
json_file = Path("data/json/config.json")

# WRONG - Hardcoded configuration
TIMEOUT = 30
MAX_RETRIES = 3
```

✅ **REQUIRED:**
```python
# RIGHT - Load from JSON
from config.settings import PATH
with open(PATH.screen_regions) as f:
    region_colors = json.load(f)["region_colors"]

# RIGHT - Use PATH constants
json_file = PATH.screen_regions

# RIGHT - Use config classes
from config.settings import BETTING
timeout = BETTING.lock_timeout
```

**Configuration hierarchy:**
1. **config/static/** - Version-controlled configuration (screen regions, bookmakers, ML models)
2. **config/settings.py** - PATH constants and runtime config classes
3. **config/user/** - User-specific settings (NOT in Git)

**When to hardcode:**
- Constants that NEVER change: `PI = 3.14159`, `MAX_INT = 2**31`
- Implementation details: loop counters, temporary values
- Development-only debugging values (with clear comment)

**Golden rule:** If you're about to type a literal value (string, number, dict), ask: "Should this be in a JSON file or settings.py?"

---

### RULE #4: NO BACKWARD COMPATIBILITY - REFACTOR PROPERLY

**CRITICAL:** When refactoring, ALWAYS update ALL callers. NEVER add "backward compatibility" wrappers!

❌ **FORBIDDEN - "Backward Compatibility":**
```python
# WRONG - Adding wrapper method to avoid fixing callers
def load_config(self):  # "backward compatibility"
    """Old method that combines new split methods."""
    return {
        'betting': self.get_betting_agent_config(),
        'last_setup': self.get_last_setup()
    }
```

✅ **REQUIRED - Proper Refactoring:**
```python
# Step 1: Remove old method completely
# OLD: config = manager.load_config()

# Step 2: Update ALL callers to use new methods
betting = manager.get_betting_agent_config()
last_setup = manager.get_last_setup()
```

**Why "backward compatibility" is BAD:**
- Creates **technical debt** - old code never gets updated
- Hides the need for refactoring
- Makes codebase confusing (multiple ways to do same thing)
- Accumulates cruft over time

**Refactoring procedure:**
1. Search for ALL callers: `Grep pattern="old_method\("`
2. Update EACH caller to use new API
3. Delete old method completely
4. Test that nothing calls old method anymore

**Exception:** NEVER. No exceptions. If you refactor, refactor EVERYTHING.

**Golden rule:** If you're tempted to add "backward compatibility" → You're doing refactoring WRONG.

---

### RULE #5: NO DEFENSIVE PROGRAMMING FOR IMPOSSIBLE SCENARIOS

**CRITICAL:** Before adding try/except blocks or defensive checks, ASK: "Can this scenario actually happen?"

❌ **FORBIDDEN - Defensive Code for Impossible Scenarios:**
```python
# WRONG - Checking for impossible scenario
def _calculate_preview_bounds(self):
    if not self.coords:  # ← Impossible! Always set in __init__
        return 0, 0, 1280, 1044  # Hardcoded fallback!

    # Process coords...

# WRONG - Catching exceptions that can't happen
try:
    value = self.required_attribute  # Always exists after __init__
except AttributeError:
    value = default_value  # Dead code!
```

✅ **REQUIRED - Trust Your Initialization:**
```python
# RIGHT - No check needed if truly impossible
def _calculate_preview_bounds(self):
    # self.coords is GUARANTEED to exist after _load_coords() in __init__
    # Process coords directly...

# RIGHT - Document requirements instead
def process_data(self, data: Dict):
    """Process data.

    Args:
        data: Non-empty dictionary (validated by caller)
    """
    # Trust that caller validated data
    return data["required_key"]
```

**When defensive code IS appropriate:**
- External input (user input, file I/O, network requests)
- Cross-process communication (multiprocessing, IPC)
- Public API boundaries (library interfaces)
- Known edge cases from production logs

**When defensive code is NOT appropriate:**
- Internal method calls within same class
- Data that's validated in __init__
- Scenarios that would indicate a programming bug (not runtime error)

**Decision procedure:**
1. **ASK:** "What conditions would cause this scenario?"
2. **TRACE:** Can those conditions actually occur given the code flow?
3. **VERIFY:** If unsure, ASK the user before adding defensive code
4. **DOCUMENT:** If truly impossible, add comment explaining why no check is needed

**Why avoid defensive programming for impossible scenarios:**
- Hides bugs instead of exposing them
- Adds unnecessary code complexity
- Creates hardcoded fallback values (violates RULE #3)
- Suggests lack of confidence in the code structure

**Golden rule:** If the scenario is impossible, let it fail loudly. Defensive code should defend against REAL threats, not imaginary ones.

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

**Implementation:** See `gui/app_controller.py:_init_shared_writers()`

---

### Pattern 2: Closure Pattern for Agent Access to local_state

**Problem:** Agents run as threads inside Worker process. How do they access Worker's `local_state`?

**Solution:** Pass closure functions, NOT shared memory.

```python
# In orchestration/bookmaker_worker.py
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

# In agents/betting_agent.py
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
# orchestration/bookmaker_worker.py
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

### Core Orchestration (orchestration/bookmaker_worker.py)
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

### Screen Region Management (core/capture/region_manager.py)

**RegionManager** handles all screen coordinate calculations and multi-monitor support.

**Key Classes:**
- `Region`: Simple dataclass with left, top, width, height
- `RegionManager`: Core class that:
  - Detects monitors using MSS
  - Loads region configurations from JSON
  - Calculates dynamic coordinates for different layouts (2x2, 2x3, 2x4)
  - Transforms base regions to specific grid positions

**Key Methods:**
```python
RegionManager.get_region(region_name, position, layout, monitor)
    # Returns Region with calculated coordinates for specific bookmaker position

RegionManager.get_all_regions_for_position(position, layout, monitor)
    # Returns all regions for one bookmaker

RegionManager.get_bookmaker_regions(bookmaker_name, bookmaker_config)
    # Returns all regions based on bookmaker's config
```

**Usage in Worker:**
```python
# Workers receive pre-calculated coords dict, NOT RegionManager instance
worker = BookmakerWorker(
    coords={'score': {'left': 100, 'top': 200, 'width': 300, 'height': 100}}
)
```

**Important:** RegionManager is used ONCE during initialization in GUI/setup, then coordinates are passed as plain dicts to workers.

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
1. CLAUDE.md (this file) - Core principles and workflow
2. ARCHITECTURE.md - Detailed system design
3. README.md - Project overview
4. CHANGELOG.md - Recent changes
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
   - OCR changes → Run `pytest tests/ocr_performance.py`
   - ML changes → Run `pytest tests/ml_phase_performance.py`
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
3. Check screen resolution and monitor setup
4. **Class to investigate:** `core.ocr.engine.MultiRegionOCRReader`

### Worker Process Crashes
1. Check logs in GUI log widgets
2. Look for unhandled exceptions in worker loop
3. Verify shared memory access is defensive (use `.get()`)
4. Check EventBus queue depth
5. Memory leak - check with `psutil`
6. **Class to investigate:** `orchestration.bookmaker_worker.BookmakerWorker`

### RegionManager / Coordinate Issues
1. **Class:** `core.capture.region_manager.RegionManager`
2. Verify monitor detection: `RegionManager._detect_monitors()`
3. Check layout calculations: `RegionManager.calculate_layout_offsets()`
4. Inspect config file: `config/screen_regions.json`

---

## IMPORTANT CONSTRAINTS

### Platform
- **Windows Only** (uses pywin32 for GUI automation)
- **Tesseract Required** (must install separately)
- **Python 3.11+** required (tested on 3.13)

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

1. **MANDATORY WORKFLOW** - ASK questions before work, VERIFY compliance after work
2. **Data Accuracy > Speed** - Better slow and correct than fast and wrong
3. **Worker Process Parallelism** - 1 Bookmaker = 1 Process = 1 CPU Core
4. **Batch Everything** - Never single operations (50-100x faster)
5. **Shared Writers per TYPE** - Not per worker (massive efficiency gain)
6. **Closure Pattern** - Agents access local_state via closures (no multiprocessing overhead)
7. **Event-Driven GUI** - EventBus for loose coupling
8. **Atomic Transactions** - All-or-nothing for betting
9. **Update Docs** - Always update CHANGELOG.md after work
10. **Verify Dependencies** - Check impact on related files
11. **ASK When Unsure** - Better 100 questions than 1 broken feature
