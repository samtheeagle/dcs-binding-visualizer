"""Image rendering engine - composes the final A4 output PNG."""

import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .abbreviations import abbreviate
from .config import AppConfig, RenderingConfig
from .layout import place_labels
from .models import Binding, ButtonPosition, LabelBox, RenderJob



def render_binding_image(
    job: RenderJob,
    left_positions: list[ButtonPosition],
    right_positions: list[ButtonPosition],
    left_image_path: str,
    right_image_path: str,
    config: AppConfig,
    output_path: Optional[str] = None,
) -> str:
    """Render a complete binding image for one aircraft/seat.

    Args:
        job: The render job with aircraft name, seat, and bindings
        left_positions: Button positions for the left device
        right_positions: Button positions for the right device
        left_image_path: Path to left device image
        right_image_path: Path to right device image
        config: Application configuration
        output_path: Override output path (optional)

    Returns:
        Path to the generated output image
    """
    rc = config.rendering
    canvas_w = rc.canvas_width
    canvas_h = rc.canvas_height

    # Create canvas
    bg_colour = (255, 255, 255) if rc.background == "white" else (30, 30, 30)
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_colour)
    draw = ImageDraw.Draw(canvas)

    # Load font
    font = _load_font(rc.font_family, rc.font_size, rc.dpi)
    title_font = _load_font(rc.font_family, rc.title_font_size, rc.dpi)

    # Draw title
    title_h = _draw_title(draw, job.title, title_font, canvas_w, rc)

    # Available area for devices
    content_top = title_h + 10
    content_h = canvas_h - content_top - rc.margin

    # Split canvas into left and right halves
    half_w = (canvas_w - rc.device_spacing) // 2

    # Render left device
    left_area = (rc.margin, content_top, half_w - rc.margin, content_h)
    _render_device(
        canvas, draw, left_image_path, left_positions,
        job.bindings, left_area, font, rc,
    )

    # Render right device
    right_offset = half_w + rc.device_spacing
    right_area = (right_offset + rc.margin, content_top,
                  canvas_w - right_offset - rc.margin, content_h)
    _render_device(
        canvas, draw, right_image_path, right_positions,
        job.bindings, right_area, font, rc,
    )

    # Save output
    if output_path is None:
        output_dir = config.output.output_dir
        os.makedirs(output_dir, exist_ok=True)
        filename = job.aircraft_name
        if job.seat:
            filename += f"_{job.seat}"
        filename += ".png"
        output_path = os.path.join(output_dir, filename)

    canvas.save(output_path, "PNG", dpi=(rc.dpi, rc.dpi))
    return output_path



def _render_device(
    canvas: Image.Image,
    draw: ImageDraw.Draw,
    image_path: str,
    positions: list[ButtonPosition],
    bindings: dict[str, Binding],
    area: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
    rc: RenderingConfig,
) -> None:
    """Render a single device image with labels onto the canvas."""
    area_x, area_y, area_w, area_h = area

    # Load and scale device image
    try:
        device_img = Image.open(image_path).convert("RGB")
    except (FileNotFoundError, Exception):
        return

    # Scale to fit area while maintaining aspect ratio
    img_w, img_h = device_img.size
    scale = min(area_w / img_w, area_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)

    device_img = device_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Center the device image in the area
    offset_x = area_x + (area_w - new_w) // 2
    offset_y = area_y + (area_h - new_h) // 2

    canvas.paste(device_img, (offset_x, offset_y))

    # Scale button positions to match the rendered image
    buttons_for_layout = []
    for pos in positions:
        # Look up binding for this button
        binding = bindings.get(pos.dcs_button_id)
        if not binding:
            continue

        # Scale position
        scaled_x = int(pos.x * scale) + offset_x
        scaled_y = int(pos.y * scale) + offset_y

        # Abbreviate text if needed
        def measure(text):
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Convert ALL CAPS words to Title Case for readability
        action_name = _title_case(binding.action_name)

        label_text = _wrap_text(
            action_name,
            rc.label_max_width,
            font,
        )

        if binding.has_modifier:
            label_text += " [M]"

        buttons_for_layout.append({
            "text": label_text,
            "x": scaled_x,
            "y": scaled_y,
            "has_modifier": binding.has_modifier,
        })

    # Run label placement
    def measure_fn(text):
        lines = text.split("\n")
        max_w = 0
        total_h = 0
        for line in lines:
            bbox = font.getbbox(line)
            max_w = max(max_w, bbox[2] - bbox[0])
            total_h += bbox[3] - bbox[1]
        # Add line spacing
        total_h += (len(lines) - 1) * 2
        return max_w, total_h

    # Detect hat groups (cross patterns) and replace with composite labels
    buttons_for_layout = _group_hat_buttons(buttons_for_layout, measure_fn)

    labels = place_labels(
        buttons_for_layout,
        measure_fn,
        canvas.width,
        canvas.height,
        rc.leader_line_threshold,
    )

    # Draw labels
    for label in labels:
        _draw_label(draw, label, font, rc)



