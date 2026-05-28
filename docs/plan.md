# DCS Binding Visualizer — Project Plan

## Overview

A Python CLI utility that reads joystick/HOTAS button mappings from DCS World configuration files and renders visual reference images showing the control bindings overlaid on user-provided device photographs/diagrams. Outputs printable A4 landscape PNGs — one per aircraft seat/role — with both devices (stick + throttle/collective) displayed side by side. Multi-seat aircraft (e.g., AH-64D Pilot/CPG, F-14 Pilot/RIO) are automatically detected and produce separate binding images per seat.

## Target Environment

- **Primary OS**: Nobara Linux (Fedora-based)
- **Cross-platform**: Should work on Linux, Windows, macOS
- **DCS runs via**: Wine/Proton (Linux) or native (Windows)
- **Language**: Python 3
- **Interface**: CLI

---

## Architecture

### High-Level Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ DCS Config Files │────▶│  Lua Parser      │────▶│  Binding Data Model │
│ (Lua tables)     │     │                  │     │                     │
└─────────────────┘     └──────────────────┘     └────────┬────────────┘
                                                           │
┌─────────────────┐     ┌──────────────────┐              │
│ Device Images   │────▶│  OCR / Circle    │──┐           │
│ (numbered)       │     │  Detection       │  │           │
└─────────────────┘     └──────────────────┘  │           │
                                               ▼           ▼
                                      ┌────────────────────────────┐
                                      │  Button Position Mapping   │
                                      │  (image# → DCS button ID)  │
                                      └────────────┬───────────────┘
                                                   │
                                                   ▼
                                      ┌────────────────────────────┐
                                      │  Image Renderer            │
                                      │  (Pillow-based)            │
                                      │  - A4 landscape canvas     │
                                      │  - Two devices side by side│
                                      │  - Labels near buttons     │
                                      └────────────┬───────────────┘
                                                   │
                                                   ▼
                                      ┌────────────────────────────┐
                                      │  Output PNG per aircraft   │
                                      │  per seat/role             │
                                      └────────────────────────────┘
```

---

## Components

### 1. Configuration System

**User config file** (YAML) specifying:

```yaml
dcs:
  install_dir: "/path/to/DCS/install"
  saved_games_dir: "/path/to/Saved Games/DCS"

devices:
  - name: "WinWing Orion 2 EX (Stick)"
    image: "images/winwing-orion2-stick.png"
    button_mapping: "mappings/winwing-orion2-stick.yaml"
    position: left  # placement on the A4 page

  - name: "WinWing Orion 2 EX (F-18 Throttle)"
    image: "images/winwing-orion2-throttle.png"
    button_mapping: "mappings/winwing-orion2-throttle.yaml"
    position: right

output:
  format: png
  orientation: landscape
  page_size: A4
  dpi: 150
```

### 2. DCS Lua Config Parser

- Parse DCS input binding files located at:
  `<saved_games_dir>/Config/Input/<aircraft>/<device_name>/joystick/`
- Files are Lua tables (not full Lua scripts) — use a lightweight Lua table parser
- Extract: button/hat/axis assignments, binding display names, modifier keys
- Handle both `default.lua` (defaults) and user-overridden profiles

**Multi-seat aircraft detection:**

Some aircraft have multiple crew positions with independent binding sets. DCS organizes these as separate subdirectories or profile sets within the aircraft's input config folder. Examples:

| Aircraft | Seats |
|----------|-------|
| AH-64D Apache | Pilot, CPG (Co-Pilot/Gunner) |
| F-14 Tomcat | Pilot, RIO (Radar Intercept Officer) |
| Mi-24P Hind | Pilot, Operator |
| SA342 Gazelle | Pilot, Gunner |
| UH-1H Huey | Pilot, Gunner |

The parser must:
1. **Detect seat/role directories** within each aircraft's config path (e.g., subdirectories or naming conventions that indicate separate crew positions)
2. **Enumerate all seats** for a given aircraft automatically
3. **Parse bindings per seat** — each seat produces its own independent binding set
4. **Generate separate output images per seat** — named clearly (e.g., `AH-64D_Pilot.png`, `AH-64D_CPG.png`)

The tool should auto-discover seats without requiring manual configuration. Single-seat aircraft simply produce one image as normal.

**Candidate libraries:**
- `lupa` (Lua interpreter in Python)
- `slpp` (Simple Lua Preprocessor for Python — parses Lua tables to Python dicts)
- Custom regex-based parser as fallback

### 3. Device Image OCR & Circle Detection

Automatically locate numbered button markers on device images:

1. **Circle detection**: Use OpenCV (`cv2.HoughCircles` or contour detection) to find white circles on the image
2. **OCR**: Use Tesseract (`pytesseract`) to read the number inside each detected circle
3. **Output**: A mapping of `{image_number: (x, y)}` pixel coordinates

**Image requirements for users:**
- Device photo/diagram on any background
- Each button/hat/axis position marked with a white circle containing a black number
- Circles should be reasonably sized and non-overlapping

**Detection pipeline:**
```
Image → Grayscale → Threshold → Find contours (circles) → 
Extract ROI per circle → OCR each ROI → Return {number: (x, y)}
```

### 4. Button Number Mapping (ID only — no coordinates)

The user never specifies (x, y) positions. All button positions are determined automatically by the image detection pipeline (Component 3). The mapping file's sole purpose is to translate the number found in the image to the corresponding DCS button ID:

```yaml
# mappings/winwing-orion2-stick.yaml
device_name: "F18 Stick"  # as DCS identifies it

# Maps the NUMBER visible in the image circle → DCS button ID
# The (x, y) position is auto-detected from the image — not specified here
mappings:
  1: "JOY_BTN1"
  2: "JOY_BTN2"
  3: "JOY_BTN3"
  4: "JOY_BTN_POV1_U"  # hat up
  5: "JOY_BTN_POV1_D"  # hat down
  # ... etc

# Optional: Linux-specific overrides (same format, different IDs)
linux_overrides:
  1: "JOY_BTN3"   # Linux driver remaps btn1 → btn3
  2: "JOY_BTN1"
```

This handles the Linux driver reordering problem. The user maintains one mapping file per device that only defines number-to-ID relationships — the tool handles all spatial/position detection automatically from the image.

### 5. Image Renderer

Uses **Pillow** (PIL) to compose the final output:

**Canvas setup:**
- A4 landscape: 3508 × 2480 px at 300 DPI (or 1754 × 1240 at 150 DPI)
- White or dark background (configurable)
- Left half: device 1 image (scaled to fit)
- Right half: device 2 image (scaled to fit)
- Title bar at top: aircraft name + seat/role (e.g., "AH-64D Apache — Pilot")

**Label rendering:**
- For each bound button:
  - Find the (x, y) position from OCR detection (scaled to final image coords)
  - Render binding name as text near the button circle
  - Use a semi-transparent background box behind text for readability
  - Text placement: prefer to the right/below the circle, with collision avoidance
- Original numbered circles remain visible
- Unbound buttons: left blank (no label rendered)

**Text handling:**
- Use full DCS binding names where space allows
- Abbreviate long names if they would overlap other labels (e.g., "Countermeasures Dispense Btn" → "CM Dispense")
- Font: bundled TTF (e.g., DejaVu Sans or similar open-source font)

**Modifier support:**
- If a binding uses a modifier, append modifier indicator (e.g., "[MOD]" prefix or color coding)
- Optionally render a small legend explaining modifier notation

---

## CLI Interface

```bash
# Generate all aircraft binding images (all seats)
dcs-bindings render --config config.yaml

# Generate for a specific aircraft (all seats)
dcs-bindings render --config config.yaml --aircraft "AH-64D_BLK_II"

# Generate for a specific aircraft and seat only
dcs-bindings render --config config.yaml --aircraft "AH-64D_BLK_II" --seat "Pilot"

# List detected aircraft profiles (shows seats where applicable)
dcs-bindings list-aircraft --config config.yaml

# Detect and preview button positions from a device image (for setup/debugging)
dcs-bindings detect-buttons --image images/winwing-orion2-stick.png

# Validate configuration and mappings
dcs-bindings validate --config config.yaml
```

**Example `list-aircraft` output:**
```
Detected aircraft profiles:
  FA-18C_hornet          (1 seat)
  AH-64D_BLK_II         (2 seats: Pilot, CPG)
  F-14B                  (2 seats: Pilot, RIO)
  Ka-50_3                (1 seat)
```

**Output file naming:**
- Single-seat: `output/FA-18C_hornet.png`
- Multi-seat: `output/AH-64D_BLK_II_Pilot.png`, `output/AH-64D_BLK_II_CPG.png`

---

## Project Structure

```
dcs-binding-visualizer/
├── pyproject.toml              # Project metadata, dependencies
├── README.md
├── config.example.yaml         # Example user configuration
│
├── src/
│   └── dcs_bindings/
│       ├── __init__.py
│       ├── cli.py              # Click/argparse CLI entry point
│       ├── config.py           # Config loading & validation
│       ├── lua_parser.py       # DCS Lua table parser
│       ├── ocr_detector.py     # Circle detection + OCR
│       ├── mapping.py          # Button number mapping logic
│       ├── renderer.py         # Pillow-based image composition
│       └── models.py           # Data models (Binding, Device, etc.)
│
├── images/                     # User-provided device images (gitignored)
│   └── .gitkeep
│
├── mappings/                   # Button mapping files
│   ├── winwing-orion2-stick.yaml
│   ├── winwing-orion2-throttle.yaml
│   └── virpil-rotor-tcs-dual-sf.yaml
│
├── fonts/                      # Bundled open-source fonts
│   └── DejaVuSans.ttf
│
├── output/                     # Generated images (gitignored)
│   └── .gitkeep
│
└── tests/
    ├── test_lua_parser.py
    ├── test_ocr_detector.py
    └── test_renderer.py
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `Pillow` | Image rendering and composition |
| `opencv-python` | Circle/contour detection on device images |
| `pytesseract` | OCR to read numbers inside circles |
| `slpp` or `lupa` | Lua table parsing for DCS config files |
| `PyYAML` | Configuration file parsing |
| `click` | CLI framework |

**System dependencies:**
- Tesseract OCR engine (available via package manager on all platforms)

---

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Project scaffolding (pyproject.toml, package structure)
- [ ] Configuration system (YAML loading, path validation)
- [ ] DCS Lua config parser (read binding files, extract assignments)
- [ ] Multi-seat detection (auto-discover crew positions per aircraft)

### Phase 2: Image Detection
- [ ] Circle detection (OpenCV contours on device images)
- [ ] OCR integration (read numbers from detected circles)
- [ ] Position mapping output (generate/cache detected positions)
- [ ] Detection preview command (visual debug output)

### Phase 3: Rendering
- [ ] A4 landscape canvas setup
- [ ] Device image scaling and placement (two-up layout)
- [ ] Label rendering with background boxes
- [ ] Text placement with basic collision avoidance
- [ ] Title and aircraft name + seat/role header
- [ ] Per-seat output file naming

### Phase 4: Integration & Polish
- [ ] Full pipeline: config → parse → detect → render → output
- [ ] CLI commands (render, list-aircraft, detect-buttons, validate)
- [ ] Abbreviation logic for long binding names
- [ ] Modifier notation support
- [ ] Error handling and helpful user messages

### Phase 5: Nice-to-Have (Future)
- [ ] Axis binding labels
- [ ] Multiple page support if bindings overflow
- [ ] Dark/light theme options
- [ ] Community device image/mapping repository
- [ ] Batch export (all aircraft at once)
- [ ] Custom label colors per binding category (weapons, navigation, systems, etc.)

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Python + Pillow | Cross-platform, rich ecosystem, easy image manipulation |
| OCR for button detection | All (x, y) positions determined automatically from the image — user never manually specifies coordinates; just numbers their image with circles |
| YAML config | Human-readable, easy to edit, widely supported |
| Per-device mapping file | Handles Linux/Windows button ID differences cleanly |
| A4 landscape with two devices | Fits stick + throttle/collective on one printable sheet |
| Labels near buttons (not legend table) | More intuitive — see the binding right where the button is |
| Auto-detect multi-seat aircraft | No manual configuration needed — tool discovers seats from DCS directory structure and generates separate images per seat |

---

## Open Considerations

- **DCS device naming**: DCS uses internal device names that may differ from marketing names. The mapping file `device_name` field will need to match what DCS uses in its config paths. The `list-aircraft` command should help users discover these.
- **Hat switches**: Hats have multiple directions (up/down/left/right/press). Each direction may need its own label position — could use small directional offsets from the hat center circle.
- **Multi-page**: If a device has many bindings and labels become too crowded on A4, consider overflow to a second page or scaling adjustments.
- **Caching OCR results**: Circle detection + OCR can be cached per image (by hash) to avoid re-running on every render.
- **Seat discovery heuristics**: The DCS directory structure for multi-seat aircraft may vary across modules. The parser should handle known patterns (e.g., subdirectories named by role) and gracefully fall back to treating unrecognized structures as single-seat.
