#!/usr/bin/env python3
"""
utils/generate_structure_md.py
VERSION: 1.0
PURPOSE: Auto-generate structure.md from actual project files
USAGE: python utils/generate_structure_md.py
"""

from pathlib import Path
from datetime import datetime

# ============================================================================
# FOLDER DESCRIPTIONS
# ============================================================================

FOLDER_INFO = {
    "apps": {
        "emoji": "🎮",
        "title": "Main Applications",
        "desc": "Standalone programs that can run independently",
    },
    "core": {
        "emoji": "🔧",
        "title": "Core System Logic",
        "desc": "Fundamental system components used across all apps",
    },
    "regions": {
        "emoji": "👁️",
        "title": "Screen Region Readers",
        "desc": "Individual screen region handlers for data extraction",
    },
    "database": {
        "emoji": "💾",
        "title": "Database Layer",
        "desc": "SQLite database management and optimization",
    },
    "gui": {
        "emoji": "🖥️",
        "title": "GUI Control Panel",
        "desc": "PySide6 GUI application for controlling all programs",
    },
    "ai": {
        "emoji": "🤖",
        "title": "Machine Learning",
        "desc": "ML models for game phase prediction and color classification",
    },
    "utils": {
        "emoji": "🛠️",
        "title": "Utility Tools",
        "desc": "Standalone tools for development, debugging, and maintenance",
    },
    "tests": {
        "emoji": "🧪",
        "title": "Testing Suite",
        "desc": "Unit tests and integration tests",
    },
    "data": {
        "emoji": "📦",
        "title": "Data Storage",
        "desc": "Databases, models, screenshots, and coordinate files",
    },
    "logs": {
        "emoji": "📝",
        "title": "Log Files",
        "desc": "Application logs (auto-rotated: 10MB × 5 backups)",
    },
    "docs": {
        "emoji": "📚",
        "title": "Documentation",
        "desc": "Complete project documentation",
    },
    "analysis": {
        "emoji": "📊",
        "title": "Analysis Tools & Data",
        "desc": "Data analysis scripts and exported data",
    },
}


# ============================================================================
# FILE DESCRIPTIONS
# ============================================================================

FILE_DESCRIPTIONS = {
    # Root
    "main.py": "GUI Application Entry Point",
    "config.py": "Configuration Management",
    "config.json": "User Configuration File",
    "logger.py": "Centralized Logging System",
    "requirements.txt": "Python Dependencies",
    "README.md": "Project Overview & Quick Start",
    "CHANGELOG.md": "Version History",
    "javascript.txt": "CSS Injection Code for Browsers",
    "structure.md": "This File - Project Structure",
    "project_structure.txt": "Auto-generated File Tree",
    "__init__.py": "Python Package Marker",
    # apps/
    "base_app.py": "Base template for all apps",
    "main_data_collector.py": "**Program 1** - Multi-bookmaker data collection",
    "rgb_collector.py": "**Program 2** - RGB training data collection",
    "betting_agent.py": "**Program 3** - Automated betting system",
    "session_keeper.py": "**Program 4** - Keep sessions alive",
    "prediction_agent.py": "**Program 5** - ML-based predictions",
    # core/
    "coord_manager.py": "Coordinate system management (v5.x)",
    "screen_reader.py": "Screenshot capture & OCR",
    "ocr_processor.py": "Tesseract OCR wrapper",
    "smart_validator.py": "OCR result validation & correction",
    "gui_controller.py": "Mouse & keyboard automation",
    "event_collector.py": "Event management system",
    "bookmaker_process.py": "Individual bookmaker process handler",
    "bookmaker_orchestrator.py": "Multi-bookmaker coordination",
    # regions/
    "base_region.py": "Base class for all regions",
    "score.py": 'Game score OCR (e.g., "1.50x")',
    "my_money.py": "User balance OCR",
    "other_money.py": "Other player balance OCR",
    "other_count.py": "Player count OCR",
    "game_phase.py": "Game phase detection (K-means)",
    # database/
    "models.py": "**PRIMARY** - SQLAlchemy models & DB operations",
    "setup.py": "Database initialization",
    "optimizer.py": "Performance optimization & cleanup",
    "writer.py": "Batch writer for high-throughput",
    "worker.py": "Background worker process",
    "database.py": "Legacy database utilities",
    # gui/
    "app_controller.py": "Process control + live log streaming",
    "stats_widgets.py": "Real-time statistics display (DB polling)",
    "config_manager.py": "Configuration save/load",
    "setup_dialog.py": "Setup wizard dialog",
    "log_reader.py": "Live log file reader",
    "stats_queue.py": "Stats queue management",
    # ai/
    "color_collector.py": "Collect RGB training data",
    "color_selector.py": "Interactive RGB labeling tool",
    "model_trainer.py": "Train K-means clustering models",
    "phase_predictor.py": "Predict game phase from RGB",
    # utils/
    "region_editor.py": "Interactive coordinate editor",
    "region_visualizer.py": "Visualize & verify coordinates",
    "diagnostic.py": "System diagnostics",
    "debug_monitor.py": "Real-time debug monitor",
    "performance_analyzer.py": "Performance metrics",
    "data_analyzer.py": "Database data analysis",
    "pre_run_verification.py": "Pre-run system check",
    "quick_test.py": "Quick system test",
    "list_structure.py": "Generate project structure tree",
    # tests/
    "quick_check.py": "Quick system check",
    "test_betting.py": "Betting agent tests",
    "test_ocr_accuracy.py": "OCR accuracy tests",
    "test_reader.py": "Screen reader tests",
    # analysis/
    "analysis_readme.md": "Analysis guide",
    "betting_stats.py": "Betting statistics analyzer",
    "data_extractor.py": "Extract data from databases",
    "log_processor.py": "Process log files",
    "style_getter.py": "Extract styling patterns",
}