def _draw_label(
    draw: ImageDraw.Draw,
    label: LabelBox,
    font: ImageFont.FreeTypeFont,
    rc: RenderingConfig,
) -> None:
    """Draw a single label box with background, border, and text."""
    # Semi-transparent background
    bg_opacity = int(rc.label_opacity * 255)
    bg_colour = (255, 255, 255, bg_opacity) if rc.background == "white" else (40, 40, 40, bg_opacity)

    # Draw background rectangle
    # (transparent - no fill)

    # Draw text
    text_colour = (30, 30, 30) if rc.background == "white" else (220, 220, 220)
    draw.multiline_text(
        (label.x + 5, label.y + 3),
        label.text,
        fill=text_colour,
        font=font,
        spacing=2,
        align="center",
    )

    # Draw leader line if needed
    if label.needs_leader_line:
        _draw_leader_line(draw, label)


def _draw_leader_line(draw: ImageDraw.Draw, label: LabelBox) -> None:
    """Draw a leader line from label edge to button position."""
    # Find the closest edge point of the label to the button
    label_cx = label.x + label.width // 2
    label_cy = label.y + label.height // 2

    # Determine which edge to connect from
    if label.button_x < label.x:
        start_x = label.x
    elif label.button_x > label.right:
        start_x = label.right
    else:
        start_x = label.button_x

    if label.button_y < label.y:
        start_y = label.y
    elif label.button_y > label.bottom:
        start_y = label.bottom
    else:
        start_y = label.button_y

    draw.line(
        [(start_x, start_y), (label.button_x, label.button_y)],
        fill=(120, 120, 120),
        width=1,
    )
    # Small dot at button end
    r = 3
    draw.ellipse(
        [label.button_x - r, label.button_y - r,
         label.button_x + r, label.button_y + r],
        fill=(120, 120, 120),
    )


def _draw_title(
    draw: ImageDraw.Draw,
    title: str,
    font: ImageFont.FreeTypeFont,
    canvas_w: int,
    rc: RenderingConfig,
) -> int:
    """Draw the title at the top of the canvas. Returns title height."""
    bbox = font.getbbox(title)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = (canvas_w - text_w) // 2
    y = rc.margin // 2

    text_colour = (30, 30, 30) if rc.background == "white" else (220, 220, 220)
    draw.text((x, y), title, fill=text_colour, font=font)

    return y + text_h + 10


def _title_case(text: str) -> str:
    """Convert words that are ALL CAPS to Title Case, leave acronyms (≤3 chars) unchanged."""
    words = text.split()
    result = []
    for word in words:
        stripped = word.strip("-/()[]")
        if len(stripped) > 3 and stripped == stripped.upper() and stripped.isalpha():
            result.append(word.capitalize())
        else:
            result.append(word)
    return " ".join(result)


