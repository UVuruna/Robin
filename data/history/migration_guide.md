# 📚 AVIATOR PROJECT - MIGRATION GUIDE

## 🎯 CILJ MIGRACIJE

Prelazak sa trenutne monolitne arhitekture na modularnu, skalabilnu arhitekturu sa:
- **10x bržim OCR** (10-15ms vs 100ms)
- **Atomskim transakcijama** za betting
- **Pravim paralelizmom** sa multiprocessing
- **Centralizovanom komunikacijom** preko Event Bus-a
- **Automatskim health monitoring** i restart

## ⚡ QUICK WINS (Odmah implementiraj)

### 1. Transaction Controller (1 dan)
**Šta:** Zameni `core/gui_controller.py` sa novim `TransactionController`

**Zašto:** 
- Trenutni GUI controller nije thread-safe
- Nema atomske transakcije
- Može se prekinuti usred operacije

**Kako:**
```python
# Staro (gui_controller.py)
gui = GUIController()
gui.click(coords)
gui.type_text(amount)

# Novo (transaction_controller.py)
from core.input.transaction_controller import transaction_controller

controller = transaction_controller
controller.start()

# Atomska bet transakcija
trans_id = controller.place_bet(
    bookmaker="Admiral",
    amount=10.0,
    auto_stop=2.0,
    amount_coords=(100, 200),
    auto_stop_coords=(100, 250), 
    play_button_coords=(150, 300),
    callback=lambda t: print(f"Bet completed: {t.status}")
)
```

### 2. Fast OCR Engine (2 dana)

**Šta:** Zameni `core/screen_reader.py` sa `FastOCREngine`

**Zašto:**
- Trenutni Tesseract: 100ms po čitanju
- Template matching: 10ms po čitanju (10x brže!)

**Kako:**
```python
# Staro (screen_reader.py)
reader = ScreenReader(region)
score = reader.read_score()  # 100ms

# Novo (fast_ocr_engine.py)
from core.ocr.fast_ocr_engine import ocr_engine

result = ocr_engine.read_region(region, "score_region_small")
score = result.value  # 10ms!

# Ili direktno
score = ocr_engine.read_score(region)
```

**Priprema template slika:**
1. Snimi screenshot-ove svih cifara (0-9) iz Aviator-a
2. Iseci svaku cifru kao zasebnu sliku
3. Sačuvaj u `data/ocr_templates/digits/`
4. Template matching će automatski prepoznavati

## 📋 FAZA 1: REFAKTORISANJE CORE-a (Nedelja 1)

### Dan 1-2: Event Bus integracija

**Implementacija:**
```python
# apps/main_data_collector.py - NOVO
from core.communication.event_bus import EventPublisher, EventSubscriber, EventType

class MainDataCollectorV4(Process):
    def __init__(self, bookmaker: str):
        self.publisher = EventPublisher(f"MainCollector-{bookmaker}")
        self.subscriber = EventSubscriber(f"MainCollector-{bookmaker}")
        
    def run(self):
        # Subscribe na relevantne eventove
        self.subscriber.subscribe(EventType.PHASE_CHANGE, self.on_phase_change)
        
        # Publish eventove
        self.publisher.round_start(self.bookmaker)
        self.publisher.score_update(self.bookmaker, score)
        self.publisher.round_end(self.bookmaker, final_score)
```

### Dan 3-4: Process Manager integracija

**Zameni postojeći multiprocessing kod:**
```python
# Staro (main.py)
processes = []
for bookmaker in bookmakers:
    p = Process(target=worker, args=(bookmaker,))
    p.start()
    processes.append(p)

# Novo
from orchestration.process_manager import ProcessManager, WorkerConfig

manager = ProcessManager(max_workers=10)

# Registruj worker-e
for bookmaker in bookmakers:
    config = WorkerConfig(
        name=f"Collector-{bookmaker}",
        target_func=collector_worker,
        args=(bookmaker, coords),
        auto_restart=True,
        max_restarts=3
    )
    manager.register_worker(config)

# Pokreni sve
manager.start_all()
```

### Dan 5: Database Batch Writer

**Implementiraj batch pisanje:**
```python
# data/database/batch_writer.py
class BatchWriter:
    def __init__(self, db_path: str, batch_size: int = 50):
        self.buffer = []
        self.batch_size = batch_size
        
    def add(self, record: dict):
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        if not self.buffer:
            return
        
        # Bulk insert
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.executemany(self.insert_query, self.buffer)
        conn.commit()
        conn.close()
        
        self.buffer.clear()
```

## 📋 FAZA 2: REFAKTORISANJE APPS (Nedelja 2)

### Novi Main Data Collector

```python
# apps/collectors/main_collector_v4.py
from core.ocr.fast_ocr_engine import ocr_engine
from core.communication.event_bus import EventPublisher
from data.database.batch_writer import BatchWriter

class MainCollectorV4:
    def __init__(self, bookmaker: str, coords: dict):
        self.bookmaker = bookmaker
        self.coords = coords
        
        # Fast OCR
        self.ocr = ocr_engine
        
        # Event publishing
        self.publisher = EventPublisher(f"MainCollector-{bookmaker}")
        
        # Batch database writing
        self.db_writer = BatchWriter("data/databases/main_game_data.db")
        
    def collect_round(self):
        # Ultra brzo čitanje (10ms)
        score = self.ocr.read_score(self.coords['score_region'])
        
        # Publish event
        self.publisher.score_update(self.bookmaker, score)
        
        # Add to batch
        self.db_writer.add({
            'bookmaker': self.bookmaker,
            'score': score,
            'timestamp': time.time()
        })
```

