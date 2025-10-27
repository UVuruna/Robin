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

## ARCHITECTURE PRINCIPLES

### 1. SHARED READER PATTERN
- **JEDAN OCR čita, SVI koriste podatke**
- SharedGameStateReader čita jednom i stavlja u shared memory
- Svi collectors i agents pristupaju istim podacima bez dodatnog OCR-a
- Ovo je CORE princip - nikad dupliraj OCR čitanje

### 2. BATCH OPERATIONS
- **NIKAD single insert u bazu**
- Uvek koristi BatchDatabaseWriter sa buffer-om od 50-100 zapisa
- Flush na interval (2 sekunde) ili kada se napuni buffer
- 50x brže od pojedinačnih INSERT operacija

### 3. ATOMIC TRANSACTIONS
- **Sve betting operacije moraju biti atomske**
- TransactionController garantuje all-or-nothing
- Lock mehanizam za svaku transakciju
- Retry logika sa exponential backoff

### 4. EVENT-DRIVEN COMMUNICATION
- **EventBus za svu inter-process komunikaciju**
- Pub/Sub pattern, ne direktne veze
- Process-safe preko multiprocessing Queue
- Rate limiting i priority events

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
├── shared_reader.py        → Single OCR reader for all workers
├── process_manager.py      → Worker lifecycle management
├── coordinator.py          → Multi-bookmaker synchronization
├── bookmaker_worker.py     → Individual bookmaker worker
└── health_monitor.py       → Process health checking
```

### COLLECTORS (data gathering workers)
```
collectors/
├── base_collector.py       → Base class for all collectors
├── main_collector.py       → Round & threshold data collection
├── rgb_collector.py        → RGB training data collection
└── phase_collector.py      → Game phase detection
```

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
- Dupliraj OCR čitanje
- Direktna komunikacija između procesa (uvek EventBus)
- Blokiraj main thread sa I/O operacijama
- Hardkoduj koordinate ili putanje
- Koristi global state bez lock-a
- Ignoriši error handling

### ❌ NE MENJAJ BEZ DISKUSIJE
- Shared Reader arhitekturu
- Event Bus komunikaciju
- Batch Writer logiku
- Transaction Controller atomicity
- Process Manager health checks

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
1. **ALWAYS load and read these files:**
   - [CLAUDE.md](CLAUDE.md) - This file - core technical principles
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system structure
   - [README.md](README.md) - Project overview and setup
   - [CHANGELOG.md](CHANGELOG.md) - Recent changes history

2. **Understand the request context:**
   - Identify which module/folder is being worked on
   - Check dependencies (what imports this, what does it import)
   - Review related test files in `tests/`
   - Check if change affects Shared Reader or Event Bus

3. **For GUI changes:**
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