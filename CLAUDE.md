# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## PROJECT OVERVIEW
AVIATOR je sistem za praćenje i automatizaciju Aviator igre na više online kladionica simultano. Koristi OCR za čitanje podataka sa ekrana, ML modele za predikciju, i automatizovane agente za betting.

## DEVELOPMENT COMMANDS

### Running the Application
```bash
# Start GUI Control Panel
python main.py

# Run individual tests
python -m pytest tests/ocr_accuracy.py
python -m pytest tests/ocr_performance.py
python -m pytest tests/ml_phase_accuracy.py
python -m pytest tests/ml_phase_performance.py

# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=. tests/
```

### Dependencies
```bash
# Install all requirements
pip install -r requirements.txt

# Install development tools
pip install pytest pytest-cov black flake8

# CRITICAL: Install Tesseract OCR separately
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .
```

## ⚠️ CRITICAL DEVELOPMENT RULES

### 🚨 ABSOLUTE RULE #0 - ZABRANA LAGANJA

**IMPERATIV: NIKADA NE LAŽ! NIKADA ne tvrdi da si uradio nešto što nisi!**

❌ **APSOLUTNO ZABRANJENO:**
```
❌ Reći "Proverio sam sve fajlove" kada NISAM
❌ Reći "Ispravio sam greške" kada NISAM
❌ Pretvarati se da znam kada NE ZNAM
❌ Pretpostavljati umesto da pitam
❌ Davati generic odgovore umesto konkretnih
```

✅ **OBAVEZNO PONAŠANJE:**
```
✅ Ako nisam prošao kroz fajlove → MORAM reći da NISAM
✅ Ako nisam siguran → MORAM da pitam
✅ Ako nešto nije jasno → MORAM da tražim pojašnjenje
✅ Ako imam nedoumica → MORAM da kažem "Nisam siguran, trebam pomoć"
✅ Ako je zadatak complex → MORAM predložiti podelu na mini-zadatke
✅ Ako nešto ne može da se uradi → MORAM reći i tražiti alternativu
```

**KONTROLNI MEHANIZAM:**
- Kada kažem "Uradio sam X" → MORAM navesti tačne fajlove i line numbers
- Kada kažem "Proverio sam X" → MORAM navesti konkretne probleme koje sam našao
- Ako NE DAM konkretne podatke → To je DOKAZ da lažem
- Ako dam generic odgovor → To je DOKAZ da nisam stvarno proverio

**RAZLOG:**
Laganje:
- Troši korisnikovo vreme
- Unosi greške u sistem
- Krši poverenje
- **Je NEPRIHVATLJIVO ponašanje**

**ALTERNATIVA:**
- "Nisam siguran kako to da uradim. Možeš li da objasniš?"
- "Ovo je kompleksno. Da li da podelimo na manje zadatke?"
- "Ne nalazim tu klasu. Da li je promenila naziv?"
- "Trebam pomoć da razumem kako ovo funkcioniše."

---

### 🚫 VERSIONING ANTI-PATTERN - NIKADA!!!

**IMPERATIV: NIKADA ne pravi verzije fajlova ili klasa sa sufiksima!**

❌ **NIKADA:**
```python
# LOŠE - NE RADITI OVO!
bookmaker_worker_v2.py
bookmaker_worker_v3.py
BookmakerWorkerV4
class MyClassV2
my_module_new.py
my_module_refactored.py
```

✅ **UVEK:**
```python
# DOBRO - DIREKTNO MENJAJ POSTOJEĆI FAJL
bookmaker_worker.py  # Menja se direktno!
class BookmakerWorker  # Ista klasa, nova implementacija
```

**RAZLOZI:**
1. Git čuva istoriju - nema potrebe za verzijama
2. Stare verzije zagađuju codebase
3. Import statements se ne menjaju
4. Refactoring je ZAMENA, ne dodavanje

