import base64
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.printer import pil_to_escpos_raster, prepare_image_for_printing


def test_escpos_initialization_and_header():
    """Verify that ESC/POS payload begins with ESC @ (0x1B 0x40) followed by GS v 0 raster header."""
    image = Image.new("RGB", (384, 100), (255, 255, 255))
    payload = pil_to_escpos_raster(image, target_width=384)

    # ESC @ initialization
    assert payload.startswith(b"\x1b\x40")

    # GS v 0 0 xL xH yL yH
    # For width=384 (width_bytes=48: 0x30, 0x00) and height=100 (0x64, 0x00)
    raster_slice = payload[2:10]
    assert raster_slice == b"\x1d\x76\x30\x00\x30\x00\x64\x00"

    # Total payload size: 2 (init) + 8 (header) + 48*100 (bitmap) + 4 (feed)
    assert len(payload) == 2 + 8 + (48 * 100) + 4
    assert payload.endswith(b"\n\n\n\n")


def test_prepare_image_for_printing_preserves_original_and_scales():
    """Verify that original AI image is untouched while 1-bit scaled version is generated."""
    original = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
    prepared = prepare_image_for_printing(original, target_width=384)

    # Original is untouched
    assert original.size == (1024, 1024)
    assert original.mode == "RGBA"

    # Prepared image is 1-bit and 384px wide
    assert prepared.size == (384, 384)
    assert prepared.mode == "1"


def test_escpos_black_pixel_bit_packing():
    """Verify that black pixels become 1-bits and white pixels become 0-bits."""
    # 8x1 image, explicit target_width=8
    image = Image.new("1", (8, 1), 1)  # all white
    image.putpixel((0, 0), 0)          # leftmost black (bit 7)
    image.putpixel((7, 0), 0)          # rightmost black (bit 0)

    payload = pil_to_escpos_raster(image, target_width=8)
    # Init: 2 bytes, Header: 8 bytes, Data: 1 byte, Feed: 4 bytes
    bitmap_byte = payload[10]
    assert bitmap_byte == 0b10000001


def test_print_endpoint_decodes_data_uri_and_returns_printer_result(monkeypatch):
    image = Image.new("RGB", (384, 200), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    calls = []

    def fake_print(decoded, width, height, gap):
        calls.append((decoded.size, width, height, gap))
        return True, "Sent to test printer"

    monkeypatch.setattr("app.routers.print_label", fake_print)
    response = TestClient(app).post("/api/print", json={"image_base64": data_uri})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert calls == [((384, 200), 50, 50, 2)]


def test_print_endpoint_rejects_invalid_image():
    response = TestClient(app).post("/api/print", json={"image_base64": "not base64"})
    assert response.status_code == 422


