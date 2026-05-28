"""Scan DCS saved games directory for installed aircraft and their seats."""

from pathlib import Path
from typing import Optional

from .models import AircraftProfile


def scan_aircraft(input_config_path: Path) -> list[AircraftProfile]:
    """Scan the DCS input config directory for aircraft with joystick bindings.

    Args:
        input_config_path: Path to <saved_games>/Config/Input/

    Returns:
        List of AircraftProfile with detected seats.
    """
    profiles: list[AircraftProfile] = []

    if not input_config_path.exists():
        return profiles

    for aircraft_dir in sorted(input_config_path.iterdir()):
        if not aircraft_dir.is_dir():
            continue

        # Skip non-aircraft directories
        name = aircraft_dir.name
        if name.startswith(".") or name in ("__MACOSX",):
            continue

        # Detect seats and check for joystick bindings
        seats = _detect_seats(aircraft_dir)
        has_bindings = _has_joystick_bindings(aircraft_dir)

        if has_bindings:
            profiles.append(
                AircraftProfile(
                    name=name,
                    display_name=_format_display_name(name),
                    seats=seats,
                )
            )

    return profiles


def _detect_seats(aircraft_dir: Path) -> list[str]:
    """Detect crew positions/seats for an aircraft.

    DCS multi-seat aircraft typically have subdirectories for each seat
    within the aircraft's input config folder.
    """
    seats: list[str] = []

    # Look for seat-specific subdirectories
    # Common patterns: direct device dirs at top level (single-seat)
    # or seat-named subdirs containing device dirs (multi-seat)
    for item in sorted(aircraft_dir.iterdir()):
        if not item.is_dir():
            continue

        # If this subdirectory itself contains device directories with
        # joystick bindings, it's likely a seat directory
        if _is_seat_directory(item):
            seats.append(item.name)

    # If no explicit seat directories found, check if bindings exist
    # at the top level (single-seat aircraft)
    if not seats:
        # Check for device directories directly under aircraft
        for item in aircraft_dir.iterdir():
            if item.is_dir() and _has_binding_files(item):
                # This is a device directory, not a seat directory
                # Single-seat aircraft
                return []

    return seats


def _is_seat_directory(path: Path) -> bool:
    """Check if a directory is a seat/role directory (contains device subdirs)."""
    for item in path.iterdir():
        if item.is_dir() and _has_binding_files(item):
            return True
    return False


def _has_joystick_bindings(aircraft_dir: Path) -> bool:
    """Check if an aircraft directory has any joystick binding files."""
    # Check direct device directories (single-seat)
    for item in aircraft_dir.iterdir():
        if item.is_dir():
            if _has_binding_files(item):
                return True
            # Check for seat subdirectories
            for sub in item.iterdir():
                if sub.is_dir() and _has_binding_files(sub):
                    return True
    return False


def _has_binding_files(device_dir: Path) -> bool:
    """Check if a device directory contains binding Lua files."""
    # DCS stores bindings as .lua files in device directories
    for ext in ("*.lua", "*.diff.lua"):
        if list(device_dir.glob(ext)):
            return True
    # Also check in a 'joystick' subdirectory
    joystick_dir = device_dir / "joystick"
    if joystick_dir.exists():
        for ext in ("*.lua", "*.diff.lua"):
            if list(joystick_dir.glob(ext)):
                return True
    return False


def _format_display_name(internal_name: str) -> str:
    """Convert DCS internal aircraft name to a display-friendly format."""
    # Simple cleanup - replace underscores, handle common patterns
    replacements = {
        "FA-18C_hornet": "F/A-18C Hornet",
        "F-16C_50": "F-16C Viper",
        "AH-64D_BLK_II": "AH-64D Apache",
        "F-14B": "F-14B Tomcat",
        "Ka-50_3": "Ka-50 Black Shark",
        "Mi-24P": "Mi-24P Hind",
        "UH-1H": "UH-1H Huey",
        "A-10C_2": "A-10C II Warthog",
        "SA342": "SA342 Gazelle",
    }
    # Try exact match first
    if internal_name in replacements:
        return replacements[internal_name]
    # Try prefix match
    for key, val in replacements.items():
        if internal_name.startswith(key):
            return val
    # Fallback: just return the internal name
    return internal_name


def prompt_aircraft_selection(profiles: list[AircraftProfile]) -> list[AircraftProfile]:
    """Display aircraft list and prompt user for selection.

    Returns the selected AircraftProfile objects.
    """
    import click

    click.echo()
    click.echo("  Scanning for aircraft with joystick bindings...")
    click.echo()
    click.echo(f"  Found {len(profiles)} aircraft:")
    click.echo()

    for i, profile in enumerate(profiles, 1):
        seat_info = f"({profile.seat_count} seat{'s' if profile.is_multi_seat else ''})"
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
