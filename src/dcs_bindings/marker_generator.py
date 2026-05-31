"""Generate helper images with button markers for manual placement."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .models import DeviceMapping


# Marker rendering constants
CIRCLE_RADIUS = 20
CIRCLE_OUTLINE = 2
LINE_WIDTH = 2
SPACING = 45  # space between circle centers in groups
GRID_CELL_W = 200  # grid cell width for layout
GRID_CELL_H = 200  # grid cell height for layout
MARGIN = 40


def _get_font(size=16):
    """Get a suitable font for marker numbers."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except (OSError, IOError):
        try:
            return ImageFont.truetype("arial.ttf", size)
        except (OSError, IOError):
            return ImageFont.load_default()


def _draw_circle(draw, cx, cy, number, font):
    """Draw a single button marker circle."""
    r = CIRCLE_RADIUS
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill="#00cc00", outline="black", width=CIRCLE_OUTLINE
    )
    text = str(number)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - 1), text, fill="black", font=font)


def _draw_line(draw, x1, y1, x2, y2):
    """Draw a connecting line between circles."""
    draw.line([x1, y1, x2, y2], fill="black", width=LINE_WIDTH)


def generate_marker_image(mapping: DeviceMapping, output_path: str, circle_radius: int = 20):
    """Generate a transparent PNG with all button markers laid out in a grid.

    Single buttons are circles. Groups are rendered as connected circles
    in the appropriate layout (vertical, horizontal, hat).
    """
    global CIRCLE_RADIUS
    CIRCLE_RADIUS = circle_radius

    font = _get_font(max(12, circle_radius - 4))

    # Separate grouped and ungrouped buttons
    grouped_buttons = set()
    for group in mapping.groups:
        for btn in group["buttons"]:
            grouped_buttons.add(btn)

    # All mapped button numbers
    all_buttons = sorted(mapping.mappings.keys())
    ungrouped = [b for b in all_buttons if b not in grouped_buttons]

    # Calculate what we need to render
    items = []  # list of (type, data, width, height)

    # Groups first
    for group in mapping.groups:
        buttons = group["buttons"]
        layout = group.get("layout", "vertical")
        # Only include buttons that are in the mapping
        buttons = [b for b in buttons if b in mapping.mappings]
        if len(buttons) < 2:
            continue

        if layout == "hat":
            # Cross: 3 wide, 3 tall
            w = SPACING * 2 + CIRCLE_RADIUS * 2 + MARGIN
            h = SPACING * 2 + CIRCLE_RADIUS * 2 + MARGIN
            items.append(("hat", buttons, w, h))
        elif layout == "horizontal":
            n = len(buttons)
            w = SPACING * (n - 1) + CIRCLE_RADIUS * 2 + MARGIN
            h = CIRCLE_RADIUS * 2 + MARGIN
            items.append(("horizontal", buttons, w, h))
        elif layout == "rotary":
            # 3 positions in arc + push below
            w = SPACING * 2 + CIRCLE_RADIUS * 2 + MARGIN
            h = SPACING + CIRCLE_RADIUS * 2 + MARGIN
            items.append(("rotary", buttons, w, h))
        else:  # vertical
            n = len(buttons)
            w = CIRCLE_RADIUS * 2 + MARGIN
            h = SPACING * (n - 1) + CIRCLE_RADIUS * 2 + MARGIN
            items.append(("vertical", buttons, w, h))

    # Ungrouped buttons
    for btn in ungrouped:
        w = CIRCLE_RADIUS * 2 + MARGIN
        h = CIRCLE_RADIUS * 2 + MARGIN
        items.append(("single", [btn], w, h))

    if not items:
        return

    # Layout items in rows
    max_row_width = 1200
    rows = []
    current_row = []
    current_row_w = 0
    current_row_h = 0

    for item in items:
        item_w = item[2]
        item_h = item[3]
        if current_row and current_row_w + item_w > max_row_width:
            rows.append((current_row, current_row_w, current_row_h))
            current_row = []
            current_row_w = 0
            current_row_h = 0
        current_row.append(item)
        current_row_w += item_w
        current_row_h = max(current_row_h, item_h)

    if current_row:
        rows.append((current_row, current_row_w, current_row_h))

    # Calculate total image size
    total_w = max(row_w for _, row_w, _ in rows) + MARGIN * 2
    total_h = sum(row_h for _, _, row_h in rows) + MARGIN * 2
    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Render each item
    y_offset = MARGIN
    for row_items, row_w, row_h in rows:
        x_offset = MARGIN
        for item_type, buttons, item_w, item_h in row_items:
            # Center vertically in row
            cy_base = y_offset + row_h // 2
            cx_base = x_offset + item_w // 2

            if item_type == "single":
                _draw_circle(draw, cx_base, cy_base, buttons[0], font)

            elif item_type == "horizontal":
                n = len(buttons)
                start_x = cx_base - SPACING * (n - 1) // 2
                for i, btn in enumerate(buttons):
                    cx = start_x + i * SPACING
                    if i > 0:
                        _draw_line(draw, cx - SPACING + CIRCLE_RADIUS, cy_base,
                                   cx - CIRCLE_RADIUS, cy_base)
                    _draw_circle(draw, cx, cy_base, btn, font)

            elif item_type == "vertical":
                n = len(buttons)
                start_y = cy_base - SPACING * (n - 1) // 2
                for i, btn in enumerate(buttons):
                    cy = start_y + i * SPACING
                    if i > 0:
                        _draw_line(draw, cx_base, cy - SPACING + CIRCLE_RADIUS,
                                   cx_base, cy - CIRCLE_RADIUS)
                    _draw_circle(draw, cx_base, cy, btn, font)

            elif item_type == "hat":
                # Cross arrangement
                # Lowest number = center (push), then up, left, down, right
                # Order from mapping file: center, top, right, bottom, left
                if len(buttons) >= 5:
                    center, up, right, down, left = buttons[0], buttons[1], buttons[2], buttons[3], buttons[4]
                elif len(buttons) == 4:
                    up, right, down, left = buttons[0], buttons[1], buttons[2], buttons[3]
                    center = None
                else:
                    # Fallback: render as vertical
                    n = len(buttons)
                    start_y = cy_base - SPACING * (n - 1) // 2
                    for i, btn in enumerate(buttons):
                        cy = start_y + i * SPACING
                        if i > 0:
                            _draw_line(draw, cx_base, cy - SPACING + CIRCLE_RADIUS,
                                       cx_base, cy - CIRCLE_RADIUS)
                        _draw_circle(draw, cx_base, cy, btn, font)
                    x_offset += item_w
                    continue

                # Draw connecting lines
                # Up to center
                _draw_line(draw, cx_base, cy_base - SPACING + CIRCLE_RADIUS,
                           cx_base, cy_base - CIRCLE_RADIUS)
                # Center to down
                _draw_line(draw, cx_base, cy_base + CIRCLE_RADIUS,
                           cx_base, cy_base + SPACING - CIRCLE_RADIUS)
                # Left to center
                _draw_line(draw, cx_base - SPACING + CIRCLE_RADIUS, cy_base,
                           cx_base - CIRCLE_RADIUS, cy_base)
                # Center to right
                _draw_line(draw, cx_base + CIRCLE_RADIUS, cy_base,
                           cx_base + SPACING - CIRCLE_RADIUS, cy_base)

                # Draw circles
                _draw_circle(draw, cx_base, cy_base - SPACING, up, font)  # up
                _draw_circle(draw, cx_base, cy_base + SPACING, down, font)  # down
                _draw_circle(draw, cx_base - SPACING, cy_base, left, font)  # left
                _draw_circle(draw, cx_base + SPACING, cy_base, right, font)  # right
                if center:
                    _draw_circle(draw, cx_base, cy_base, center, font)  # center

            elif item_type == "rotary":
                # Order: pos1, pos2, pos3, push
                # Render: 3 positions in a row with arc, push circle below center
                pos1, pos2, pos3 = buttons[0], buttons[1], buttons[2]
                push = buttons[3] if len(buttons) >= 4 else None

                # 3 positions in a row at top
                top_y = cy_base - SPACING // 3
                left_x = cx_base - SPACING
                right_x = cx_base + SPACING

                # Draw arc connecting the 3 positions
                arc_bbox = [left_x - CIRCLE_RADIUS, top_y - SPACING // 2,
                            right_x + CIRCLE_RADIUS, top_y + SPACING]
                draw.arc(arc_bbox, start=200, end=340, fill="black", width=LINE_WIDTH)

                # Draw position circles
                _draw_circle(draw, left_x, top_y, pos1, font)
                _draw_circle(draw, cx_base, top_y, pos2, font)
                _draw_circle(draw, right_x, top_y, pos3, font)

                # Draw push circle below
                if push:
                    push_y = top_y + SPACING
                    _draw_line(draw, cx_base, top_y + CIRCLE_RADIUS,
                               cx_base, push_y - CIRCLE_RADIUS)
                    _draw_circle(draw, cx_base, push_y, push, font)

            x_offset += item_w
        y_offset += row_h

    img.save(output_path)
    return output_path
