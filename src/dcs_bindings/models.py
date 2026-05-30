"""Data models for DCS Binding Visualizer."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DetectedMarker:
    """A marker detected in a device image via colour isolation + OCR."""

    number: int
    center_x: int
    center_y: int
    radius: int
    confidence: float = 100.0


@dataclass
class ButtonPosition:
    """A button's position on a device image, linked to its DCS ID."""

    image_number: int
    dcs_button_id: str
    x: int
    y: int
    description: str = ""


@dataclass
class Binding:
    """A single DCS binding assignment."""

    button_id: str  # e.g., "JOY_BTN1", "JOY_BTN_POV1_U"
    action_name: str  # e.g., "Weapon Release"
    category: str = ""  # e.g., "weapons", "navigation"
    modifiers: list[str] = field(default_factory=list)

    @property
    def has_modifier(self) -> bool:
        return len(self.modifiers) > 0


@dataclass
class DeviceConfig:
    """Configuration for a single physical device."""

    name: str
    image_path: str
    button_mapping_path: str
    position: str  # "left" or "right"


@dataclass
class DeviceMapping:
    """Button number mapping for a device (loaded from YAML)."""

    device_name: str
    device_name_alt: str = ""
    description: str = ""
    mappings: dict[int, str] = field(default_factory=dict)  # image_number -> DCS button ID
    axes: list[dict[str, str]] = field(default_factory=list)
    groups: list[dict] = field(default_factory=list)  # [{buttons: [1,2,3], layout: "vertical"}]


@dataclass
class LabelBox:
    """A positioned label ready for rendering."""

    text: str
    x: int
    y: int
    width: int
    height: int
    button_x: int  # original button position (for leader lines)
    button_y: int
    has_modifier: bool = False
    needs_leader_line: bool = False

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def overlaps(self, other: "LabelBox") -> bool:
        """Check if this label box overlaps with another."""
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )

    def distance_to_button(self) -> float:
        """Calculate distance from label center to its button."""
        label_cx = self.x + self.width // 2
        label_cy = self.y + self.height // 2
        return ((label_cx - self.button_x) ** 2 + (label_cy - self.button_y) ** 2) ** 0.5


@dataclass
class AircraftProfile:
    """An aircraft with its detected seats and bindings."""

    name: str  # DCS internal name, e.g., "FA-18C_hornet"
    display_name: str = ""
    seats: list[str] = field(default_factory=list)  # e.g., ["Pilot", "CPG"]
    seat_dirs: dict[str, str] = field(default_factory=dict)  # seat_name -> actual dir name

    @property
    def is_multi_seat(self) -> bool:
        return len(self.seats) > 1

    @property
    def seat_count(self) -> int:
        return max(1, len(self.seats))


@dataclass
class RenderJob:
    """A single rendering task (one aircraft + one seat = one output image)."""

    aircraft_name: str
    seat: Optional[str] = None  # None for single-seat aircraft
    bindings: dict[str, Binding] = field(default_factory=dict)  # button_id -> Binding
    output_path: str = ""

    @property
    def title(self) -> str:
        if self.seat:
            return f"{self.aircraft_name} — {self.seat}"
        return self.aircraft_name
