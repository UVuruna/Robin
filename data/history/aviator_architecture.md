# 🎰 AVIATOR PROJECT - REFAKTORISANA ARHITEKTURA

## 📂 STRUKTURA PROJEKTA

```
aviator/
├── core/                       # Jezgro sistema
│   ├── ocr/                   # OCR engine
│   │   ├── engine.py          # Glavni OCR engine sa multiple strategijama
│   │   ├── tesseract_ocr.py   # Tesseract strategija
│   │   ├── template_ocr.py    # Template matching strategija
│   │   └── cnn_ocr.py         # CNN strategija (budući)
│   ├── capture/                # Screen capture
│   │   ├── screen_capture.py  # MSS-based capture
│   │   └── region_manager.py  # Upravljanje regionima
│   ├── input/                  # Input kontrola
│   │   ├── transaction_controller.py  # Transakcioni GUI kontroler
│   │   └── action_queue.py    # Queue za akcije
│   └── communication/          # Međuprocesna komunikacija
│       ├── event_bus.py       # Centralni event bus
│       └── shared_state.py    # Deljeno stanje između procesa
│
├── data/                       # Data layer
│   ├── models/                 # Modeli podataka
│   │   ├── base.py           # Bazni model
│   │   ├── round.py          # Round model
│   │   ├── threshold.py      # Threshold model
│   │   └── bet.py            # Bet model
│   ├── database/              # Database operacije
│   │   ├── connection.py     # Connection pool
│   │   ├── batch_writer.py   # Batch pisanje
│   │   └── query_builder.py  # Query builder
│   └── cache/                 # Keširanje
│       └── redis_cache.py    # Redis keširanje (opciono)
│
├── collectors/                 # Kolektori podataka
│   ├── base_collector.py     # Bazna klasa
│   ├── main_collector.py     # Glavni kolektor
│   ├── rgb_collector.py      # RGB kolektor
│   └── phase_collector.py    # Game phase kolektor
│
├── agents/                     # Agenti
│   ├── betting_agent.py      # Betting agent
│   ├── session_keeper.py     # Session keeper
│   └── strategy_executor.py  # Strategy executor
│
├── orchestration/              # Orkestracija
│   ├── process_manager.py    # Upravljanje procesima
│   ├── bookmaker_worker.py   # Worker po kladionici
│   ├── coordinator.py        # Koordinator
│   └── health_monitor.py     # Health monitoring
│
├── strategies/                 # Betting strategije
│   ├── base_strategy.py      # Bazna strategija
│   ├── martingale.py         # Martingale strategija
│   ├── fibonacci.py          # Fibonacci strategija
│   └── custom_strategy.py    # Custom strategije
│
├── gui/                        # GUI (postojeći)
├── utils/                      # Utilities (postojeći)
└── config/                     # Konfiguracija
    ├── settings.py            # Glavna podešavanja
    └── regions.json           # Region definicije
```

## 🔄 FLOW PODATAKA

### 1. **Paralelno praćenje kladionica**
```
[Bookmaker 1] → [Worker Process 1] → [Event Bus] → [Database]
[Bookmaker 2] → [Worker Process 2] → [Event Bus] → [Database]
[Bookmaker 3] → [Worker Process 3] → [Event Bus] → [Database]
...
[Bookmaker 6] → [Worker Process 6] → [Event Bus] → [Database]
```

### 2. **OCR Pipeline**
```
Screen Capture (5ms) → Preprocessing (2ms) → OCR Engine → Result
                                                ├── Tesseract (100ms)
                                                ├── Template (10ms)
                                                └── CNN (15ms future)
```

### 3. **Betting Transaction Flow**
```
Strategy → Action Queue → Transaction Controller → [LOCK]
                                                    ├── Click Amount Field
                                                    ├── Type Amount
                                                    ├── Click Auto-stop Field
                                                    ├── Type Auto-stop
                                                    ├── Click Play Button
                                                    └── [UNLOCK]
```

