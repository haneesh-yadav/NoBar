"""
Password hashing and JWT helpers for the user-facing auth layer.

Uses only the Python standard library (hashlib.pbkdf2_hmac) plus PyJWT for
token signing, so the demo runs with zero external accounts. Tokens are
signed with the app-level JWT_SECRET from settings.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

_PBKDF2_ITERATIONS = 200_000
_AADHAAR_RE = re.compile(r"^\d{12}$")


def normalize_aadhaar(value: str) -> str:
    """Return the 12 digits with any spaces/dashes removed. Raises ValueError
    if the value is not a valid 12-digit Aadhaar number."""
    digits = re.sub(r"[\s\-]", "", value or "")
    if not _AADHAAR_RE.match(digits):
        raise ValueError("Aadhaar number must be exactly 12 digits")
    return digits


def aadhaar_digest(aadhaar: str) -> str:
    """SHA-256 of the normalized Aadhaar number — used only for lookups so the
    full number is never stored in the database."""
    return hashlib.sha256(normalize_aadhaar(aadhaar).encode("ascii")).hexdigest()


def mask_aadhaar(aadhaar: str) -> str:
    """'XXXX-XXXX-<last4>' display form."""
    digits = normalize_aadhaar(aadhaar)
    return f"XXXX-XXXX-{digits[-4:]}"


def aadhaar_placeholder_email(digest: str) -> str:
    """Deterministic internal email for Aadhaar-first accounts (never shown as
    a real contact address). Uniqueness is guaranteed by the digest."""
    return f"aadhaar-{digest[:12]}@nobar.local"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"$pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")[1:]
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None