# CLAUDE.md - AVIATOR PROJECT CORE KNOWLEDGE

## PROJECT OVERVIEW
AVIATOR je sistem za praćenje i automatizaciju Aviator igre na više online kladionica simultano. Koristi OCR za čitanje podataka sa ekrana, ML modele za predikciju, i automatizovane agente za betting.

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

## MODULE DEPENDENCIES

### CORE MODULES (ne menjaj bez razloga)
```
core/
├── ocr/engine.py           → Multi-strategy OCR
├── capture/screen_capture.py → MSS-based capture
├── input/transaction_controller.py → Atomic GUI ops
└── communication/event_bus.py → Central communication
```

### ORCHESTRATION (kritično za skalabilnost)
```
orchestration/
├── shared_reader.py    → Shared OCR reading
├── process_manager.py  → Lifecycle & health
├── coordinator.py      → Multi-bookmaker sync
└── bookmaker_worker.py → Individual workers
```

### DATA LAYER (optimizovano za brzinu)
```
data_layer/
├── database/batch_writer.py → Batch inserts
├── models/base.py           → Data models
└── cache/redis_cache.py     → Future caching
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
- Primiti shutdown_event
- Handlovati graceful shutdown
- Reportovati health status
- Logirati statistics periodično
```

### MULTIPROCESSING RULES
- Koristi multiprocessing, ne threading za CPU-intensive
- Shared memory za velike podatke
- Queue za komunikaciju
- Event za signalizaciju

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

## SESSION WORKFLOW

### 🚀 On Session Start
1. **ALWAYS load and read these files:**
   - `CLAUDE.md` - Core technical principles
   - `ARCHITECTURE.md` - System structure  
   - `STRUCTURE.md` - File organization
   - `Project Knowledge Instructions` - Workflow rules

2. **Analyze current task scope:**
   - Identify which module/folder is being worked on
   - Check dependencies (what imports this, what does it import)
   - Review related test files

### ✅ After Completing Work
1. **Update documentation:**
   - `CHANGELOG.md` - Add entry for changes made
   - `ARCHITECTURE.md` - Update if structure changed
   - `README.md` - Update if functionality added
   - `__init__.py` - Update exports in affected folder

2. **Check impact on related files:**
   - Analyze all files that import the changed module
   - Update import statements if needed
   - Adapt interfaces if structure changed
   - Run related tests to verify

3. **Dependency chain verification:**
   ```python
   # Example: If changing core/ocr/engine.py
   Check → collectors/* (uses OCR)
   Check → orchestration/shared_reader.py (uses OCR)
   Check → tests/test_ocr.py (tests OCR)
   ```

## REMEMBER ALWAYS

1. **Data Accuracy > Speed** - Bolje spor i tačan nego brz i netačan
2. **Shared Reader Pattern** - Jedan čita, svi koriste
3. **Batch Everything** - Nikad single operacije
4. **Event-Driven** - Loose coupling preko EventBus
5. **Atomic Transactions** - All or nothing za betting
6. **Health Monitoring** - Auto-recovery za sve
7. **Clean Code** - Readability > cleverness
8. **Update Docs** - Always update CHANGELOG after work
9. **Check Dependencies** - Verify impact on related files