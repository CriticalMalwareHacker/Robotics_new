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
    margin = 20
    y = margin
    data = label_data.qr_data or label_data.body or label_data.title or "https://printsensei.local"

    # Render clean standalone QR code centered on the label (no text above or below)
    qr_size = 280
    qr_img = generate_qr_image(data, size=qr_size)
    y = center_image(image, qr_img, y)
    y += margin
    return y