**PROCEDURA ZA REFACTORING:**
1. Čitaj postojeći fajl
2. Napravi backup pomoću Git (git commit pre promene)
3. DIREKTNO izmeni postojeći fajl
4. Testiraj
5. Commit sa jasnom porukom

**AKO TI TREBA BACKUP:**
- Koristi Git: `git stash` ili `git commit`
- NEMOJ kreirati `_old`, `_backup`, `_v2` fajlove!

---

### 🚨 MISSING FUNCTIONALITY - ABSOLUTE PROHIBITION

**IMPERATIV: NIKADA ne brišeš ili ignorišeš postojeću funkcionalnost bez provere!**

❌ **ZABRANJENO:**
```python
# Scenario: Vidiš self.coords_manager u kodu
# LOŠE: Samo obrišeš jer ne znaš šta je
# self.coords_manager.calculate_coords(...)  # <- DELETE (GREŠKA!)
```

✅ **OBAVEZNA PROCEDURA:**
```python
# 1. STOP - Ne diraj kod odmah!
# 2. TRAŽI fajl/klasu:
#    - Glob/Grep za "coords_manager", "CoordinateManager", "RegionManager"
#    - Proveri imports u fajlu
# 3. RAZUMI šta radi:
#    - Pročitaj implementaciju
#    - Vidi šta prima i vraća
# 4. AKO NE NAĐEŠ - PITAJ KORISNIKA!
#    "Našao sam self.coords_manager ali ne mogu da nađem klasu.
#     Da li je promenila naziv? Šta je njena uloga?"
# 5. TEK ONDA menjaj kod
```

**RAZLOZI:**
1. Možda je funkcionalnost promenila naziv (RegionManager umesto coords_manager)
2. Možda je premestena u drugi modul
3. Možda je **KRITIČNA** za sistem (kao koordinate!)
4. Brisanje core funkcionalnosti = **BROKEN SYSTEM**

**PRIMER IZ OVOG PROJEKTA:**
```python
# ❌ ŠTA SAM URADIO (LOŠE):
# Linija: self.coords_manager.calculate_coords(...)
# Akcija: Samo obrisao bez provere
# Rezultat: Koordinate se ne računaju! GREŠKA!

# ✅ ŠTA SAM TREBAO (DOBRO):
# 1. Grep za "coords_manager"
# 2. Naći RegionManager (to je taj modul!)
# 3. Integrisati RegionManager pravilno
# 4. Pitati korisnika ako nisam siguran
```

**KADA SI NESIGURAN - PITAJ!**
- "Vidim self.X ali ne nalazim tu klasu. Da li je promenila naziv?"
- "Ne razumem kako funkcioniše koordinatni sistem. Možeš li da objasniš?"
- "Imam stari kod koji koristi X, da li to treba zameniti sa Y?"

**BOLJE JE DA PITAŠ 10 PUTA NEGO DA OBRIŠEŠ CORE FUNKCIONALNOST!**

---

## ARCHITECTURE PRINCIPLES

### 1. WORKER PROCESS PATTERN - PARALELIZAM JE IMPERATIV
- **JEDAN BOOKMAKER = JEDAN PROCES = JEDAN CPU CORE**
- Svaki Worker Process ima SVOJ OCR reader
- OCR je CPU-intensive (Tesseract ~100ms) - mora paralelno!
- 6 bookmaker-a = 6 paralelnih procesa = 100ms (ne 600ms!)
- Ovo je CORE princip - nikad sekvencijalno OCR čitanje

**Razlog:** Sekvencijalno čitanje 6 bookmaker-a bi trajalo 600ms što je neprihvatljivo za real-time tracking.

### 2. BATCH OPERATIONS - SHARED WRITER ARHITEKTURA
- **NIKAD single insert u bazu**
- **JEDAN BatchWriter po collector/agent TIPU, ne po bookmaker-u!**
- Uvek koristi BatchDatabaseWriter sa buffer-om od 50-100 zapisa
- Flush na interval (2 sekunde) ili kada se napuni buffer
- 50-100x brže od pojedinačnih INSERT operacija

