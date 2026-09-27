from PIL import Image, ImageDraw

from app.models.label_data import LabelData
from app.renderer.fonts import FontManager
from app.renderer.image_utils import draw_border, draw_wrapped_text, text_size
from app.renderer.qr import generate_qr_image
from app.renderer.templates.common import render_dynamic_template


def render_inventory_template(label_data: LabelData) -> Image.Image:
    return render_dynamic_template(label_data, _draw_inventory)


def _draw_inventory(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    fonts: FontManager,
    label_data: LabelData,
) -> int:
    margin = 18
    y = margin
    max_width = image.width - (margin * 2)
    title_font = fonts.get("large")
    body_font = fonts.get("small")

    # Split lines: Line 1 = Bold Big Title, Line 2+ = Small Text
    raw_title = label_data.title or "INVENTORY ITEM"
    lines = [line.strip() for line in raw_title.split("\n") if line.strip()]
    main_title = lines[0].upper() if lines else "INVENTORY ITEM"
    sub_lines = list(lines[1:])
    if label_data.body:
        for b_line in label_data.body.split("\n"):
            b_line = b_line.strip()
            if b_line and b_line not in sub_lines and b_line.upper() != main_title:
                sub_lines.append(b_line)

    # 1. Line 1: Bold Large Text
    y = draw_wrapped_text(draw, y, main_title, title_font, margin, max_width)
    y += 4

    # 2. Line 2+: Small Text
    for sub in sub_lines:
        y = draw_wrapped_text(draw, y, sub, body_font, margin, max_width)
        y += 4

    shelf = label_data.metadata.get("shelf")
    if shelf:
        draw.text((margin, y), f"Shelf : {shelf}", fill="black", font=body_font)
        y += text_size(draw, f"Shelf : {shelf}", body_font)[1] + 6

    if label_data.quantity is not None:
        draw.text((margin, y), f"Qty : {label_data.quantity}", fill="black", font=body_font)
        y += text_size(draw, f"Qty : {label_data.quantity}", body_font)[1] + 8

    qr_value = label_data.qr_data or main_title
    y = _paste_qr(image, qr_value, y)
    draw_border(draw, image.width, image.height)
    return y


def _paste_qr(image: Image.Image, value: str, y: int) -> int:
    qr_image = generate_qr_image(value, size=112)
    image.paste(qr_image, ((image.width - qr_image.width) // 2, y))
    return y + qr_image.height
