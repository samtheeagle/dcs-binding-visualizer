"""OCR module for reading numbers from detected markers using Tesseract."""

import cv2
import numpy as np
import pytesseract

from .config import DetectionConfig
from .models import DetectedMarker


def read_marker_numbers(
    image_path: str, markers: list[DetectedMarker], config: DetectionConfig
) -> list[DetectedMarker]:
    """Read the number inside each detected marker using OCR.

    Args:
        image_path: Path to the device image
        markers: List of detected markers (with positions but number=-1)
        config: Detection configuration

    Returns:
        Updated markers with numbers read (markers with failed OCR are removed)
    """
    image = cv2.imread(image_path)
    if image is None:
        return []

    successful: list[DetectedMarker] = []

    for marker in markers:
        number, confidence = _read_number_from_roi(image, marker, config)
        if number is not None:
            marker.number = number
            marker.confidence = confidence
            successful.append(marker)

    return successful


def _read_number_from_roi(
    image: np.ndarray, marker: DetectedMarker, config: DetectionConfig
) -> tuple[int | None, float]:
    """Extract and OCR the number from a single marker region.

    Approach: mask out the green fill, leaving only the number as
    dark pixels on a white background. Scale up and OCR.

    Returns (number, confidence) or (None, 0) on failure.
    """
    padding = 2
    x1 = max(0, marker.center_x - marker.radius - padding)
    y1 = max(0, marker.center_y - marker.radius - padding)
    x2 = min(image.shape[1], marker.center_x + marker.radius + padding)
    y2 = min(image.shape[0], marker.center_y + marker.radius + padding)

    roi = image[y1:y2, x1:x2].copy()
    if roi.size == 0:
        return None, 0.0

    # Mask out the marker colour — what remains is the number
    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hex_colour = config.marker_colour_hex
    target_hue = _get_target_hue(hex_colour)
    hue_low = max(0, target_hue - config.hue_tolerance)
    hue_high = min(179, target_hue + config.hue_tolerance)

    green_mask = cv2.inRange(
        roi_hsv,
        np.array([hue_low, config.saturation_min, config.value_min]),
        np.array([hue_high, 255, 255]),
    )

    # Convert to greyscale, set green pixels to white (background)
    grey_base = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    grey_base[green_mask > 0] = 255

    result, confidence = _ocr_with_shrink(grey_base, marker, 1, config)

    # If result has more digits than the circle can fit (3+ digits in a small circle),
    # retry with a tighter mask to remove edge artifacts
    if result is not None and len(str(result)) > 2 and marker.radius <= 17:
        result2, confidence2 = _ocr_with_shrink(grey_base, marker, 2, config)
        if result2 is not None:
            result, confidence = result2, confidence2

    return result, confidence


def _ocr_with_shrink(
    grey_base: np.ndarray, marker: DetectedMarker, shrink: int, config: DetectionConfig
) -> tuple[int | None, float]:
    """Run OCR on the marker with a given circle mask shrink value."""
    grey = grey_base.copy()
    h, w = grey.shape
    circle_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(circle_mask, (w // 2, h // 2), marker.radius - shrink, 255, -1)
    grey[circle_mask == 0] = 255

    # Scale up for OCR
    scale = max(6, 96 // max(h, 1))
    big = cv2.resize(grey, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Threshold to clean binary image
    _, final = cv2.threshold(big, 180, 255, cv2.THRESH_BINARY)

    # Add border
    final = cv2.copyMakeBorder(final, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    # Run Tesseract
    custom_config = "--psm 8 -c tessedit_char_whitelist=0123456789"

    try:
        data = pytesseract.image_to_data(
            final, config=custom_config, output_type=pytesseract.Output.DICT
        )

        texts = []
        confidences = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if text and text.isdigit():
                texts.append(text)
                confidences.append(float(data["conf"][i]))

        if texts:
            result_text = "".join(texts)
            avg_confidence = sum(confidences) / len(confidences)
            if avg_confidence >= config.ocr_confidence_threshold:
                try:
                    return int(result_text), avg_confidence
                except ValueError:
                    pass

        # Fallback
        text = pytesseract.image_to_string(final, config=custom_config).strip()
        if text.isdigit():
            return int(text), 50.0

    except Exception:
        pass

    return None, 0.0


def _get_target_hue(hex_colour: str) -> int:
    """Convert hex colour to OpenCV HSV hue (0-179)."""
    hex_colour = hex_colour.lstrip("#")
    r = int(hex_colour[0:2], 16)
    g = int(hex_colour[2:4], 16)
    b = int(hex_colour[4:6], 16)
    pixel = np.uint8([[[b, g, r]]])
    hsv_pixel = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)
    return int(hsv_pixel[0][0][0])