**Arhitektura:**
```python
# ✅ ISPRAVNO - Shared writer
# U main.py kreira SHARED writers
main_writer = BatchDatabaseWriter("main_game.db", batch_size=100)
betting_writer = BatchDatabaseWriter("betting_history.db", batch_size=50)

# Prosleđuje ISTE instance svim Workers-ima
worker1 = BookmakerWorkerProcess(main_writer=main_writer)  # Shared
worker2 = BookmakerWorkerProcess(main_writer=main_writer)  # Shared
worker3 = BookmakerWorkerProcess(main_writer=main_writer)  # Shared

# Svi workers dodaju u ISTI buffer → batch flush efikasniji
```

**Zašto shared?**
- Više zapisa u jednom batch-u (100 umesto 10-20)
- Manje flush operacija (1 umesto 6)
- Thread-safe (BatchWriter ima lock)
- SQLite WAL mode dozvoljava concurrent writes

### 3. ATOMIC TRANSACTIONS
- **Sve betting operacije moraju biti atomske**
- TransactionController garantuje all-or-nothing
- Lock mehanizam za svaku transakciju
- Retry logika sa exponential backoff

### 4. EVENT-DRIVEN COMMUNICATION
- **EventBus za real-time GUI updates i logging**
- Pub/Sub pattern, ne direktne veze
- Process-safe preko multiprocessing Queue
- Workers publish events, GUI subscribes

**Upotreba:**
```python
# Worker publishes
event_bus.publish(EventType.ROUND_END, {'bookmaker': 'Admiral', 'score': 3.45})

# GUI subscribes
@event_subscriber.subscribe(EventType.ROUND_END)
def on_round_end(event):
    self.log_widget.append(f"Round: {event.data['score']}")
```

### 5. LOCAL STATE vs SHARED STATE
**KRITIČNO razumevanje:**

**A) LOCAL STATE (unutar Worker procesa - PRIMARY)**
- Glavni state structure unutar svakog Worker procesa
- `local_state = {}` - Python dict, in-process memory
- **BRZI pristup** - nema multiprocessing overhead
- Collectors i Agents interno koriste local_state

**B) SHARED GAME STATE (između procesa - OPTIONAL)**
- `core/communication/shared_state.py` - Manager().dict()
- Za deljenje statistike sa GUI-jem
- **Sporiji** - multiprocessing overhead
- Workers opciono pišu statistiku ovde za GUI

**Ko koristi šta:**
- **MainCollector**: Čita `local_state` procesa
- **BettingAgent**: Čita `local_state` (closure funkcija)
- **RGBCollector**: Direktan screen capture (ne koristi ni jedan state)
- **GUI**: Čita `SharedGameState` za prikaz statistike

**Tok podataka:**
```python
# U Worker procesu:
local_state = ocr_reader.read()  # OCR čitanje
main_collector.collect(local_state)  # Koristi local state

# Opciono za GUI:
shared_game_state.set('Admiral_stats', {
    'rounds': 1245,
    'profit': 250.0
})

# GUI čita:
stats = shared_game_state.get('Admiral_stats')
```

## PERFORMANCE REQUIREMENTS

### KRITIČNI TARGETI
- **OCR Speed**: < 15ms per read (template matching za brojeve)
- **Round Detection**: Real-time, bez kašnjenja
- **Batch Write**: > 5000 records/second
- **Memory per Worker**: < 100MB
- **CPU per Worker**: < 10% idle

### DATA ACCURACY > SPEED
- Bolje propustiti podatak nego zapisati netačan
- Uvek validacija pre upisa
- Retry mehanizmi za sve kritične operacije

## TECHNOLOGY STACK

### GUI Framework: PySide6 (Qt for Python)
- **Event Loop**: Qt event loop manages all GUI operations
- **Thread Safety**: Use Qt signals/slots for cross-thread communication
- **Widget Updates**: All widget updates MUST happen in main GUI thread
- **Log Callbacks**: `on_log_received()` is thread-safe via Qt
- **Dark Theme**: Fusion style with custom QPalette

