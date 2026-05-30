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

### Key Principle: Image Detection is a One-Time Operation

**Image detection (circle finding + OCR) runs only once per device image.** The detected button positions are cached persistently to a file. Subsequent runs of the tool (e.g., re-rendering after changing aircraft bindings) load positions from the cache and skip detection entirely. Detection only re-runs if:

- The device image file has changed (detected via SHA256 hash comparison)
- The user explicitly requests re-detection (e.g., `--force-detect` flag)
- No cache file exists yet for that image

This means the normal workflow is:
1. **First run (or after image change)**: Detection runs → positions cached → render executes
2. **All subsequent runs**: Cached positions loaded instantly → render executes (fast)

**Important:** Only image detection results are cached. DCS binding data (Lua files) is **always read fresh on every render** — never cached. This ensures the output always reflects the user's current binding configuration without needing manual cache invalidation.

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
│                  │     │ (ONE-TIME only,  │  │           │
│                  │     │  results cached) │  │           │
└─────────────────┘     └──────────────────┘  │           │
                                               ▼           │
                              ┌───────────────────────┐    │
                              │  Position Cache File  │    │
                              │  (.yaml per image)    │    │
                              └───────────┬───────────┘    │
                                          │                │
                                          ▼                ▼
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

#### 1.1 Interactive First-Run Setup (Guided Wizard)

If no config file exists when the user runs a command, the tool launches an **interactive setup wizard** that prompts the user through initial configuration:

```
$ dcs-bindings render

  No configuration found. Let's set things up!

  ─── DCS Paths ───────────────────────────────────────────────

  DCS install directory
  (where DCS World is installed, e.g. the folder containing 'bin'):
  > /home/user/Games/DCS World

  ✓ Found DCS installation at /home/user/Games/DCS World

  DCS saved games directory
  (where your user config/bindings are stored):
  > /home/user/.local/share/DCS/Saved Games

  ✓ Found saved games directory

  ─── Marker Colour ───────────────────────────────────────────

  What colour did you use to fill the numbered circles on your device images?

    1. Green   (#00FF00) — recommended default
    2. Magenta (#FF00FF)
    3. Cyan    (#00FFFF)
    4. Custom hex colour

  Select (1-4):
  > 1

  ✓ Marker colour set to: green

  ─── Device Images ───────────────────────────────────────────

  Provide paths to your annotated device images:

  Left device image (e.g. stick):
  > images/winwing-f16ex-stick.png

  Right device image (e.g. throttle/collective):
  > images/winwing-f18-throttle.png

  ─── Button Mappings ─────────────────────────────────────────

  Left device mapping file:
  > mappings/winwing-orion2-f16ex-stick.yaml

  Right device mapping file:
  > mappings/winwing-orion2-f18-throttle.yaml

  ─── Configuration Saved ─────────────────────────────────────

  ✓ Configuration saved to config.yaml
  ✓ Run 'dcs-bindings render' to generate binding images.
```

**Wizard behavior:**
- Triggered automatically when no `config.yaml` (or `--config` target) exists
- Can also be invoked explicitly via `dcs-bindings init`
- Validates paths as the user enters them (confirms DCS install found, saved games exist)
- Pre-populates device mappings if matching bundled YAML files are found
- Saves result as `config.yaml` in the working directory
- Does NOT include aircraft selection — that is prompted every time on render (see 1.2)

#### 1.2 Aircraft Selection (Prompted Every Run)

Each time the user runs `dcs-bindings render` (without the `--aircraft` flag), the tool scans for installed aircraft and prompts the user to choose which to render:

```
$ dcs-bindings render

  Scanning for aircraft with joystick bindings...

  Found 8 aircraft:

     1.  A-10C_2           (1 seat)
     2.  AH-64D_BLK_II    (2 seats: Pilot, CPG)
     3.  F-14B             (2 seats: Pilot, RIO)
     4.  F-16C_50          (1 seat)
     5.  FA-18C_hornet     (1 seat)
     6.  Ka-50_3           (1 seat)
     7.  Mi-24P            (2 seats: Pilot, Operator)
     8.  UH-1H             (2 seats: Pilot, Gunner)

  Select aircraft (comma-separated numbers, or 'all'):
  > 4

  Rendering F-16C_50...
  ✓ Saved: output/F-16C_50.png

  Done! 1 image generated.
```