### Novi Betting Agent

```python
# apps/agents/betting_agent_v2.py
from core.input.transaction_controller import transaction_controller
from core.communication.event_bus import EventSubscriber, EventType

class BettingAgentV2:
    def __init__(self, bookmaker: str, strategy: str):
        self.bookmaker = bookmaker
        self.strategy = strategy
        
        # Transaction control
        self.tx_controller = transaction_controller
        
        # Event listening
        self.subscriber = EventSubscriber(f"BettingAgent-{bookmaker}")
        self.subscriber.subscribe(EventType.PHASE_CHANGE, self.on_phase_change)
        
    def place_bet(self, amount: float, auto_stop: float):
        # Atomska transakcija!
        trans_id = self.tx_controller.place_bet(
            bookmaker=self.bookmaker,
            amount=amount,
            auto_stop=auto_stop,
            amount_coords=self.coords['amount'],
            auto_stop_coords=self.coords['auto_stop'],
            play_button_coords=self.coords['play'],
            priority=1,  # Visok prioritet
            callback=self.on_bet_complete
        )
        
    def on_bet_complete(self, transaction):
        if transaction.status == TransactionStatus.COMPLETED:
            self.logger.info("Bet placed successfully!")
        else:
            self.logger.error(f"Bet failed: {transaction.error}")
```

## 🔄 POSTUPNA MIGRACIJA (Korak po korak)

### Korak 1: Parallel Run (1 nedelja)
- Pokreni NOVU arhitekturu paralelno sa STAROM
- Uporedi rezultate
- Identifikuj probleme

### Korak 2: Gradual Switchover (1 nedelja)
- Prebaci jednu po jednu kladionicu na novi sistem
- Monitoring performansi
- Rollback ako ima problema

### Korak 3: Full Migration (1 nedelja)
- Sve kladionice na novom sistemu
- Ukloni stari kod
- Optimizacija

## 📊 MERENJE USPEHA

### Pre migracije:
- OCR brzina: 100ms
- Rounds/hour: 960
- CPU usage: 60%
- Memory: 800MB
- Error rate: 5%

### Posle migracije (očekivano):
- OCR brzina: 10ms (10x brže!)
- Rounds/hour: 960 (isto, ali stabilnije)
- CPU usage: 30% (2x manje)
- Memory: 400MB (2x manje)
- Error rate: <1% (5x manje)

## 🐛 TROUBLESHOOTING

### Problem: Template matching ne radi
**Rešenje:** 
1. Proveri da li su template slike tačne
2. Adjust threshold u `TemplateMatchingOCR` (default 0.8)
3. Fallback na Tesseract ako ne uspe

### Problem: Event Bus gubi poruke
**Rešenje:**
1. Povećaj queue size u `EventBus.__init__`
2. Proveri rate limiting
3. Log sve eventove za debug

### Problem: Process se restartuje stalno
**Rešenje:**
1. Proveri memory leak
2. Povećaj `memory_limit_mb` u `WorkerConfig`
3. Smanji `max_restarts`

## ✅ CHECKLIST ZA MIGRACIJU

- [ ] **Dan 1:** Implementiraj Transaction Controller
- [ ] **Dan 2:** Implementiraj Fast OCR Engine
- [ ] **Dan 3:** Generiši template slike
- [ ] **Dan 4:** Integriši Event Bus
- [ ] **Dan 5:** Integriši Process Manager
- [ ] **Dan 6:** Refaktoriši Main Collector
- [ ] **Dan 7:** Refaktoriši Betting Agent
- [ ] **Dan 8:** Batch Database Writer
- [ ] **Dan 9:** Testing & Debugging
- [ ] **Dan 10:** Performance tuning

## 🚀 QUICK START SCRIPT

```python
# start_new_system.py
from orchestration.process_manager import ProcessManager, WorkerConfig
from core.input.transaction_controller import transaction_controller
from core.communication.event_bus import event_bus
from core.ocr.fast_ocr_engine import ocr_engine

# Start core services
transaction_controller.start()
event_bus.start()

# Create process manager
manager = ProcessManager()

# Register collectors
bookmakers = ["Admiral", "BalkanBet", "Merkur", "Soccer"]
for bookmaker in bookmakers:
    config = WorkerConfig(
        name=f"Collector-{bookmaker}",
        target_func=main_collector_worker,
        args=(bookmaker,),
        auto_restart=True
    )
    manager.register_worker(config)

# Start all
manager.start_all()

print("✅ New system running!")
print("📊 Monitor at: http://localhost:8080/dashboard")

# Run until Ctrl+C
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    manager.shutdown_all()
```

## 📞 PODRŠKA

Ako imaš problema sa migracijom:
1. Proveri logs u `logs/migration.log`
2. Pokreni dijagnostiku: `python utils/diagnostic.py --check-all`
3. Rollback ako treba: `git checkout stable-old-version`

## 🎉 ZAVRŠNI KORACI

Kada završiš migraciju:
1. **Benchmark:** Pokreni `python tests/performance_test.py`
2. **Dokumentuj:** Update README sa novim uputstvima
3. **Backup:** Napravi backup starog koda
4. **Deploy:** Push na production
5. **Monitor:** Prati prve 24h intenzivno

---

**NAPOMENA:** Ova migracija će drastično poboljšati performanse i stabilnost sistema. Vredna je truda! 🚀