def _group_hat_buttons(
    buttons: list[dict],
    measure_fn,
) -> list[dict]:
    """Detect cross-pattern button groups (hat switches) and merge into composite labels.

    Detects 4 buttons arranged in a cross pattern (up/down/left/right).
    A 5th center button is included if present.
    """
    if len(buttons) < 4:
        return buttons

    def short_name(text):
        parts = text.replace("\n", " ").split(" - ")
        if len(parts) > 1:
            return parts[-1].strip()
        return text.replace("\n", " ").strip()

    used = set()
    result = []

    # For each button, check if it could be the "up" of a cross
    # by looking for down (same x, below), left (same y, to left), right (same y, to right)
    tolerance = 25  # pixels tolerance for alignment

    for i, btn_up in enumerate(buttons):
        if i in used:
            continue

        # Look for a button directly below (same x ± tolerance, further y)
        down_idx = None
        for j, btn in enumerate(buttons):
            if j == i or j in used:
                continue
            if abs(btn["x"] - btn_up["x"]) < tolerance and 50 < (btn["y"] - btn_up["y"]) < 150:
                down_idx = j
                break

        if down_idx is None:
            continue

        btn_down = buttons[down_idx]
        # The center y of the cross
        mid_y = (btn_up["y"] + btn_down["y"]) // 2
        mid_x = btn_up["x"]

        # Look for left and right at mid_y
        left_idx = right_idx = center_idx = None
        for j, btn in enumerate(buttons):
            if j in (i, down_idx) or j in used:
                continue
            if abs(btn["y"] - mid_y) < tolerance:
                if -150 < (btn["x"] - mid_x) < -30:
                    left_idx = j
                elif 30 < (btn["x"] - mid_x) < 150:
                    right_idx = j
                elif abs(btn["x"] - mid_x) < tolerance:
                    center_idx = j

        if left_idx is None and right_idx is None and center_idx is None:
            continue  # need at least one of left, right, or center to form a group

        # Found a cross pattern (possibly partial)
        used.update([i, down_idx])
        if left_idx is not None:
            used.add(left_idx)
        if right_idx is not None:
            used.add(right_idx)
        if center_idx is not None:
            used.add(center_idx)

        btn_left = buttons[left_idx] if left_idx is not None else None
        btn_right = buttons[right_idx] if right_idx is not None else None
        btn_center = buttons[center_idx] if center_idx is not None else None

        # Get common prefix from any of the directional buttons
        full = btn_up["text"].replace("\n", " ")
        parts = full.split(" - ")
        prefix = parts[0] if len(parts) > 1 else ""

        u = short_name(btn_up["text"])
        d = short_name(btn_down["text"])
        l = short_name(btn_left["text"]) if btn_left else ""
        r = short_name(btn_right["text"]) if btn_right else ""
        c = short_name(btn_center["text"]) if btn_center else ""

        # Build compact cross layout - only show arrows when bound
        u_str = f"↑ {u}" if u else ""
        d_str = f"↓ {d}" if d else ""
        l_str = f"← {l}" if l else ""
        r_str = f"→ {r}" if r else ""
        c_str = f"● {c}" if c else ""
        composite = f"{prefix}\n{u_str}\n{l_str}\t{c_str}\t{r_str}\n{d_str}"

        result.append({
            "text": composite,
            "x": mid_x,
            "y": mid_y,
            "has_modifier": False,
        })

    # Second pass: detect horizontal rows (3 buttons at same y)
    remaining = [i for i in range(len(buttons)) if i not in used]
    for i in remaining:
        if i in used:
            continue
        btn_i = buttons[i]
        # Find all buttons at the same y
        row = [i]
        for j in remaining:
            if j == i or j in used:
                continue
            if abs(buttons[j]["y"] - btn_i["y"]) < tolerance and abs(buttons[j]["x"] - btn_i["x"]) < 150:
                row.append(j)

        if len(row) < 3:
            continue

        # Sort by x to determine left/center/right
        row.sort(key=lambda idx: buttons[idx]["x"])

        if len(row) == 3:
            left_idx, center_idx, right_idx = row
        else:
            continue

        used.update(row)

        btn_l = buttons[left_idx]
        btn_c = buttons[center_idx] if center_idx is not None else None
        btn_r = buttons[right_idx]

        # Extract prefix from any button
        source = btn_c if btn_c else btn_l
        full = source["text"].replace("\n", " ")
        parts = full.split(" - ")
        prefix = parts[0] if len(parts) > 1 else ""

        l_name = short_name(btn_l["text"])
        m_name = short_name(btn_c["text"]) if btn_c else ""
        r_name = short_name(btn_r["text"])

        l_str = f"← {l_name}" if l_name else ""
        m_str = f"● {m_name}" if m_name else ""
        r_str = f"→ {r_name}" if r_name else ""

        composite = f"{prefix}\n\n{l_str}\t{m_str}\t{r_str}\n"

        mid_x = buttons[center_idx]["x"] if center_idx is not None else (btn_l["x"] + btn_r["x"]) // 2
        mid_y = btn_l["y"]

        result.append({
            "text": composite,
            "x": mid_x,
            "y": mid_y,
            "has_modifier": False,
        })

    # Add remaining ungrouped buttons
    for i, btn in enumerate(buttons):
        if i not in used:
            result.append(btn)

    return result