**Selection behavior:**
- Aircraft selection is **prompted interactively on every run** — not stored in config
- Allows comma-separated numbers (e.g., `3,4,6`) or `all`
- Can be bypassed entirely with the `--aircraft` CLI flag for scripting/automation
- Scans `<saved_games_dir>/Config/Input/` for aircraft with joystick bindings
- Filters to aircraft that actually have binding files present
- Shows multi-seat info so the user knows which aircraft will generate multiple images
- This keeps the workflow fresh — no stale selections in config to maintain

#### 1.3 Config File Format

**User config file** (YAML) — generated by the wizard or created manually.
Aircraft selection is NOT stored here — it is prompted interactively each run.

**Complete config example:**

```yaml
# ─── DCS Paths ───────────────────────────────────────────────
dcs:
  install_dir: "/home/user/Games/DCS World"
  saved_games_dir: "/home/user/.local/share/DCS/Saved Games"

# ─── Device Configuration ────────────────────────────────────
devices:
  - name: "WinWing Orion 2 EX (F-16EX Stick)"
    image: "images/winwing-f16ex-stick.png"
    button_mapping: "mappings/winwing-orion2-f16ex-stick.yaml"
    position: left  # placement on the A4 page

  - name: "WinWing Orion 2 (F-18 Throttle)"
    image: "images/winwing-f18-throttle.png"
    button_mapping: "mappings/winwing-orion2-f18-throttle.yaml"
    position: right

# ─── Detection Settings ──────────────────────────────────────
detection:
  marker_colour: green          # preset: green, magenta, cyan — or hex: "#RRGGBB"
  hue_tolerance: 15             # ± degrees around target hue in HSV space
  saturation_min: 100           # minimum saturation (0-255) to count as coloured
  value_min: 100                # minimum brightness (0-255)
  min_marker_area: 300          # px² — minimum contour area to consider
  ocr_confidence_threshold: 60  # Tesseract confidence minimum (0-100)

# ─── Rendering Settings ──────────────────────────────────────
rendering:
  dpi: 300                     # output resolution (300 recommended for print)
  background: white            # white | dark | transparent
  font_family: DejaVu Sans    # font family (bundled or system-installed TTF)
  font_size: 9                 # pt — single fixed size for ALL labels
  title_font_size: 24          # pt — for aircraft/seat title heading
  label_opacity: 0.85          # background box opacity (0.0-1.0)
  label_max_width: 200         # px max label width before abbreviating
  leader_line_threshold: 50    # px displacement before leader line is drawn
  margin: 40                   # px margin around device images
  device_spacing: 20           # px gap between left and right device images

# ─── Output Settings ─────────────────────────────────────────
output:
  format: png
  page_size: A4
  orientation: landscape
  output_dir: "output/"        # where generated images are saved
```

### 2. DCS Lua Config Parser

- Parse DCS input binding files located at:
  `<saved_games_dir>/Config/Input/<aircraft>/joystick/<device_name> {GUID}.diff.lua`
- Files are Lua tables (not full Lua scripts) — use a lightweight Lua table parser
- Extract: button/hat/axis assignments, binding display names, modifier keys
- Handle user-overridden profiles (`.diff.lua` files containing `keyDiffs` with `added`/`removed` entries)

**Multi-seat aircraft detection:**

Some aircraft have multiple crew positions with independent binding sets. DCS organizes these as **separate top-level directories** with seat/role suffixes. Examples:

| Aircraft | Seats |
|----------|-------|
| AH-64D Apache | Pilot, CPG (Co-Pilot/Gunner) |
| F-14 Tomcat | Pilot, RIO (Radar Intercept Officer) |
| Mi-24P Hind | Pilot, Operator |
| SA342 Gazelle | Pilot, Gunner |
| UH-1H Huey | Pilot, Gunner |

The parser must:
1. **Detect seat/role directories** by recognising known naming patterns in top-level directory names (e.g., `AH-64D_BLK_II_PLT`, `Mi-24P_pilot`, `F-14B-RIO`)
2. **Group related directories** into a single aircraft profile with multiple seats
3. **Parse bindings per seat** — each seat produces its own independent binding set
4. **Generate separate output images per seat** — named clearly (e.g., `AH-64D_BLK_II_Pilot.png`, `AH-64D_BLK_II_CPG.png`)

Seat discovery uses a known-patterns dictionary mapping base aircraft names to their seat suffixes. This is a pragmatic choice given the inconsistent naming conventions DCS uses across modules (e.g., `_PLT` vs `_pilot` vs `-Pilot`). New multi-seat modules require adding an entry to the patterns dictionary. Single-seat aircraft simply produce one image as normal.

