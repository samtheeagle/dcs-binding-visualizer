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

        # Generate combined A4 landscape SVG
        svg_files = []
        for position in sorted(device_data.keys()):
            data = device_data[position]
            svg_filename = job.aircraft_name
            if job.seat:
                svg_filename += f"_{job.seat}"
            svg_filename += f"_{position}.svg"
            svg_files.append(os.path.join(config.output.output_dir, svg_filename))

        if len(svg_files) > 1:
            combined_filename = job.aircraft_name
            if job.seat:
                combined_filename += f"_{job.seat}"
            combined_filename += "_combined.svg"
            combined_path = os.path.join(config.output.output_dir, combined_filename)
            _generate_combined_svg(svg_files, combined_path)
            _echo(state, f"  ✓ Saved: {combined_path}")

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
    from .group_detection import detect_groups as _detect_groups

    if not Path(image).exists():
        click.echo(f"  Error: Image not found: {image}", err=True)
        return

    # Load cached marker positions
    markers = get_cached_markers(image)
    if not markers:
        _echo(state, f"  No cached positions for {image}. Run detect-buttons first.")
        return

    _echo(state, f"\n  Scanning for connected markers in: {image}")

    results = _detect_groups(image, markers)

    # Output as YAML
    _echo(state, f"  Found {len(results)} groups:\n")
    _echo(state, "groups:")
    for g in results:
        _echo(state, f"  - buttons: {g['buttons']}")
        _echo(state, f"    layout: {g['layout']}")
    _echo(state, "")


@cli.command("generate-markers")
@click.option("--mapping", "-m", required=True, help="Path to device mapping YAML file")
@click.option("--output", "-o", default=None, help="Output PNG file path (default: output dir)")
@click.option("--radius", type=int, default=20, help="Circle radius in pixels (default: 20)")
@pass_state
def generate_markers(state, mapping, output, radius):
    """Generate a transparent PNG with button marker circles for manual placement."""
    from .marker_generator import generate_marker_image
    import os

    if not Path(mapping).exists():
        click.echo(f"  Error: Mapping file not found: {mapping}", err=True)
        return

    config = load_config(state.config_path)
    device_mapping = load_device_mapping(mapping)

    if not output:
        os.makedirs(config.output.output_dir, exist_ok=True)
        stem = Path(mapping).stem
        output = os.path.join(config.output.output_dir, f"{stem}_markers.png")
    _echo(state, f"\n  Generating markers from: {mapping}")
    _echo(state, f"  Device: {device_mapping.device_name}")
    _echo(state, f"  Buttons: {len(device_mapping.mappings)}, Groups: {len(device_mapping.groups)}")

    result = generate_marker_image(device_mapping, output, circle_radius=radius)
    if result:
        _echo(state, f"  ✓ Saved: {result}")
    _echo(state, "")


