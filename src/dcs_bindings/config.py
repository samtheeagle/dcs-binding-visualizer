"""Configuration loading and validation for DCS Binding Visualizer."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .models import DeviceConfig

DEFAULT_CONFIG_FILENAME = "config.yaml"

# Default detection settings
DEFAULT_DETECTION = {
    "marker_colour": "green",
    "hue_tolerance": 15,
    "saturation_min": 100,
    "value_min": 100,
    "min_marker_area": 300,
    "ocr_confidence_threshold": 60,
}

# Default rendering settings
DEFAULT_RENDERING = {
    "dpi": 300,
    "background": "white",
    "font_family": "DejaVu Sans",
    "font_size": 9,
    "title_font_size": 24,
    "label_opacity": 0.85,
    "label_max_width": 200,
    "leader_line_threshold": 50,
    "margin": 40,
    "device_spacing": 20,
}

# Default output settings
DEFAULT_OUTPUT = {
    "format": "png",
    "page_size": "A4",
    "orientation": "landscape",
    "output_dir": "output/",
}

# Colour presets (name -> hex)
COLOUR_PRESETS = {
    "green": "#00FF00",
    "magenta": "#FF00FF",
    "cyan": "#00FFFF",
}


@dataclass
class DetectionConfig:
    """Detection-related configuration."""

    marker_colour: str = "green"
    hue_tolerance: int = 15
    saturation_min: int = 100
    value_min: int = 100
    min_marker_area: int = 300
    ocr_confidence_threshold: int = 60

    @property
    def marker_colour_hex(self) -> str:
        """Resolve preset name to hex, or return hex directly."""
        if self.marker_colour.startswith("#"):
            return self.marker_colour
        return COLOUR_PRESETS.get(self.marker_colour, COLOUR_PRESETS["green"])


@dataclass
class RenderingConfig:
    """Rendering-related configuration."""

    dpi: int = 300
    background: str = "white"
    font_family: str = "DejaVu Sans"
    font_size: int = 9
    title_font_size: int = 24
    label_opacity: float = 0.85
    label_max_width: int = 200
    leader_line_threshold: int = 50
    margin: int = 40
    device_spacing: int = 20

    @property
    def canvas_width(self) -> int:
        """A4 landscape width in pixels at configured DPI."""
        return int(11.69 * self.dpi)  # A4 = 297mm = 11.69in

    @property
    def canvas_height(self) -> int:
        """A4 landscape height in pixels at configured DPI."""
        return int(8.27 * self.dpi)  # A4 = 210mm = 8.27in


@dataclass
class OutputConfig:
    """Output-related configuration."""

    format: str = "png"
    page_size: str = "A4"
    orientation: str = "landscape"
    output_dir: str = "output/"


@dataclass
class AppConfig:
    """Complete application configuration."""

    dcs_install_dir: str = ""
    dcs_saved_games_dir: str = ""
    devices: list[DeviceConfig] = field(default_factory=list)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    rendering: RenderingConfig = field(default_factory=RenderingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @property
    def input_config_path(self) -> Path:
        """Path to the DCS input config directory."""
        return Path(self.dcs_saved_games_dir) / "Config" / "Input"

    def validate(self) -> list[str]:
        """Validate configuration, return list of error messages."""
        errors = []

        if not self.dcs_saved_games_dir:
            errors.append("DCS saved games directory not configured")
        elif not Path(self.dcs_saved_games_dir).exists():
            errors.append(
                f"DCS saved games directory not found: {self.dcs_saved_games_dir}"
            )

        if not self.devices:
            errors.append("No devices configured")

        for device in self.devices:
            if not Path(device.image_path).exists():
                errors.append(f"Device image not found: {device.image_path}")
            if not Path(device.button_mapping_path).exists():
                errors.append(
                    f"Button mapping not found: {device.button_mapping_path}"
                )

        return errors


def load_config(config_path: Optional[str] = None) -> Optional[AppConfig]:
    """Load configuration from a YAML file.

    Returns None if the config file doesn't exist.
    """
    path = Path(config_path or DEFAULT_CONFIG_FILENAME)
    if not path.exists():
        return None

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    return _parse_config(data)


def save_config(config: AppConfig, config_path: Optional[str] = None) -> None:
    """Save configuration to a YAML file."""
    path = Path(config_path or DEFAULT_CONFIG_FILENAME)

    data: dict[str, Any] = {
        "dcs": {
            "install_dir": config.dcs_install_dir,
            "saved_games_dir": config.dcs_saved_games_dir,
        },
        "devices": [
            {
                "name": d.name,
                "image": d.image_path,
                "button_mapping": d.button_mapping_path,
                "position": d.position,
            }
            for d in config.devices
        ],
        "detection": {
            "marker_colour": config.detection.marker_colour,
            "hue_tolerance": config.detection.hue_tolerance,
            "saturation_min": config.detection.saturation_min,
            "value_min": config.detection.value_min,
            "min_marker_area": config.detection.min_marker_area,
            "ocr_confidence_threshold": config.detection.ocr_confidence_threshold,
        },
        "rendering": {
            "dpi": config.rendering.dpi,
            "background": config.rendering.background,
            "font_family": config.rendering.font_family,
            "font_size": config.rendering.font_size,
            "title_font_size": config.rendering.title_font_size,
            "label_opacity": config.rendering.label_opacity,
            "label_max_width": config.rendering.label_max_width,
            "leader_line_threshold": config.rendering.leader_line_threshold,
            "margin": config.rendering.margin,
            "device_spacing": config.rendering.device_spacing,
        },
        "output": {
            "format": config.output.format,
            "page_size": config.output.page_size,
            "orientation": config.output.orientation,
            "output_dir": config.output.output_dir,
        },
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _parse_config(data: dict[str, Any]) -> AppConfig:
    """Parse raw YAML data into an AppConfig."""
    dcs = data.get("dcs", {})
    detection_data = {**DEFAULT_DETECTION, **data.get("detection", {})}
    rendering_data = {**DEFAULT_RENDERING, **data.get("rendering", {})}
    output_data = {**DEFAULT_OUTPUT, **data.get("output", {})}

    devices = []
    for d in data.get("devices", []):
        devices.append(
            DeviceConfig(
                name=d.get("name", ""),
                image_path=d.get("image", ""),
                button_mapping_path=d.get("button_mapping", ""),
                position=d.get("position", "left"),
            )
        )

    return AppConfig(
        dcs_install_dir=dcs.get("install_dir", ""),
        dcs_saved_games_dir=dcs.get("saved_games_dir", ""),
        devices=devices,
        detection=DetectionConfig(**detection_data),
        rendering=RenderingConfig(**rendering_data),
        output=OutputConfig(**output_data),
    )