**Candidate libraries:**
- `lupa` (Lua interpreter in Python)
- `slpp` (Simple Lua Preprocessor for Python — parses Lua tables to Python dicts)
- Custom regex-based parser as fallback

### 3. Device Image Circle Detection & OCR (Critical Component)

This is the core mechanism that eliminates manual coordinate entry. The tool must reliably detect numbered circles in device images and extract both their position and the number they contain.

**Key design: colour-filled markers on greyscale images.**

Since device template images are primarily black/white/greyscale, markers use a **solid highlight colour fill** (with black number text inside). This makes detection trivial — simply threshold for the marker colour in HSV colour space, and nothing else in the greyscale image will match.

#### 3.0 Marker Specification

**Marker format:** Circle filled with a configurable highlight colour, containing a black number.

```
    ┌───────────┐
    │  ●●●●●●●  │  ← solid colour fill (e.g., bright green)
    │  ●● 7 ●●  │  ← black digit(s) centered inside
    │  ●●●●●●●  │
    └───────────┘
```

**Why colour fill (not coloured digits):**
- Large colour area = reliable detection via HSV thresholding
- Black text on colour background = strong contrast for OCR
- Works even with small circles (fill area always larger than digit strokes)
- Simple for users to create (paint bucket tool on the circle)
- Near-zero false positives on greyscale device images

**Predefined colour presets:**

| Preset Name | Hex | HSV Hue Range | Best For |
|-------------|-----|---------------|----------|
| `green` | `#00FF00` | H: 35-85 | Default — never appears on hardware photos |
| `magenta` | `#FF00FF` | H: 140-170 | Alternative if image has green elements |
| `cyan` | `#00FFFF` | H: 85-100 | Another alternative |

**Custom colour:** User can also specify any hex colour value (e.g., `#FF8800` for orange). The tool will compute the appropriate HSV hue range for thresholding automatically based on the provided hex value.

**Configuration in config.yaml:**

```yaml
detection:
  marker_colour: green          # preset name OR hex value (e.g., "#FF00FF")
  # Available presets: green, magenta, cyan
  # Or specify any custom hex: "#RRGGBB"
```

**Wizard prompt (during `dcs-bindings init`):**

```
─── Marker Colour ─────────────────────────────────────────

What colour did you use to fill the numbered circles on your device images?

  1. Green  (#00FF00) — recommended default
  2. Magenta (#FF00FF)
  3. Cyan   (#00FFFF)
  4. Custom hex colour

Select (1-4):
> 1

✓ Marker colour set to: green
```

#### 3.1 Detection Pipeline (Detailed)

```
Input Image
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Step 1: Colour Isolation                             │
│  - Convert image to HSV colour space                 │
│  - Threshold for the configured marker colour:       │
│    • Compute target hue ± tolerance from config      │
│    • Apply saturation minimum (reject desaturated)   │
│    • Apply value/brightness minimum                  │
│  - Result: binary mask where ONLY markers are white  │
│  - This single step eliminates nearly all false      │
│    positives — nothing else on a greyscale image     │
│    will have saturated colour                        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: Blob Detection & Filtering                   │
│  - Find contours on the colour mask                  │
│  - Pre-filter noise (minimum area threshold)         │
│  - Merge nearby contours (handles numbers that       │
│    split the fill into separate blobs)               │
│  - Filter by:                                        │
│    • Minimum area (reject tiny noise/artifacts)      │
│    • Aspect ratio (width/height ≈ 1.0)              │
│    • Green density (≥50% of bounding box is green)   │
│  - Compute center point and radius from bounding box │
│  - Output: list of marker centers + radii            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: Number Extraction (OCR)                      │
│  - Crop each detected marker region                  │
│  - Preprocess ROI for OCR:                           │
│    • Strip marker colour (set green pixels to white) │
│    • Apply circle mask to remove background          │
│    • Scale up (6x minimum) for OCR accuracy          │
│    • Threshold to clean binary image                 │
│  - Run Tesseract with digit-only config:             │
│    --psm 8 (single word) -c tessedit_char_whitelist= │
│    0123456789                                        │
│  - If result has too many digits for circle size,    │
│    retry with tighter mask to remove edge artifacts  │
│  - Validate: reject non-numeric / low confidence     │
│  - Output: {number: (center_x, center_y)} mapping    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: Persistent Cache (CRITICAL)                  │
│  - Save results to a YAML/JSON file per image:       │
│    e.g., .cache/winwing-stick_positions.yaml         │
│  - Cache file contains:                              │
│    • Source image SHA256 hash                        │
│    • Detected positions: {number: (x, y)}            │
│    • Detection timestamp                             │
│    • Detection parameters used                       │
│    • Marker colour used                              │
│  - On subsequent runs:                               │
│    1. Compute hash of current image                  │
│    2. If hash matches cache → load positions (FAST)  │
│    3. If hash differs → re-run detection pipeline    │
│  - CLI flag: --force-detect to bypass cache          │
│  - Log warnings for:                                 │
│    • Duplicate numbers detected                      │
│    • Expected numbers missing (from mapping file)    │
│    • Low-confidence OCR reads                        │
└─────────────────────────────────────────────────────┘
```

