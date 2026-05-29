"""DCS Lua config file parser for joystick bindings."""

import re
from pathlib import Path
from typing import Optional

from .models import Binding


def parse_bindings_for_aircraft(
    input_config_path: Path,
    aircraft_name: str,
    device_name: str,
    device_name_alt: str = "",
    seat: Optional[str] = None,
) -> dict[str, Binding]:
    """Parse DCS binding files for a specific aircraft and device.

    DCS structure: <Input>/<aircraft>/joystick/<device_name> {GUID}.diff.lua

    For multi-seat aircraft, DCS uses separate top-level directories with
    seat suffixes (e.g., AH-64D_BLK_II_PLT, F-14B-Pilot).

    Args:
        input_config_path: Path to <saved_games>/Config/Input/
        aircraft_name: DCS aircraft folder name (e.g., "FA-18C_hornet")
        device_name: Device name to match against filenames
        device_name_alt: Alternative device name (newer firmware)
        seat: Optional seat name for multi-seat aircraft

    Returns:
        Dictionary mapping button_id -> Binding
    """
    aircraft_dir = input_config_path / aircraft_name

    if not aircraft_dir.exists():
        return {}

    # Look for the joystick subdirectory
    joystick_dir = aircraft_dir / "joystick"
    if not joystick_dir.exists():
        return {}

    # Find the .diff.lua file matching our device name
    lua_file = _find_device_file(joystick_dir, device_name, device_name_alt)
    if not lua_file:
        return {}

    try:
        return _parse_lua_binding_file(lua_file)
    except Exception:
        return {}


def _find_device_file(
    joystick_dir: Path, device_name: str, device_name_alt: str = ""
) -> Optional[Path]:
    """Find a .diff.lua file matching the device name (starts-with matching).

    DCS filenames include a GUID suffix, e.g.:
    'Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16 {GUID}.diff.lua'
    """
    if not joystick_dir.exists():
        return None

    names_to_match = [device_name.lower()]
    if device_name_alt:
        names_to_match.append(device_name_alt.lower())

    for item in joystick_dir.iterdir():
        if not item.is_file() or not item.name.endswith(".lua"):
            continue
        filename_lower = item.name.lower()
        for name in names_to_match:
            if filename_lower.startswith(name.lower()):
                return item

    return None


def _parse_lua_binding_file(lua_file: Path) -> dict[str, Binding]:
    """Parse a single DCS Lua binding file.

    DCS diff.lua files have the structure:
        local diff = { ["keyDiffs"] = { ["id"] = { ["added"] = { [1] = { ["key"] = "JOY_BTN1" } }, ["name"] = "Action" } } }
        return diff
    """
    content = lua_file.read_text(encoding="utf-8", errors="ignore")
    bindings: dict[str, Binding] = {}

    # Try slpp first
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

    # Strip 'local diff = ' prefix and 'return diff' suffix
    table_match = re.search(r"local\s+diff\s*=\s*(\{.*\})", content, re.DOTALL)
    if not table_match:
        table_match = re.search(r"(\{.*\})", content, re.DOTALL)
    if not table_match:
        return bindings

    try:
        data = lua.decode(table_match.group(1))
    except Exception:
        return bindings

    if not isinstance(data, dict):
        return bindings

    # Extract from keyDiffs structure
    key_diffs = data.get("keyDiffs", {})
    if isinstance(key_diffs, dict):
        for action_id, entry in key_diffs.items():
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            added = entry.get("added", {})
            if isinstance(added, dict):
                for idx, binding_entry in added.items():
                    if isinstance(binding_entry, dict):
                        key = binding_entry.get("key", "")
                        if key.startswith("JOY_BTN"):
                            reformers = binding_entry.get("reformers", [])
                            modifiers = []
                            if isinstance(reformers, list):
                                modifiers = [str(r) for r in reformers]
                            bindings[key] = Binding(
                                button_id=key,
                                action_name=name,
                                modifiers=modifiers,
                            )

    return bindings


def _parse_with_regex(content: str) -> dict[str, Binding]:
    """Fallback regex-based parser for DCS Lua diff files.

    Extracts ["name"] and ["key"] pairs from keyDiffs entries.
    """
    bindings: dict[str, Binding] = {}

    # Match keyDiffs entries: blocks containing "name" and "added" with "key"
    # Pattern: find each entry in keyDiffs that has a name and a JOY_BTN key
    entry_pattern = re.compile(
        r'\["name"\]\s*=\s*"([^"]*)"', re.DOTALL
    )
    key_pattern = re.compile(
        r'\["key"\]\s*=\s*"(JOY_BTN[^"]*)"'
    )

    # Split content into keyDiffs entries by looking for the entry ID pattern
    in_key_diffs = False
    current_block = ""
    brace_depth = 0

    for line in content.split("\n"):
        if '["keyDiffs"]' in line:
            in_key_diffs = True
            continue
        if not in_key_diffs:
            continue

        # Track brace depth to isolate individual entries
        for ch in line:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1

        current_block += line + "\n"

        # When we close back to depth 2, we've completed one entry
        if brace_depth <= 2 and current_block.strip():
            name_match = entry_pattern.search(current_block)
            key_match = key_pattern.search(current_block)
            if name_match and key_match:
                action_name = name_match.group(1)
                button_id = key_match.group(1)
                bindings[button_id] = Binding(
                    button_id=button_id, action_name=action_name
                )
            current_block = ""

    return bindings
