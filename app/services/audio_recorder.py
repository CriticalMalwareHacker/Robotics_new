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
        self._start_time: float = 0.0

    def _get_alsa_device_and_card(self) -> tuple[str, int]:
        """Find the ALSA capture device string and card index for the USB Camera."""
        try:
            res = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines():
                if "1080P" in line or "Camera" in line or "USB Audio" in line or "card" in line:
                    import re
                    match = re.search(r"card (\d+):.*device (\d+):", line)
                    if match:
                        card, dev = match.groups()
                        return f"plughw:{card},{dev}", int(card)
        except Exception as exc:
            logger.warning(f"Error enumerating arecord devices: {exc}")
        return "plughw:0,0", 0

    def _boost_alsa_volume(self, card_idx: int):
        """Ensure ALSA capture volume is set to maximum and unmuted."""
        try:
            subprocess.run(["amixer", "-c", str(card_idx), "sset", "Mic", "100%", "unmute"], capture_output=True, timeout=1)
        except Exception:
            pass

    def _cleanup_orphaned_arecord(self):
        """Clean up any stuck arecord processes holding the audio capture device."""
        try:
            subprocess.run(["killall", "-9", "arecord"], capture_output=True, timeout=1)
        except Exception:
            pass

    def start_recording(self) -> dict[str, Any]:
        """Start capturing audio from the physical USB camera microphone."""
        with self._lock:
            if self._recording and self._process is not None:
                self.stop_and_discard()

            # Ensure ALSA soundcard is free and volume is maximized
            self._cleanup_orphaned_arecord()
            device, card_idx = self._get_alsa_device_and_card()
            self._boost_alsa_volume(card_idx)

            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", prefix="usb_mic_", delete=False)
            self._current_wav = Path(temp_file.name)
            temp_file.close()

            # arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -t wav /tmp/...wav
            cmd = [
                "arecord",
                "-D", device,
                "-f", "S16_LE",
                "-r", "16000",
                "-c", "1",
                "-t", "wav",
                "-q",
                str(self._current_wav),
            ]
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._recording = True
                self._start_time = time.time()
                logger.info(f"Started USB mic recording (PID {self._process.pid}) to {self._current_wav} on {device}")
                return {"status": "recording", "device": device}
            except Exception as exc:
                self._recording = False
                logger.error(f"Failed to start arecord: {exc}")
                return {"status": "error", "message": str(exc)}

    def _amplify_wav(self, path: Path):
        """Remove DC offset and normalize audio signal so Whisper receives clear speech input."""
        try:
            with wave.open(str(path), "rb") as wf:
                params = wf.getparams()
                n_frames = wf.getnframes()
                if n_frames == 0:
                    return
                frames = wf.readframes(n_frames)

            if not frames:
                return

            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            if len(samples) < 100:
                return

            # Remove DC offset / bias
            dc_offset = np.mean(samples)
            samples = samples - dc_offset

            # Measure peak and RMS
            peak = float(np.percentile(np.abs(samples), 99.5))
            rms = float(np.sqrt(np.mean(samples**2)))
            logger.info(f"Audio stats before gain: peak={peak:.1f}, rms={rms:.1f}, samples={len(samples)}")

            if peak > 1.0:
                # Target peak around 22000 for 16-bit audio
                target_peak = 22000.0
                gain = min(50.0, max(1.0, target_peak / peak))
                amplified = np.clip(samples * gain, -32767, 32767).astype(np.int16)
                with wave.open(str(path), "wb") as wf:
                    wf.setparams(params)
                    wf.writeframes(amplified.tobytes())
                logger.info(f"Applied {gain:.2f}x gain normalization to {path}")
        except Exception as exc:
            logger.warning(f"Audio amplification warning: {exc}")

    def stop_and_transcribe(self) -> tuple[bool, str, str]:
        """Stop arecord process via SIGINT and transcribe the captured audio."""
        with self._lock:
            if not self._recording or self._process is None:
                return False, "", "No recording in progress."

            # Ensure minimum duration so ALSA captures complete speech phonemes
            elapsed = time.time() - self._start_time
            if elapsed < 0.8:
                time.sleep(max(0.0, 0.8 - elapsed))

            proc = self._process
            wav_path = self._current_wav
            self._process = None
            self._recording = False
            self._current_wav = None

        # Terminate arecord process cleanly
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=1.5)
        except Exception:
            try:
                proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        if not wav_path or not wav_path.exists():
            return False, "", "Audio recording file was not created."

        file_size = wav_path.stat().st_size
        logger.info(f"Recorded WAV size: {file_size} bytes ({wav_path})")
        if file_size < 1000:
            wav_path.unlink(missing_ok=True)
            return False, "", "Audio recording was too short. Please speak clearly into the USB mic."

        try:
            self._amplify_wav(wav_path)
            logger.info(f"Transcribing USB mic audio with Whisper tiny: {wav_path}")
            text, lang = get_speech_service().transcribe(wav_path)
            if not text:
                return False, "", "No speech was detected from the USB mic. Please hold the button while speaking close to the webcam."
            logger.info(f"USB mic transcript success: '{text}' (lang: {lang})")
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