#### 3.2 Handling Edge Cases

| Scenario | Strategy |
|----------|----------|
| Multi-digit numbers (10+) | OCR config allows multi-digit; validate against mapping file expected range |
| Circles partially obscured by device edges | Detect partial contours; use minimum enclosing circle estimation |
| Varying circle sizes in one image | Use relative size filtering (within 2× of median detected size) |
| Image has some colour elements (LEDs, logos) | HSV hue range is narrow enough to avoid most; user can pick a different marker colour |
| Numbers touching circle edge | Add padding when cropping ROI for OCR |
| Blurry or low-res images | Warn user; provide minimum recommended resolution in docs |
| User chose a colour that appears in their image | `detect-buttons --debug` will reveal false positives; user should switch colour in config |

#### 3.3 Detection Tuning & Debug Tools

The `detect-buttons` CLI command provides visual debugging:

```bash
# Run detection and output annotated debug image
dcs-bindings detect-buttons --image images/winwing-stick.png --debug

# Output:
#   images/winwing-stick_detected.png  (annotated with detected circles + numbers)
#   images/winwing-stick_positions.yaml (detected positions for review)
```

The debug image will show:
- Green circles around successfully detected + OCR'd markers
- Red circles around candidates that failed validation
- Yellow circles around low-confidence OCR results
- Number label next to each detection showing what was read

**Tuning parameters** (configurable in config.yaml or CLI flags):
```yaml
detection:
  marker_colour: green          # preset: green, magenta, cyan — or hex: "#RRGGBB"
  hue_tolerance: 15             # ± degrees around target hue in HSV space
  saturation_min: 100           # minimum saturation (0-255) to count as coloured
  value_min: 100                # minimum brightness (0-255)
  min_marker_area: 300          # px² - minimum contour area to consider
  ocr_confidence_threshold: 60  # Tesseract confidence minimum (0-100)
```

#### 3.4 Image Requirements for Users

To ensure reliable detection, user-provided device images should follow these guidelines:

- **Image base**: Greyscale/black-and-white photograph or diagram of the device
- **Marker style**: Circle filled with the configured highlight colour (default: bright green `#00FF00`) containing black number text
- **Marker size**: Minimum ~20px radius at final image resolution; consistent size preferred
- **Colour saturation**: Use a pure, saturated fill colour — avoid muted/pastel shades
- **Spacing**: Markers should not overlap or touch each other
- **Numbers**: Clear, simple digits (sans-serif style works best for OCR)
- **Resolution**: Minimum 150 DPI equivalent; higher is better for OCR accuracy
- **Format**: PNG preferred (lossless); JPEG acceptable if high quality
- **Avoid**: Other saturated-colour elements in the image that match your marker colour

### 4. Button Number Mapping (ID only — no coordinates)

The user never specifies (x, y) positions. All button positions are determined automatically by the image detection pipeline (Component 3). The mapping file's sole purpose is to translate the number found in the image to the corresponding DCS button ID:

```yaml
# mappings/winwing-orion2-f16ex-stick.yaml
device_name: "Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16"
device_name_alt: "WINWING Orion Joystick Base 2 + JGRIP-F16"

# Maps the NUMBER visible in the image circle → DCS button ID
# The (x, y) position is auto-detected from the image — not specified here
mappings:
  1: "JOY_BTN1"
  2: "JOY_BTN2"
  3: "JOY_BTN3"
  # ... etc
```

**Device-to-DCS matching:** When the tool searches for bindings, it scans the **filenames** in `Config/Input/<aircraft>/joystick/` and matches against the `device_name` (and `device_name_alt`) field using **starts-with matching**. DCS device filenames include a GUID suffix (e.g., `Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16 {9E573ED2-...}.diff.lua`), so the tool matches if the filename **starts with** the `device_name` string. The `device_name` should use the latest firmware naming convention, with `device_name_alt` as a fallback for older firmware versions. If no match is found for a device, the tool logs a warning and skips that device for that aircraft (the other device will still render with its bindings).

