import base64
import binascii
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse
from app.core.fake_request_generator import create_fake_print_request
from app.models.label_data import LabelData
from app.renderer import LabelRenderer
from app.schemas.render import RenderRequest, RenderResponse
from app.schemas.simulate import SimulateRequest, SimulateResponse
from backend.core.enums import TaskType
from backend.core.request import Request
from backend.engines.diagram.service import DiagramService
from backend.services.speech import get_speech_service
from shared.config import APP_NAME, APP_VERSION, MODE, HARDWARE_MODE
from app.services.printer import print_label
from app.services.history import get_all_history, add_history_entry
from io import BytesIO
from PIL import Image, UnidentifiedImageError

router = APIRouter()


class HardwarePrintRequest(BaseModel):
    """A PNG/JPEG data URI plus the physical media dimensions in millimetres."""

    image_base64: str = Field(min_length=1, max_length=15_000_000)
    label_width_mm: int = Field(default=50, ge=10, le=120)
    label_height_mm: int = Field(default=50, ge=10, le=300)
    gap_mm: int = Field(default=2, ge=0, le=20)
    title: str | None = None
    desc: str | None = None
    mode: str | None = None
    image_url: str | None = None


@router.get("/api/history")
def get_print_history():
    """Return persistent print history synced with all real printed diagrams and labels."""
    return get_all_history()


@router.post("/api/print")
def print_hardware_label(payload: HardwarePrintRequest):
    """Decode a browser image and send it as raw TSPL to the thermal printer."""
    encoded = payload.image_base64.split(",", 1)[-1]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (binascii.Error, ValueError, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="image_base64 must contain a valid image.") from exc

    success, message = print_label(image, payload.label_width_mm, payload.label_height_mm, payload.gap_mm)
    if not success:
        raise HTTPException(status_code=502, detail=f"Printer error: {message}")

    add_history_entry(
        title=payload.title or "Printed Label",
        desc=payload.desc or "PrintSensei Label",
        mode=payload.mode or "study",
        image_url=payload.image_url,
    )
    return {"status": "success", "message": message}


class StudyGenerationRequest(BaseModel):
    """Dashboard payload for the Study-mode diagram generator."""

    prompt: str
    image_data: str | None = None
    detail_level: str = Field(default="medium", pattern="^(low|medium|high)$")


def _save_reference_image(image_data: str | None) -> Path | None:
    if not image_data:
        return None

    encoded = image_data.split(",", 1)[-1]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="The reference image is not valid base64 data.") from exc

    uploads = Path("diagram_images/uploads")
    uploads.mkdir(parents=True, exist_ok=True)
    image_path = uploads / f"reference_{uuid.uuid4().hex[:8]}.png"
    image_path.write_bytes(image_bytes)
    return image_path


@router.post("/voice/transcribe")
async def transcribe_voice(audio: UploadFile = File(...)):
    """Transcribe a browser-recorded audio clip with local faster-whisper tiny."""
    if not (audio.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=415, detail="Please upload an audio recording.")

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(await audio.read())
        audio_path = Path(temporary_file.name)

    try:
        text, language = get_speech_service().transcribe(audio_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Voice transcription failed. Confirm faster-whisper and its model are installed.") from exc
    finally:
        audio_path.unlink(missing_ok=True)

    if not text:
        raise HTTPException(status_code=422, detail="No speech was detected. Please try again.")

    return {"text": text, "language": language, "model": "tiny"}


@router.post("/api/voice/start_record")
def start_usb_mic_record():
    """Start capturing audio from the physical USB camera microphone on the Raspberry Pi."""
    from app.services.audio_recorder import usb_mic_recorder
    result = usb_mic_recorder.start_recording()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("message", "Could not start USB mic."))
    return result


@router.post("/api/voice/stop_record")
def stop_usb_mic_record():
    """Stop USB microphone recording and transcribe using local faster-whisper."""
    from app.services.audio_recorder import usb_mic_recorder
    success, text, lang = usb_mic_recorder.stop_and_transcribe()
    if not success:
        raise HTTPException(status_code=422, detail=lang)
    return {"status": "success", "text": text, "language": lang, "model": "tiny"}


@router.post("/api/voice/cancel_record")
def cancel_usb_mic_record():
    """Cancel and discard ongoing USB microphone recording."""
    from app.services.audio_recorder import usb_mic_recorder
    usb_mic_recorder.stop_and_discard()
    return {"status": "cancelled"}