### Multiprocessing Architecture
- **Process Management**: multiprocessing.Manager for shared state
- **Communication**: multiprocessing.Queue for EventBus
- **Shutdown**: Use Event objects for graceful shutdown
- **Isolation**: Each worker in separate process for crash isolation

### OCR Technologies
1. **Template Matching** (10-15ms) - Primary method for numbers
2. **Tesseract OCR** (100ms) - Fallback for complex text
3. **CNN OCR** (planned) - Future ML-based OCR

### Database
- **SQLite** - Local file-based database
- **Connection Pooling** - Multiple connections for concurrent writes
- **Batch Inserts** - BufferedWriter pattern for performance

## MODULE DEPENDENCIES

### CORE MODULES (ne menjaj bez razloga)
```
core/
├── ocr/
│   ├── engine.py           → Multi-strategy OCR coordinator
│   ├── template_ocr.py     → Fast template matching (10ms)
│   ├── tesseract_ocr.py    → Tesseract fallback (100ms)
│   └── cnn_ocr.py          → Future CNN-based OCR
├── capture/
│   ├── screen_capture.py   → MSS-based screen capture
│   └── region_manager.py   → Region coordinate management
├── input/
│   ├── transaction_controller.py → Atomic GUI operations
│   └── action_queue.py     → Input action queueing
└── communication/
    ├── event_bus.py        → Process-safe pub/sub system
    └── shared_state.py     → Multiprocessing shared memory
```

### ORCHESTRATION (kritično za skalabilnost)
```
orchestration/
├── bookmaker_worker.py     → Individual bookmaker worker process
│                             (SVE za jedan bookmaker: OCR, Collectors, Agents)
├── process_manager.py      → Worker lifecycle management
│                             (Spawns N worker processes, 1 per bookmaker)
├── coordinator.py          → Multi-bookmaker synchronization (optional)
└── health_monitor.py       → Process health checking
```

**VAŽNO:** `shared_reader.py` je deprecated - svaki worker ima svoj OCR reader!

### COLLECTORS (data gathering workers)
```
collectors/
├── base_collector.py       → Base class for all collectors
├── main_collector.py       → Round & threshold data collection
│                             Čita local_state, prati runde
├── rgb_collector.py        → RGB training data collection
│                             Direktan screen capture, 2 Hz sampling
└── phase_collector.py      → Game phase transition tracking
                              Prati BETTING→PLAYING→ENDED promene
```

**RAZLIKA PhaseCollector vs RGBCollector:**
- **PhaseCollector**: Logičke promene faza (iz OCR results), retko
- **RGBCollector**: Raw RGB pixeli (direktan capture), često (2 Hz)
- **Oba potrebna** - različite svrhe (flow analiza vs ML training)

### AGENTS (automation components)
```
agents/
├── betting_agent.py        → Betting execution & strategy coordination
│                             - Thread u Worker procesu
│                             - Čuva round_history (deque 100)
│                             - Poziva StrategyExecutor
│                             - Izvršava preko TransactionController
│                             - Kad aktivan → SessionKeeper PAUSED
│
├── session_keeper.py       → Session maintenance via fake clicks
│                             - Thread u Worker procesu
│                             - Interval: 250-350s (random)
│                             - Prvi klik: 300s + offset (30s * index)
│                             - Kad aktivan → BettingAgent NE radi
│
└── strategy_executor.py    → Strategy decision engine
                              - Objekat (ne thread)
                              - Input: round_history (100 rundi)
                              - Output: [bet_amounts], [auto_stops]
                              - Stateless - čista funkcija
```

**KRITIČNO: BettingAgent i SessionKeeper NIKAD simultano za isti bookmaker!**

### DATA LAYER (optimizovano za brzinu)
```
data_layer/
├── database/
│   ├── batch_writer.py     → Buffered batch inserts (50-100 records)
│   ├── connection.py       → Connection pool management
│   └── query_builder.py    → SQL query construction
├── models/
│   ├── base.py             → Base data model classes
│   ├── round.py            → Round data model
│   └── threshold.py        → Threshold crossing model
└── cache/
    └── redis_cache.py      → Future Redis caching layer
```

