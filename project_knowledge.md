# PROJECT KNOWLEDGE INSTRUCTIONS

## FOR AI SESSIONS

When starting a new Claude session for AVIATOR project development:

### 1. ALWAYS LOAD THESE FILES ON START
```
1. CLAUDE.md          - Core technical principles
2. ARCHITECTURE.md    - System structure
3. STRUCTURE.md       - File organization
4. Project Knowledge INSTRUCTIONS - This file
5. Current module     - File you're working on
6. Related modules    - Files that import or are imported by current
```

### 2. WORK COMPLETION WORKFLOW

#### After completing ANY work:
```python
# 1. Update documentation
UPDATE → CHANGELOG.md (add entry for changes)
UPDATE → ARCHITECTURE.md (if structure changed)
UPDATE → README.md (if functionality added)
UPDATE → __init__.py (update exports in folder)

# 2. Check dependency chain
ANALYZE → Files that import this module
ANALYZE → Files this module imports
UPDATE → Any broken imports
UPDATE → Any changed interfaces

# 3. Example workflow
If changed: core/ocr/engine.py
Then check: → collectors/main_collector.py
           → orchestration/shared_reader.py
           → tests/test_ocr.py
           → Update all if needed
```

### 3. ⚠️ CRITICAL DEVELOPMENT RULES

#### 🚫 VERSIONING ANTI-PATTERN - ABSOLUTE PROHIBITION

**IMPERATIV: NIKADA ne kreirati verzije fajlova ili klasa!**

❌ **ZABRANJENO:**
```python
# NE SMEŠ OVO DA RADIŠ!
my_module_v2.py
my_module_v3.py
MyClassV2
MyClassRefactored
my_module_new.py
my_module_old.py
my_module_backup.py
```

✅ **JEDINI ISPRAVAN NAČIN:**
```python
# DIREKTNO MENJAJ POSTOJEĆI FAJL!
my_module.py  # <- Izmeni ovaj fajl direktno
class MyClass  # <- Isti naziv, nova implementacija
```

**RAZLOG:**
- Git automatski čuva istoriju svake izmene
- Stare verzije zagađuju codebase i prave konfuziju
- Import statements ostaju isti
- Refactoring = ZAMENA postojećeg, ne dodavanje novog

**PROCEDURA:**
1. `git commit` pre refaktorisanja (backup u Git-u!)
2. DIREKTNO izmeni postojeći fajl
3. Testiraj izmene
4. `git commit` sa opisom izmena

**AKO NAPRAVIŠ GREŠKU:**
- `git revert` ili `git checkout` da vratiš fajl
- NEMOJ kreirati `_old` ili `_backup` verzije!

---

#### 🚨 DELETING CODE - CRITICAL PROHIBITION

**IMPERATIV: NIKADA ne brišeš funkcionalnost bez 100% sigurnosti!**

❌ **SCENARIO (LOŠE):**
```python
# Vidiš: self.unknown_manager.do_something()
# Misliš: "Ovo ne postoji, obrišem"
# DELETE <-- FATALNA GREŠKA!
```

✅ **OBAVEZNA PROCEDURA:**
```
1. STOP - Nemoj brisati odmah!

2. ISTRAŽI:
   Glob **/*unknown*.py
   Glob **/*manager*.py
   Grep "unknown_manager" (možda je uvezen sa drugim nazivom)
   Grep "UnknownManager" (možda klasa postoji)

3. PROVERI imports u fajlu

4. AKO NE NAĐEŠ:
   🔴 PITAJ KORISNIKA OBAVEZNO! 🔴

   "Našao sam self.unknown_manager u kodu ali ne mogu
    da nađem tu klasu. Da li:
    - Je promenila naziv?
    - Je premestena u drugi modul?
    - Koja je njena uloga u sistemu?"

5. TEK NAKON ODGOVORA - menjaj kod
```

**PRIMER IZ PROJEKTA (coords_manager):**
```python
# ❌ URAĐENO (LOŠE):
self.coords_manager.calculate_coords(...)  # Obrisan jer ne postoji

# ✅ TREBALO (DOBRO):
# 1. Glob **/*coord*.py -> Našao RegionManager
# 2. Razumeo: coords_manager = RegionManager (promenjen naziv)
# 3. Dodao: self.region_manager = RegionManager()
# 4. Koristio: self.region_manager.get_bookmaker_regions(...)
# ILI
# 1. Pitao: "Ne nalazim coords_manager. Šta to radi?"
# 2. Dobio odgovor: "To je RegionManager sada"
# 3. Ispravio kod
```

