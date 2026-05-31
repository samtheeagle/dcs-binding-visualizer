# DCS Binding Visualizer

A Python CLI tool that reads DCS World joystick bindings and generates printable SVG reference cards showing which button does what — with labels placed directly on photos of your actual devices.

## Features

- **Automatic button detection** — Uses green circle markers on device images. OpenCV + OCR finds them automatically.
- **One-time detection, cached** — Image analysis runs once and is cached. Subsequent renders are instant.
- **Multi-seat aircraft support** — Detects multi-crew aircraft (e.g., AH-64D Pilot/CPG) and generates separate output per seat.
- **Smart label placement** — Collision-aware algorithm tries 8 positions around each button, samples the raster image to avoid busy areas.
- **Button grouping** — Hat switches, multi-position switches, and rotary encoders rendered as single grouped labels.
- **SVG output** — Editable in Inkscape. Labels can be manually repositioned after generation.
- **Combined A4 landscape** — Two devices side-by-side on one printable page at 300 DPI.
- **Hardware probing** — Reads connected joystick axes/buttons directly from the OS (Linux and Windows).
- **Marker image generation** — Creates transparent PNGs with button markers for building annotated device images.
- **Mapping file generation** — Bootstraps device mapping files from detected markers with offset support.

## Quick Start

### Prerequisites

- Python 3.9+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
  - **Fedora/Nobara:** `sudo dnf install tesseract`
  - **Ubuntu/Debian:** `sudo apt install tesseract-ocr`
  - **Windows:** [Installer](https://github.com/UB-Mannheim/tesseract/wiki)

### Installation

```bash
git clone https://github.com/samtheeagle/dcs-binding-visualizer.git
cd dcs-binding-visualizer
pip install -e .
```

### First Run

```bash
dcs-bindings init
```

Launches the setup wizard to configure DCS paths, device images, and mapping files.

### Generate Binding Cards

```bash
dcs-bindings render --aircraft F-16C_50
```

## CLI Commands

### `dcs-bindings render`

Generate SVG binding reference cards for an aircraft.

```bash
dcs-bindings render [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--aircraft <name>` | Render specific aircraft (skip interactive prompt) |
| `--seat <name>` | Render specific seat only (use with `--aircraft`) |
| `--force-detect` | Re-run image detection, ignoring cache |
| `--dry-run` | Preview what would be generated without rendering |

**Output:** Per-device SVGs + a combined A4 landscape SVG (when multiple devices configured).

---

### `dcs-bindings list-aircraft`

Show all detected aircraft profiles with seat information.

```bash
dcs-bindings list-aircraft
```

---

### `dcs-bindings detect-buttons`

Run marker detection and OCR on a device image. Results are cached for use by `render`.

```bash
dcs-bindings detect-buttons --image <path> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--image <path>` | Path to device image (required) |
| `--debug` | Save annotated debug image showing detected markers |

---

### `dcs-bindings detect-groups`

Scan an image for connecting lines between markers to suggest button groups.

```bash
dcs-bindings detect-groups --image <path>
```

| Option | Description |
|--------|-------------|
| `--image <path>` | Path to device image (required) |

**Output:** YAML `groups:` section ready to paste into a mapping file.

---

### `dcs-bindings generate-mapping`

Generate a skeleton mapping file from detected markers on a device image.

```bash
dcs-bindings generate-mapping --image <path> --device-name <name> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--image <path>` | Path to device image (required) |
| `--device-name <name>` | DCS device name as it appears in diff files (required) |
| `--output <path>` | Output file path (default: `output/<image>_mapping.yaml`) |
| `--offset <n>` | Offset: DCS button = image number + offset (default: 0) |
| `--description <text>` | Device description |
| `--probe-device` | Probe connected hardware to auto-populate axes |

**Output:** Complete YAML mapping file with sequential button entries (undetected markers commented out), auto-detected groups, and optionally probed axis information.

---

### `dcs-bindings generate-markers`

Generate a transparent PNG containing button marker circles for manual placement onto device images.

```bash
dcs-bindings generate-markers --mapping <path> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--mapping <path>` | Path to device mapping YAML file (required) |
| `--output <path>` | Output PNG path (default: `output/<mapping>_markers.png`) |
| `--radius <n>` | Circle radius in pixels (default: 20) |

**Output:** Transparent PNG with all buttons and groups rendered as green circles with black numbers, connected by lines according to group layout type.

---

### `dcs-bindings validate`

Check configuration and mapping files for errors.

```bash
dcs-bindings validate
```

---

### `dcs-bindings init`

Interactive setup wizard for first-time configuration.

```bash
dcs-bindings init
```

---

### Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--config <path>` | `-c` | Config file path (default: `config.yaml`) |
| `--quiet` | `-q` | Suppress output except errors |
| `--verbose` | `-v` | Detailed debug output |
| `--version` | | Show version |

## Mapping File Format

Each device needs a YAML mapping file that translates image marker numbers to DCS button IDs:

```yaml
device_name: "Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16"
device_name_alt: ""
description: "WinWing Orion 2 F-16EX Stick"

axes:
  - id: "JOY_AXIS_X"
    description: "X"
  - id: "JOY_AXIS_Y"
    description: "Y"

mappings:
  1: "JOY_BTN1"
  2: "JOY_BTN2"
  3: "JOY_BTN3"
  # ...

groups:
  - buttons: [9, 10, 11, 12, 13]
    layout: hat
  - buttons: [4, 5]
    layout: horizontal
  - buttons: [86, 87, 88]
    layout: vertical
  - buttons: [69, 70, 71, 72]
    layout: rotary
```

### Group Layout Types

| Type | Description | Button Order |
|------|-------------|--------------|
| `hat` | 4-5 button cross pattern | center, top, right, bottom, left |
| `horizontal` | 2-3 position switch (left/right) | left to right |
| `vertical` | 2-3 position switch (up/down) | top to bottom |
| `rotary` | 3-position rotary + push | pos1, pos2, pos3, push |

## Workflow

1. **Find/create a device image** — greyscale photo or diagram of your stick/throttle
2. **Generate marker overlay** — `generate-markers` creates circles you can place on the image
3. **Annotate the image** — In an image editor, place markers at each button location
4. **Generate mapping** — `generate-mapping` detects markers and creates the YAML file
5. **Tweak mapping** — Adjust button offsets, fix any OCR misreads, refine groups
6. **Render** — `render` produces the final labelled SVG cards

## Project Structure

```
dcs-binding-visualizer/
├── src/dcs_bindings/       # Application source
├── mappings/               # Button mapping YAML files
├── images/                 # Device images (gitignored)
├── output/                 # Generated output (gitignored)
├── .cache/                 # Detection cache (gitignored)
├── config.yaml             # User configuration
└── pyproject.toml          # Python project metadata
```

## Cross-Platform

- **Primary target:** Linux (Nobara/Fedora) with DCS via Proton
- **Also works on:** Windows (native DCS)
- Hardware probing supports both Linux (`/dev/input/js*`) and Windows (`winmm.dll`)

## License

MIT