### GUI LAYER (PySide6)
```
gui/
├── app_controller.py       → Application lifecycle controller
├── config_manager.py       → Configuration persistence
├── setup_dialog.py         → Bookmaker setup dialog
├── stats_widgets.py        → Real-time statistics widgets
└── tools_tab.py            → Utility tools interface
```

## DEVELOPMENT PRIORITIES

1. **OCR Optimization** - Template matching pre Tesseract
2. **Data Quality** - Tačnost podataka je prioritet
3. **ML Models** - Game phase detector, score predictor
4. **Remote Control** - Android app za monitoring

## NO-GO ZONES - NIKAD NE RADI

### ❌ NIKAD
- Single database insert umesto batch
- Sekvencijalno OCR čitanje (mora paralelno!)
- Direktna komunikacija između procesa (uvek EventBus za GUI)
- Blokiraj main GUI thread sa I/O operacijama
- Hardkoduj koordinate ili putanje
- Koristi global state bez lock-a
- Ignoriši error handling
- Čitaj iz baze unutar Worker-a (samo INSERT, ne SELECT!)

### ❌ NE MENJAJ BEZ DISKUSIJE
- **Worker Process per Bookmaker** arhitekturu (paralelizam!)
- Event Bus komunikaciju
- Batch Writer logiku
- Transaction Controller atomicity
- Process Manager health checks
- Local state vs SharedGameState razliku

## FILE STRUCTURE RULES

### NAMING CONVENTIONS
- Snake_case za Python fajlove
- PascalCase za klase
- SCREAMING_SNAKE za konstante
- Descriptive names > kratke skraćenice

### MODULE ORGANIZATION
```python
# Svaki modul mora imati:
1. Docstring sa PURPOSE i VERSION
2. Logging setup
3. Error handling
4. Stats tracking
5. Cleanup metode
```

## PARALLEL PROCESSING

### WORKER PATTERN
```python
# Svaki worker mora:
- Primiti shutdown_event (multiprocessing.Event)
- Handlovati graceful shutdown u read loop-u
- Reportovati health status preko EventBus
- Logirati statistics periodično (svake 2-3 sekunde)
- Cleanup metodu koja oslobađa resurse
```

**Example Worker Structure:**
```python
def worker_process(config, shutdown_event, log_callback):
    """Standard worker process template"""
    logger = setup_logger()

    try:
        # Initialize components
        shared_reader = SharedGameStateReader()
        batch_writer = BatchDatabaseWriter()

        # Main loop
        while not shutdown_event.is_set():
            # Read from shared memory (no OCR!)
            state = shared_reader.get_state(bookmaker_name)

            # Process data
            data = process_data(state)

            # Buffer write (don't insert directly!)
            batch_writer.add(data)

            # Report health
            event_bus.publish(Event(EventType.HEALTH_CHECK, {...}))

            time.sleep(0.1)  # Avoid busy loop

    except Exception as e:
        logger.error(f"Worker crashed: {e}")
    finally:
        # Cleanup - ALWAYS flush buffers
        batch_writer.flush()
        logger.info("Worker stopped")
```

### MULTIPROCESSING RULES
- **CPU-Intensive**: Use multiprocessing, NOT threading (GIL bypass)
- **Shared State**: multiprocessing.Manager().dict() for shared memory
- **Communication**: multiprocessing.Queue for EventBus messages
- **Signaling**: multiprocessing.Event for shutdown coordination
- **Isolation**: Each process has own memory space - crash won't affect others

## ERROR HANDLING

### RETRY LOGIC
- 3 pokušaja sa exponential backoff
- Log svaki retry
- Fallback strategija za kritične operacije

### CRASH RECOVERY
- Auto-restart crashed workers
- Preserve state pre restart-a
- Log crash reason i stack trace

