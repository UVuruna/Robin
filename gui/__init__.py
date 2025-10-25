# gui/__init__.py
# VERSION: 1.0
# PURPOSE: GUI package initialization

"""
Aviator Control Panel GUI Package

Modules:
- config_manager: Configuration file management
- app_controller: Application process control
- setup_dialog: Setup configuration dialog
- stats_widgets: Statistics widgets for each app type
"""

from gui.config_manager import ConfigManager
from gui.app_controller import AppController
from gui.setup_dialog import SetupDialog
from gui.stats_widgets import (
    DataCollectorStats,
    RGBCollectorStats,
    BettingAgentStats,
    SessionKeeperStats,
)

__all__ = [
    "ConfigManager",
    "AppController",
    "SetupDialog",
    "DataCollectorStats",
    "RGBCollectorStats",
    "BettingAgentStats",
    "SessionKeeperStats",
]

__version__ = "1.0.0"


# ============================================================================
# INSTALLATION GUIDE
# ============================================================================

"""
INSTALACIJA I POKRETANJE GUI-ja

1. INSTALACIJA PYSIDE6
   ----------------------
   pip install PySide6

2. FOLDER STRUKTURA
   ------------------
   Aviator/
   ├── main.py                    # NOVI - GUI Control Panel
   ├── config.json                # NOVI - Automatski se kreira
   ├── gui/                       # NOVI FOLDER
   │   ├── __init__.py
   │   ├── config_manager.py
   │   ├── app_controller.py
   │   ├── setup_dialog.py
   │   └── stats_widgets.py
   ├── apps/
   │   ├── base_app.py
   │   ├── main_data_collector.py
   │   ├── betting_agent.py
   │   ├── rgb_collector.py
   │   └── session_keeper.py
   ├── core/
   ├── regions/
   └── ...

3. POKRETANJE
   -----------
   python main.py

4. KORIŠĆENJE
   -----------
   
   a) PRVI PUT - Setup Configuration:
      - Klikni "⚙️ Setup Config"
      - Odaberi dual monitor setup (ako koristiš 2 monitora)
      - Dodaj bookmakers (Add Bookmaker button)
      - Za svaki bookmaker odaberi position (TL, TR, BL, BR, TC, BC)
      - Konfiguriši Betting Agent parametre (bet amount, auto cashout)
      - Konfiguriši Session Keeper interval
      - Klikni OK
      - Klikni "💾 Save Setup" da sačuvaš konfiguraciju
   
   b) POKRETANJE APPS:
      - Idi u tab aplikacije koju hoćeš (Data, RGB, Agent, Keeper)
      - Klikni "▶️ START"
      - Prati logove u desnom delu prozora
      - Prati statistiku u levom delu prozora
   
   c) ZAUSTAVLJANJE APPS:
      - Za Data/RGB/Keeper: Klikni "⏹️ STOP"
      - Za Betting Agent:
        * "🛑 GRACEFUL STOP" - završi trenutni ciklus
        * "⚡ INSTANT STOP" - prekini odmah
   
   d) UČITAVANJE PRETHODNOG SETUP-a:
      - Klikni "🔄 Load Last Setup"
      - Automatski učitava iz config.json

5. NAPOMENE
   ---------
   - config.json se automatski kreira pri prvom pokretanju
   - Logovi se čuvaju i u log fajlovima (logs/ folder)
   - GUI prikazuje samo poslednje logove (1000 linija po app-u)
   - Možeš pokrenuti više apps istovremeno
   - Pri zatvaranju GUI-ja, svi apps se automatski zaustavljaju

6. DARK THEME
   -----------
   GUI koristi tamnu temu automatski. Ako želiš svetlu temu,
   zakomentiraj apply_dark_theme() u main.py

7. TROUBLESHOOTING
   ----------------
   
   Q: GUI se ne pokreće?
   A: Proveri da li je PySide6 instaliran: pip list | grep PySide6
   
   Q: Apps se ne pokreću iz GUI-ja?
   A: Proveri da li imaš sve apps fajlove u apps/ folderu
   
   Q: Logovi se ne prikazuju?
   A: Trenutna implementacija je placeholder - treba implementirati
      threading za čitanje stdout-a iz subprocess-a
   
   Q: Stats se ne update-uju?
   A: Stats widgeti su trenutno placeholder - treba implementirati
      čitanje iz baza podataka i real-time update

8. TODO - BUDUĆA POBOLJŠANJA
   --------------------------
   - Implementirati threading za čitanje logova iz subprocess-a
   - Implementirati real-time stats update iz baza
   - Dodati grafikone za threshold distribution (matplotlib)
   - Dodati Export logs funkcionalnost
   - Dodati Auto-restart on crash
   - Dodati notification system
   - Dodati tray icon za minimizaciju u background
"""
