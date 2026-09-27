"""Local speech-to-text using the small, fast Whisper ``tiny`` model."""

from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


class SpeechToTextService:
    def __init__(self) -> None:
        # int8 is substantially faster and lighter on CPU/Raspberry Pi hardware.
        self.model = WhisperModel("tiny", device="cpu", compute_type="int8")

    def transcribe(self, audio_path: Path) -> tuple[str, str | None]:
        # First try with vad_filter disabled for sensitive USB mics
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=1,
            vad_filter=False,
            task="translate",
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, info.language


@lru_cache(maxsize=1)
def get_speech_service() -> SpeechToTextService:
    """Load the model once; first use downloads tiny if it is not cached yet."""
    return SpeechToTextService()
