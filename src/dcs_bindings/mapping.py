"""Button number mapping - translates image numbers to DCS button IDs."""

from pathlib import Path

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

    axes = data.get("axes", [])

    return DeviceMapping(
        device_name=data.get("device_name", ""),
        device_name_alt=data.get("device_name_alt", ""),
        description=data.get("description", ""),
        mappings=mappings,
        axes=axes,
    )


def resolve_button_positions(
    markers: list[DetectedMarker],
    mapping: DeviceMapping,
) -> list[ButtonPosition]:
    """Combine detected marker positions with button ID mappings.

    Args:
        markers: Detected markers with positions and numbers
        mapping: Device mapping (image number -> DCS button ID)

    Returns:
        List of ButtonPosition objects with DCS button IDs and positions
    """
    positions: list[ButtonPosition] = []

    for marker in markers:
        if marker.number in mapping.mappings:
            button_id = mapping.mappings[marker.number]
            positions.append(
                ButtonPosition(
                    image_number=marker.number,
                    dcs_button_id=button_id,
                    x=marker.center_x,
                    y=marker.center_y,
                )
            )

    return positions