## 📊 KLJUČNE KOMPONENTE

### Core Layer

#### 1. **OCR Engine** - Multi-strategy pristup
- **Template Matching**: Za brojeve sa fiksnim fontom (10ms)
- **Tesseract**: Fallback za kompleksan tekst (100ms)
- **CNN**: Budući custom model (15ms cilj)

#### 2. **Transaction Controller** - Atomske operacije
- Queue-based sistem
- Lock mehanizam za svaku transakciju
- Retry logika sa exponential backoff

#### 3. **Event Bus** - Centralna komunikacija
- Pub/Sub model
- Event tipovi: ROUND_START, ROUND_END, THRESHOLD_CROSSED, BET_PLACED
- Asinhrono procesiranje

### Data Layer

#### 1. **Batch Writer** - Optimizovano pisanje
- Buffer od 50-100 zapisa
- Bulk insert svake 2 sekunde
- Async write sa callback-om

#### 2. **Connection Pool** - Efikasne konekcije
- Pool od 10 konekcija
- Auto-reconnect logika
- Query timeout: 5s

### Orchestration Layer

#### 1. **Process Manager** - Upravljanje procesima
- Spawn/kill worker procesa
- Health check svakih 10s
- Auto-restart failed workers

#### 2. **Coordinator** - Sinhronizacija
- Round synchronization između kladionica
- Shared state management
- Conflict resolution

## 🚀 PERFORMANSE

### Trenutno (pre refaktorisanja)
- OCR: 100ms po čitanju
- Rounds/hour: ~160 po kladionici
- Total rounds/hour: ~960 (6 kladionica)
- Database writes: Sinhrono, sporo

### Ciljano (posle refaktorisanja)
- OCR: 10-15ms (template matching)
- Rounds/hour: ~160 po kladionici (isto)
- Total rounds/hour: ~960 (isto)
- Database writes: Batch, 50x brže
- CPU usage: -40% (bolja paralelizacija)
- Memory: +100MB (trade-off za brzinu)

## 🔧 IMPLEMENTACIJA - PRIORITETI

### Faza 1: Core refaktorisanje (Nedelja 1)
1. ✅ Transaction Controller
2. ✅ OCR Engine sa template matching
3. ✅ Event Bus
4. ✅ Process Manager

### Faza 2: Data layer (Nedelja 2)
1. ✅ Batch Writer
2. ✅ Connection Pool
3. ✅ Modeli sa foreign keys

### Faza 3: Collectors & Agents (Nedelja 3)
1. ✅ Refaktorisan Main Collector
2. ✅ Refaktorisan Betting Agent
3. ✅ Strategy system

### Faza 4: GUI & Testing (Nedelja 4)
1. ✅ GUI integracija
2. ✅ Unit testovi
3. ✅ Performance testovi

## 💡 KLJUČNE PREDNOSTI

1. **Modularnost** - Svaka komponenta ima jasnu ulogu
2. **Skalabilnost** - Lako dodavanje novih kladionica
3. **Brzina** - 10x brži OCR, batch DB operacije
4. **Pouzdanost** - Health monitoring, auto-restart
5. **Održivost** - Čist kod, jasna struktura
6. **Testabilnost** - Svaka komponenta se može testirati nezavisno

## 🎯 METRICS & MONITORING

### Praćene metrike
- OCR speed (ms per read)
- Rounds collected per minute
- Database write latency
- Process memory usage
- Error rate per component

### Alerting
- OCR failure > 10%
- Database connection lost
- Worker process died
- Memory > 2GB
- CPU > 80% sustained

## 🔐 SIGURNOST

1. **Transaction Safety** - Lock na svakoj bet transakciji
2. **Data Integrity** - Foreign keys, constraints
3. **Process Isolation** - Svaki worker u svom procesu
4. **Error Recovery** - Graceful degradation
5. **Audit Log** - Sve akcije se loguju