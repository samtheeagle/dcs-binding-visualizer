"""CLI interface for DCS Binding Visualizer."""

import os
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .aircraft_scanner import prompt_aircraft_selection, scan_aircraft
from .config import DEFAULT_CONFIG_FILENAME, AppConfig, load_config, save_config
from .detection_cache import get_cached_markers, save_markers_to_cache, set_cache_dir
from .detector import detect_markers, generate_debug_image
from .lua_parser import parse_bindings_for_aircraft
from .mapping import load_device_mapping, resolve_button_positions
from .models import AircraftProfile, RenderJob
from .ocr import read_marker_numbers
from .renderer import render_binding_image
from .setup_wizard import run_wizard



class State:
    """Shared state for CLI commands."""

    def __init__(self):
        self.verbose = False
        self.quiet = False
        self.config_path = DEFAULT_CONFIG_FILENAME


pass_state = click.make_pass_decorator(State, ensure=True)


@click.group()
@click.option("--config", "-c", default=DEFAULT_CONFIG_FILENAME, help="Path to config file")
@click.option("--quiet", "-q", is_flag=True, help="Suppress output except errors")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed debug output")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx, config, quiet, verbose):
    """DCS Binding Visualizer - Generate visual reference cards for DCS World joystick bindings."""
    ctx.ensure_object(State)
    ctx.obj.config_path = config
    ctx.obj.quiet = quiet
    ctx.obj.verbose = verbose


@cli.command()
@pass_state
def init(state):
    """Run the interactive setup wizard to create a config file."""
    run_wizard(state.config_path)


@cli.command()
@click.option("--aircraft", help="Render a specific aircraft (skip interactive prompt)")
@click.option("--seat", help="Render a specific seat only (requires --aircraft)")
@click.option("--force-detect", is_flag=True, help="Re-run image detection ignoring cache")
@click.option("--output-dir", help="Override output directory")
@click.option("--dry-run", is_flag=True, help="Preview what would be generated")
@pass_state
def render(state, aircraft, seat, force_detect, output_dir, dry_run):
    """Generate binding reference images."""
    config = _ensure_config(state)
    if not config:
        return

    if output_dir:
        config.output.output_dir = output_dir

    # Scan for aircraft
    profiles = scan_aircraft(config.input_config_path)
    if not profiles:
        _echo(state, "  No aircraft with joystick bindings found.", err=True)
        _echo(state, f"  Checked: {config.input_config_path}", err=True)
        return

    # Select aircraft
    if aircraft:
        selected = [p for p in profiles if p.name == aircraft]
        if not selected:
            _echo(state, f"  Aircraft '{aircraft}' not found.", err=True)
            return
    else:
        selected = prompt_aircraft_selection(profiles)

    if not selected:
        _echo(state, "  No aircraft selected.")
        return

    # Filter by seat if specified
    if seat and aircraft:
        for p in selected:
            if seat in p.seats:
                p.seats = [seat]

    # Load device mappings and detect positions
    device_data = _load_device_data(config, state, force_detect)
    if not device_data:
        return

    # Generate render jobs
    jobs = _create_render_jobs(selected, config, device_data)

    if dry_run:
        _show_dry_run(jobs, device_data, state)
        return

    # Render
    os.makedirs(config.output.output_dir, exist_ok=True)
    rendered = 0
    for job in jobs:
        # Render SVG for each device (editable in Inkscape)
        from .renderer import render_binding_svg
        for position, data in device_data.items():
            svg_filename = job.aircraft_name
            if job.seat:
                svg_filename += f"_{job.seat}"
            svg_filename += f"_{position}.svg"
            svg_path = os.path.join(config.output.output_dir, svg_filename)
            render_binding_svg(
                job, data["positions"], data["image_path"],
                data.get("bindings", {}), config, svg_path,
                groups=data["mapping"].groups,
            )
            _echo(state, f"  ✓ Saved: {svg_path}")

        rendered += 1

    _echo(state, f"\n  Done! {rendered} image{'s' if rendered != 1 else ''} generated.")



@cli.command("list-aircraft")
@pass_state
def list_aircraft(state):
    """List detected aircraft profiles with seat information."""
    config = _ensure_config(state)
    if not config:
        return

    profiles = scan_aircraft(config.input_config_path)
    if not profiles:
        _echo(state, "  No aircraft with joystick bindings found.")
        return

    _echo(state, "\n  Detected aircraft profiles:\n")
    for profile in profiles:
        seat_info = f"({profile.seat_count} seat)"
        if profile.is_multi_seat:
            seat_info = f"({profile.seat_count} seats: {', '.join(profile.seats)})"
        _echo(state, f"    {profile.name:<24s} {seat_info}")
    _echo(state, "")


