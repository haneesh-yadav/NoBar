"""
File storage. Local disk by default (backend/storage/) — zero setup, works
today. If SUPABASE_URL + SUPABASE_SERVICE_KEY are set, uploaded PDFs could be
mirrored to a Supabase Storage bucket instead; that swap is isolated to this
module so nothing else in the app needs to know which backend is active.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.config import STORAGE_DIR

UPLOADS_DIR = STORAGE_DIR / "uploads"
AUDIO_DIR = STORAGE_DIR / "audio"
UPLOADS_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)


def save_upload(file_bytes: bytes, original_filename: str) -> str:
    safe_name = f"{uuid.uuid4()}_{Path(original_filename).name}"
    dest = UPLOADS_DIR / safe_name
    dest.write_bytes(file_bytes)
    return str(dest)


def audio_dir_for_document() -> str:
    return str(AUDIO_DIR)
