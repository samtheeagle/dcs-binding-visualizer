# DCS Binding Visualizer

A Python CLI tool that reads your DCS World joystick bindings and generates printable A4 reference cards showing which button does what — with labels placed directly on photos of your actual devices.

## Features

- **Automatic button detection** — Uses colour-filled circle markers on your device images. OpenCV + OCR finds them automatically; no manual coordinate entry.
- **One-time detection, cached** — Image analysis runs once and is cached. Subsequent renders are instant.
- **Multi-seat aircraft support** — Automatically detects multi-crew aircraft (e.g., AH-64D Pilot/CPG) and generates a separate image per seat.
- **Smart label placement** — Anti-collision algorithm with 8-position candidates, force-directed nudging, and leader lines for dense layouts.
- **A4 landscape output** — Two devices side-by-side (stick + throttle) on one printable page.
- **Linux button remapping** — Per-device YAML mapping handles Windows vs Linux button ID differences.
- **Interactive aircraft selection** — Scans your installed DCS modules and prompts you to pick which to render.
- **Interactive first-run wizard** — Guides you through setup on first use.
- **Configurable fonts & rendering** — Change font family, size, DPI, colours, and more.
- **Modifier support** — Bindings with modifiers are annotated with `[M]`.
- **Dry-run mode** — Preview what would be generated without actually rendering.

## Quick Start

### Prerequisites

- Python 3.9+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed on your system
  - **Fedora/Nobara:** `sudo dnf install tesseract`
  - **Ubuntu/Debian:** `sudo apt install tesseract-ocr`
  - **macOS:** `brew install tesseract`
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

This launches the setup wizard which will prompt you for:
1. DCS install and saved games directories
2. Marker colour used on your device images
3. Paths to your annotated device images
4. Button mapping files for each device

### Generate Binding Images

```bash
dcs-bindings render
```

You'll be prompted with a numbered list of your installed aircraft — select which ones to generate images for.

## How It Works

### 1. Prepare Device Images

Take or find a greyscale photo/diagram of each device (stick, throttle, collective). Add **colour-filled circles with black numbers** at each button/hat position:

- Default marker colour: **bright green** (`#00FF00`)
- Each button direction gets its own numbered circle (e.g., 4-way hat = 4 circles)
- Numbers should be clear sans-serif digits

### 2. Create Button Mappings

A YAML file per device maps image numbers to DCS button IDs:

```yaml
device_name: "WINWING Orion Joystick Base 2 + JGRIP-F16"
device_name_alt: "WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16"

mappings:
  1: "JOY_BTN1"    # Trigger First Detent
  2: "JOY_BTN6"    # Trigger Second Detent
  3: "JOY_BTN2"    # Pickle Button
  # ...

linux_overrides:   # Optional: if Linux driver remaps buttons
  1: "JOY_BTN3"
```

Default mappings are included for:
- WinWing Orion 2 F-16EX Stick
- WinWing Orion 2 F-18 Throttle
- Virpil Rotor TCS Plus with Dual-SF Grip

### 3. Run & Print

```bash
# Render all selected aircraft
dcs-bindings render

# Render a specific aircraft
dcs-bindings render --aircraft "F-16C_50"

# Preview without rendering
dcs-bindings render --dry-run
```

Output: A4 landscape PNG per aircraft (per seat for multi-crew), ready to print.

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `dcs-bindings init` | Interactive setup wizard |
| `dcs-bindings render` | Generate binding images |
| `dcs-bindings list-aircraft` | Show detected aircraft with seat info |
| `dcs-bindings detect-buttons` | Run/debug marker detection on an image |
| `dcs-bindings validate` | Check config and mappings for errors |

### Global Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--config <path>` | `-c` | Config file path (default: `config.yaml`) |
| `--quiet` | `-q` | Suppress output except errors |
| `--verbose` | `-v` | Detailed debug output |

### Render Flags

| Flag | Description |
|------|-------------|
| `--aircraft <name>` | Skip interactive prompt; render specific aircraft |
| `--seat <name>` | Render specific seat only (with `--aircraft`) |
| `--force-detect` | Re-run image detection ignoring cache |
| `--output-dir <path>` | Override output directory |
| `--dry-run` | Preview what would be generated |

## Configuration

Copy `config.example.yaml` to `config.yaml`, or run `dcs-bindings init`.

See the [example config](config.example.yaml) for all available options with descriptions.

### Key Settings

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `detection` | `marker_colour` | `green` | Preset or hex colour for markers |
| `rendering` | `font_family` | `DejaVu Sans` | Font for all labels |
| `rendering` | `font_size` | `9` | Label font size in pt |
| `rendering` | `dpi` | `300` | Output resolution |
| `output` | `output_dir` | `output/` | Where images are saved |

## Project Structure

```
dcs-binding-visualizer/
├── src/dcs_bindings/       # Application source code
├── mappings/               # Button mapping YAML files
├── images/                 # Your device images (gitignored)
├── output/                 # Generated images (gitignored)
├── .cache/                 # Detection cache (gitignored)
├── fonts/                  # Bundled fonts
├── docs/plan.md            # Detailed project plan
├── config.example.yaml     # Example configuration
└── pyproject.toml          # Python project metadata
```

## Supported Devices (Bundled Mappings)

- **WinWing Orion 2 EX + F-16EX Stick Grip** — 39 buttons, 4 axes
- **WinWing Orion 2 + F-18 Throttle Handles** — 56 buttons, 4 axes
- **Virpil Rotor TCS Plus + Dual-SF Collective Grip** — 19 buttons, 2 axes

Adding new devices: create a YAML mapping file and an annotated image.

## Cross-Platform

- **Primary target:** Nobara Linux (Fedora-based)
- **Also works on:** Windows, macOS
- DCS runs via Wine/Proton on Linux or natively on Windows

## License

MIT
