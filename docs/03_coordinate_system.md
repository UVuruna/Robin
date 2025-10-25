# 📐 Coordinate System Guide

**VERSION: 3.0**  
**Understanding how coordinates work in the Aviator project**

---

## 🎯 Overview

The coordinate system uses **base coordinates** + **position offsets** to support multiple bookmakers in a grid layout.

**Key Concepts:**
- **Base Coordinates:** Region locations relative to Top-Left (0, 0) of a single bookmaker
- **Position Offsets:** Grid positions (TL, TC, TR, BL, BC, BR) for placing bookmakers on screen
- **Final Coordinates:** Base + Offset = Where to actually read on screen

**Why This Design?**
- Define regions ONCE per bookmaker
- Position ANY bookmaker at ANY grid location
- No need to re-create coordinates for each position

---

## 📂 JSON Structure

### File: `data/coordinates/bookmaker_coords.json`

```json
{
  "positions": {
    "TL": {"left": 0, "top": 0},
    "TC": {"left": 1030, "top": 0},
    "TR": {"left": 2060, "top": 0},
    "BL": {"left": 0, "top": 1120},
    "BC": {"left": 1030, "top": 1120},
    "BR": {"left": 2060, "top": 1120}
  },
  "bookmakers": {
    "BalkanBet": {
      "score_region": {
        "left": 615,
        "top": 420,
        "width": 800,
        "height": 215
      },
      "my_money_region": {
        "left": 1240,
        "top": 140,
        "width": 140,
        "height": 40
      },
      "player_count_region": {
        "left": 270,
        "top": 900,
        "width": 110,
        "height": 35
      },
      "other_money_region": {
        "left": 305,
        "top": 935,
        "width": 130,
        "height": 35
      },
      "phase_region": {
        "left": 450,
        "top": 420,
        "width": 410,
        "height": 180
      },
      "play_button_coords": {
        "left": 380,
        "top": 750,
        "width": 220,
        "height": 80
      },
      "bet_amount_coords": {
        "left": 165,
        "top": 715,
        "width": 150,
        "height": 45
      },
      "auto_play_coords": {
        "left": 390,
        "top": 865,
        "width": 80,
        "height": 35
      }
    },
    "Mozzart": {
      "score_region": { ... },
      ...
    }
  }
}
```

---

## 🧮 How It Works

### Grid Layout (3x2 - Six Bookmakers)

```
┌──────────┬──────────┬──────────┐
│    TL    │    TC    │    TR    │
│ (0, 0)   │(1030, 0) │(2060, 0) │
├──────────┼──────────┼──────────┤
│    BL    │    BC    │    BR    │
│(0, 1120) │(1030,1120)│(2060,1120)│
└──────────┴──────────┴──────────┘
```

**Position Codes:**
- **TL** = Top-Left
- **TC** = Top-Center  
- **TR** = Top-Right
- **BL** = Bottom-Left
- **BC** = Bottom-Center
- **BR** = Bottom-Right

### Calculation Formula

```python
final_coords = base_coords + position_offset

# Example: BalkanBet @ TC
base = {"left": 615, "top": 420, "width": 800, "height": 215}
position = {"left": 1030, "top": 0}  # TC offset

final = {
    "left": 615 + 1030 = 1645,
    "top": 420 + 0 = 420,
    "width": 800,  # unchanged
    "height": 215  # unchanged
}
```

**Result:** The score region for BalkanBet at TC position is at (1645, 420) with size 800x215

---

## 🔧 CoordsManager API

### Usage in Code

```python
from core.coord_manager import CoordsManager

manager = CoordsManager()

# Get available options
bookmakers = manager.get_available_bookmakers()
# Returns: ['BalkanBet', 'Mozzart', 'Meridian', ...]

positions = manager.get_available_positions()
# Returns: ['TL', 'TC', 'TR', 'BL', 'BC', 'BR']

# Calculate final coordinates
coords = manager.calculate_coords(
    bookmaker_name="BalkanBet",
    position_code="TC",
    monitor_offset=0  # If using second monitor, add offset
)

# Returns complete region dict:
{
    "score_region": {"left": 1645, "top": 420, "width": 800, "height": 215},
    "my_money_region": {"left": 2270, "top": 140, "width": 140, "height": 40},
    "player_count_region": {...},
    "other_money_region": {...},
    "phase_region": {...},
    "play_button_coords": {...},
    "bet_amount_coords": {...},
    "auto_play_coords": {...}
}
```

