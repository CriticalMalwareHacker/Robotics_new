"""Parking violation ticket: High-contrast Pillow image formatted for 58 mm thermal printers.

Width is 384 dots (THERMAL_PRINT_WIDTH_PX). Uses clean visual hierarchy, inverted
brand & violation banners, boxed registration plate, scannable QR verification code,
and bottom margin buffer for thermal printer tear bars.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cv2
import numpy as np

from app.services.printer import THERMAL_PRINT_WIDTH_PX
from .models import Detection, Slot

W = THERMAL_PRINT_WIDTH_PX
MARGIN = 14

_lock = threading.Lock()
_seq = 0
_history_path = Path("app/database/parking_tickets.json")


def get_history() -> list[dict]:
    """Return saved parking tickets, newest first."""
    # 1. Try reading from SQLite database table
    try:
        from infrastructure.database import SessionLocal, init_db
        from infrastructure.database_models import TicketRecord
        init_db()
        with SessionLocal() as session:
            rows = session.query(TicketRecord).order_by(TicketRecord.id.desc()).all()
            if rows:
                return [
                    {
                        "number": r.number,
                        "plate": r.plate,
                        "vehicle": r.vehicle_id,
                        "slot": r.slot_id,
                        "violation": r.violation,
                        "status": r.status,
                        "message": r.message,
                        "image_url": r.image_url,
                        "evidence_url": r.evidence_url,
                        "time": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
    except Exception:
        pass

    # 2. Fallback to JSON history file
    try:
        data = json.loads(_history_path.read_text(encoding="utf-8"))
        return list(reversed(data)) if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def record_ticket(ticket: dict) -> dict:
    """Persist a ticket record to both JSON and SQLite database so history survives restarts."""
    with _lock:
        # JSON file persistence
        try:
            existing = json.loads(_history_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except (OSError, json.JSONDecodeError):
            existing = []
        existing.append(ticket)
        _history_path.parent.mkdir(parents=True, exist_ok=True)
        _history_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        LAST["ticket"] = ticket

        # SQLite database persistence
        try:
            from infrastructure.database import SessionLocal, init_db
            from infrastructure.database_models import TicketRecord
            init_db()
            with SessionLocal() as session:
                rec = TicketRecord(
                    number=ticket.get("number", ""),
                    plate=ticket.get("plate", ""),
                    vehicle_id=ticket.get("vehicle"),
                    slot_id=ticket.get("slot"),
                    violation=ticket.get("violation", ""),
                    status=ticket.get("status", "printed"),
                    message=ticket.get("message"),
                    image_url=ticket.get("image_url"),
                    evidence_url=ticket.get("evidence_url"),
                )
                session.add(rec)
                session.commit()
        except Exception:
            pass
    return ticket


def generate_annotated_evidence(
    frame_bgr: np.ndarray | None,
    bays: list[Slot],
    vehicle_det: Detection | None,
    slot_id: str | None,
    violation_name: str,
    plate: str,
    ticket_number: str,
) -> str:
    """Create an annotated photographic evidence snapshot showing bay lines and violating vehicle.
    
    Saves to generated_labels/evidence_<number>.jpg and returns its web-accessible URL.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        # High-contrast fallback canvas if optical camera is unavailable
        img = np.full((360, 640, 3), 36, dtype=np.uint8)
        # Draw placeholder mat
        cv2.rectangle(img, (80, 80), (560, 310), (220, 220, 220), -1)
        cv2.putText(img, "OFFLINE SENSOR SNAPSHOT", (180, 195),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 50, 50), 2, cv2.LINE_AA)
    else:
        img = frame_bgr.copy()

    fh, fw = img.shape[:2]
    overlay = img.copy()

    # 1. Overlay Parking Bays (Green for regular, Red for infraction bay)
    violated_slot = (slot_id or "").upper().strip()
    for bay in bays:
        pts = np.asarray(bay.polygon_px or bay.polygon, dtype=np.int32)
        if len(pts) >= 3:
            is_violated = (bay.slot_id.upper() == violated_slot)
            if is_violated:
                cv2.fillPoly(overlay, [pts], (0, 0, 170))
                cv2.polylines(img, [pts], True, (0, 0, 255), 2, cv2.LINE_AA)
            else:
                cv2.polylines(img, [pts], True, (0, 180, 0), 1, cv2.LINE_AA)

            top_pt = min(pts, key=lambda p: p[1])
            tag = f"BAY {bay.slot_id}" + (" [INFRACTION]" if is_violated else "")
            color = (0, 0, 255) if is_violated else (0, 220, 0)
            cv2.putText(img, tag, (int(top_pt[0]), max(20, int(top_pt[1] - 4))),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

    # Blend translucent bay fills
    cv2.addWeighted(overlay, 0.35, img, 0.65, 0, img)

    # 2. Overlay Violating Vehicle Bounding Polygon
    if vehicle_det and (vehicle_det.polygon_px or vehicle_det.polygon):
        v_pts = np.asarray(vehicle_det.polygon_px or vehicle_det.polygon, dtype=np.int32)
        if len(v_pts) >= 3:
            # Neon yellow/orange bounding box with corner vertices
            cv2.polylines(img, [v_pts], True, (0, 220, 255), 3, cv2.LINE_AA)
            for pt in v_pts:
                cv2.circle(img, (int(pt[0]), int(pt[1])), 4, (0, 220, 255), -1, cv2.LINE_AA)

            top_v = min(v_pts, key=lambda p: p[1])
            badge_text = f"{plate.upper()} [{violation_name.upper()}]"
            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            bx = max(4, min(fw - tw - 12, int(top_v[0] - tw / 2)))
            by = max(44, int(top_v[1] - 8))
            cv2.rectangle(img, (bx - 4, by - th - 4), (bx + tw + 4, by + 4), (10, 10, 10), -1)
            cv2.rectangle(img, (bx - 4, by - th - 4), (bx + tw + 4, by + 4), (0, 220, 255), 1)
            cv2.putText(img, badge_text, (bx, by), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # 3. Top Cyber HUD Banner
    cv2.rectangle(img, (0, 0), (fw, 32), (12, 16, 24), -1)
    cv2.line(img, (0, 32), (fw, 32), (0, 220, 255), 1)
    header_l = f"PARKSENSEI AI PATROL | CITATION #{ticket_number}"
    header_r = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(img, header_l, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 220, 255), 1, cv2.LINE_AA)
    (rw, _), _ = cv2.getTextSize(header_r, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
    cv2.putText(img, header_r, (fw - rw - 10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 210, 225), 1, cv2.LINE_AA)

    # 4. Bottom Cyber HUD Banner
    cv2.rectangle(img, (0, fh - 28), (fw, fh), (12, 16, 24), -1)
    cv2.line(img, (0, fh - 28), (fw, fh - 28), (50, 60, 75), 1)
    footer_l = f"PLATE: {plate.upper()} | BAY: {slot_id or 'UNKNOWN'} | INFRACTION: {violation_name.upper()}"
    cv2.putText(img, footer_l, (10, fh - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

    outdir = Path("generated_labels")
    outdir.mkdir(exist_ok=True)
    outname = f"evidence_{ticket_number.replace('/', '-')}.jpg"
    cv2.imwrite(str(outdir / outname), img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return f"/generated_labels/{outname}"


LAST: dict = {"ticket": (get_history()[0] if get_history() else None)}


def next_number() -> str:
    global _seq
    with _lock:
        today = datetime.now().strftime("%y%m%d")
        persisted = get_history()
        matching = [str(row.get("number", "")) for row in persisted
                    if str(row.get("number", "")).startswith(f"T-{today}-")]
        highest = max((int(number.rsplit("-", 1)[-1]) for number in matching
                       if number.rsplit("-", 1)[-1].isdigit()), default=0)
        _seq = max(_seq, highest) + 1
        return f"T-{datetime.now().strftime('%y%m%d')}-{_seq:03d}"


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Find the best available TrueType font on Linux/Pi, macOS, or Windows."""
    candidates = [
        # Linux (Raspberry Pi OS)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Pillow 10+ scalable default font fallback
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def format_violation_title(raw_violation: str) -> str:
    mapping = {
        "OUTSIDE_SLOT": "PARKED OUTSIDE BAY",
        "STRADDLING": "BAY STRADDLING / DOUBLE BAY",
        "WRONG_ORIENTATION": "WRONG HEADING / ANGLE",
        "NO_PARKING_ZONE": "UNAUTHORIZED / NO-PARK ZONE",
        "LEGAL": "LEGAL (NO INFRACTION)",
    }
    return mapping.get(raw_violation.upper(), raw_violation.replace("_", " ").upper())


def build_ticket_image(number: str, when: str, plate: str, vehicle: str,
                       slot: str, violation: str) -> Image.Image:
    """Render a crisp, high-contrast 384 px monochrome citation image."""
    fonts = {
        "header_title": get_font(20, bold=True),
        "header_sub": get_font(11, bold=True),
        "section_tag": get_font(11, bold=True),
        "label": get_font(12, bold=False),
        "value": get_font(13, bold=True),
        "plate": get_font(25, bold=True),
        "violation": get_font(14, bold=True),
        "small": get_font(10, bold=False),
        "small_bold": get_font(11, bold=True),
    }

    # Initial canvas with generous vertical room
    img = Image.new("RGB", (W, 750), "white")
    d = ImageDraw.Draw(img)

    y = 6
    # 1. Top Inverted Black Brand Banner
    banner_height = 50
    d.rectangle([MARGIN, y, W - MARGIN, y + banner_height], fill="black")

    title_text = "PARKSENSEI"
    sub_text = "[ OFFICIAL PARKING CITATION ]"

    tw = d.textlength(title_text, font=fonts["header_title"])
    d.text(((W - tw) / 2, y + 6), title_text, fill="white", font=fonts["header_title"])

    sw = d.textlength(sub_text, font=fonts["header_sub"])
    d.text(((W - sw) / 2, y + 31), sub_text, fill="white", font=fonts["header_sub"])

    y += banner_height + 10

    # 2. Metadata Section (Clean Left & Right align)
    def draw_row(label: str, val: str, cur_y: int):
        d.text((MARGIN + 6, cur_y), label, fill="black", font=fonts["label"])
        vw = d.textlength(val, font=fonts["value"])
        d.text((W - MARGIN - 6 - vw, cur_y), val, fill="black", font=fonts["value"])

    draw_row("CITATION NO:", number, y); y += 19
    draw_row("DATE / TIME:", when, y); y += 19
    draw_row("LOCATION:", f"BAY {slot.upper()}", y); y += 19
    draw_row("PATROL UNIT:", "AUTONOMOUS UNIT #1", y); y += 22

    # Divider line
    d.line([MARGIN + 4, y, W - MARGIN - 4, y], fill="black", width=1)
    y += 10

    # 3. Boxed Vehicle Plate (Focal Point)
    plate_box_h = 62
    d.rectangle([MARGIN + 4, y, W - MARGIN - 4, y + plate_box_h], outline="black", width=2)
    tag_text = "VEHICLE REGISTRATION MARK"
    tag_w = d.textlength(tag_text, font=fonts["section_tag"])
    d.text(((W - tag_w) / 2, y + 6), tag_text, fill="black", font=fonts["section_tag"])

    clean_plate = plate.strip().upper() or "UNREAD"
    pw = d.textlength(clean_plate, font=fonts["plate"])
    d.text(((W - pw) / 2, y + 22), clean_plate, fill="black", font=fonts["plate"])
    y += plate_box_h + 10

    # 4. Inverted Infraction Box
    v_box_h = 48
    d.rectangle([MARGIN + 4, y, W - MARGIN - 4, y + v_box_h], fill="black")
    v_tag = "INFRACTION OBSERVED"
    v_tw = d.textlength(v_tag, font=fonts["section_tag"])
    d.text(((W - v_tw) / 2, y + 5), v_tag, fill="white", font=fonts["section_tag"])

    v_name = format_violation_title(violation)
    vn_w = d.textlength(v_name, font=fonts["violation"])
    d.text(((W - vn_w) / 2, y + 23), v_name, fill="white", font=fonts["violation"])
    y += v_box_h + 12

    # 5. Scannable High-Contrast QR Code for Verification & Digital Photo Evidence Portal
    portal_base = os.getenv("TICKET_PORTAL_BASE_URL", "http://10.42.0.1:8000").rstrip("/")
    target_url = f"{portal_base}/history?ticket={number}"

    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(target_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_w, qr_h = qr_img.size
        qr_x = int((W - qr_w) / 2)

        # Enclosing Verification Frame
        qr_box_pad = 8
        d.rectangle(
            [qr_x - qr_box_pad, y, qr_x + qr_w + qr_box_pad, y + qr_h + 38],
            outline="black",
            width=2,
        )
        # Inverted mini-banner
        d.rectangle(
            [qr_x - qr_box_pad, y, qr_x + qr_w + qr_box_pad, y + 18],
            fill="black",
        )
        q_tag = "DIGITAL EVIDENCE & VERIFICATION"
        q_tw = d.textlength(q_tag, font=fonts["small_bold"])
        d.text(((W - q_tw) / 2, y + 3), q_tag, fill="white", font=fonts["small_bold"])

        img.paste(qr_img, (qr_x, y + 20))
        y += qr_h + 24

        scan_info = "CAMERA SCAN OPENS PHOTO EVIDENCE"
        si_w = d.textlength(scan_info, font=fonts["small_bold"])
        d.text(((W - si_w) / 2, y), scan_info, fill="black", font=fonts["small_bold"])
        y += 22
    except Exception:
        # Graceful fallback if qrcode is not present
        pass

    # 6. Dotted Perforation Line & Disclaimer
    for x in range(MARGIN, W - MARGIN, 8):
        d.line([x, y, x + 4, y], fill="black", width=1)
    y += 9

    disc1 = "ACADEMIC PROTOTYPE ONLY"
    disc2 = "NOT AN OFFICIAL TRAFFIC FINE"
    d1_w = d.textlength(disc1, font=fonts["small_bold"])
    d.text(((W - d1_w) / 2, y), disc1, fill="black", font=fonts["small_bold"]); y += 15

    d2_w = d.textlength(disc2, font=fonts["small"])
    d.text(((W - d2_w) / 2, y), disc2, fill="black", font=fonts["small"]); y += 22

    # 7. Generous bottom buffer so the physical tear bar / cutter never slices text or QR
    final_h = y + 36
    final_img = img.crop((0, 0, W, final_h))

    # Outer border frame
    final_draw = ImageDraw.Draw(final_img)
    final_draw.rectangle([2, 2, W - 3, final_h - 3], outline="black", width=2)

    return final_img


def save_ticket_png(image: Image.Image, number: str) -> str:
    """Persist PNG for the HUD preview + reprint; returns public URL path."""
    outdir = Path("generated_labels")
    outdir.mkdir(exist_ok=True)
    name = f"ticket_{number.replace('/', '-')}.png"
    image.save(outdir / name, "PNG")
    return f"/generated_labels/{name}"