The user maintains one mapping file per device that only defines number-to-ID relationships — the tool handles all spatial/position detection automatically from the image.

### 5. Image Renderer & Label Layout Engine (Critical Component)

The renderer must produce clean, readable output even when buttons are densely packed. This requires a sophisticated label placement algorithm that avoids overlaps and maintains visual clarity.

#### 5.1 Canvas Composition

Uses **Pillow** (PIL) to compose the final output:

**Canvas setup:**
- A4 landscape at the configured DPI (default 300 DPI = 3508 × 2480 px)
- White or dark background (configurable)
- Left half: device 1 image (scaled to fit with margin)
- Right half: device 2 image (scaled to fit with margin)
- Title bar at top: aircraft name + seat/role (e.g., "AH-64D Apache — Pilot")
- Margins: configurable padding around each device image to leave room for labels that extend beyond the device boundary

**Coordinate scaling:**
- Button positions detected from the original device image must be scaled proportionally when the image is resized to fit the A4 canvas
- Maintain aspect ratio of device images
- Store the scale factor and offset for accurate position mapping

#### 5.2 Label Layout Algorithm (Anti-Collision)

This is the most critical rendering logic. Labels must be placed near their associated button without overlapping other labels or obscuring important parts of the device image.

**Strategy: Force-directed label placement with priority zones**

```
For each button with a binding:
    1. Calculate ideal label position (preferred offset from button center)
    2. Check for collisions with existing placed labels
    3. If collision: try alternative positions in priority order
    4. If all positions collide: use force-directed nudging
    5. Draw leader line from label to button if displaced far
```

**Step-by-step algorithm:**

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Initial Placement                                   │
│                                                              │
│  For each button (sorted by position, top-to-bottom,         │
│  left-to-right):                                             │
│    - Calculate text bounding box at preferred font size      │
│    - Try placement at 8 candidate positions around button:   │
│      Priority order:                                         │
│        1. Right of button (most readable for LTR text)       │
│        2. Left of button                                     │
│        3. Above button                                       │
│        4. Below button                                       │
│        5. Upper-right diagonal                               │
│        6. Lower-right diagonal                               │
│        7. Upper-left diagonal                                │
│        8. Lower-left diagonal                                │
│    - Place at first position with no collision               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Collision Resolution                                │
│                                                              │
│  For any label that couldn't be placed without collision:    │
│    - Increase displacement distance from button (extend      │
│      outward in same preferred direction)                    │
│    - Re-check collisions at extended position                │
│    - If still colliding after max extension:                 │
│      → Apply more aggressive text abbreviation               │
│      → If still failing: mark for force-directed pass        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Force-Directed Nudging (remaining conflicts)        │
│                                                              │
│  Treat overlapping labels as particles with repulsion:       │
│    - Each label exerts a repulsive force on overlapping      │
│      neighbors                                               │
│    - Each label has an attractive force toward its button    │
│    - Iterate until equilibrium (max N iterations)            │
│    - Constraint: labels must stay within canvas bounds       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Leader Lines                                        │
│                                                              │
│  For labels displaced more than threshold distance from      │
│  their button:                                               │
│    - Draw a thin leader line from label edge to button       │
│      circle                                                  │
│    - Line style: thin, semi-transparent, with a small dot    │
│      or arrow at the button end                              │
│    - Avoid crossing other labels where possible              │
└─────────────────────────────────────────────────────────────┘
```

#### 5.3 Label Rendering Details

**Label box anatomy:**
```
┌─────────────────────────┐
│  Weapon Release  [M]    │  ← text + optional modifier indicator
└─────────────────────────┘
  ↑ semi-transparent background (e.g., white @ 85% opacity)
  ↑ thin border (1px, dark gray)
  ↑ padding: 3px horizontal, 2px vertical
