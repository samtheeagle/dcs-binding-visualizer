"""Button number mapping - translates image numbers to DCS button IDs."""

import platform
from pathlib import Path
from typing import Optional

import yaml

from .models import ButtonPosition, DetectedMarker, DeviceMapping


def load_device_mapping(mapping_path: str) -> DeviceMapping:
    """Load a device button mapping file.

    Args:
        mapping_path: Path to the YAML mapping file

    Returns:
        DeviceMapping with all mappings loaded
    """
    with open(mapping_path, "r") as f:
        data = yaml.safe_load(f)

    mappings = {}
    raw_mappings = data.get("mappings", {})
    for key, value in raw_mappings.items():
        mappings[int(key)] = str(value)

    linux_overrides = {}
    raw_overrides = data.get("linux_overrides", {})
    if raw_overrides:
        for key, value in raw_overrides.items():
            linux_overrides[int(key)] = str(value)

    axes = data.get("axes", [])

    return DeviceMapping(
        device_name=data.get("device_name", ""),
        device_name_alt=data.get("device_name_alt", ""),
        description=data.get("description", ""),
        mappings=mappings,
        linux_overrides=linux_overrides,
        axes=axes,
    )


def resolve_button_positions(
    markers: list[DetectedMarker],
    mapping: DeviceMapping,
    use_linux_overrides: Optional[bool] = None,
) -> list[ButtonPosition]:
    """Combine detected marker positions with button ID mappings.

    Args:
        markers: Detected markers with positions and numbers
        mapping: Device mapping (image number -> DCS button ID)
        use_linux_overrides: Force Linux overrides on/off.
            None = auto-detect based on current OS.

    Returns:
        List of ButtonPosition objects with DCS button IDs and positions
    """
    # Determine which mapping set to use
    if use_linux_overrides is None:
        use_linux_overrides = platform.system() == "Linux"

    if use_linux_overrides and mapping.linux_overrides:
        active_mappings = mapping.linux_overrides
    else:
        active_mappings = mapping.mappings

    positions: list[ButtonPosition] = []

    for marker in markers:
        if marker.number in active_mappings:
            button_id = active_mappings[marker.number]
            # Get description from the base mappings comments (if available)
            positions.append(
                ButtonPosition(
                    image_number=marker.number,
                    dcs_button_id=button_id,
                    x=marker.center_x,
                    y=marker.center_y,
                )
            )

    return positions
