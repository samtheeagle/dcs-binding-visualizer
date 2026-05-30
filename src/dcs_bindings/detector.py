"""Circle/marker detection using HSV colour isolation and contour analysis."""

import cv2
import numpy as np

from .config import DetectionConfig
from .models import DetectedMarker


def detect_markers(
    image_path: str, config: DetectionConfig
) -> list[DetectedMarker]:
    """Detect colour-filled circular markers in a device image.

    Approach:
    1. Find green blobs (areas that are mostly the marker colour)
    2. For each blob, check if the bounding region is roughly circular
    3. Return center and radius for each valid marker

    Args:
        image_path: Path to the device image
        config: Detection configuration parameters

    Returns:
        List of detected markers (without OCR - just positions and radii)
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Create colour mask
    mask = _create_colour_mask(hsv, config)

    # Light noise removal
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Find connected components (blobs of green)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Pre-filter noise, keep anything that could be part of a marker
    contours = [c for c in contours if cv2.contourArea(c) >= 100]

    # Merge nearby contours that are likely one circle split by the number
    contours = _merge_nearby_contours(contours)

    markers: list[DetectedMarker] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < config.min_marker_area:
            continue

        # Get bounding box of this blob
        x, y, w, h = cv2.boundingRect(contour)

        # Aspect ratio check — should be roughly square
        ar = w / h if h > 0 else 0
        if ar < 0.6 or ar > 1.6:
            continue

        # Check green density: what fraction of the bounding box is green?
        roi_mask = mask[y:y+h, x:x+w]
        green_ratio = cv2.countNonZero(roi_mask) / (w * h)
        if green_ratio < 0.5:
            continue

        # Compute center and radius from bounding box
        cx = x + w // 2
        cy = y + h // 2
        radius = max(w, h) // 2

        markers.append(DetectedMarker(
            number=-1,
            center_x=cx,
            center_y=cy,
            radius=radius,
        ))

    return markers


def _merge_nearby_contours(contours: list) -> list:
    """Merge contours whose bounding box centers are very close together.

    When a number cuts through the green fill, it splits one circle into
    two contours. This merges them back into one combined contour.
    """
    if len(contours) < 2:
        return contours

    # Compute centers and radii for all contours
    info = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        info.append((x + w // 2, y + h // 2, max(w, h) // 2, c))

    merged = []
    used = set()

    for i in range(len(info)):
        if i in used:
            continue
        cx1, cy1, r1, c1 = info[i]
        partner = None
        for j in range(i + 1, len(info)):
            if j in used:
                continue
            cx2, cy2, r2, c2 = info[j]
            dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
            if dist < max(r1, r2) * 2:
                partner = j
                break

        if partner is not None:
            used.add(partner)
            # Concatenate the two contours into one
            merged.append(np.vstack([c1, info[partner][3]]))
        else:
            merged.append(c1)

    return merged


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
        # Green circle for successful detections, yellow for OCR failures
        colour = (0, 255, 0) if marker.number >= 0 and marker.confidence >= 60 else (0, 255, 255)
        cv2.circle(
            image, (marker.center_x, marker.center_y), marker.radius, colour, 2
        )
        # Label with detected number in red
        label = str(marker.number) if marker.number >= 0 else "?"
        cv2.putText(
            image,
            label,
            (marker.center_x + marker.radius + 5, marker.center_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
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