```

**Font rules (strict single size):**
- **All labels use exactly the same font family and size** — no per-label shrinking
- Font family and size are configurable in `config.yaml` with sensible defaults
- Default font: `DejaVu Sans` (bundled, open-source, good readability at small sizes)
- Default size: `9pt` (scaled to the configured output DPI)
- If labels overflow available space, the tool handles it via abbreviation and layout displacement — never by changing font size per-label
- This ensures a clean, uniform appearance across the entire output image

**Text content rules:**
1. Use full DCS binding name if it fits within max label width
2. If too long, apply abbreviation rules:
   - Remove common suffixes ("Button", "Switch", "Btn")
   - Abbreviate known terms ("Countermeasures" → "CM", "Communication" → "Comm")
   - Truncate with ellipsis as last resort ("Counter..." )
3. Max label width: configurable, default ~40% of device image half-width

**Color and contrast:**
- Label background: white with 85% opacity (allows device image to show through slightly)
- Text color: black (or dark gray)
- Border: 1px medium gray
- Leader lines: medium gray, 1px, slight transparency
- Modifier indicators: small colored badge or bracketed text (e.g., `[S]` for shift modifier)

#### 5.4 Dense Layout Handling

For devices with many closely-spaced buttons (e.g., throttle base panels):

1. **Grouping**: If multiple buttons are within a cluster threshold distance, try to place labels on the same side of the cluster (reducing visual chaos)
2. **Stacking**: Labels for a tight group can be stacked vertically with leader lines fanning out to their respective buttons
3. **Overflow detection**: If more than N% of labels required force-directed nudging, log a warning suggesting the user increase image resolution or spread out markers
4. **Abbreviation escalation**: If layout is too dense, apply progressively more aggressive abbreviation to all labels (never change font size — keep it uniform)

#### 5.5 Rendering Configuration

```yaml
rendering:
  dpi: 300                     # output resolution (300 recommended for print)
  background: white            # white | dark | transparent
  font_family: DejaVu Sans    # font family (must be a bundled or system-installed TTF)
  font_size: 9                 # pt — single fixed size for ALL labels (default: 9)
  title_font_size: 24          # pt — for aircraft/seat title heading
  label_opacity: 0.85          # background box opacity (0.0-1.0)
  label_max_width: 200         # px max label width before abbreviating
  leader_line_threshold: 50    # px displacement before leader line is drawn
  margin: 40                   # px margin around device images
  device_spacing: 20           # px gap between left and right device images
```

**Bundled fonts:**
- `DejaVu Sans` (default) — clean sans-serif, excellent small-size readability
- `DejaVu Sans Mono` — monospace alternative if user prefers fixed-width labels

Users can also specify any TTF font installed on their system or placed in the project `fonts/` directory.

#### 5.6 Original Circles Preserved

- The numbered circle markers in the source image remain visible in the output
- Labels are placed adjacent to (not on top of) the circles
- This allows the user to cross-reference the image number with the mapping file if needed

**Modifier support:**
- If a binding uses a modifier, append modifier indicator (e.g., "[MOD]" prefix or color coding)
- Optionally render a small legend explaining modifier notation at the bottom of the page

---

## CLI Interface

```bash
# ─── First-time setup / interactive wizard ───
# Run the guided setup wizard (creates config.yaml interactively)
dcs-bindings init

# ─── Rendering ───
# Generate binding images — prompts user to select aircraft interactively
# If no config exists, triggers the interactive setup wizard first
dcs-bindings render --config config.yaml

# Skip the interactive prompt — generate for a specific aircraft directly
dcs-bindings render --config config.yaml --aircraft "F-16C_50"

# Generate for a specific aircraft and seat only
dcs-bindings render --config config.yaml --aircraft "AH-64D_BLK_II" --seat "Pilot"

# Force re-detection of button positions from images (ignores cache)
dcs-bindings render --config config.yaml --force-detect

# Override output directory (without editing config)
dcs-bindings render --config config.yaml --output-dir /tmp/bindings/

# Preview what would be generated without actually rendering
dcs-bindings render --config config.yaml --dry-run

# ─── Discovery & debugging ───
# List detected aircraft profiles (shows seats where applicable)
dcs-bindings list-aircraft --config config.yaml

# Run detection on a device image and save to cache (for initial setup / debugging)
dcs-bindings detect-buttons --image images/winwing-orion2-stick.png

# Run detection with debug overlay image output
dcs-bindings detect-buttons --image images/winwing-orion2-stick.png --debug

# Validate configuration and mappings
dcs-bindings validate --config config.yaml

# ─── Verbosity ───
# Suppress all output except errors
dcs-bindings render --config config.yaml --quiet

