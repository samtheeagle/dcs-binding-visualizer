"""Text abbreviation rules for long DCS binding names."""

# Common suffixes to remove
REMOVABLE_SUFFIXES = [
    " Button",
    " Switch",
    " Btn",
    " - Toggle",
    " Toggle",
    " Lever",
]

# Known abbreviations (full term -> short form)
ABBREVIATIONS = {
    "Countermeasures": "CM",
    "Countermeasure": "CM",
    "Communication": "Comm",
    "Communications": "Comms",
    "Electronic": "Elec",
    "Weapons": "Wpn",
    "Weapon": "Wpn",
    "Navigation": "Nav",
    "Autopilot": "A/P",
    "Disconnect": "Disc",
    "Forward": "Fwd",
    "Backward": "Bwd",
    "Landing": "Ldg",
    "Master": "Mstr",
    "Caution": "Caut",
    "Warning": "Warn",
    "Release": "Rel",
    "Dispense": "Disp",
    "Dispenser": "Disp",
    "Select": "Sel",
    "Selected": "Sel",
    "Management": "Mgmt",
    "Display": "Disp",
    "Control": "Ctrl",
    "Designator": "Desig",
    "Designate": "Desig",
    "Undesignate": "Undesig",
    "Emergency": "Emerg",
    "External": "Ext",
    "Internal": "Int",
    "Throttle": "Thrtl",
    "Targeting": "Tgt",
    "Target": "Tgt",
    "Jettison": "Jett",
    "Override": "Ovrd",
    "Altitude": "Alt",
    "Airspeed": "AS",
    "Heading": "Hdg",
    "Increase": "Inc",
    "Decrease": "Dec",
    "Frequency": "Freq",
    "Channel": "Ch",
    "Volume": "Vol",
    "Brightness": "Brt",
    "Contrast": "Cont",
    "Position": "Pos",
    "Selector": "Sel",
    "Indicator": "Ind",
    "Arresting": "Arr",
}


def abbreviate(text: str, max_width: int, font_measure_fn=None) -> str:
    """Abbreviate a binding name to fit within max_width.

    Applies progressively more aggressive abbreviation:
    1. Remove common suffixes
    2. Apply known abbreviations
    3. Truncate with ellipsis

    Args:
        text: Full binding name
        max_width: Maximum pixel width allowed
        font_measure_fn: Function that takes text and returns pixel width.
            If None, uses character count * 7 as estimate.

    Returns:
        Abbreviated text that fits within max_width
    """
    if font_measure_fn is None:
        font_measure_fn = lambda t: len(t) * 7  # rough estimate

    # Check if original fits
    if font_measure_fn(text) <= max_width:
        return text

    # Level 1: Remove suffixes
    shortened = _remove_suffixes(text)
    if font_measure_fn(shortened) <= max_width:
        return shortened

    # Level 2: Apply abbreviations
    shortened = _apply_abbreviations(shortened)
    if font_measure_fn(shortened) <= max_width:
        return shortened

    # Level 3: Truncate with ellipsis
    return _truncate(shortened, max_width, font_measure_fn)


def _remove_suffixes(text: str) -> str:
    """Remove common suffixes from binding names."""
    for suffix in REMOVABLE_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text.strip()


def _apply_abbreviations(text: str) -> str:
    """Replace known long terms with abbreviations."""
    result = text
    for full, short in ABBREVIATIONS.items():
        # Case-insensitive replacement preserving boundaries
        import re

        pattern = re.compile(re.escape(full), re.IGNORECASE)
        result = pattern.sub(short, result)
    return result


def _truncate(text: str, max_width: int, font_measure_fn) -> str:
    """Truncate text with ellipsis to fit within max_width."""
    ellipsis = "..."
    # Binary search for the right length
    for length in range(len(text), 0, -1):
        candidate = text[:length] + ellipsis
        if font_measure_fn(candidate) <= max_width:
            return candidate
    return ellipsis
