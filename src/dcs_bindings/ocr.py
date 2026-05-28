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

    Modifies markers in-place by setting their .number field.

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

    Returns (number, confidence) or (None, 0) on failure.
    """
    # Calculate ROI with padding
    padding = int(marker.radius * 0.3)
    x1 = max(0, marker.center_x - marker.radius - padding)
    y1 = max(0, marker.center_y - marker.radius - padding)
    x2 = min(image.shape[1], marker.center_x + marker.radius + padding)
    y2 = min(image.shape[0], marker.center_y + marker.radius + padding)

    roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        return None, 0.0

    # Convert to greyscale
    grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Threshold to isolate black text from coloured background
    # Black text on bright background -> threshold and invert
    _, thresh = cv2.threshold(grey, 80, 255, cv2.THRESH_BINARY_INV)

    # Resize to consistent height for better OCR accuracy
    target_height = 48
    scale = target_height / thresh.shape[0]
    resized = cv2.resize(
        thresh,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )

    # Add white border for Tesseract
    bordered = cv2.copyMakeBorder(
        resized, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=0
    )

    # Invert (Tesseract prefers black text on white background)
    final = cv2.bitwise_not(bordered)

    # Run Tesseract with digit-only configuration
    custom_config = (
        "--psm 7 "  # Single text line
        "-c tessedit_char_whitelist=0123456789"
    )

    try:
        # Get detailed output with confidence
        data = pytesseract.image_to_data(
            final, config=custom_config, output_type=pytesseract.Output.DICT
        )

        # Extract text and confidence
        texts = []
        confidences = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if text and text.isdigit():
                texts.append(text)
                conf = float(data["conf"][i])
                confidences.append(conf)

        if texts:
            result_text = "".join(texts)
            avg_confidence = sum(confidences) / len(confidences)

            if avg_confidence >= config.ocr_confidence_threshold:
                try:
                    return int(result_text), avg_confidence
                except ValueError:
                    pass

        # Fallback: simple image_to_string
        text = pytesseract.image_to_string(final, config=custom_config).strip()
        if text.isdigit():
            return int(text), 50.0  # Lower confidence for fallback

    except Exception:
        pass

    return None, 0.0