---

## 🎨 Creating Base Coordinates

### Using Region Editor

```bash
python utils/region_editor.py
```

**Steps:**
1. **Position browser** at Top-Left (fullscreen with F11)
2. **Select bookmaker** name (will be saved under this name)
3. **Draw 8 regions** with mouse:
   - SCORE - Center display (large, shows 1.86x)
   - PHASE - Around score (for RGB detection)
   - MY_MONEY - Top-right corner (balance)
   - PLAYER_COUNT - Left sidebar (3269/3588)
   - OTHER_MONEY - Left sidebar (below player count)
   - PLAY_BUTTON - Green "Play" button
   - BET_AMOUNT - Bet input field
   - AUTO_PLAY - Auto cashout input
4. **Press 's'** to save
5. **Coordinates saved** to `bookmaker_coords.json`

### Important Tips

- Browser MUST be fullscreen (F11)
- Zoom MUST be 100%
- CSS MUST be injected (dark theme, larger text)
- Draw regions ACCURATELY - OCR depends on this!

---

## 🧪 Testing Coordinates

### Visual Verification

```bash
python utils/region_visualizer.py
```

**What it does:**
- Screenshots each region
- Displays with colored borders
- Shows bookmaker name + position
- Helps verify alignment

**Check:**
- ✅ Borders align with screen elements
- ✅ Score region captures multiplier text
- ✅ Money regions capture numbers
- ✅ No text cut off

### Quick Test

```bash
python utils/quick_test.py
```

**Verifies:**
- JSON format valid
- CoordsManager loads correctly
- Coordinate calculation works
- All required regions present

---

## 📐 Region Types & Sizes

| Region | Purpose | OCR Type | Typical Size | Notes |
|--------|---------|----------|--------------|-------|
| **score_region** | Read multiplier | score | 800x215 | Large, center screen |
| **my_money_region** | Read balance | money_small | 140x40 | Top-right |
| **player_count_region** | Read player counts | player_count | 110x35 | Left sidebar, tiny |
| **other_money_region** | Read total bets | money_medium | 130x35 | Left sidebar |
| **phase_region** | Detect phase | RGB (K-means) | 410x180 | Around score, NO OCR |
| **play_button_coords** | Button position | RGB detection | 220x80 | Green button |
| **bet_amount_coords** | Input field | Click target | 150x45 | Where to type amount |
| **auto_play_coords** | Input field | Click target | 80x35 | Auto cashout value |

---

## 🔄 Workflow: Adding New Bookmaker

### Step 1: Create Base Coordinates

```bash
# Position browser at TL (fullscreen)
python utils/region_editor.py

# Select: "NewBookmaker"
# Draw 8 regions
# Press 's' to save
```

### Step 2: Verify Coordinates

```bash
python utils/region_visualizer.py
# Test: NewBookmaker @ TL
# Check all regions align correctly
```

### Step 3: Test Multiple Positions

```bash
# Move browser to TC position
python utils/region_visualizer.py
# Test: NewBookmaker @ TC
# Should work with same base coords!
```

### Step 4: Add to GUI

```bash
python main.py
# Setup Config → Add Bookmaker
# Name: NewBookmaker
# Position: TC
# Save
```

### Step 5: Production Run

```bash
# Start Data Collector in GUI
# Monitor logs for 5 minutes
# Verify data in database
```

---

## ⚙️ Multi-Monitor Setup

### Monitor Offset

If using second monitor:

```python
# Example: Monitor 1 = 1920px wide
# Bookmaker on Monitor 2 (right)

coords = manager.calculate_coords(
    bookmaker_name="BalkanBet",
    position_code="TL",
    monitor_offset=1920  # Add monitor 1 width
)

# Result: Coordinates shifted +1920px to the right
```

### Config