def _wrap_text(text: str, max_width: int, font: ImageFont.FreeTypeFont) -> str:
    """Wrap text to fit within max_width, breaking on word boundaries."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = font.getbbox(test)
        width = bbox[2] - bbox[0]
        if width <= max_width or not current_line:
            current_line = test
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


def _load_font(
    family: str, size_pt: int, dpi: int
) -> ImageFont.FreeTypeFont:
    """Load a font at the specified point size and DPI."""
    # Convert pt to pixels: px = pt * dpi / 72
    size_px = int(size_pt * dpi / 72)

    # Try to find the font
    font_paths = [
        # Bundled font
        Path("fonts") / f"{family.replace(' ', '')}.ttf",
        Path("fonts") / "DejaVuSans.ttf",
        # System paths (Linux)
        Path(f"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(f"/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),
        Path(f"/usr/share/fonts/TTF/DejaVuSans.ttf"),
        # macOS
        Path("/System/Library/Fonts/Helvetica.ttc"),
        # Windows
        Path("C:/Windows/Fonts/arial.ttf"),
    ]

    for font_path in font_paths:
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size_px)
            except Exception:
                continue

    # Fallback to default
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size_px)
    except Exception:
        return ImageFont.load_default()


def _group_by_mapping(buttons: list[dict], groups: list[dict]) -> list[dict]:
    """Group buttons using explicit group definitions from the mapping file."""

    def short_name(text):
        parts = text.replace("\n", " ").split(" - ")
        if len(parts) > 1:
            return parts[-1].strip()
        return text.replace("\n", " ").strip()

    btn_by_num = {b["image_number"]: b for b in buttons}
    used = set()
    result = []

    for group in groups:
        group_buttons = group["buttons"]
        layout = group.get("layout", "vertical")

        # Find which buttons in this group have bindings
        members = [btn_by_num[n] for n in group_buttons if n in btn_by_num]
        if len(members) < 2:
            continue

        used.update(b["image_number"] for b in members)

        # Sort by position
        if layout == "horizontal":
            members.sort(key=lambda b: b["x"])
        else:
            members.sort(key=lambda b: b["y"])

        # Get prefix from first member
        full = members[0]["text"].replace("\n", " ")
        parts = full.split(" - ")
        prefix = parts[0] if len(parts) > 1 else ""

        # Center position
        cx = sum(b["x"] for b in members) // len(members)
        cy = sum(b["y"] for b in members) // len(members)

        if layout == "hat" and len(members) >= 4:
            # Determine directions by position relative to center
            up = down = left = right = center = None
            for b in members:
                dx = b["x"] - cx
                dy = b["y"] - cy
                if abs(dx) < 20 and dy < -20:
                    up = b
                elif abs(dx) < 20 and dy > 20:
                    down = b
                elif dx < -20 and abs(dy) < 20:
                    left = b
                elif dx > 20 and abs(dy) < 20:
                    right = b
                elif abs(dx) < 20 and abs(dy) < 20:
                    center = b

            u = short_name(up["text"]) if up else ""
            d = short_name(down["text"]) if down else ""
            l = short_name(left["text"]) if left else ""
            r = short_name(right["text"]) if right else ""
            c = short_name(center["text"]) if center else ""

            u_str = f"↑ {u}" if u else ""
            d_str = f"↓ {d}" if d else ""
            l_str = f"← {l}" if l else ""
            r_str = f"→ {r}" if r else ""
            c_str = f"● {c}" if c else ""
            composite = f"{prefix}\n{u_str}\n{l_str}\t{c_str}\t{r_str}\n{d_str}"
        elif layout == "vertical":
            names = [short_name(b["text"]) for b in members]
            u_str = f"↑ {names[0]}" if names[0] else ""
            d_str = f"↓ {names[-1]}" if names[-1] else ""
            c_str = ""
            if len(members) == 3:
                c_str = f"● {names[1]}" if names[1] else ""
            composite = f"{prefix}\n{u_str}\n\t{c_str}\t\n{d_str}"
        else:  # horizontal
            names = [short_name(b["text"]) for b in members]
            l_str = f"← {names[0]}" if names[0] else ""
            r_str = f"→ {names[-1]}" if names[-1] else ""
            c_str = ""
            if len(members) == 3:
                c_str = f"● {names[1]}" if names[1] else ""
            composite = f"{prefix}\n\n{l_str}\t{c_str}\t{r_str}\n"

        result.append({
            "text": composite,
            "x": cx,
            "y": cy,
            "has_modifier": False,
        })

    # Add ungrouped buttons
    for b in buttons:
        if b["image_number"] not in used:
            result.append(b)

    return result


def render_binding_svg(
    job: RenderJob,
    positions: list[ButtonPosition],
    image_path: str,
    bindings: dict[str, Binding],
    config: AppConfig,
    output_path: str,
    groups: list[dict] = None,
) -> str:
    """Render an editable SVG with device image and positioned labels.

    Labels are individual text elements that can be moved in Inkscape.
    Leader lines connect labels to button group centers.
    """
    import base64

    rc = config.rendering

    # Load image to get dimensions
    try:
        img = Image.open(image_path)
        img_w, img_h = img.size
    except Exception:
        return output_path

    # SVG canvas matches image size
    svg_w = img_w
    svg_h = img_h

    # Embed image as base64
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Determine image mime type
    ext = Path(image_path).suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"

    # Build label data — use same hat grouping as PNG renderer
    bound_buttons = []
    for pos in positions:
        binding = bindings.get(pos.dcs_button_id)
        if not binding:
            continue
        action_name = _title_case(binding.action_name)
        bound_buttons.append({
            "text": action_name,
            "x": pos.x,
            "y": pos.y,
            "image_number": pos.image_number,
        })

    # Group buttons using explicit groups from mapping file, or fall back to spatial heuristics
    if groups:
        bound_buttons = _group_by_mapping(bound_buttons, groups)
    else:
        def measure_fn(text):
            lines_list = text.split("\n")
            max_w = max(len(l) * 8 for l in lines_list)
            total_h = len(lines_list) * 16
            return max_w, total_h
        bound_buttons = _group_hat_buttons(bound_buttons, measure_fn)

    # Build SVG
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}">')
    lines.append(f'  <image href="data:{mime};base64,{img_b64}" width="{svg_w}" height="{svg_h}"/>')

    font_size = max(14, round(svg_w / 80))
    line_h = font_size + 2
    char_w = font_size * 0.6
    pad = 8

    # Compute bounding box for a hat group label given anchor (cx, cy = top-left of first row text baseline)
    def _hat_group_bbox(btn, cx, cy):
        text_lines = btn["text"].split("\n")
        middle_parts = text_lines[2].split("\t")
        cell_h = line_h
        if len(middle_parts) == 3:
            col_widths = [len(middle_parts[i]) * char_w + pad for i in range(3)]
        elif len(middle_parts) == 2:
            col_widths = [len(middle_parts[0]) * char_w + pad, pad, len(middle_parts[1]) * char_w + pad]
        else:
            col_widths = [len(text_lines[2]) * char_w + pad, 0, 0]
        top_row_w = max(len(text_lines[0]), len(text_lines[1]), len(text_lines[3])) * char_w + pad
        table_w = max(sum(col_widths), top_row_w)
        table_h = cell_h * 4
        # bbox: (x, y, w, h) where x,y is top-left
        return (cx - table_w / 2, cy - font_size, table_w, table_h)

    def _rects_intersect(r1, r2):
        x1, y1, w1, h1 = r1
        x2, y2, w2, h2 = r2
        return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)

    def _out_of_bounds(rect, img_w, img_h):
        x, y, w, h = rect
        return x < 0 or y < 0 or x + w > img_w or y + h > img_h

    # Load image for background sampling
    import cv2
    import numpy as np
    _bg_img = cv2.imread(str(image_path))
    _bg_gray = cv2.cvtColor(_bg_img, cv2.COLOR_BGR2GRAY) if _bg_img is not None else None

    def _non_white_ratio(rect):
        """Sample the image under rect and return ratio of non-white pixels."""
        if _bg_gray is None:
            return 0.0
        x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
        x = max(0, x)
        y = max(0, y)
        x2 = min(x + w, _bg_gray.shape[1])
        y2 = min(y + h, _bg_gray.shape[0])
        if x2 <= x or y2 <= y:
            return 0.0
        region = _bg_gray[y:y2, x:x2]
        non_white = np.count_nonzero(region < 240)
        total = region.size
        return non_white / total if total > 0 else 0.0

    def _count_collisions(rect, placed_rects, img_w, img_h):
        count = 0
        if _out_of_bounds(rect, img_w, img_h):
            count += 100  # heavy penalty for out of bounds
        for pr in placed_rects:
            if _rects_intersect(rect, pr):
                count += 10
        # Add non-white pixel ratio as a fractional score
        count += _non_white_ratio(rect) * 5
        return count

    # Placement offsets for 8 positions around group center
    # 12, 3, 6, 9, then 1:30, 4:30, 7:30, 10:30
    group_radius = max(65, round(svg_w / 17))  # scale with image size
    def _candidate_positions(btn):
        """Return list of (cx, cy) for the label anchor at 8 clock positions."""
        gx, gy = btn["x"], btn["y"]
        text_lines = btn["text"].split("\n")
        middle_parts = text_lines[2].split("\t")
        cell_h = line_h
        if len(middle_parts) == 3:
            col_widths = [len(middle_parts[i]) * char_w + pad for i in range(3)]
        elif len(middle_parts) == 2:
            col_widths = [len(middle_parts[0]) * char_w + pad, pad, len(middle_parts[1]) * char_w + pad]
        else:
            col_widths = [len(text_lines[2]) * char_w + pad, 0, 0]
        top_row_w = max(len(text_lines[0]), len(text_lines[1]), len(text_lines[3])) * char_w + pad
        table_w = max(sum(col_widths), top_row_w)
        table_h = cell_h * 4

        r = group_radius
        # cy is the first tspan y; bbox top = cy - font_size, bbox bottom = cy - font_size + table_h
        # For 12 o'clock: bbox bottom must be above gy - r, so cy = gy - r - table_h + font_size
        positions = [
            (gx, gy - r - table_h + font_size),                # 12: table bottom clears top buttons
            (gx + r + table_w / 2, gy - table_h / 2 + font_size),  # 3: centered vertically
            (gx, gy + r + font_size),                           # 6: table top below bottom buttons
            (gx - r - table_w / 2, gy - table_h / 2 + font_size),  # 9: centered vertically
            (gx + r * 0.7 + table_w / 2, gy - r * 0.7 - table_h / 2 + font_size),  # 1:30
            (gx + r * 0.7 + table_w / 2, gy + r * 0.7 - table_h / 2 + font_size),  # 4:30
            (gx - r * 0.7 - table_w / 2, gy + r * 0.7 - table_h / 2 + font_size),  # 7:30
            (gx - r * 0.7 - table_w / 2, gy - r * 0.7 - table_h / 2 + font_size),  # 10:30
        ]
        return positions

    # First pass: place hat group labels with collision avoidance
    # Start with button marker positions as obstacles
    placed_rects = []
    for pos in positions:
        # Each button marker is a circle of ~17px radius
        placed_rects.append((pos.x - 17, pos.y - 17, 34, 34))

    group_placements = {}  # index -> (cx, cy)

    for i, btn in enumerate(bound_buttons):
        text_lines = btn["text"].split("\n")
        if len(text_lines) != 4:
            continue

        candidates = _candidate_positions(btn)
        best_pos = candidates[0]
        best_collisions = float('inf')

        for cx, cy in candidates:
            bbox = _hat_group_bbox(btn, cx, cy)
            collisions = _count_collisions(bbox, placed_rects, svg_w, svg_h)
            if collisions == 0:
                best_pos = (cx, cy)
                best_collisions = 0
                break
            if collisions < best_collisions:
                best_collisions = collisions
                best_pos = (cx, cy)

        group_placements[i] = best_pos
        placed_rects.append(_hat_group_bbox(btn, best_pos[0], best_pos[1]))

    # Second pass: place single button labels with collision avoidance
    single_radius = max(25, round(svg_w / 45))  # scale with image size
    single_placements = {}  # index -> (lx, ly)

    for i, btn in enumerate(bound_buttons):
        text_lines = btn["text"].split("\n")
        if len(text_lines) != 1:
            continue

        text = btn["text"]
        gx, gy = btn["x"], btn["y"]
        label_w = len(text) * char_w + pad
        label_h = line_h

        r = single_radius
        candidates = [
            (gx, gy - r - label_h + font_size),                # 12
            (gx + r + label_w / 2, gy),                         # 3
            (gx, gy + r + font_size),                           # 6
            (gx - r - label_w / 2, gy),                         # 9
            (gx + r * 0.7 + label_w / 2, gy - r * 1.0),        # 1:30
            (gx + r * 0.7 + label_w / 2, gy + r * 0.7),        # 4:30
            (gx - r * 0.7 - label_w / 2, gy + r * 0.7),        # 7:30
            (gx - r * 0.7 - label_w / 2, gy - r * 0.7),        # 10:30
        ]

        best_pos = candidates[0]
        best_collisions = float('inf')

        for lx, ly in candidates:
            bbox = (lx - label_w / 2, ly - font_size, label_w, label_h)
            collisions = _count_collisions(bbox, placed_rects, svg_w, svg_h)
            if collisions == 0:
                best_pos = (lx, ly)
                best_collisions = 0
                break
            if collisions < best_collisions:
                best_collisions = collisions
                best_pos = (lx, ly)

        single_placements[i] = best_pos
        lx, ly = best_pos
        placed_rects.append((lx - label_w / 2, ly - font_size, label_w, label_h))

    # Labels layer
    lines.append(f'  <g id="labels" font-family="DejaVu Sans, sans-serif" font-size="{font_size}">')
    for i, btn in enumerate(bound_buttons):
        text = btn["text"]
        num = btn.get("image_number", "grp")
        label_id = f"btn-{num}"
        text_lines = text.split("\n")

        if len(text_lines) == 1:
            # Single button label, placed by collision avoidance
            lx, ly = single_placements[i]
            escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f'    <text x="{lx}" y="{ly}" id="{label_id}" text-anchor="middle">{escaped}</text>')
        elif len(text_lines) == 4:
            cx, cy = group_placements[i]
            prefix = text_lines[0]
            up = text_lines[1]
            middle_parts = text_lines[2].split("\t")
            down = text_lines[3]

            def esc(s):
                return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            cell_h = line_h
            if len(middle_parts) == 3:
                col_widths = [len(middle_parts[j]) * char_w + pad for j in range(3)]
            elif len(middle_parts) == 2:
                col_widths = [len(middle_parts[0]) * char_w + pad, pad, len(middle_parts[1]) * char_w + pad]
            else:
                col_widths = [len(text_lines[2]) * char_w + pad, 0, 0]

            top_row_w = max(len(prefix), len(up), len(down)) * char_w + pad
            table_w = max(sum(col_widths), top_row_w)
            if sum(col_widths) < table_w:
                extra = (table_w - sum(col_widths)) / 3
                col_widths = [w + extra for w in col_widths]

            table_x = cx - table_w / 2

            # Text elements — align center stack to middle column
            left_cx = table_x + col_widths[0] / 2
            mid_cx = table_x + col_widths[0] + col_widths[1] / 2
            right_cx = table_x + col_widths[0] + col_widths[1] + col_widths[2] / 2

            mid_left = table_x + col_widths[0]  # left edge of middle column

            lines.append(f'    <g id="{label_id}">')
            lines.append(f'      <text x="{cx}" y="{cy}" text-anchor="middle">{esc(prefix)}</text>')
            lines.append(f'      <text x="{mid_left:.0f}" y="{cy + cell_h}">{esc(up)}</text>')
            if len(middle_parts) == 3:
                lines.append(f'      <text x="{left_cx:.0f}" y="{cy + cell_h * 2}" text-anchor="middle">{esc(middle_parts[0])}</text>')
                lines.append(f'      <text x="{mid_left:.0f}" y="{cy + cell_h * 2}">{esc(middle_parts[1])}</text>')
                lines.append(f'      <text x="{right_cx:.0f}" y="{cy + cell_h * 2}" text-anchor="middle">{esc(middle_parts[2])}</text>')
            elif len(middle_parts) == 2:
                lines.append(f'      <text x="{left_cx:.0f}" y="{cy + cell_h * 2}" text-anchor="middle">{esc(middle_parts[0])}</text>')
                lines.append(f'      <text x="{right_cx:.0f}" y="{cy + cell_h * 2}" text-anchor="middle">{esc(middle_parts[1])}</text>')
            lines.append(f'      <text x="{mid_left:.0f}" y="{cy + cell_h * 3}">{esc(down)}</text>')
            lines.append(f'    </g>')
        else:
            # Fallback for other multiline
            lx = btn["x"]
            ly = btn["y"] - 20
            lines.append(f'    <text x="{lx}" y="{ly}" id="{label_id}" text-anchor="middle">')
            for idx, tl in enumerate(text_lines):
                escaped = tl.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                lines.append(f'      <tspan x="{lx}" y="{ly + idx * line_h}">{escaped}</tspan>')
            lines.append(f'    </text>')
    lines.append('  </g>')

    lines.append('</svg>')

    svg_content = "\n".join(lines)
    with open(output_path, "w") as f:
        f.write(svg_content)

    return output_path
