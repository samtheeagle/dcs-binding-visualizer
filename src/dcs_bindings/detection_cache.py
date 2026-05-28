"""Cache for detected marker positions, keyed by image file hash."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .models import DetectedMarker

CACHE_DIR = Path(".cache")


def get_cached_markers(image_path: str) -> Optional[list[DetectedMarker]]:
    """Load cached marker positions for an image if the cache is valid.

    Returns None if no valid cache exists (image changed or no cache file).
    """
    cache_file = _get_cache_path(image_path)
    if not cache_file.exists():
        return None

    current_hash = _compute_image_hash(image_path)

    try:
        with open(cache_file, "r") as f:
            data = yaml.safe_load(f)
    except Exception:
        return None

    if not data or data.get("image_hash") != current_hash:
        return None

    # Reconstruct markers from cache
    markers: list[DetectedMarker] = []
    for entry in data.get("positions", []):
        markers.append(
            DetectedMarker(
                number=entry["number"],
                center_x=entry["x"],
                center_y=entry["y"],
                radius=entry.get("radius", 15),
                confidence=entry.get("confidence", 100.0),
            )
        )

    return markers


def save_markers_to_cache(
    image_path: str,
    markers: list[DetectedMarker],
    marker_colour: str = "green",
) -> None:
    """Save detected marker positions to cache file.

    Args:
        image_path: Path to the source image
        markers: Detected markers to cache
        marker_colour: The marker colour used for detection
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _get_cache_path(image_path)

    data = {
        "image_hash": _compute_image_hash(image_path),
        "image_path": image_path,
        "detection_timestamp": datetime.now().isoformat(),
        "marker_colour": marker_colour,
        "positions": [
            {
                "number": m.number,
                "x": m.center_x,
                "y": m.center_y,
                "radius": m.radius,
                "confidence": m.confidence,
            }
            for m in markers
        ],
    }

    with open(cache_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def invalidate_cache(image_path: str) -> None:
    """Delete the cache file for an image."""
    cache_file = _get_cache_path(image_path)
    if cache_file.exists():
        cache_file.unlink()


def _get_cache_path(image_path: str) -> Path:
    """Get the cache file path for a given image."""
    # Use image filename (without extension) + _positions.yaml
    image_name = Path(image_path).stem
    return CACHE_DIR / f"{image_name}_positions.yaml"


def _compute_image_hash(image_path: str) -> str:
    """Compute SHA256 hash of an image file."""
    sha256 = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