**PRAVILO:**
🔴 **Brisanje core funkcije = Sistem ne radi**
🟢 **Pitanje = 1 minut, sistem OK**

**BOLJE 100 PITANJA NEGO 1 OBRISANA CORE FUNKCIJA!**

---

### 4. CORE PRINCIPLES TO REMEMBER

#### DATA ACCURACY > SPEED
- Never sacrifice accuracy for performance
- Validate all data before processing
- Better to miss data than record wrong data

#### WORKER PROCESS PARALLELISM
- ONE BOOKMAKER = ONE PROCESS = ONE CPU CORE
- Each Worker has its OWN OCR reader
- Parallel OCR execution (6 bookmakers = 100ms, not 600ms!)
- Never sequential OCR reading

#### BATCH EVERYTHING
- Never single database insert
- Buffer 50-100 records minimum
- Flush on interval or buffer full

#### ATOMIC TRANSACTIONS
- All betting operations must be atomic
- Use TransactionController for GUI operations
- Lock mechanism for every transaction

#### EVENT-DRIVEN ARCHITECTURE
- All inter-process communication via EventBus
- No direct process-to-process calls
- Pub/Sub pattern for loose coupling

### 3. WHEN CREATING NEW MODULES

#### ALWAYS INCLUDE
```python
"""
Module: [name]
Purpose: [clear description]
Version: [x.x]
"""

import logging
from typing import ...

class YourClass:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # ... initialization
        
    def cleanup(self):
        """Always implement cleanup"""
        pass
        
    def get_stats(self):
        """Always implement stats"""
        return {}
```

#### NEVER DO
- Hard-code paths or coordinates
- Use global variables without locks
- Ignore error handling
- Skip logging
- Create tight coupling between modules

### 4. ADDING A NEW AGENT

Agents run as **threads inside Worker process** (not separate processes).

#### Template Structure:
```python
"""
Module: [AgentName]
Purpose: [Clear description of agent's role]
Version: 1.0
"""

import time
import logging
import threading
from typing import Dict, Optional
from collections import deque

class YourAgent:
    """
    Agent description.

    Runtime: Thread inside Worker process
    Dependencies: [List what it needs]
    Exclusivity: [If conflicts with other agents]
    """

    def __init__(self, bookmaker: str, config: Dict):
        self.bookmaker = bookmaker
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}-{bookmaker}")

        # State
        self.running = False
        self.active = True  # Can be paused

        # Stats
        self.stats = {
            'start_time': time.time(),
            'actions_count': 0
        }

    def run(self):
        """Main agent loop - runs in thread."""
        self.logger.info(f"Starting {self.__class__.__name__}")
        self.running = True

        while self.running:
            try:
                if self.active:
                    # Agent logic here
                    self._do_work()

                time.sleep(1)  # Avoid busy loop

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error: {e}", exc_info=True)
                time.sleep(5)

        self.logger.info(f"{self.__class__.__name__} stopped")

    def _do_work(self):
        """Override this with agent-specific logic."""
        pass

    def pause(self):
        """Pause agent (e.g., when other agent is active)."""
        self.active = False
        self.logger.info("Agent paused")

    def resume(self):
        """Resume agent."""
        self.active = True
        self.logger.info("Agent resumed")

    def stop(self):
        """Stop agent gracefully."""
        self.running = False

    def get_stats(self) -> Dict:
        """Get agent statistics."""
        uptime = time.time() - self.stats['start_time']
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'status': 'active' if self.active else 'paused' if self.running else 'stopped'
        }

    def cleanup(self):
        """Cleanup resources."""
        self.logger.info(f"{self.__class__.__name__} cleanup")
```

#### Integration Steps:

1. **Create agent file** in `agents/your_agent.py`
2. **Add to Worker Process** in `orchestration/bookmaker_worker.py`:
   ```python
   self.your_agent = YourAgent(bookmaker, config)
   self.agent_thread = threading.Thread(
       target=self.your_agent.run,
       daemon=False
   )
   self.agent_thread.start()
   ```