## TESTING REQUIREMENTS

### UNIT TESTS
- Svaka nova funkcionalnost mora test
- Mock external dependencies
- Test edge cases

### INTEGRATION TESTS
- End-to-end sa 1 kladionicom
- Performance benchmarks
- Memory leak detection

## DATABASE SCHEMA

### CORE TABLES
- **rounds**: Završene runde sa final score
- **threshold_scores**: Prelasci pragova
- **rgb_samples**: RGB podaci za ML treniranje
- **bets**: Betting istorija

### INDEXING STRATEGY
- Index na bookmaker + timestamp
- Composite index za često JOIN-ovane
- Partition po datumu za velike tabele

## LOGGING STANDARDS

### LOG LEVELS
- DEBUG: Detaljan flow
- INFO: Važni eventi
- WARNING: Potencijalni problemi
- ERROR: Greške koje ne prekidaju rad
- CRITICAL: Fatalne greške

### LOG FORMAT
```python
"%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
```

## GIT WORKFLOW

### BRANCH NAMING
- feature/naziv-feature
- bugfix/opis-problema
- refactor/sta-se-refaktoriše

### COMMIT MESSAGES
- Imperativ: "Add", "Fix", "Refactor"
- Kratak opis < 50 karaktera
- Detaljan opis ako treba

## COMMON DEVELOPMENT PATTERNS

### Adding a New Collector
1. **Extend BaseCollector** in `collectors/base_collector.py`
2. **Implement required methods**:
   - `collect(state)` - Process shared state data
   - `validate(data)` - Validate before buffering
3. **Use BatchWriter** - Never direct database inserts
4. **Register worker** in `orchestration/process_manager.py`
5. **Add GUI tab** in `main.py` if needed

### Adding a New Event Type
1. **Define in EventType enum** (`core/communication/event_bus.py`)
2. **Create Event with type and data** dict
3. **Publish via EventBus**: `event_bus.publish(event)`
4. **Subscribe in consumers**: `event_bus.subscribe(EventType.YOUR_TYPE, handler)`

### Modifying OCR Regions
1. **Edit coordinates** in config setup (`gui/setup_dialog.py`)
2. **Test with visualizer**: `python utils/region_visualizer.py`
3. **Verify alignment** at 100% browser zoom
4. **Update region_manager** if adding new regions

### Working with Shared Memory
```python
# WRITE (only in SharedReader)
shared_memory['bookmaker1'] = {
    'score': 3.45,
    'phase': 'crashed',
    'timestamp': time.time()
}

# READ (in all collectors/agents)
state = shared_reader.get_state('bookmaker1')
score = state.get('score')  # Defensive access
```

## SESSION WORKFLOW

### 🚀 On Session Start
1. **ALWAYS load and read these files FIRST:**
   - [CLAUDE.md](CLAUDE.md) - This file - core technical principles
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system structure
   - [README.md](README.md) - Project overview and setup
   - [CHANGELOG.md](CHANGELOG.md) - Recent changes history
   - [project_knowledge.md](project_knowledge.md) - Project-specific knowledge

2. **CRITICAL: ASK QUESTIONS BEFORE CODING**
   - **NEVER start implementing without clarifying ambiguities**
   - If ANY aspect of the task is unclear, ASK first
   - If multiple approaches are possible, ASK which one to use
   - If requirements are missing, ASK for details
   - **Only after receiving clear answers, proceed with implementation**

3. **Understand the request context:**
   - Identify which module/folder is being worked on
   - Check dependencies (what imports this, what does it import)
   - Review related test files in `tests/`
   - Check if change affects Shared Reader or Event Bus

4. **For GUI changes:**
   - Understand PySide6 thread safety requirements
   - Check if callbacks need Qt signal/slot mechanism
   - Verify main thread vs worker thread context

### ✅ After Completing Work
1. **Update documentation:**
   - [CHANGELOG.md](CHANGELOG.md) - **MUST** add entry for changes made
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Update if structure changed
   - [README.md](README.md) - Update if functionality added
   - `__init__.py` - Update exports in affected folder