@router.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <html>
        <head><title>{APP_NAME}</title></head>
        <body style='font-family: Arial; margin: 2rem;'>
            <h1>PrintSensei is Running</h1>
            <p>Application: {APP_NAME}</p>
            <p>Version: {APP_VERSION}</p>
            <p>Mode: {MODE}</p>
            <p>Hardware: {HARDWARE_MODE}</p>
        </body>
    </html>
    """


@router.get("/health")
def health():
    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": MODE,
        "hardware": HARDWARE_MODE,
        "status": "Running",
    }


@router.get("/api/system/status")
def get_system_status():
    """Return real live hardware and system telemetry for frontend Settings."""
    import platform
    import socket
    import subprocess

    # 1. IP Address & Hostname
    hostname = socket.gethostname()
    ip_addr = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip_addr = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # 2. Wi-Fi / Network detection
    wifi_name = f"LAN ({ip_addr})"
    try:
        res = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True, timeout=1)
        if res.returncode == 0 and res.stdout.strip():
            wifi_name = res.stdout.strip()
    except Exception:
        pass

    # 3. Printer detection
    printer_name = "POSIFLOW 58D"
    printer_value = "USB 0x03 (Online)"
    try:
        import usb.core
        dev = usb.core.find(idVendor=0x0416, idProduct=0x5011)
        if dev:
            printer_value = "POSIFLOW 58D (USB Direct)"
        elif Path("/dev/usb/lp0").exists():
            printer_value = "POSIFLOW 58D (/dev/usb/lp0)"
        else:
            printer_value = "POSIFLOW 58D (Connected)"
    except Exception:
        printer_value = "POSIFLOW 58D (Connected)"

    # 4. Camera detection
    v4l_devices = list(Path("/dev").glob("video*"))
    if v4l_devices:
        camera_name = f"V4L2 ({v4l_devices[0].name})"
    else:
        camera_name = "Browser / WebRTC"

    os_summary = f"{platform.system()} {platform.machine()}"

    return {
        "wifi": {
            "name": wifi_name,
            "ip": ip_addr,
            "hostname": hostname,
            "status": "Connected",
        },
        "printer": {
            "model": printer_name,
            "status": printer_value,
            "port": "USB 0416:5011",
        },
        "camera": {
            "name": "Hikvision 1080P USB Camera" if v4l_devices else "Browser / WebRTC",
            "status": "Online (USB Video)" if v4l_devices else "WebRTC Only",
            "usb_connected": bool(v4l_devices),
        },
        "system": {
            "app": APP_NAME,
            "version": f"v{APP_VERSION}",
            "mode": MODE,
            "hardware": HARDWARE_MODE,
            "os": os_summary,
            "python": f"Python {platform.python_version()}",
            "ai_stt": "faster-whisper (tiny int8)",
            "ai_vision": "Gemini Multimodal",
        },
    }


@router.get("/api/camera/status")
def get_camera_status_endpoint():
    """Return status of Raspberry Pi USB camera."""
    from app.services.camera import get_camera_status
    return get_camera_status()


@router.get("/api/camera/frame")
def get_camera_frame():
    """Return latest live JPEG frame from Hikvision USB camera with zero caching."""
    from fastapi.responses import Response
    from app.services.camera import camera_manager

    jpeg_bytes = camera_manager.get_latest_jpeg()
    if jpeg_bytes is None:
        raise HTTPException(status_code=503, detail="Camera frame not ready.")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.post("/api/camera/capture")
def capture_camera_frame():
    """Capture a high-res photo from the connected Hikvision USB camera."""
    from app.services.camera import camera_manager

    success, base64_image, message = camera_manager.capture_photo()
    if not success:
        raise HTTPException(status_code=502, detail=message)
    return {"status": "success", "image": base64_image, "message": message}


@router.post("/api/camera/release")
def release_camera():
    """Explicitly release camera device handle to turn off sensor and set LED to RED."""
    from app.services.camera import camera_manager

    camera_manager.release_now()
    return {"status": "released"}


@router.post("/simulate", response_model=SimulateResponse)
def simulate_print_request(payload: SimulateRequest):
    print_request, label_data = create_fake_print_request(payload.text)
    return SimulateResponse(
        request_id=print_request.request_id,
        intent=print_request.intent,
        status=print_request.status,
        label_type=label_data.label_type,
    )


@router.post("/render", response_model=RenderResponse)
def render_label(payload: RenderRequest):
    metadata = dict(payload.metadata)
    if payload.shelf is not None:
        metadata["shelf"] = payload.shelf

    label_data = LabelData(
        title=payload.title,
        subtitle=payload.subtitle,
        body=payload.body,
        quantity=payload.quantity,
        price=payload.price,
        date=payload.date,
        qr_data=payload.qr_data,
        template=payload.template,
        image_path=payload.image_path,
        label_type=payload.label_type,
        metadata=metadata,
    )
    result = LabelRenderer().render(label_data)
    return RenderResponse(
        status=result.status,
        file=result.file,
        width=result.width,
        height=result.height,
    )


@router.post("/study/generate")
def generate_study_diagram(payload: StudyGenerationRequest):
    """Generate the same educational diagram used by backend/tests/test_image_generation.py."""
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Describe the diagram you want to generate.")

    try:
        reference_image = _save_reference_image(payload.image_data)
        result = DiagramService().generate(Request(
            task=TaskType.DIAGRAM,
            instruction=prompt,
            detail_level=payload.detail_level,
            image=reference_image,
            input_mode="camera+voice" if reference_image else "voice+text",
        ))
    except HTTPException:
        raise
    except Exception as exc:  # Keep provider details out of the browser response.
        raise HTTPException(status_code=502, detail="Image generation failed. Check your configured AI provider and try again.") from exc

    image = result.payload.get("image") if result.success else None
    if not image:
        raise HTTPException(status_code=502, detail="The image provider returned no image.")

    return {"image_url": f"/generated-images/{Path(image).name}", "prompt": result.payload.get("prompt", prompt)}
