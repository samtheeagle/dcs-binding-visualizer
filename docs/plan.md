# DCS Binding Visualizer — Architecture & Plan

## Overview

A CLI tool that generates visual reference cards (SVG) for DCS World joystick bindings. It takes annotated device images (with numbered green circles marking button positions), detects those markers via computer vision + OCR, reads DCS Lua binding files, and renders labelled SVG diagrams showing what each button does for a given aircraft.

The primary output is per-device A5 portrait SVGs (editable in Inkscape), with an optional combined A4 landscape SVG (via `--combined` flag) when multiple devices are configured.

## Architecture

```
src/dcs_bindings/
├── __init__.py           # Package metadata (__version__)
├── cli.py                # Click CLI commands and orchestration
├── config.py             # YAML config loading, dataclass definitions
├── models.py             # Shared data models (dataclasses)
├── detector.py           # HSV colour isolation + contour detection
├── ocr.py                # Tesseract OCR for reading marker numbers
├── detection_cache.py    # SHA256-keyed YAML cache for marker positions
├── mapping.py            # Load device YAML mappings, resolve positions
├── lua_parser.py         # Parse DCS .diff.lua binding files
├── aircraft_scanner.py   # Scan DCS saved games for aircraft profiles
├── renderer.py           # SVG + PNG rendering with label placement
├── layout.py             # Collision-avoidance label placement algorithm
├── marker_generator.py   # Generate helper PNGs with numbered circles
├── device_probe.py       # Probe connected joystick hardware (Linux/Windows)
├── abbreviations.py      # Text shortening rules for long action names
└── setup_wizard.py       # Interactive first-run config wizard
```

## CLI Commands

Entry point: `dcs-bindings` (defined in pyproject.toml → `dcs_bindings.cli:cli`)

### Global Options
- `--config / -c` — path to config YAML (default: `config.yaml`)
- `--quiet / -q` — suppress non-error output
- `--verbose / -v` — debug output
- `--version`

### `init`
Runs the interactive setup wizard (`setup_wizard.py`). Prompts for DCS paths, marker colour, device images, and mapping files. Writes `config.yaml`.

### `render`
Main command. Generates binding reference SVGs for selected aircraft.

Options: `--aircraft`, `--seat`, `--force-detect`, `--output-dir`, `--dry-run`

Flow:
1. Load config, scan for aircraft profiles
2. Prompt user to select aircraft (or use `--aircraft`)
3. For each configured device: load mapping, detect/cache marker positions, resolve button positions
4. For each selected aircraft+seat: parse DCS Lua bindings, render per-device SVGs via `render_binding_svg()`
5. If `--combined` flag and multiple devices, generate a combined A4 landscape SVG

### `list-aircraft`
Lists detected aircraft profiles with seat information from the DCS saved games directory.

### `detect-buttons`
Runs marker detection + OCR on a single image for debugging/setup. Saves results to cache. Optional `--debug` flag generates an annotated image.

### `detect-groups`
Scans a device image for connected button markers (dark lines between circles) and suggests group definitions (hat, horizontal, vertical) for the mapping file. Uses union-find with max group size 5.

### `generate-markers`
Generates a transparent PNG with numbered circles laid out in a grid, matching the button/group structure from a mapping file. Used as a helper overlay for annotating device photos.

### `generate-mapping`
Generates a skeleton YAML mapping file from detected markers. Applies a button number offset, detects groups via line scanning, and optionally probes hardware for axis info.

Options: `--image`, `--device-name`, `--output`, `--offset`, `--description`, `--probe-device`

### `validate`
Validates the config file (checks paths exist, devices configured).

## Detection Pipeline

### detector.py
1. Load image, convert to HSV
2. Create binary mask isolating the configured marker colour (hue ± tolerance, saturation/value minimums)
3. Morphological open to remove noise
4. Find external contours, filter by area ≥ 100px
5. Merge nearby contours (handles numbers splitting a circle into two blobs)
6. For each merged contour: check area ≥ `min_marker_area`, aspect ratio 0.6–1.6, green density ≥ 50%
7. Return `DetectedMarker` list (positions + radii, number=-1)