@cli.command("generate-mapping")
@click.option("--image", required=True, help="Path to device image")
@click.option("--device-name", required=True, help="DCS device name (e.g. 'Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16')")
@click.option("--output", "-o", default=None, help="Output YAML mapping file path (default: output dir)")
@click.option("--offset", type=int, default=0, help="Offset to apply: DCS button = image number + offset")
@click.option("--description", default="", help="Device description")
@click.option("--probe-device", is_flag=True, help="Probe connected hardware to populate axes info")
@pass_state
def generate_mapping(state, image, device_name, output, offset, description, probe_device):
    """Generate a skeleton mapping file from detected markers on a device image."""
    from .group_detection import detect_groups as _detect_groups

    config = load_config(state.config_path)
    if not output:
        import os
        os.makedirs(config.output.output_dir, exist_ok=True)
        stem = Path(image).stem
        output = os.path.join(config.output.output_dir, f"{stem}_mapping.yaml")

    detection_config = config.detection if config else None

    if not Path(image).exists():
        click.echo(f"  Error: Image not found: {image}", err=True)
        return

    # Load cached markers or detect
    markers = get_cached_markers(image)
    if not markers:
        _echo(state, f"  No cached positions for {image}. Running detection...")
        raw_markers = detect_markers(image, detection_config)
        markers = read_marker_numbers(image, raw_markers, detection_config)
        save_markers_to_cache(image, markers, detection_config.marker_colour)

    _echo(state, f"  Found {len(markers)} markers in: {image}")

    # Deduplicate marker numbers (take highest confidence)
    # Filter out implausible numbers (OCR errors producing >3 digit results)
    best_markers = {}
    for m in markers:
        if m.number > 200:
            continue  # OCR misread
        if m.number not in best_markers or m.confidence > best_markers[m.number].confidence:
            best_markers[m.number] = m
    marker_nums = sorted(best_markers.keys())

    # Generate mappings with offset
    lines = []
    lines.append(f'# Auto-generated mapping file for: {device_name}')
    lines.append(f'# Image: {image}')
    lines.append(f'# Offset applied: {offset} (DCS button = image number + offset)')
    lines.append(f'')
    lines.append(f'device_name: "{device_name}"')
    lines.append(f'device_name_alt: ""')
    lines.append(f'description: "{description}"')
    lines.append(f'')

    # Probe hardware for axes info if requested
    probed_axes = []
    if probe_device:
        from .device_probe import list_devices
        try:
            devices = list_devices()
            # Find device matching the name (substring match)
            matched = [d for d in devices if device_name.lower() in d.name.lower()
                       or d.name.lower() in device_name.lower()]
            if matched:
                dev = matched[0]
                probed_axes = dev.axes
                _echo(state, f"  Probed device: {dev.name} ({dev.num_buttons} buttons, {dev.num_axes} axes)")
            else:
                _echo(state, f"  ⚠ No connected device matching '{device_name}' found")
                _echo(state, f"    Available: {[d.name for d in devices]}")
        except RuntimeError as e:
            _echo(state, f"  ⚠ Device probing failed: {e}")

    if probed_axes:
        lines.append(f'axes:')
        for ax in probed_axes:
            lines.append(f'  - id: "{ax["id"]}"')
            lines.append(f'    description: "{ax["description"]}"')
    else:
        lines.append(f'axes: []')

    lines.append(f'')
    lines.append(f'mappings:')
    max_num = max(marker_nums) if marker_nums else 0
    detected_set = set(marker_nums)
    for num in range(1, max_num + 1):
        dcs_btn = num + offset
        if num in detected_set:
            lines.append(f'  {num}: "JOY_BTN{dcs_btn}"')
        else:
            lines.append(f'  # {num}: "JOY_BTN{dcs_btn}"  # NOT DETECTED')

    # Detect groups using shared logic
    group_results = _detect_groups(image, list(best_markers.values()))

    if group_results:
        lines.append(f'')
        lines.append(f'groups:')
        for g in group_results:
            lines.append(f'  - buttons: {g["buttons"]}')
            lines.append(f'    layout: {g["layout"]}')

    # Write output
    with open(output, "w") as f:
        f.write("\n".join(lines) + "\n")

    _echo(state, f"  ✓ Generated mapping file: {output}")
    _echo(state, f"    {len(marker_nums)} buttons mapped, {len(group_results)} groups detected")
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


def _generate_combined_svg(svg_files: list[str], output_path: str):
    """Combine multiple SVG files side by side into an A4 landscape SVG."""
    import re

    # A4 landscape at 300 DPI
    page_w = 3508
    page_h = 2480

    # Parse dimensions from each SVG
    panels = []
    for svg_file in svg_files:
        with open(svg_file, "r") as f:
            content = f.read()
        # Extract width and height from the SVG tag
        w_match = re.search(r'width="(\d+)"', content)
        h_match = re.search(r'height="(\d+)"', content)
        if w_match and h_match:
            w = int(w_match.group(1))
            h = int(h_match.group(1))
            # Extract everything between <svg ...> and </svg>
            body_start = content.index(">") + 1
            body_end = content.rindex("</svg>")
            body = content[body_start:body_end]
            panels.append({"w": w, "h": h, "body": body})

    if not panels:
        return

    # Calculate scaling to fit side by side
    n = len(panels)
    panel_w = page_w / n
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="297mm" height="210mm" '
                 f'viewBox="0 0 {page_w} {page_h}">')

    x_offset = 0
    for panel in panels:
        scale_x = panel_w / panel["w"]
        scale_y = page_h / panel["h"]
        scale = min(scale_x, scale_y)
        scaled_h = panel["h"] * scale
        y_offset = (page_h - scaled_h) / 2

        lines.append(f'  <g transform="translate({x_offset},{y_offset}) scale({scale})">')
        lines.append(panel["body"])
        lines.append(f'  </g>')
        x_offset += panel_w

    lines.append('</svg>')

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


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