3. **Add GUI tab** in `main.py` (if needed)
4. **Update CHANGELOG.md**

#### Agent Communication:

**Access Worker's local_state:**
```python
# In Worker Process:
class BookmakerWorkerProcess:
    def start_agents(self):
        self.betting_agent = BettingAgent(
            get_state_fn=lambda: self.local_state,  # Closure!
            get_history_fn=lambda: list(self.round_history)
        )

# In BettingAgent:
class BettingAgent:
    def __init__(self, get_state_fn, get_history_fn):
        self.get_state = get_state_fn
        self.get_history = get_history_fn

    def _do_work(self):
        state = self.get_state()  # Reads Worker's local_state
        history = self.get_history()  # Reads Worker's round_history
```

**Mutual Exclusivity (e.g., BettingAgent vs SessionKeeper):**
```python
# When BettingAgent starts:
def start_betting(self):
    self.session_keeper.pause()  # Pause SessionKeeper
    self.betting_agent.resume()

# When SessionKeeper starts:
def start_session_keeping(self):
    self.betting_agent.pause()  # Pause BettingAgent
    self.session_keeper.resume()
```

### 5. TESTING REQUIREMENTS

Before considering any module complete:
1. Unit tests for all public methods
2. Integration test with related modules
3. Performance benchmark
4. Memory leak check
5. Error recovery test

### 5. DOCUMENTATION STANDARDS

Every function must have:
```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """
    Brief description.
    
    Args:
        param1: Description
        param2: Description
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this happens
    """
```

### 6. PERFORMANCE TARGETS

Critical operations must meet:
- OCR: < 15ms per read
- Database batch write: > 5000 records/sec
- Event processing: < 10ms
- Memory per worker: < 100MB

### 7. GIT WORKFLOW

Commit messages format:
```
[TYPE] Brief description

Detailed explanation if needed

- Bullet point 1
- Bullet point 2
```

Types: FEATURE, FIX, REFACTOR, PERF, DOCS, TEST

### 8. PRIORITY HIERARCHY

When making decisions, prioritize in this order:
1. **Data Accuracy** - Never compromise
2. **System Stability** - Must run 24/7
3. **Performance** - Meet targets
4. **Features** - Add incrementally
5. **UI/UX** - Polish last

### 9. QUESTIONS TO ASK

Before implementing anything:
1. Does this follow Worker Process per Bookmaker pattern (parallel)?
2. Am I using batch operations for database?
3. Is this loosely coupled (EventBus for GUI, direct for workers)?
4. Have I handled all error cases?
5. Will this scale to 6+ bookmakers?
6. Am I using local_state (fast) or SharedGameState (GUI only)?

### 10. RED FLAGS TO AVOID

Stop immediately if you find yourself:
- Writing sequential OCR code (must be parallel!)
- Doing single database inserts (must batch!)
- Reading from database in Workers (only INSERT!)
- Creating direct inter-process calls (use EventBus for GUI)
- Hardcoding values
- Skipping error handling
- Not writing tests

## FOR HUMAN DEVELOPERS

When reviewing code or planning features:

### ASK THESE QUESTIONS
1. Is the architecture consistent with ARCHITECTURE.md?
2. Are core principles from CLAUDE.md followed?
3. Is the code testable and maintainable?
4. Will this work at scale (6+ bookmakers)?
5. Is error recovery implemented?

### CHECK THESE ITEMS
- [ ] Follows Worker Process per Bookmaker pattern (parallel OCR)
- [ ] Uses batch database operations (no single inserts)
- [ ] Uses local_state primarily, SharedGameState only for GUI
- [ ] Communicates via EventBus for GUI updates
- [ ] Has proper error handling
- [ ] Includes cleanup methods
- [ ] Has statistics tracking
- [ ] Documented properly
- [ ] Has unit tests

### REMEMBER
This is a long-term project focused on:
- **Reliability over features**
- **Data quality over quantity**  
- **Maintainability over cleverness**
- **Safety over aggressive profit**

The goal is a system that runs 24/7 with minimal intervention, collecting accurate data and executing safe betting strategies.