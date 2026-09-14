"""
Stage: Text-to-speech. Uses macOS's built-in `say` (AVSpeechSynthesizer
voices) as the default local provider — zero download, works fully offline,
and this corpus's three target languages each have a decent built-in voice
on macOS: English (Samantha), Hindi (Lekha), Tamil (Vani). Given the 8GB
RAM / ~13GB disk budget on this dev machine, adding a torch-based TTS model
(Coqui/MMS) purely for a nicer voice wasn't a good trade — see README for
that upgrade path on stronger/non-macOS hardware.

Kept behind a narrow function interface so swapping the backend later
touches nothing upstream.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings

_VOICE_BY_LANG = {
    "en": settings.tts_voice_en,
    "hi": settings.tts_voice_hi,
    "ta": settings.tts_voice_ta,
}


class TTSUnavailableError(RuntimeError):
    pass


def tts_available() -> bool:
    return shutil.which("say") is not None and shutil.which("ffmpeg") is not None


def synthesize_speech(text: str, *, language: str, output_path: str) -> str:
    """Synthesizes `text` (in `language`) to an mp3 at output_path. Raises
    TTSUnavailableError if `say`/`ffmpeg` aren't available (e.g. not on
    macOS), so callers can degrade to text-only rather than crash."""
    if not tts_available():
        raise TTSUnavailableError("`say` and/or `ffmpeg` not found on this system")

    voice = _VOICE_BY_LANG.get(language, settings.tts_voice_en)
    output_path_str = str(output_path)
    Path(output_path_str).parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
        aiff_path = tmp.name

    try:
        subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, text],
            check=True,
            capture_output=True,
            timeout=180,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", aiff_path, output_path_str],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise TTSUnavailableError(f"TTS synthesis failed: {exc}") from exc
    finally:
        Path(aiff_path).unlink(missing_ok=True)

    return output_path_str
