"""Label placement algorithm with collision avoidance and force-directed nudging."""

from typing import Callable, Optional

from .models import LabelBox


# 8 candidate positions around a button (dx_factor, dy_factor relative to label size)
PLACEMENT_CANDIDATES = [
    (1.8, -0.3),   # Right of button
    (-2.8, -0.3),  # Left of button
    (-0.5, -2.0),  # Above button
    (-0.5, 1.8),   # Below button
    (1.5, -1.8),   # Upper-right diagonal
    (1.5, 1.5),    # Lower-right diagonal
    (-2.5, -1.8),  # Upper-left diagonal
    (-2.5, 1.5),   # Lower-left diagonal
]



def place_labels(
    buttons: list[dict],
    measure_text_fn: Callable[[str], tuple[int, int]],
    canvas_width: int,
    canvas_height: int,
    leader_line_threshold: int = 50,
) -> list[LabelBox]:
    """Place labels for all buttons using anti-collision algorithm.

    Args:
        buttons: List of dicts with keys: text, x, y, has_modifier
        measure_text_fn: Function(text) -> (width, height) in pixels
        canvas_width: Total canvas width
        canvas_height: Total canvas height
        leader_line_threshold: Distance threshold for leader lines

    Returns:
        List of positioned LabelBox objects
    """
    # Sort buttons top-to-bottom, left-to-right
    sorted_buttons = sorted(buttons, key=lambda b: (b["y"], b["x"]))

    # Compute center of all buttons for relative placement
    if sorted_buttons:
        avg_x = sum(b["x"] for b in sorted_buttons) / len(sorted_buttons)
        avg_y = sum(b["y"] for b in sorted_buttons) / len(sorted_buttons)
    else:
        avg_x = canvas_width / 2
        avg_y = canvas_height / 2

    placed: list[LabelBox] = []

    for btn in sorted_buttons:
        text = btn["text"]
        btn_x = btn["x"]
        btn_y = btn["y"]
        has_mod = btn.get("has_modifier", False)

        w, h = measure_text_fn(text)
        # Add padding
        w += 10
        h += 6

        # Determine preferred placement direction based on button position
        # relative to the group center
        candidates = _get_oriented_candidates(btn_x, btn_y, avg_x, avg_y)

        label = _try_place(
            text, btn_x, btn_y, w, h, has_mod, placed, canvas_width, canvas_height,
            candidates,
        )
        if label:
            label.needs_leader_line = (
                label.distance_to_button() > leader_line_threshold
            )
            placed.append(label)

    return placed


def _get_oriented_candidates(
    btn_x: int, btn_y: int, center_x: float, center_y: float
) -> list[tuple[float, float]]:
    """Return placement candidates ordered by the button's position relative to center."""
    # If button is left of center, prefer placing label to the left
    # If button is right of center, prefer placing label to the right
    # Same logic for above/below
    left = btn_x < center_x
    above = btn_y < center_y

    if left and above:
        return [
            (-2.8, -1.8),  # Upper-left
            (-2.8, -0.3),  # Left
            (-0.5, -2.0),  # Above
            (-2.5, 1.5),   # Lower-left
            (1.8, -0.3),   # Right
            (1.5, -1.8),   # Upper-right
            (-0.5, 1.8),   # Below
            (1.5, 1.5),    # Lower-right
        ]
    elif left and not above:
        return [
            (-2.8, -0.3),  # Left
            (-2.5, 1.5),   # Lower-left
            (-0.5, 1.8),   # Below
            (-2.8, -1.8),  # Upper-left
            (1.8, -0.3),   # Right
            (1.5, 1.5),    # Lower-right
            (-0.5, -2.0),  # Above
            (1.5, -1.8),   # Upper-right
        ]
    elif not left and above:
        return [
            (1.8, -0.3),   # Right
            (1.5, -1.8),   # Upper-right
            (-0.5, -2.0),  # Above
            (1.5, 1.5),    # Lower-right
            (-2.8, -0.3),  # Left
            (-2.8, -1.8),  # Upper-left
            (-0.5, 1.8),   # Below
            (-2.5, 1.5),   # Lower-left
        ]
    else:  # right and below
        return [
            (1.8, -0.3),   # Right
            (1.5, 1.5),    # Lower-right
            (-0.5, 1.8),   # Below
            (1.5, -1.8),   # Upper-right
            (-2.8, -0.3),  # Left
            (-2.5, 1.5),   # Lower-left
            (-0.5, -2.0),  # Above
            (-2.8, -1.8),  # Upper-left
        ]



