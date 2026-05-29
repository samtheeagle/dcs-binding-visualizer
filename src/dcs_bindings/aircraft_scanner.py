"""Scan DCS saved games directory for installed aircraft and their seats."""

import re
from pathlib import Path
from typing import Optional

from .models import AircraftProfile

# Known multi-seat aircraft patterns: base_name -> {suffix: seat_display_name}
MULTI_SEAT_PATTERNS = {
    "AH-64D_BLK_II": {"_PLT": "Pilot", "_CPG": "CPG"},
    "F-14B": {"-Pilot": "Pilot", "-RIO": "RIO"},
    "Mi-24P": {"_pilot": "Pilot", "_operator": "Operator"},
}

# Directories to skip (not actual flyable aircraft profiles)
SKIP_SUFFIXES = ("_AI_Menu", "_AimingStation")
SKIP_NAMES = {"UiLayer", "disabled.lua", "F-14", "F-14_RIO", "SA342 Pilot"}


def scan_aircraft(input_config_path: Path) -> list[AircraftProfile]:
    """Scan the DCS input config directory for aircraft with joystick bindings.

    DCS structure: <Input>/<aircraft>/joystick/<device>.diff.lua
    Multi-seat aircraft use separate top-level dirs with seat suffixes.

    Args:
        input_config_path: Path to <saved_games>/Config/Input/

    Returns:
        List of AircraftProfile with detected seats.
    """
    if not input_config_path.exists():
        return []

    # Collect all directories that have joystick bindings
    aircraft_dirs: list[str] = []
    for item in sorted(input_config_path.iterdir()):
        if not item.is_dir():
            continue
        if item.name in SKIP_NAMES or item.name.startswith("."):
            continue
        if any(item.name.endswith(s) for s in SKIP_SUFFIXES):
            continue
        joystick_dir = item / "joystick"
        if joystick_dir.exists() and any(joystick_dir.glob("*.lua")):
            aircraft_dirs.append(item.name)

    # Group multi-seat aircraft
    profiles = _group_multi_seat(aircraft_dirs)
    return profiles


def _group_multi_seat(aircraft_dirs: list[str]) -> list[AircraftProfile]:
    """Group multi-seat aircraft directories into single profiles with seats."""
    used: set[str] = set()
    profiles: list[AircraftProfile] = []

    # First pass: identify known multi-seat patterns
    for base_name, suffixes in MULTI_SEAT_PATTERNS.items():
        seats: list[str] = []
        seat_dirs: dict[str, str] = {}
        matched_dirs: list[str] = []
        for suffix, seat_name in suffixes.items():
            dir_name = base_name + suffix
            if dir_name in aircraft_dirs:
                seats.append(seat_name)
                seat_dirs[seat_name] = dir_name
                matched_dirs.append(dir_name)

        if seats:
            used.update(matched_dirs)
            # Also mark the bare base name as used if it exists
            if base_name in aircraft_dirs:
                used.add(base_name)
            profiles.append(AircraftProfile(
                name=base_name,
                display_name=_format_display_name(base_name),
                seats=seats,
                seat_dirs=seat_dirs,
            ))

    # Second pass: remaining directories are single-seat
    for dir_name in aircraft_dirs:
        if dir_name in used:
            continue
        # Skip if this looks like a variant of an already-matched multi-seat
        # (e.g., "F-14" when we already have "F-14B")
        is_variant = False
        for base_name in MULTI_SEAT_PATTERNS:
            if dir_name.startswith(base_name) or base_name.startswith(dir_name):
                is_variant = True
                break
        if is_variant:
            continue

        profiles.append(AircraftProfile(
            name=dir_name,
            display_name=_format_display_name(dir_name),
            seats=[],
        ))

    return sorted(profiles, key=lambda p: p.name.lower())


def _format_display_name(internal_name: str) -> str:
    """Convert DCS internal aircraft name to a display-friendly format."""
    replacements = {
        "FA-18C_hornet": "F/A-18C Hornet",
        "F-16C_50": "F-16C Viper",
        "AH-64D_BLK_II": "AH-64D Apache",
        "F-14B": "F-14B Tomcat",
        "Ka-50_3": "Ka-50 Black Shark",
        "Ka-50 III": "Ka-50 III Black Shark",
        "Mi-24P": "Mi-24P Hind",
        "UH-1H": "UH-1H Huey",
        "A-10C_2": "A-10C II Warthog",
        "A-10C II": "A-10C II Warthog",
        "SA342": "SA342 Gazelle",
    }
    if internal_name in replacements:
        return replacements[internal_name]
    for key, val in replacements.items():
        if internal_name.startswith(key):
            return val
    return internal_name


def prompt_aircraft_selection(profiles: list[AircraftProfile]) -> list[AircraftProfile]:
    """Display aircraft list and prompt user for selection."""
    import click

    click.echo()
    click.echo("  Scanning for aircraft with joystick bindings...")
    click.echo()
    click.echo(f"  Found {len(profiles)} aircraft:")
    click.echo()

    for i, profile in enumerate(profiles, 1):
        seat_info = f"({profile.seat_count} seat)"
        if profile.is_multi_seat:
            seat_info = f"({profile.seat_count} seats: {', '.join(profile.seats)})"
        click.echo(f"     {i:2d}.  {profile.name:<22s} {seat_info}")

    click.echo()
    selection = click.prompt(
        "  Select aircraft (comma-separated numbers, or 'all')",
        type=str,
        default="all",
    )

    if selection.strip().lower() == "all":
        return profiles

    selected: list[AircraftProfile] = []
    try:
        indices = [int(s.strip()) for s in selection.split(",")]
        for idx in indices:
            if 1 <= idx <= len(profiles):
                selected.append(profiles[idx - 1])
            else:
                click.echo(f"  ⚠ Invalid selection: {idx} (skipped)")
    except ValueError:
        click.echo("  ⚠ Invalid input. Selecting all aircraft.")
        return profiles

    return selected
