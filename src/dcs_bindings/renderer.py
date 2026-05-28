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

        label_text = abbreviate(
            binding.action_name,
            rc.label_max_width,
            lambda t: measure(t)[0],
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
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

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
    draw.rectangle(
        [label.x, label.y, label.right, label.bottom],
        fill=(255, 255, 255),
        outline=(150, 150, 150),
        width=1,
    )

    # Draw text
    text_colour = (30, 30, 30) if rc.background == "white" else (220, 220, 220)
    draw.text(
        (label.x + 5, label.y + 3),
        label.text,
        fill=text_colour,
        font=font,
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