@cli.command("detect-buttons")
@click.option("--image", required=True, help="Path to device image to analyze")
@click.option("--debug", is_flag=True, help="Output annotated debug image")
@pass_state
def detect_buttons(state, image, debug):
    """Run marker detection on a device image (for setup/debugging)."""
    config = load_config(state.config_path)
    detection_config = config.detection if config else __import__(
        "dcs_bindings.config", fromlist=["DetectionConfig"]
    ).DetectionConfig()

    if not Path(image).exists():
        click.echo(f"  Error: Image not found: {image}", err=True)
        return

    _echo(state, f"\n  Detecting markers in: {image}")
    _echo(state, f"  Marker colour: {detection_config.marker_colour}")

    # Run detection
    raw_markers = detect_markers(image, detection_config)
    _echo(state, f"  Found {len(raw_markers)} candidate markers")

    # Run OCR
    markers = read_marker_numbers(image, raw_markers, detection_config)
    _echo(state, f"  Successfully read {len(markers)} numbers")

    # Show results
    for m in sorted(markers, key=lambda x: x.number):
        conf_str = f"{m.confidence:.0f}%" if m.confidence < 100 else ""
        _echo(state, f"    #{m.number:3d} at ({m.center_x}, {m.center_y}) {conf_str}")

    # Save to cache
    save_markers_to_cache(image, markers, detection_config.marker_colour)
    _echo(state, f"\n  ✓ Positions cached")

    # Generate debug image if requested
    if debug:
        debug_path = str(Path(image).with_suffix("")) + "_detected.png"
        generate_debug_image(image, raw_markers, debug_path)
        _echo(state, f"  ✓ Debug image saved: {debug_path}")

    _echo(state, "")


@cli.command("detect-groups")
@click.option("--image", required=True, help="Path to device image to analyze")
@pass_state
def detect_groups(state, image):
    """Scan image for connected button markers and suggest groups for the mapping file."""
    import cv2
    import numpy as np

    config = load_config(state.config_path)
    detection_config = config.detection if config else None

    if not Path(image).exists():
        click.echo(f"  Error: Image not found: {image}", err=True)
        return

    # Load cached marker positions
    markers = get_cached_markers(image)
    if not markers:
        _echo(state, f"  No cached positions for {image}. Run detect-buttons first.")
        return

    _echo(state, f"\n  Scanning for connected markers in: {image}")

    img = cv2.imread(str(image))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    pos_map = {m.number: m for m in markers}

    # Detect lines connecting marker pairs
    def check_line(p1, p2):
        x1, y1 = p1.center_x, p1.center_y
        x2, y2 = p2.center_x, p2.center_y
        dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if dist < 30 or dist > 135:
            return False
        num_samples = int(dist) // 3
        skip = 20 / dist
        dark = 0
        total = 0
        for t in np.linspace(skip, 1 - skip, num_samples):
            x = int(x1 + t * (x2 - x1))
            y = int(y1 + t * (y2 - y1))
            if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
                if gray[y, x] < 180:
                    dark += 1
                total += 1
        return total > 0 and (dark / total) > 0.5

    connected = []
    marker_list = list(pos_map.values())
    for i, p1 in enumerate(marker_list):
        for p2 in marker_list[i + 1:]:
            if check_line(p1, p2):
                connected.append((p1.number, p2.number))

    # Union-find with max group size 5
    parent = {}
    size = {}

    def find(x):
        if x not in parent:
            parent[x] = x
            size[x] = 1
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb and size[ra] + size[rb] <= 5:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]

    for a, b in connected:
        union(a, b)

    groups = {}
    for a, b in connected:
        for x in (a, b):
            r = find(x)
            groups.setdefault(r, set()).add(x)

    # Determine layout type for each group
    results = []
    for root, members in sorted(groups.items(), key=lambda x: min(x[1])):
        if len(members) < 2:
            continue
        buttons = sorted(members)
        xs = [pos_map[n].center_x for n in buttons]
        ys = [pos_map[n].center_y for n in buttons]
        x_spread = max(xs) - min(xs)
        y_spread = max(ys) - min(ys)

        if len(buttons) >= 4 and x_spread > 50 and y_spread > 50:
            layout = "hat"
        elif x_spread > y_spread:
            layout = "horizontal"
        else:
            layout = "vertical"

        results.append({"buttons": buttons, "layout": layout})

    # Output as YAML
    _echo(state, f"  Found {len(results)} groups:\n")
    _echo(state, "groups:")
    for g in results:
        _echo(state, f"  - buttons: {g['buttons']}")
        _echo(state, f"    layout: {g['layout']}")
    _echo(state, "")


