"""Hardware USB Microphone recording service using ALSA / arecord, signal boosting, and faster-whisper."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np
from backend.services.speech import get_speech_service

logger = logging.getLogger(__name__)

class UsbMicRecorder:
    """Manages background arecord process from the USB Webcam ALSA card."""

    def __init__(self):
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._current_wav: Path | None = None
        self._recording: bool = False

    def _get_alsa_device_and_card(self) -> tuple[str, int]:
        """Find the ALSA capture device string and card index for the USB Camera."""
        try:
            res = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=1)
            for line in res.stdout.splitlines():
                if "1080P" in line or "Camera" in line or "USB Audio" in line:
                    import re
                    match = re.search(r"card (\d+):.*device (\d+):", line)
                    if match:
                        card, dev = match.groups()
                        return f"plughw:{card},{dev}", int(card)
        except Exception:
            pass
        return "plughw:0,0", 0

    def _boost_alsa_volume(self, card_idx: int):
        """Ensure ALSA capture volume is set to maximum and unmuted."""
        try:
            subprocess.run(["amixer", "-c", str(card_idx), "sset", "Mic", "100%", "unmute"], capture_output=True, timeout=1)
        except Exception:
            pass

    def start_recording(self) -> dict[str, Any]:
        """Start capturing audio from the physical USB camera microphone."""
        with self._lock:
            if self._recording and self._process is not None:
                self.stop_and_discard()

            device, card_idx = self._get_alsa_device_and_card()
            self._boost_alsa_volume(card_idx)

            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", prefix="usb_mic_", delete=False)
            self._current_wav = Path(temp_file.name)
            temp_file.close()

            # arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 /tmp/...wav
            cmd = [
                "arecord",
                "-D", device,
                "-f", "S16_LE",
                "-r", "16000",
                "-c", "1",
                "-q",
                str(self._current_wav),
            ]
            try:
                self._process = subprocess.Popen(cmd)
                self._recording = True
                logger.info(f"Started USB mic recording to {self._current_wav} on {device}")
                return {"status": "recording", "device": device}
            except Exception as exc:
                self._recording = False
                logger.error(f"Failed to start arecord: {exc}")
                return {"status": "error", "message": str(exc)}

    def _amplify_wav(self, path: Path):
        """Boost audio signal so Whisper receives clean, audible input."""
        try:
            with wave.open(str(path), "rb") as wf:
                params = wf.getparams()
                frames = wf.readframes(wf.getnframes())

            if not frames:
                return

            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            max_amp = np.max(np.abs(samples))
            if max_amp > 10:
                # Amplify up to 24000 peak without clipping
                target_peak = 24000.0
                gain = min(15.0, target_peak / max_amp)
                amplified = np.clip(samples * gain, -32767, 32767).astype(np.int16)
                with wave.open(str(path), "wb") as wf:
                    wf.setparams(params)
                    wf.writeframes(amplified.tobytes())
                logger.info(f"Boosted audio signal by {gain:.2f}x (original peak: {max_amp})")
        except Exception as exc:
            logger.warning(f"Audio amplification warning: {exc}")

    def stop_and_transcribe(self) -> tuple[bool, str, str]:
        """Stop arecord process via SIGINT and transcribe the captured audio."""
        with self._lock:
            if not self._recording or self._process is None:
                return False, "", "No recording in progress."

            try:
                # Send SIGINT so arecord writes the clean WAV header with correct chunk sizes
                self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=2.0)
            except Exception:
                try:
                    self._process.terminate()
                except Exception:
                    pass

            self._process = None
            self._recording = False
            wav_path = self._current_wav
            self._current_wav = None

        if not wav_path or not wav_path.exists() or wav_path.stat().st_size < 1000:
            return False, "", "Audio recording was too short or empty."

        try:
            self._amplify_wav(wav_path)
            logger.info(f"Transcribing USB mic audio: {wav_path} ({wav_path.stat().st_size} bytes)")
            text, lang = get_speech_service().transcribe(wav_path)
            if not text:
                return False, "", "No speech was detected from the USB mic."
            return True, text, lang or "en"
        except Exception as exc:
            logger.error(f"Whisper transcription failed: {exc}")
            return False, "", f"Transcription error: {exc}"
        finally:
            if wav_path and wav_path.exists():
                wav_path.unlink(missing_ok=True)

    def stop_and_discard(self):
        """Cancel and clean up recording without transcribing."""
        with self._lock:
            if self._process is not None:
                try:
                    self._process.send_signal(signal.SIGINT)
                    self._process.wait(timeout=1.0)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                self._process = None
            self._recording = False
            if self._current_wav and self._current_wav.exists():
                self._current_wav.unlink(missing_ok=True)
            self._current_wav = None


usb_mic_recorder = UsbMicRecorder()