# Show detailed debug information (detection params, layout decisions, etc.)
dcs-bindings render --config config.yaml --verbose
```

**Global flags (available on all commands):**

| Flag | Short | Description |
|------|-------|-------------|
| `--config <path>` | `-c` | Path to config file (default: `config.yaml` in working directory) |
| `--quiet` | `-q` | Suppress all output except errors |
| `--verbose` | `-v` | Show detailed debug/diagnostic output |

**Render-specific flags:**

| Flag | Description |
|------|-------------|
| `--aircraft <name>` | Skip interactive prompt — render a specific aircraft directly |
| `--seat <name>` | Render a specific seat only (requires `--aircraft`) |
| `--force-detect` | Re-run image detection ignoring the cache |
| `--output-dir <path>` | Override output directory from config |
| `--dry-run` | Show what would be generated without rendering (still prompts for aircraft selection unless `--aircraft` is used) |

**`--dry-run` example output:**
```
$ dcs-bindings render --config config.yaml --dry-run

  Dry run — no images will be generated.

  Would render 3 images:

    1. output/FA-18C_hornet.png
       - 26 bindings matched to WinWing Orion 2 EX (F-16EX Stick)
       - 18 bindings matched to WinWing Orion 2 (F-18 Throttle)
       - 7 unbound buttons

    2. output/AH-64D_BLK_II_Pilot.png
       - 19 bindings matched to WinWing Orion 2 EX (F-16EX Stick)
       - 22 bindings matched to WinWing Orion 2 (F-18 Throttle)
       - 3 unbound buttons

    3. output/AH-64D_BLK_II_CPG.png
       - 14 bindings matched to WinWing Orion 2 EX (F-16EX Stick)
       - 20 bindings matched to WinWing Orion 2 (F-18 Throttle)
       - 5 unbound buttons

  ⚠ Warning: 2 buttons in mapping have no corresponding DCS binding ID
    (winwing-orion2-f16ex-stick.yaml: image #37, #39)
```

**First-run behavior:** If the user runs `dcs-bindings render` without an existing config file, the tool automatically launches the interactive setup wizard (equivalent to `dcs-bindings init`). This ensures new users are guided through configuration without needing to read documentation first.

**Aircraft selection:** Every `render` invocation (without `--aircraft`) presents the user with a numbered list of installed aircraft to choose from. This is intentionally not stored in config — the user picks fresh each time.

**Performance note:** The `render` command is designed to be fast on repeat runs. Image detection (the slow OpenCV + OCR step) only runs once per device image and is cached. Changing DCS bindings (new aircraft, updated controls) triggers only the fast re-render path — no image re-analysis needed.

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
│       ├── cli.py              # Click CLI entry point
│       ├── config.py           # Config loading & validation
│       ├── setup_wizard.py     # Interactive first-run setup wizard
│       ├── aircraft_scanner.py # Scan DCS install for available aircraft/seats
│       ├── lua_parser.py       # DCS Lua table parser
│       ├── detector.py         # Blob detection (HSV colour isolation, contour merging)
│       ├── ocr.py              # OCR number reading (Tesseract integration)
│       ├── detection_cache.py  # Cache detected positions by image hash
│       ├── mapping.py          # Button number mapping logic
│       ├── layout.py           # Label placement algorithm (collision avoidance, force-directed)
│       ├── renderer.py         # Pillow-based image composition & drawing
│       ├── abbreviations.py    # Text abbreviation rules for long binding names
│       └── models.py           # Data models (Binding, Device, LabelBox, etc.)
│
├── images/                     # Annotated device images for detection
│   └── .gitkeep
│
├── resources/                  # Source device images (unannotated)
│   └── .gitkeep
│
├── mappings/                   # Button mapping files
│   ├── winwing-orion2-f16ex-stick.yaml
│   ├── winwing-orion2-f18-throttle.yaml
│   └── virpil-rotor-tcs-dual-sf.yaml
│
├── docs/                       # Documentation
│   ├── plan.md
│   └── linux-input-devices.md
│
├── output/                     # Generated images (gitignored)
│   └── .gitkeep
│
├── .cache/                     # Detected button positions cache (gitignored)
│   └── .gitkeep
│
└── tests/                      # Tests (TODO)
    └── .gitkeep
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `Pillow` | Image rendering, composition, and text drawing |
| `opencv-python` | Circle/contour detection, image preprocessing |
| `numpy` | Array operations for OpenCV image processing |
| `pytesseract` | OCR to read numbers inside detected circles |
| `slpp` or `lupa` | Lua table parsing for DCS config files |
| `PyYAML` | Configuration file parsing |
| `click` | CLI framework |

**System dependencies:**
- Tesseract OCR engine (available via package manager on all platforms)
  - Linux: `sudo dnf install tesseract` (Fedora/Nobara) or `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: installer from https://github.com/UB-Mannheim/tesseract/wiki

---

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Project scaffolding (pyproject.toml, package structure)
- [ ] Configuration system (YAML loading, path validation)
- [ ] Interactive setup wizard (prompt for paths, validate DCS install)
- [ ] Aircraft scanner (detect installed modules from saved games directory)
- [ ] Interactive aircraft selection prompt (numbered list on every render)
- [ ] DCS Lua config parser (read binding files, extract assignments)
- [ ] Multi-seat detection (auto-discover crew positions per aircraft)

### Phase 2: Image Detection (Critical Path)
- [ ] HSV colour isolation (threshold for configured marker colour)
- [ ] Contour detection on colour mask
- [ ] Circularity, aspect ratio, and minimum area filtering
- [ ] OCR integration with Tesseract (digit-only, single-line mode)
- [ ] Multi-digit number support
- [ ] Confidence scoring and low-confidence warnings
- [ ] Result caching by image hash (SHA256)
- [ ] Detection debug/preview command with annotated output image
- [ ] Configurable detection tuning parameters (marker colour, hue tolerance, etc.)
- [ ] Edge case handling (partial contours, varied sizes, colour bleed)

### Phase 3: Rendering & Label Layout (Critical Path)
- [ ] A4 landscape canvas setup with configurable margins
- [ ] Device image scaling with aspect ratio preservation
- [ ] Coordinate transformation (detected positions → canvas positions)
- [ ] Label text rendering with semi-transparent background boxes
- [ ] 8-position candidate placement algorithm (right, left, above, below, diagonals)
- [ ] Collision detection between label bounding boxes
- [ ] Extended displacement for colliding labels
- [ ] Force-directed nudging for remaining overlaps
- [ ] Leader line rendering for displaced labels
- [ ] Dense cluster detection and grouped label stacking
- [ ] Text abbreviation logic (remove suffixes, known abbreviations, truncation)
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
| OCR for button detection | All (x, y) positions determined automatically from the image — user never manually specifies coordinates; just adds colour-filled numbered circles to their image |
| Colour-filled markers on greyscale images | Using a configurable highlight colour (default: green) makes detection trivially reliable via HSV thresholding — near-zero false positives since greyscale images have no saturated colour |
| YAML config | Human-readable, easy to edit, widely supported |
| Per-device mapping file | Handles Linux/Windows button ID differences cleanly |
| A4 landscape with two devices | Fits stick + throttle/collective on one printable sheet |
| Labels near buttons (not legend table) | More intuitive — see the binding right where the button is |
| Auto-detect multi-seat aircraft | No manual configuration needed — tool discovers seats from DCS directory structure and generates separate images per seat |
| One-time image detection with persistent cache | Image OCR/detection is slow — runs only once per image, results cached to disk. Subsequent renders are fast (just reads cache + DCS bindings). Re-detection only on image change or explicit `--force-detect` |
| Interactive first-run wizard | Zero-config start for new users — guided prompts for paths and device setup. No documentation reading required to get started |
| Aircraft selection prompted every run | User picks aircraft fresh each time from a numbered list — no stale selections in config to maintain. Can bypass with `--aircraft` flag for automation |

---

## Open Considerations

- **Multi-page**: If a device has many bindings and labels become too crowded on A4, consider overflow to a second page or scaling adjustments.
- **Seat discovery heuristics**: DCS uses separate top-level directories with inconsistent naming conventions for multi-seat aircraft (e.g., `_PLT`, `_pilot`, `-Pilot`). The tool uses a known-patterns dictionary to group these. Unrecognised structures are treated as single-seat.

## Decided Design Details

These were previously open considerations and have now been resolved:

- **DCS device naming & matching**: The mapping file `device_name` field is matched against DCS **filenames** in `<aircraft>/joystick/` using **starts-with matching** (ignoring GUID suffixes). Both `device_name` and `device_name_alt` are tried. If no match is found, the device is skipped with a warning.
- **Hat switches**: Each hat direction gets its **own numbered circle** on the device image. A 4-way hat = 4 circles (e.g., numbered 6, 7, 8, 9 for up/down/left/right). A 5-way hat (4-way + push) = 5 circles. The mapping file maps each to its own DCS button ID (`JOY_BTN_POV1_U`, `JOY_BTN_POV1_D`, etc.). This keeps the system simple and consistent — every bindable input gets one marker.
- **Binding data freshness**: DCS Lua binding files are always read fresh on every render — never cached. Only image detection (positions) is cached.