def _try_place(
    text: str,
    btn_x: int,
    btn_y: int,
    width: int,
    height: int,
    has_modifier: bool,
    placed: list[LabelBox],
    canvas_width: int,
    canvas_height: int,
    candidates: list[tuple[float, float]] = None,
) -> Optional[LabelBox]:
    """Try to place a label using the 8-position candidate algorithm.

    Falls back to extended displacement and force-directed nudging.
    """
    if candidates is None:
        candidates = PLACEMENT_CANDIDATES

    # Phase 1: Try candidate positions at normal distance
    for dx_factor, dy_factor in candidates:
        x = btn_x + int(dx_factor * width * 0.5)
        y = btn_y + int(dy_factor * height)
        label = LabelBox(
            text=text, x=x, y=y, width=width, height=height,
            button_x=btn_x, button_y=btn_y, has_modifier=has_modifier,
        )
        if _is_valid_placement(label, placed, canvas_width, canvas_height):
            return label

    # Phase 2: Extended displacement (try further out)
    for multiplier in [1.5, 2.0, 2.5, 3.0]:
        for dx_factor, dy_factor in candidates:
            x = btn_x + int(dx_factor * width * 0.5 * multiplier)
            y = btn_y + int(dy_factor * height * multiplier)
            label = LabelBox(
                text=text, x=x, y=y, width=width, height=height,
                button_x=btn_x, button_y=btn_y, has_modifier=has_modifier,
            )
            if _is_valid_placement(label, placed, canvas_width, canvas_height):
                return label

    # Phase 3: Force-directed nudge from the best candidate
    best = _find_least_overlap_position(
        text, btn_x, btn_y, width, height, has_modifier, placed
    )
    if best:
        nudged = _force_directed_nudge(best, placed, canvas_width, canvas_height)
        return nudged

    # Last resort: place at first candidate position regardless of overlap
    x = btn_x + int(PLACEMENT_CANDIDATES[0][0] * width * 0.5)
    y = btn_y + int(PLACEMENT_CANDIDATES[0][1] * height)
    return LabelBox(
        text=text, x=x, y=y, width=width, height=height,
        button_x=btn_x, button_y=btn_y, has_modifier=has_modifier,
    )



def _is_valid_placement(
    label: LabelBox, placed: list[LabelBox], canvas_width: int, canvas_height: int
) -> bool:
    """Check if a label placement is valid (no overlaps, within bounds)."""
    # Bounds check
    if label.x < 0 or label.y < 0:
        return False
    if label.right > canvas_width or label.bottom > canvas_height:
        return False

    # Overlap check
    for existing in placed:
        if label.overlaps(existing):
            return False

    return True


def _find_least_overlap_position(
    text: str,
    btn_x: int,
    btn_y: int,
    width: int,
    height: int,
    has_modifier: bool,
    placed: list[LabelBox],
) -> Optional[LabelBox]:
    """Find the position with minimum overlap among candidates."""
    best_label = None
    best_overlap_count = float("inf")

    for dx_factor, dy_factor in PLACEMENT_CANDIDATES:
        x = btn_x + int(dx_factor * width * 0.5)
        y = btn_y + int(dy_factor * height)
        label = LabelBox(
            text=text, x=x, y=y, width=width, height=height,
            button_x=btn_x, button_y=btn_y, has_modifier=has_modifier,
        )
        overlap_count = sum(1 for p in placed if label.overlaps(p))
        if overlap_count < best_overlap_count:
            best_overlap_count = overlap_count
            best_label = label

    return best_label


def _force_directed_nudge(
    label: LabelBox,
    placed: list[LabelBox],
    canvas_width: int,
    canvas_height: int,
    max_iterations: int = 50,
) -> LabelBox:
    """Apply force-directed nudging to resolve remaining overlaps."""
    x, y = float(label.x), float(label.y)

    for _ in range(max_iterations):
        force_x, force_y = 0.0, 0.0

        for existing in placed:
            test_label = LabelBox(
                text=label.text, x=int(x), y=int(y),
                width=label.width, height=label.height,
                button_x=label.button_x, button_y=label.button_y,
            )
            if test_label.overlaps(existing):
                # Repulsive force away from overlapping label
                dx = (x + label.width / 2) - (existing.x + existing.width / 2)
                dy = (y + label.height / 2) - (existing.y + existing.height / 2)
                dist = max(1, (dx * dx + dy * dy) ** 0.5)
                force_x += dx / dist * 5
                force_y += dy / dist * 5

        # Attractive force toward button
        dx_btn = label.button_x - (x + label.width / 2)
        dy_btn = label.button_y - (y + label.height / 2)
        dist_btn = max(1, (dx_btn * dx_btn + dy_btn * dy_btn) ** 0.5)
        force_x += dx_btn / dist_btn * 1
        force_y += dy_btn / dist_btn * 1

        x += force_x
        y += force_y

        # Clamp to canvas
        x = max(0, min(x, canvas_width - label.width))
        y = max(0, min(y, canvas_height - label.height))

        if abs(force_x) < 0.5 and abs(force_y) < 0.5:
            break

    return LabelBox(
        text=label.text, x=int(x), y=int(y),
        width=label.width, height=label.height,
        button_x=label.button_x, button_y=label.button_y,
        has_modifier=label.has_modifier,
        needs_leader_line=True,
    )