Also provides `generate_debug_image()` for annotated output.

### ocr.py
For each detected marker:
1. Extract ROI around the marker (center ± radius + padding)
2. Mask out the marker colour → leaves number as dark pixels on white
3. Apply circular mask to exclude edge artifacts
4. Scale up (6x minimum, targeting 96px height)
5. Threshold to binary, add white border
6. Run Tesseract with `--psm 8` (single word) and digit whitelist
7. Parse confidence from `image_to_data`; fall back to `image_to_string`
8. Retry with tighter mask if result has too many digits for the circle size

Returns markers with numbers and confidence scores; drops failures.

### detection_cache.py
- Cache key: image filename stem → `{stem}_positions.yaml` in `.cache/`
- Validity: SHA256 hash of the image file stored in cache; invalidated if image changes
- Stores: number, x, y, radius, confidence, detection timestamp, marker colour

## Mapping System

### models.py
Core dataclasses:
- `DetectedMarker` — position + radius + OCR result
- `ButtonPosition` — image number + DCS button ID + coordinates
- `Binding` — button_id + action_name + category + modifiers
- `DeviceConfig` — name, image path, mapping path, position (left/right)
- `DeviceMapping` — device_name, mappings (image_num → DCS button ID), axes, groups
- `LabelBox` — positioned label with collision detection (`overlaps()`, `distance_to_button()`)
- `AircraftProfile` — name, seats, seat_dirs (multi-seat support)
- `RenderJob` — aircraft + seat + bindings + output path

### mapping.py
- `load_device_mapping(path)` — loads YAML mapping file into `DeviceMapping`
- `resolve_button_positions(markers, mapping)` — joins detected markers with mapping to produce `ButtonPosition` list (only markers that have a mapping entry)

### Mapping YAML format
```yaml
device_name: "DCS device name"
device_name_alt: ""
description: ""
axes: [{id, description}]
mappings:
  1: "JOY_BTN1"
  2: "JOY_BTN2"
groups:
  - buttons: [1, 2, 3, 4, 5]
    layout: hat
  - buttons: [6, 7]
    layout: vertical
```

## Rendering Pipeline

### renderer.py

Two rendering paths:

#### `render_binding_image()` (PNG — legacy, still present)
Renders a per-device A5 portrait SVG (148.5mm×210mm, viewBox 1754×2480) with the device image scaled and centered on the page. Labels are positioned using collision-aware placement.

#### `render_binding_svg()` (SVG — primary path used by `render` command)
1. Embeds device image as base64 in SVG
2. Builds label data: for each button with a binding, creates a label dict with action text and position
3. Groups buttons using explicit mapping groups (`_group_by_mapping()`) or spatial heuristics (`_group_hat_buttons()`)
4. Collision-aware placement:
   - Button markers registered as initial obstacles
   - Hat/group labels: tries 8 clock positions at configurable radius, scores by collision count + out-of-bounds penalty + background non-white pixel ratio
   - Single labels: same 8-position approach at smaller radius
   - Background sampling via OpenCV greyscale to avoid placing labels over busy image areas
5. Outputs SVG with `<image>` element and `<g id="labels">` containing positioned `<text>` elements

#### `_group_hat_buttons()` (spatial heuristic)
Detects cross patterns (4 buttons in up/down/left/right arrangement) and horizontal rows (3 buttons at same Y). Merges into composite labels with directional arrows (↑↓←→●).

#### `_group_by_mapping()` (explicit groups)
Uses group definitions from the mapping YAML. Supports hat (cross), vertical, and horizontal layouts. Produces composite labels with directional indicators.

