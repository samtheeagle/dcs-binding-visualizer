"""Circle/marker detection using HSV colour isolation and contour analysis."""

from typing import Optional

import cv2
import numpy as np

from .config import DetectionConfig
from .models import DetectedMarker


def detect_markers(
    image_path: str, config: DetectionConfig
) -> list[DetectedMarker]:
    """Detect colour-filled circular markers in a device image.

    Uses HSV colour space thresholding to isolate markers,
    then contour analysis to find circles.

    Args:
        image_path: Path to the device image
        config: Detection configuration parameters

    Returns:
        List of detected markers (without OCR - just positions and radii)
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    # Convert to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Create colour mask based on configured marker colour
    mask = _create_colour_mask(hsv, config)

    # Clean up mask with morphological operations
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours by size and circularity
    markers: list[DetectedMarker] = []
    for contour in contours:
        marker = _validate_contour(contour, config)
        if marker:
            markers.append(marker)

    return markers


def generate_debug_image(
    image_path: str,
    markers: list[DetectedMarker],
    output_path: str,
) -> None:
    """Generate an annotated debug image showing detection results.

    Args:
        image_path: Original image path
        markers: Detected markers
        output_path: Where to save the debug image
    """
    image = cv2.imread(image_path)
    if image is None:
        return

    for marker in markers:
        # Green circle for successful detections
        colour = (0, 255, 0) if marker.confidence >= 60 else (0, 255, 255)
        cv2.circle(
            image, (marker.center_x, marker.center_y), marker.radius, colour, 2
        )
        # Label with detected number
        label = str(marker.number) if marker.number >= 0 else "?"
        cv2.putText(
            image,
            label,
            (marker.center_x + marker.radius + 5, marker.center_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            colour,
            2,
        )

    cv2.imwrite(output_path, image)


def _create_colour_mask(hsv: np.ndarray, config: DetectionConfig) -> np.ndarray:
    """Create a binary mask isolating the marker colour in HSV space."""
    hex_colour = config.marker_colour_hex
    target_hue = _hex_to_hsv_hue(hex_colour)

    hue_low = max(0, target_hue - config.hue_tolerance)
    hue_high = min(179, target_hue + config.hue_tolerance)

    lower = np.array([hue_low, config.saturation_min, config.value_min])
    upper = np.array([hue_high, 255, 255])

    mask = cv2.inRange(hsv, lower, upper)

    # Handle hue wrap-around (for reds near 0/180)
    if hue_low < 0:
        lower2 = np.array([179 + hue_low, config.saturation_min, config.value_min])
        upper2 = np.array([179, 255, 255])
        mask2 = cv2.inRange(hsv, lower2, upper2)
        mask = cv2.bitwise_or(mask, mask2)
    elif hue_high > 179:
        lower2 = np.array([0, config.saturation_min, config.value_min])
        upper2 = np.array([hue_high - 179, 255, 255])
        mask2 = cv2.inRange(hsv, lower2, upper2)
        mask = cv2.bitwise_or(mask, mask2)

    return mask


def _validate_contour(
    contour: np.ndarray, config: DetectionConfig
) -> Optional[DetectedMarker]:
    """Validate a contour as a circular marker.

    Returns a DetectedMarker if valid, None otherwise.
    """
    area = cv2.contourArea(contour)
    if area < config.min_marker_area:
        return None

    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return None

    # Circularity: 4π * area / perimeter²
    circularity = (4 * np.pi * area) / (perimeter * perimeter)
    if circularity < config.circularity_threshold:
        return None

    # Aspect ratio check
    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = w / h if h > 0 else 0
    if aspect_ratio < 0.6 or aspect_ratio > 1.6:
        return None

    # Compute center and radius
    (cx, cy), radius = cv2.minEnclosingCircle(contour)

    return DetectedMarker(
        number=-1,  # Will be filled by OCR step
        center_x=int(cx),
        center_y=int(cy),
        radius=int(radius),
    )


def _hex_to_hsv_hue(hex_colour: str) -> int:
    """Convert a hex colour to its HSV hue value (0-179 OpenCV scale)."""
    hex_colour = hex_colour.lstrip("#")
    r = int(hex_colour[0:2], 16)
    g = int(hex_colour[2:4], 16)
    b = int(hex_colour[4:6], 16)

    # Create a 1x1 pixel BGR image and convert to HSV
    pixel = np.uint8([[[b, g, r]]])
    hsv_pixel = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)

    return int(hsv_pixel[0][0][0])
