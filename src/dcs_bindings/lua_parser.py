"""DCS Lua config file parser for joystick bindings."""

import re
from pathlib import Path
from typing import Any, Optional

from .models import Binding


def parse_bindings_for_aircraft(
    input_config_path: Path,
    aircraft_name: str,
    device_name: str,
    device_name_alt: str = "",
    seat: Optional[str] = None,
) -> dict[str, Binding]:
    """Parse DCS binding files for a specific aircraft and device.

    Args:
        input_config_path: Path to <saved_games>/Config/Input/
        aircraft_name: DCS aircraft folder name (e.g., "FA-18C_hornet")
        device_name: Device name to match against folder names
        device_name_alt: Alternative device name (newer firmware)
        seat: Optional seat name for multi-seat aircraft

    Returns:
        Dictionary mapping button_id -> Binding
    """
    aircraft_dir = input_config_path / aircraft_name

    if not aircraft_dir.exists():
        return {}

    # Determine the search path based on seat
    if seat:
        search_dir = aircraft_dir / seat
        if not search_dir.exists():
            search_dir = aircraft_dir
    else:
        search_dir = aircraft_dir

    # Find the device directory matching our device_name
    device_dir = _find_device_directory(search_dir, device_name, device_name_alt)
    if not device_dir:
        return {}

    # Parse all lua files in the device directory
    bindings: dict[str, Binding] = {}
    lua_files = list(device_dir.glob("*.lua"))

    # Also check joystick subdirectory
    joystick_dir = device_dir / "joystick"
    if joystick_dir.exists():
        lua_files.extend(joystick_dir.glob("*.lua"))

    for lua_file in lua_files:
        try:
            file_bindings = _parse_lua_binding_file(lua_file)
            bindings.update(file_bindings)
        except Exception:
            # Skip files that can't be parsed
            continue

    return bindings


def _find_device_directory(
    search_dir: Path, device_name: str, device_name_alt: str = ""
) -> Optional[Path]:
    """Find a device directory matching the device name (starts-with matching).

    DCS device directories include a GUID suffix, so we match on prefix.
    """
    if not search_dir.exists():
        return None

    names_to_match = [device_name.lower()]
    if device_name_alt:
        names_to_match.append(device_name_alt.lower())

    for item in search_dir.iterdir():
        if not item.is_dir():
            continue
        folder_lower = item.name.lower()
        for name in names_to_match:
            if folder_lower.startswith(name.lower()):
                return item

    return None


def _parse_lua_binding_file(lua_file: Path) -> dict[str, Binding]:
    """Parse a single DCS Lua binding file.

    DCS binding files are Lua tables with a specific structure.
    We use regex-based parsing to extract key-value assignments.
    """
    content = lua_file.read_text(encoding="utf-8", errors="ignore")
    bindings: dict[str, Binding] = {}

    # Try to parse using slpp first
    try:
        return _parse_with_slpp(content)
    except Exception:
        pass

    # Fallback: regex-based extraction
    return _parse_with_regex(content)


def _parse_with_slpp(content: str) -> dict[str, Binding]:
    """Parse Lua table content using slpp library."""
    try:
        from slpp import slpp as lua
    except ImportError:
        from slpp import SLPP
        lua = SLPP()

    bindings: dict[str, Binding] = {}

    # Extract the diff/keyDiffs table
    # DCS files typically have: local diff = { ... } return diff
    # or contain keyDiffs tables
    table_match = re.search(
        r"(?:local\s+diff\s*=\s*|return\s+)(\{.*\})", content, re.DOTALL
    )
    if not table_match:
        # Try to find just a table
        table_match = re.search(r"(\{.*\})", content, re.DOTALL)

    if not table_match:
        return bindings

    try:
        data = lua.decode(table_match.group(1))
    except Exception:
        return bindings

    if not isinstance(data, dict):
        return bindings

    # Extract bindings from the parsed structure
    _extract_bindings_from_dict(data, bindings)

    return bindings


def _parse_with_regex(content: str) -> dict[str, Binding]:
    """Fallback regex-based parser for DCS Lua binding files."""
    bindings: dict[str, Binding] = {}

    # Pattern for key assignments in DCS diff files:
    # ["dXXX"] = { ... ["key"] = "JOY_BTNXX", ["name"] = "Action Name" ... }
    # or ["keyDiffs"]["dXXX"]["added"]["1"]["key"] = "JOY_BTN1"
    pattern = re.compile(
        r'\["key"\]\s*=\s*"(JOY_BTN[^"]*)".*?'
        r'\["name"\]\s*=\s*"([^"]*)"',
        re.DOTALL,
    )

    # Also try reversed order (name before key)
    pattern_alt = re.compile(
        r'\["name"\]\s*=\s*"([^"]*)".*?'
        r'\["key"\]\s*=\s*"(JOY_BTN[^"]*)"',
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        button_id = match.group(1)
        action_name = match.group(2)
        bindings[button_id] = Binding(button_id=button_id, action_name=action_name)

    for match in pattern_alt.finditer(content):
        action_name = match.group(1)
        button_id = match.group(2)
        if button_id not in bindings:
            bindings[button_id] = Binding(
                button_id=button_id, action_name=action_name
            )

    # Also look for simpler patterns
    simple_pattern = re.compile(
        r'"(JOY_BTN\w+)"[^}]*?"name"\s*[:=]\s*"([^"]+)"', re.DOTALL
    )
    for match in simple_pattern.finditer(content):
        button_id = match.group(1)
        action_name = match.group(2)
        if button_id not in bindings:
            bindings[button_id] = Binding(
                button_id=button_id, action_name=action_name
            )

    return bindings


def _extract_bindings_from_dict(
    data: dict[str, Any], bindings: dict[str, Binding], depth: int = 0
) -> None:
    """Recursively extract bindings from a parsed Lua table."""
    if depth > 10:
        return

    # Check if this dict has key + name (a binding entry)
    if "key" in data and "name" in data:
        key = str(data["key"])
        if key.startswith("JOY_BTN"):
            name = str(data["name"])
            reformers = data.get("reformers", [])
            modifiers = []
            if reformers and isinstance(reformers, list):
                modifiers = [str(r) for r in reformers]
            bindings[key] = Binding(
                button_id=key, action_name=name, modifiers=modifiers
            )
        return

    # Recurse into sub-dicts
    for value in data.values():
        if isinstance(value, dict):
            _extract_bindings_from_dict(value, bindings, depth + 1)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _extract_bindings_from_dict(item, bindings, depth + 1)