#### Combined SVG (`_generate_combined_svg()` in cli.py)
Places individual A5 portrait SVG bodies side by side in an A4 landscape viewBox (3508×2480 at 300 DPI, 297mm×210mm). No rescaling — each A5 panel (1754×2480) occupies half the A4 width, tops aligned.

### layout.py (used by PNG path only)
8-candidate position algorithm with:
1. Orientation-aware candidate ordering (prefers placing labels away from group center)
2. Extended displacement at 1.5x–3x distance
3. Force-directed nudging as fallback (repulsive forces from overlapping labels, attractive force toward button)
4. Leader line threshold detection

## Device Probing (device_probe.py)

Detects connected joystick hardware:
- **Linux**: reads `/dev/input/js*` via ioctl (JSIOCGAXES, JSIOCGBUTTONS, JSIOCGNAME, JSIOCGAXMAP), reads vendor/product from sysfs
- **Windows**: uses `winmm.dll` joyGetDevCaps API

Returns `DeviceInfo` with name, path, button count, axis count, axis map, vendor/product IDs. Used by `generate-mapping --probe-device` to populate axes in mapping files.

## Marker Generation (marker_generator.py)

Generates transparent PNGs with numbered circles for manual placement on device photos:
- Reads a mapping file to determine which buttons and groups to render
- Lays out items in rows (max 1200px wide)
- Renders groups with connecting lines:
  - **hat**: cross arrangement (center + 4 directions)
  - **horizontal**: row with connecting lines
  - **vertical**: column with connecting lines
  - **rotary**: 3 positions in arc + push button below
- Single buttons rendered as standalone circles

## Configuration (config.py)

Dataclass-based config with YAML serialisation:
- `AppConfig` — top-level: DCS paths, devices list, detection/rendering/output sub-configs
- `DetectionConfig` — marker colour (preset name or hex), HSV tolerances, area threshold, OCR confidence
- `RenderingConfig` — DPI, fonts, label sizing, margins, spacing; computed properties for A4 canvas dimensions
- `OutputConfig` — format, page size, orientation, output directory
- `COLOUR_PRESETS` — green/magenta/cyan name-to-hex mapping

`load_config()` merges YAML data with defaults. `save_config()` serialises back to YAML.

## Supporting Modules

### lua_parser.py
Parses DCS `.diff.lua` binding files. Two strategies:
1. **slpp library** — decodes Lua table syntax into Python dicts, extracts `keyDiffs[id].added[n].key` entries matching `JOY_BTN*`
2. **Regex fallback** — line-by-line brace-depth tracking, extracts `["name"]` and `["key"]` pairs

Handles device name matching (starts-with, case-insensitive) against filenames that include GUIDs.

### aircraft_scanner.py
Scans `<saved_games>/Config/Input/` for directories containing `joystick/*.lua` files. Groups multi-seat aircraft (AH-64D, F-14B, Mi-24P) using known suffix patterns. Provides interactive selection prompt.

### abbreviations.py
Three-level text shortening:
1. Remove common suffixes ("Button", "Switch", "Toggle", etc.)
2. Apply known abbreviations (Countermeasures→CM, Navigation→Nav, etc.)
3. Truncate with ellipsis

Currently imported by `renderer.py` but the `abbreviate()` function is not called in the SVG rendering path.

### setup_wizard.py
Interactive Click-based wizard that prompts for DCS paths, marker colour, device images, and mapping files. Saves config via `save_config()`.

## Key Data Flows

### Full Render Flow
```
config.yaml → load_config() → AppConfig
                                  │
                                  ├─→ scan_aircraft() → [AircraftProfile]
                                  │                          │
                                  │                    prompt_aircraft_selection()
                                  │                          │
                                  ├─→ For each device:       │
                                  │     load_device_mapping()│
                                  │     detect_markers()     │
                                  │     read_marker_numbers()│
                                  │     resolve_button_positions()
                                  │           │              │
                                  │           ▼              ▼
                                  │     [ButtonPosition]  [AircraftProfile]
                                  │           │              │
                                  │           └──────┬───────┘
                                  │                  ▼
                                  │     parse_bindings_for_aircraft()
                                  │           │
                                  │           ▼
                                  │     {button_id: Binding}
                                  │           │
                                  ▼           ▼
                              render_binding_svg()
                                  │
                                  ├─→ _group_by_mapping() or _group_hat_buttons()
                                  ├─→ Collision-aware placement (8 positions × scoring)
                                  └─→ SVG output with embedded image + text labels
```

