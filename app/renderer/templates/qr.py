from PIL import Image, ImageDraw

from app.models.label_data import LabelData
from app.renderer.fonts import FontManager
from app.renderer.image_utils import center_image, draw_centered_text, draw_wrapped_text
from app.renderer.qr import generate_qr_image
from app.renderer.templates.common import render_dynamic_template


def render_qr_template(label_data: LabelData) -> Image.Image:
    return render_dynamic_template(label_data, _draw_qr)


def _draw_qr(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    fonts: FontManager,
    label_data: LabelData,
) -> int:
    margin = 16
    y = margin
    data = label_data.qr_data or label_data.body or label_data.title or "https://printsensei.local"

    # 1. Render QR Code prominently at the top (no text above)
    qr_size = 144
    qr_img = generate_qr_image(data, size=qr_size)
    y = center_image(image, qr_img, y)
    y += 12

    # 2. Only print caption below the QR code
    caption = label_data.title or label_data.body or data
    if caption:
        y = draw_wrapped_text(
            draw,
            y,
            caption,
            fonts.get("small"),
            margin,
            image.width - (margin * 2),
        )
    return y