```json
{
  "bookmakers": [
    {
      "name": "BalkanBet",
      "position": "TL",
      "monitor_offset": 1920
    }
  ]
}
```

---

## 🎯 Best Practices

### 1. One Bookmaker at a Time
- Create coordinates for 1 bookmaker
- Verify thoroughly
- Then move to next bookmaker

### 2. Consistent Browser State
**Always:**
- Fullscreen mode (F11)
- 100% zoom (Ctrl+0)
- CSS injected (JavaScript console)
- Same screen resolution

### 3. Document Positions
Keep a note:
```
TL: BalkanBet
TC: Mozzart
TR: Soccer
BL: MaxBet
BC: Meridian
BR: PariMatch
```

### 4. Backup Coordinates
```bash
cp bookmaker_coords.json bookmaker_coords.backup.json
```

### 5. Test Before Production
- 5-minute test run
- Check OCR accuracy (logs)
- Verify database has correct data
- Compare with actual game values

---

## 🐛 Troubleshooting

### Issue: Regions Don't Align

**Symptom:** Borders don't match screen elements

**Solutions:**
1. Check browser is fullscreen (F11)
2. Check zoom is 100% (Ctrl+0)
3. Re-inject CSS
4. Re-create coordinates

### Issue: OCR Reads Wrong Values

**Symptom:** Score shows "ERROR" or wrong numbers

**Solutions:**
1. Check region includes full text
2. Make region slightly larger
3. Check CSS is injected (numbers should be large)
4. Verify browser not scaled by OS

### Issue: All Bookmakers Read Same Values

**Symptom:** 6 bookmakers, all show identical data

**Solutions:**
1. Check position offsets in JSON
2. Verify bookmaker names match config
3. Check calculate_coords() is called correctly
4. Test with region_visualizer.py

### Issue: Cannot Save Coordinates

**Symptom:** Region editor doesn't save

**Solutions:**
1. Check `data/coordinates/` folder exists
2. Check file permissions (write access)
3. Check JSON syntax after manual edits
4. Try running as administrator (Windows)

---

## 📚 Related Documentation

- [Quick Start](01_quick_start.md) - Setup & first run
- [GUI Guide](02_gui_guide.md) - Using GUI
- [System Architecture](03_system_architecture.md) - How it all works
- [Deployment](04_deployment_production.md) - Production setup
- [Troubleshooting](05_troubleshooting.md) - Common issues

---

## 🧮 Technical Details

### Position Math Example

```
Screen: 3090px wide x 2240px tall (dual monitor)

Monitor 1: 0 - 1920px
Monitor 2: 1920 - 3090px (1170px wide)

Grid Layout (3x2):
- Each cell: ~1030px wide x 1120px tall
- Spacing: 0px (browsers touch edge-to-edge)

Positions:
TL: (0, 0)        → Top-left corner
TC: (1030, 0)     → 1030px right
TR: (2060, 0)     → 2060px right
BL: (0, 1120)     → 1120px down
BC: (1030, 1120)  → 1030px right, 1120px down
BR: (2060, 1120)  → 2060px right, 1120px down
```

### Coordinate Components

```python
region = {
    "left": int,    # X position (px from left edge)
    "top": int,     # Y position (px from top edge)
    "width": int,   # Width in pixels
    "height": int   # Height in pixels
}
```

### CoordsManager Implementation

```python
def calculate_coords(bookmaker_name, position_code, monitor_offset=0):
    """
    Calculate final coordinates.
    
    Args:
        bookmaker_name: e.g., 'BalkanBet'
        position_code: e.g., 'TC'
        monitor_offset: e.g., 1920 (second monitor)
    
    Returns:
        Dict with all region coordinates
    """
    base = get_bookmaker_base(bookmaker_name)
    offset = get_position_offset(position_code)
    
    final = {}
    for region_name, region_data in base.items():
        final[region_name] = {
            "left": region_data["left"] + offset["left"] + monitor_offset,
            "top": region_data["top"] + offset["top"],
            "width": region_data["width"],
            "height": region_data["height"]
        }
    
    return final
```

---

**Master coordinates, master the system!** 📐