### Marker Detection Flow
```
device image (PNG) → detect_markers() → [DetectedMarker (no numbers)]
                                              │
                                              ▼
                                    read_marker_numbers() → [DetectedMarker (with numbers)]
                                              │
                                              ▼
                                    save_markers_to_cache() → .cache/{stem}_positions.yaml
```

### Mapping Generation Flow
```
device image → get_cached_markers() or detect+OCR
                    │
                    ▼
              marker positions + offset → mapping YAML skeleton
                    │
                    ├─→ Line scanning between markers → group detection
                    └─→ (optional) device_probe → axes info
```

## Code Quality Notes

### Redundancies
1. **Duplicate group detection logic** — `check_line()` + union-find appears identically in both `detect-groups` and `generate-mapping` CLI commands (~50 lines each). Should be extracted to a shared function.
2. **`_group_hat_buttons()` vs `_group_by_mapping()`** — both in renderer.py, both produce composite labels. The spatial heuristic version is also used as fallback when no explicit groups exist. The logic overlaps significantly.
3. **`_hex_to_hsv_hue()` in detector.py** and **`_get_target_hue()` in ocr.py** — identical implementations (hex → BGR pixel → cvtColor → hue value).
4. **`render_binding_image()` (PNG path)** — still present and importable but the `render` command exclusively uses `render_binding_svg()`. The PNG renderer, `_render_device()`, `_draw_label()`, `_draw_leader_line()`, `_draw_title()`, and `_load_font()` are dead code in the current CLI flow.
5. **`abbreviate()` in abbreviations.py** — imported by renderer.py but never called. The SVG path uses `_title_case()` directly instead.
6. **`PLACEMENT_CANDIDATES` constant in layout.py** — only used as fallback in `_try_place()` and `_find_least_overlap_position()`. The SVG renderer has its own placement logic and does not use layout.py at all.

### Inconsistencies
1. **Naming**: `marker_colour` (British spelling in config) vs function names using American spelling conventions elsewhere. Minor but present.
2. **Error handling**: Some functions raise exceptions (`detect_markers` raises `FileNotFoundError`), others return empty results silently (`parse_bindings_for_aircraft` returns `{}`), others return `None` (`load_config`). No consistent pattern.
3. **Import style**: `generate-mapping` command imports `cv2` and `numpy` inline; `detect-groups` does the same. Other modules import at top level.
4. **`config` loaded twice** in `generate-mapping` command (lines: `config = load_config(...)` appears twice).
5. **`render_binding_svg` imported inline** inside the `render` command (`from .renderer import render_binding_svg`) despite `render_binding_image` being imported at module top level.
6. **Group detection** in `generate-mapping` uses `check_line()` with hardcoded thresholds (distance 30–135, darkness < 180, ratio > 0.5) that differ slightly from `detect-groups` (same values currently, but maintained separately).

### Dead/Vestigial Code
1. **`render_binding_image()`** and all its helper functions (`_render_device`, `_draw_label`, `_draw_leader_line`, `_draw_title`, `_load_font`, `_wrap_text`) — the render command now uses SVG output exclusively.
2. **`layout.py`** — the entire module is only used by the dead PNG rendering path. The SVG renderer implements its own collision avoidance.
3. **`abbreviations.py`** — imported but `abbreviate()` is never called in any active code path.
4. **`output.format` config field** — always "png" in config but the tool now outputs SVG. The field is unused.
5. **`RenderJob.output_path`** — field exists but is never set or read in the current flow.