# ============================================================================
# GENERATOR CLASS
# ============================================================================


class StructureMDGenerator:
    """Generate structure.md from actual project files."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.output = []

    def generate(self) -> str:
        """Generate complete structure.md content."""
        self._add_header()
        self._add_overview()
        self._add_root_files()
        self._add_folders()
        self._add_navigation()
        self._add_stats()
        self._add_legend()
        self._add_footer()

        return "\n".join(self.output)

    def _add_header(self):
        """Add header section."""
        self.output.extend(
            [
                "# 🎰 Robin Project - File Structure",
                "**Aviator Data Collector v5.2 - Multi-Bookmaker System**",
                "",
                "---",
                "",
            ]
        )

    def _add_overview(self):
        """Add project overview."""
        self.output.extend(["## 📁 Project Overview", "", "```", "Robin/"])

        for folder_name, info in FOLDER_INFO.items():
            emoji = info["emoji"]
            title = info["title"]
            self.output.append(f"├── {emoji} {folder_name:<12} - {title}")

        self.output.extend(["```", "", "---", ""])

    def _add_root_files(self):
        """Add root files section."""
        self.output.extend(
            [
                "## 📄 Root Files",
                "",
                "| File | Status | Description |",
                "|------|--------|-------------|",
            ]
        )

        root_files = sorted(
            [
                f
                for f in self.root.iterdir()
                if f.is_file() and not f.name.startswith(".")
            ],
            key=lambda x: x.name,
        )

        for file in root_files:
            name = file.name
            status = self._get_file_status(name)
            desc = FILE_DESCRIPTIONS.get(name, "")

            self.output.append(f"| `{name}` | {status} | {desc} |")

        self.output.extend(["", "---", ""])

    def _add_folders(self):
        """Add all folder sections."""
        folders_to_document = [
            "apps",
            "core",
            "regions",
            "database",
            "gui",
            "ai",
            "utils",
            "tests",
            "data",
            "logs",
            "docs",
            "analysis",
        ]

        for folder_name in folders_to_document:
            folder_path = self.root / folder_name

            if not folder_path.exists():
                continue

            self._add_folder_section(folder_name, folder_path)

    def _add_folder_section(self, folder_name: str, folder_path: Path):
        """Add section for a specific folder."""
        info = FOLDER_INFO.get(folder_name, {})
        emoji = info.get("emoji", "📁")
        title = info.get("title", folder_name)
        desc = info.get("desc", "")

        self.output.extend(
            [f"## {emoji} {folder_name}/ - {title}", "", f"**Purpose:** {desc}", ""]
        )

        # Special handling for data/ folder (has subfolders)
        if folder_name == "data":
            self._add_data_folder_special(folder_path)
            return

        # Special handling for utils/ folder (has video_log subfolder)
        if folder_name == "utils":
            self._add_utils_folder_special(folder_path)
            return

        # Regular folder - list files
        self.output.extend(
            ["| File | Status | Description |", "|------|--------|-------------|"]
        )

        files = sorted(
            [f for f in folder_path.iterdir() if f.is_file() and f.suffix == ".py"],
            key=lambda x: x.name,
        )

        for file in files:
            name = file.name
            status = self._get_file_status(name)
            desc = FILE_DESCRIPTIONS.get(name, "")

            self.output.append(f"| `{name}` | {status} | {desc} |")

        self.output.extend(["", "---", ""])

    def _add_data_folder_special(self, folder_path: Path):
        """Special handling for data/ folder."""
        subfolders = {
            "coordinates": "📍 Coordinate configuration files",
            "databases": "💾 SQLite databases",
            "models": "🤖 Trained ML models",
            "video_screenshots": "📸 Screenshot storage for video processing",
        }

        for subfolder_name, desc in subfolders.items():
            subfolder_path = folder_path / subfolder_name

            if not subfolder_path.exists():
                continue

            self.output.extend([f"### {desc}", ""])

            if subfolder_name == "coordinates":
                self.output.extend(
                    [
                        "- `bookmaker_coords.json` - Main coordinate file (v5.x format)",
                        "- `video_regions.json` - Video processing regions (archived)",
                        "",
                    ]
                )
            elif subfolder_name == "databases":
                self.output.extend(
                    [
                        "- `main_game_data.db` - **PRIMARY** - All game data (rounds, bets)",
                        "- `game_phase.db` - Game phase training data",
                        "- `bet_button.db` - Bet button training data",
                        "",
                    ]
                )
            elif subfolder_name == "models":
                self.output.extend(
                    [
                        "- `game_phase_kmeans.pkl` - Game phase classifier",
                        "- `game_phase_weighted.pkl` - Weighted phase classifier",
                        "- `bet_button_kmeans.pkl` - Bet button classifier",
                        "- `bet_button_weighted.pkl` - Weighted button classifier",
                        "- `model_mapping.json` - Model metadata",
                        "",
                    ]
                )
            elif subfolder_name == "video_screenshots":
                self.output.extend(
                    ["**Note:** Archived feature for video processing", ""]
                )

        self.output.extend(["---", ""])

    def _add_utils_folder_special(self, folder_path: Path):
        """Special handling for utils/ folder with video_log subfolder."""
        # Regular utils files
        self.output.extend(
            [
                "### 📍 Coordinate Tools",
                "| File | Status | Description |",
                "|------|--------|-------------|",
            ]
        )

        coord_files = ["region_editor.py", "region_visualizer.py"]
        for name in coord_files:
            if (folder_path / name).exists():
                status = self._get_file_status(name)
                desc = FILE_DESCRIPTIONS.get(name, "")
                self.output.append(f"| `{name}` | {status} | {desc} |")

        self.output.extend(["", "### 🔍 Debug & Analysis"])
        self.output.extend(
            ["| File | Status | Description |", "|------|--------|-------------|"]
        )

        debug_files = [
            "diagnostic.py",
            "debug_monitor.py",
            "performance_analyzer.py",
            "data_analyzer.py",
        ]
        for name in debug_files:
            if (folder_path / name).exists():
                status = self._get_file_status(name)
                desc = FILE_DESCRIPTIONS.get(name, "")
                self.output.append(f"| `{name}` | {status} | {desc} |")

        self.output.extend(["", "### ✅ Testing & Verification"])
        self.output.extend(
            ["| File | Status | Description |", "|------|--------|-------------|"]
        )

        test_files = ["pre_run_verification.py", "quick_test.py"]
        for name in test_files:
            if (folder_path / name).exists():
                status = self._get_file_status(name)
                desc = FILE_DESCRIPTIONS.get(name, "")
                self.output.append(f"| `{name}` | {status} | {desc} |")

        # Video tools
        video_log_path = folder_path / "video_log"
        if video_log_path.exists():
            self.output.extend(["", "### 📹 Video Processing Tools"])
            self.output.extend(
                ["| File | Status | Description |", "|------|--------|-------------|"]
            )

            video_files = sorted(
                [f for f in video_log_path.iterdir() if f.suffix == ".py"]
            )
            for file in video_files:
                name = f"video_log/{file.name}"
                self.output.append(
                    f"| `{name}` | 🗂️ **ARCHIVE** | Video processing tool |"
                )

            self.output.extend(
                [
                    "",
                    "**Note:** Video tools are archived but available if needed for future video analysis features",
                    "",
                ]
            )

        # Other utils
        self.output.extend(["### 🔧 Other"])
        self.output.extend(
            ["| File | Status | Description |", "|------|--------|-------------|"]
        )

        other_files = ["list_structure.py"]
        for name in other_files:
            if (folder_path / name).exists():
                status = self._get_file_status(name)
                desc = FILE_DESCRIPTIONS.get(name, "")
                self.output.append(f"| `{name}` | {status} | {desc} |")

        self.output.extend(["", "---", ""])

    def _add_navigation(self):
        """Add quick navigation section."""
        self.output.extend(
            [
                "## 🎯 Quick Navigation",
                "",
                "### For Users",
                "1. **Getting Started:** `docs/01_quick_start.md`",
                "2. **Run GUI:** `python main.py`",
                "3. **Configuration:** Edit `config.json`",
                "",
                "### For Developers",
                "1. **System Architecture:** `docs/03_system_architecture.md`",
                "2. **Core Logic:** `core/` folder",
                "3. **Add New App:** Extend `apps/base_app.py`",
                "",
                "### For Troubleshooting",
                "1. **Common Issues:** `docs/05_troubleshooting.md`",
                "2. **Check Logs:** `logs/` folder",
                "3. **Run Diagnostics:** `python utils/diagnostic.py`",
                "",
                "---",
                "",
            ]
        )

    def _add_stats(self):
        """Add project statistics."""
        py_files = list(self.root.rglob("*.py"))
        py_count = len([f for f in py_files if "__pycache__" not in str(f)])

        self.output.extend(
            [
                "## 📈 Project Stats",
                "",
                f"- **Total Python Files:** ~{py_count} active files",
                "- **Lines of Code:** ~15,000+ lines",
                "- **Version:** 5.2",
                f"- **Last Updated:** {datetime.now().strftime('%Y-%m-%d')}",
                "",
                "---",
                "",
            ]
        )

    def _add_legend(self):
        """Add status legend."""
        self.output.extend(
            [
                "## 🔄 File Status Legend",
                "",
                "| Symbol | Meaning |",
                "|--------|---------|",
                "| ✅ **ACTIVE** | Currently used in production |",
                "| 📄 **GENERATED** | Auto-generated file |",
                "| 🗂️ **ARCHIVE** | Archived but available |",
                "| 📸 **DATA** | Data storage folder |",
                "| ⚠️ **DEPRECATED** | Will be removed in future |",
                "",
                "---",
                "",
            ]
        )

    def _add_footer(self):
        """Add footer."""
        self.output.extend(
            [
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d')}",
                "**Structure Version:** 2.0",
            ]
        )

    def _get_file_status(self, filename: str) -> str:
        """Determine file status."""
        if filename == "project_structure.txt":
            return "📄 **GENERATED**"
        elif "old" in filename.lower() or "backup" in filename.lower():
            return "🗂️ **ARCHIVE**"
        elif filename.endswith(".db"):
            return "💾 **DATABASE**"
        else:
            return "✅ **ACTIVE**"

    def save(self, output_path: Path):
        """Save generated structure.md to file."""
        content = self.generate()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Generated: {output_path}")
        print(f"   Lines: {len(self.output)}")


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    output_path = project_root / "structure.md"

    print("=" * 60)
    print("STRUCTURE.MD GENERATOR")
    print("=" * 60)
    print(f"\nProject Root: {project_root}")
    print(f"Output File: {output_path}")
    print("\nGenerating...")

    generator = StructureMDGenerator(project_root)
    generator.save(output_path)

    print("\n✅ Done!")
    print(f"\nView: {output_path}")


if __name__ == "__main__":
    main()
