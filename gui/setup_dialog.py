# gui/setup_dialog.py
# VERSION: 1.0
# PURPOSE: Setup configuration dialog

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QDialogButtonBox,
    QListWidget,
    QDoubleSpinBox,
)
from typing import Dict

class SetupDialog(QDialog):
    """
    Setup configuration dialog.

    Allows user to configure:
    - Dual monitor setup
    - Bookmakers and positions
    - Betting agent parameters
    - Session keeper parameters
    """

    def __init__(self, config: Dict = None, parent=None):
        super().__init__(parent)

        self.config = config or {}
        self.coords_manager = CoordsManager()

        self.setWindowTitle("⚙️ Setup Configuration")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)

        self.init_ui()
        self.load_from_config()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # General Setup
        general_group = self.create_general_setup()
        layout.addWidget(general_group)

        # Bookmakers Setup
        bookmakers_group = self.create_bookmakers_setup()
        layout.addWidget(bookmakers_group)

        # Betting Agent Setup
        betting_group = self.create_betting_setup()
        layout.addWidget(betting_group)

        # Session Keeper Setup
        keeper_group = self.create_keeper_setup()
        layout.addWidget(keeper_group)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def create_general_setup(self) -> QGroupBox:
        """Create general setup group."""
        group = QGroupBox("General Setup")
        layout = QFormLayout(group)

        # Dual monitor checkbox
        self.dual_monitor_check = QCheckBox("Use Dual Monitors")
        layout.addRow("Monitor Setup:", self.dual_monitor_check)

        # Number of bookmakers
        self.num_bookmakers_spin = QSpinBox()
        self.num_bookmakers_spin.setRange(1, 6)
        self.num_bookmakers_spin.setValue(1)
        self.num_bookmakers_spin.valueChanged.connect(self.update_bookmaker_list)
        layout.addRow("Number of Bookmakers:", self.num_bookmakers_spin)

        return group

    def create_bookmakers_setup(self) -> QGroupBox:
        """Create bookmakers setup group."""
        group = QGroupBox("Bookmakers Setup")
        layout = QVBoxLayout(group)

        # Instructions
        info_label = QLabel(
            "Configure each bookmaker and position:\n"
            "Select bookmaker from dropdown, then select position."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Bookmaker configurations list
        self.bookmaker_list = QListWidget()
        self.bookmaker_list.setMaximumHeight(150)
        layout.addWidget(self.bookmaker_list)

        # Add/Remove buttons
        btn_layout = QHBoxLayout()

        self.add_bookmaker_btn = QPushButton("➕ Add Bookmaker")
        self.add_bookmaker_btn.clicked.connect(self.add_bookmaker)
        btn_layout.addWidget(self.add_bookmaker_btn)

        self.remove_bookmaker_btn = QPushButton("➖ Remove Selected")
        self.remove_bookmaker_btn.clicked.connect(self.remove_bookmaker)
        btn_layout.addWidget(self.remove_bookmaker_btn)

        layout.addLayout(btn_layout)

        # Current bookmaker configuration
        config_layout = QFormLayout()

        self.bookmaker_combo = QComboBox()
        self.bookmaker_combo.addItems(self.coords_manager.get_available_bookmakers())
        config_layout.addRow("Bookmaker:", self.bookmaker_combo)

        self.position_combo = QComboBox()
        self.position_combo.addItems(self.coords_manager.get_available_positions())
        config_layout.addRow("Position:", self.position_combo)

        layout.addLayout(config_layout)

        return group

    def create_betting_setup(self) -> QGroupBox:
        """Create betting agent setup group."""
        group = QGroupBox("Betting Agent Configuration")
        layout = QFormLayout(group)

        # Bet amount
        self.bet_amount_spin = QDoubleSpinBox()
        self.bet_amount_spin.setRange(10.0, 100000.0)
        self.bet_amount_spin.setValue(10.0)
        self.bet_amount_spin.setDecimals(2)
        self.bet_amount_spin.setSuffix(" RSD")
        layout.addRow("Bet Amount:", self.bet_amount_spin)

        # Auto cash-out
        self.auto_stop_spin = QDoubleSpinBox()
        self.auto_stop_spin.setRange(1.01, 100.0)
        self.auto_stop_spin.setValue(2.0)
        self.auto_stop_spin.setDecimals(2)
        self.auto_stop_spin.setSuffix("x")
        layout.addRow("Auto Cash-Out:", self.auto_stop_spin)

        return group

    def create_keeper_setup(self) -> QGroupBox:
        """Create session keeper setup group."""
        group = QGroupBox("Session Keeper Configuration")
        layout = QFormLayout(group)

        # Interval
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(60, 3600)
        self.interval_spin.setValue(600)
        self.interval_spin.setSuffix(" seconds")
        layout.addRow("Update Interval:", self.interval_spin)

        # Info
        info_label = QLabel("(10 minutes = 600 seconds)")
        info_label.setStyleSheet("color: gray;")
        layout.addRow("", info_label)

        return group

    def add_bookmaker(self):
        """Add bookmaker to list."""
        bookmaker = self.bookmaker_combo.currentText()
        position = self.position_combo.currentText()

        if not bookmaker or not position:
            return

        item_text = f"{bookmaker} @ {position}"

        # Check if already exists
        for i in range(self.bookmaker_list.count()):
            if self.bookmaker_list.item(i).text() == item_text:
                return  # Already added

        self.bookmaker_list.addItem(item_text)

    def remove_bookmaker(self):
        """Remove selected bookmaker from list."""
        current_item = self.bookmaker_list.currentItem()
        if current_item:
            self.bookmaker_list.takeItem(self.bookmaker_list.row(current_item))

    def update_bookmaker_list(self):
        """Update bookmaker list based on number selected."""
        # This could auto-adjust the list size if needed
        pass

    def load_from_config(self):
        """Load values from existing config."""
        last_setup = self.config.get("last_setup")

        if last_setup:
            # Dual monitor
            self.dual_monitor_check.setChecked(last_setup.get("dual_monitor", False))

            # Bookmakers
            bookmakers = last_setup.get("bookmakers", [])
            self.num_bookmakers_spin.setValue(len(bookmakers))

            for bm in bookmakers:
                item_text = f"{bm['name']} @ {bm['position']}"
                self.bookmaker_list.addItem(item_text)

        # Betting agent
        betting_config = self.config.get("betting_agent", {})
        self.bet_amount_spin.setValue(betting_config.get("bet_amount", 10.0))
        self.auto_stop_spin.setValue(betting_config.get("auto_stop", 2.0))

        # Session keeper
        keeper_config = self.config.get("session_keeper", {})
        self.interval_spin.setValue(keeper_config.get("interval", 600))

    def get_config(self) -> Dict:
        """
        Get configuration from dialog.

        Returns:
            Dict with configuration
        """
        # Parse bookmakers from list
        bookmakers = []
        for i in range(self.bookmaker_list.count()):
            item_text = self.bookmaker_list.item(i).text()
            # Parse "BalkanBet @ TL"
            parts = item_text.split(" @ ")
            if len(parts) == 2:
                bookmakers.append(
                    {"name": parts[0].strip(), "position": parts[1].strip()}
                )

        return {
            "last_setup": {
                "dual_monitor": self.dual_monitor_check.isChecked(),
                "bookmakers": bookmakers,
            },
            "betting_agent": {
                "bet_amount": self.bet_amount_spin.value(),
                "auto_stop": self.auto_stop_spin.value(),
            },
            "session_keeper": {"interval": self.interval_spin.value()},
        }
