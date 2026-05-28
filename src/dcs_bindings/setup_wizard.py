"""Interactive first-run setup wizard for DCS Binding Visualizer."""

import os
from pathlib import Path

import click

from .config import COLOUR_PRESETS, AppConfig, DetectionConfig, OutputConfig, RenderingConfig, save_config
from .models import DeviceConfig


def run_wizard(config_path: str) -> AppConfig:
    """Run the interactive setup wizard and save config."""
    click.echo()
    click.echo("  No configuration found. Let's set things up!")
    click.echo()

    # DCS Paths
    click.echo("  ─── DCS Paths ───────────────────────────────────────────────")
    click.echo()

    dcs_install_dir = _prompt_path(
        "  DCS install directory\n"
        "  (where DCS World is installed, e.g. the folder containing 'bin'):\n  ",
        must_exist=False,
    )

    dcs_saved_games_dir = _prompt_path(
        "  DCS saved games directory\n"
        "  (where your user config/bindings are stored):\n  ",
        must_exist=True,
    )

    click.echo()

    # Marker Colour
    click.echo("  ─── Marker Colour ───────────────────────────────────────────")
    click.echo()
    click.echo("  What colour did you use to fill the numbered circles on your device images?")
    click.echo()
    click.echo("    1. Green   (#00FF00) — recommended default")
    click.echo("    2. Magenta (#FF00FF)")
    click.echo("    3. Cyan    (#00FFFF)")
    click.echo("    4. Custom hex colour")
    click.echo()

    colour_choice = click.prompt("  Select (1-4)", type=int, default=1)
    if colour_choice == 1:
        marker_colour = "green"
    elif colour_choice == 2:
        marker_colour = "magenta"
    elif colour_choice == 3:
        marker_colour = "cyan"
    elif colour_choice == 4:
        marker_colour = click.prompt("  Enter hex colour (e.g., #FF8800)")
    else:
        marker_colour = "green"

    click.echo(f"  ✓ Marker colour set to: {marker_colour}")
    click.echo()

    # Device Images
    click.echo("  ─── Device Images ───────────────────────────────────────────")
    click.echo()
    click.echo("  Provide paths to your annotated device images:")
    click.echo()

    left_image = click.prompt("  Left device image (e.g. stick)", default="images/stick.png")
    right_image = click.prompt("  Right device image (e.g. throttle/collective)", default="images/throttle.png")
    click.echo()

    # Button Mappings
    click.echo("  ─── Button Mappings ─────────────────────────────────────────")
    click.echo()

    left_mapping = _suggest_mapping("left", left_image)
    right_mapping = _suggest_mapping("right", right_image)
    click.echo()

    # Build config
    devices = [
        DeviceConfig(
            name="Left Device (Stick)",
            image_path=left_image,
            button_mapping_path=left_mapping,
            position="left",
        ),
        DeviceConfig(
            name="Right Device (Throttle/Collective)",
            image_path=right_image,
            button_mapping_path=right_mapping,
            position="right",
        ),
    ]

    config = AppConfig(
        dcs_install_dir=dcs_install_dir,
        dcs_saved_games_dir=dcs_saved_games_dir,
        devices=devices,
        detection=DetectionConfig(marker_colour=marker_colour),
        rendering=RenderingConfig(),
        output=OutputConfig(),
    )

    # Save
    save_config(config, config_path)

    click.echo("  ─── Configuration Saved ─────────────────────────────────────")
    click.echo()
    click.echo(f"  ✓ Configuration saved to {config_path}")
    click.echo("  ✓ Run 'dcs-bindings render' to generate binding images.")
    click.echo()

    return config


def _prompt_path(prompt_text: str, must_exist: bool = True) -> str:
    """Prompt for a path, optionally validating existence."""
    while True:
        path = click.prompt(prompt_text)
        path = os.path.expanduser(path)
        if must_exist and not Path(path).exists():
            click.echo(f"  ✗ Path not found: {path}")
            click.echo("  Please try again.")
            continue
        if Path(path).exists():
            click.echo(f"  ✓ Found: {path}")
        break
    click.echo()
    return path


def _suggest_mapping(position: str, image_path: str) -> str:
    """Suggest a mapping file based on available bundled mappings."""
    mappings_dir = Path("mappings")
    available = []
    if mappings_dir.exists():
        available = sorted(mappings_dir.glob("*.yaml"))

    if available:
        click.echo(f"  Available mapping files for {position} device:")
        for i, m in enumerate(available, 1):
            click.echo(f"    {i}. {m}")
        click.echo(f"    {len(available) + 1}. Enter custom path")
        click.echo()
        choice = click.prompt(f"  Select mapping for {position} device", type=int, default=1)
        if 1 <= choice <= len(available):
            return str(available[choice - 1])

    return click.prompt(f"  {position.capitalize()} device mapping file")