@cli.command()
@pass_state
def validate(state):
    """Validate configuration and mappings."""
    config = load_config(state.config_path)
    if not config:
        click.echo(f"  Error: Config file not found: {state.config_path}", err=True)
        return

    errors = config.validate()
    if errors:
        click.echo("\n  Configuration errors:\n", err=True)
        for error in errors:
            click.echo(f"    ✗ {error}", err=True)
        click.echo("")
    else:
        _echo(state, "\n  ✓ Configuration is valid.\n")



# ─── Helper Functions ────────────────────────────────────────────────────────


def _ensure_config(state: State) -> Optional[AppConfig]:
    """Load config, or run wizard if it doesn't exist."""
    config = load_config(state.config_path)
    if not config:
        if state.quiet:
            click.echo(f"Error: No config file found: {state.config_path}", err=True)
            return None
        config = run_wizard(state.config_path)
    # Set cache dir relative to config file location
    config_dir = Path(state.config_path).resolve().parent
    set_cache_dir(config_dir / ".cache")
    return config


def _echo(state: State, message: str, err: bool = False) -> None:
    """Echo a message unless in quiet mode."""
    if not state.quiet:
        click.echo(message, err=err)


def _load_device_data(
    config: AppConfig, state: State, force_detect: bool
) -> dict:
    """Load device mappings and detect/cache button positions."""
    device_data = {}

    for device_cfg in config.devices:
        position = device_cfg.position  # "left" or "right"

        # Load mapping
        if not Path(device_cfg.button_mapping_path).exists():
            _echo(state, f"  ⚠ Mapping not found: {device_cfg.button_mapping_path}")
            continue

        mapping = load_device_mapping(device_cfg.button_mapping_path)

        # Get or detect marker positions
        markers = None
        if not force_detect:
            if Path(device_cfg.image_path).exists():
                markers = get_cached_markers(device_cfg.image_path)
                if markers:
                    _echo(state, f"  ✓ {Path(device_cfg.image_path).name} ({len(markers)} buttons, from cache)")

        if markers is None:
            if not Path(device_cfg.image_path).exists():
                _echo(state, f"  ⚠ Image not found: {device_cfg.image_path}")
                continue

            _echo(state, f"  Detecting markers in {Path(device_cfg.image_path).name}...")
            raw_markers = detect_markers(device_cfg.image_path, config.detection)
            markers = read_marker_numbers(device_cfg.image_path, raw_markers, config.detection)
            save_markers_to_cache(device_cfg.image_path, markers, config.detection.marker_colour)
            _echo(state, f"  ✓ {Path(device_cfg.image_path).name} ({len(markers)} buttons detected)")

        # Resolve positions
        positions = resolve_button_positions(markers, mapping)

        device_data[position] = {
            "mapping": mapping,
            "positions": positions,
            "image_path": device_cfg.image_path,
            "name": device_cfg.name,
        }

    return device_data


def _create_render_jobs(
    selected: list[AircraftProfile],
    config: AppConfig,
    device_data: dict,
) -> list[RenderJob]:
    """Create render jobs for selected aircraft."""
    jobs = []

    for profile in selected:
        seats = profile.seats if profile.is_multi_seat else [None]

        for seat in seats:
            # Resolve the actual directory name for this seat
            if seat and seat in profile.seat_dirs:
                aircraft_dir_name = profile.seat_dirs[seat]
            else:
                aircraft_dir_name = profile.name

            # Collect bindings from all devices
            all_bindings: dict[str, object] = {}

            for position, data in device_data.items():
                mapping = data["mapping"]
                bindings = parse_bindings_for_aircraft(
                    config.input_config_path,
                    aircraft_dir_name,
                    mapping.device_name,
                    mapping.device_name_alt,
                )
                data["bindings"] = bindings
                all_bindings.update(bindings)

            jobs.append(
                RenderJob(
                    aircraft_name=profile.name,
                    seat=seat,
                    bindings=all_bindings,
                )
            )

    return jobs


def _show_dry_run(jobs: list[RenderJob], device_data: dict, state: State) -> None:
    """Display dry-run output showing what would be generated."""
    _echo(state, "\n  Dry run — no images will be generated.\n")
    _echo(state, f"  Would render {len(jobs)} image{'s' if len(jobs) != 1 else ''}:\n")

    for i, job in enumerate(jobs, 1):
        filename = job.aircraft_name
        if job.seat:
            filename += f"_{job.seat}"
        filename += ".png"

        _echo(state, f"    {i}. output/{filename}")

        for position, data in device_data.items():
            positions = data["positions"]
            matched = sum(
                1 for p in positions if p.dcs_button_id in job.bindings
            )
            _echo(state, f"       - {matched} bindings matched to {data['name']}")

        unbound = len(job.bindings) == 0
        if unbound:
            _echo(state, "       - ⚠ No bindings found")
        _echo(state, "")