2. **Check impact on related files:**
   - Analyze all files that import the changed module
   - Update import statements if needed
   - Adapt interfaces if structure changed
   - Run related tests to verify: `python -m pytest tests/`

3. **Dependency chain verification:**
   ```python
   # Example: If changing core/ocr/engine.py
   Check → collectors/* (uses OCR)
   Check → orchestration/shared_reader.py (uses OCR)
   Check → tests/test_ocr.py (tests OCR)
   ```

4. **Performance impact verification:**
   - If touching OCR code → Run `tests/ocr_performance.py`
   - If touching ML code → Run `tests/ml_phase_performance.py`
   - If touching batch writer → Check write speed hasn't regressed

## DEBUGGING & TROUBLESHOOTING

### Common Issues

**OCR Not Reading Correctly:**
- Check browser zoom is exactly 100%
- Verify Tesseract is installed: `tesseract --version`
- Use region visualizer: `python utils/region_visualizer.py`
- Check screen resolution and monitor setup
- Ensure windows are positioned correctly

**Worker Process Crashes:**
- Check logs in GUI log widgets
- Look for unhandled exceptions in worker loop
- Verify shared memory access is defensive (use `.get()`)
- Check if EventBus queue is full
- Memory leak - check with `psutil`

**Database Write Errors:**
- Verify database file permissions
- Check disk space
- Ensure BatchWriter buffer is being flushed
- Connection pool exhausted - increase pool size
- SQLite locked - check concurrent access

**GUI Freezing:**
- Long operations blocking main thread
- Move heavy work to worker processes
- Use Qt signals for cross-thread updates
- Check if worker processes are deadlocked

### Performance Debugging
```bash
# Check OCR speed
python tests/ocr_performance.py

# Check ML model speed
python tests/ml_phase_performance.py

# Profile specific component
python -m cProfile -o output.prof main.py
python -m pstats output.prof

# Monitor memory usage
python -c "import psutil; print(psutil.virtual_memory())"
```

### Logging Levels
```python
# Set in code or environment
import logging
logging.basicConfig(level=logging.DEBUG)  # Very verbose
logging.basicConfig(level=logging.INFO)   # Normal operation
logging.basicConfig(level=logging.WARNING)  # Issues only
```

## IMPORTANT CONSTRAINTS

### Platform-Specific
- **Windows Only**: Uses pywin32 for GUI automation
- **Tesseract Required**: Must be installed separately
- **Screen Resolution**: Optimized for 1920x1080+
- **Python 3.11+**: Required for latest features

### Performance Limits
- **Max Bookmakers**: 6 (current layout limit)
- **OCR Speed Target**: < 15ms per read
- **Memory Budget**: < 100MB per worker
- **CPU Target**: < 10% per worker (idle)
- **Batch Size**: 50-100 records (optimal)

### Safety Constraints
- **NEVER** run on real money accounts without explicit user confirmation
- **ALWAYS** use DEMO mode for testing betting features
- **NEVER** ignore validation errors - better to skip data
- **ALWAYS** flush buffers on shutdown to prevent data loss

## REMEMBER ALWAYS

1. **Data Accuracy > Speed** - Bolje spor i tačan nego brz i netačan
2. **Shared Reader Pattern** - Jedan čita, svi koriste (CORE principle!)
3. **Batch Everything** - Nikad single operacije (50x faster)
4. **Event-Driven** - Loose coupling preko EventBus (never direct calls)
5. **Atomic Transactions** - All or nothing za betting (transaction safety)
6. **Health Monitoring** - Auto-recovery za sve (process resilience)
7. **Clean Code** - Readability > cleverness (maintainability)
8. **Update Docs** - Always update [CHANGELOG.md](CHANGELOG.md) after work
9. **Check Dependencies** - Verify impact on related files (ripple effects)
10. **Thread Safety** - Qt for GUI, multiprocessing for workers (never mix!)