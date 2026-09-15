"""
Central configuration. Everything that could differ between a hackathon laptop
and a real deployment lives here, sourced from environment variables with
sane local-dev defaults so the app runs today without any external account.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BACKEND_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    # --- Local model configuration (Ollama) ---
    # NOTE: this dev machine has 8GB RAM. gemma4:latest (8B, Q4) was tried
    # first as the generator and forced heavy swap (150s+ per call, disk
    # filling up as swap grew) — not demo-viable. Two small, different-family
    # 3B models both stay comfortably resident and respond in ~5-15s, which
    # is what a live hackathon demo actually needs. On stronger hardware,
    # bump these up via env vars without touching any pipeline code.
    ollama_host: str = "http://localhost:11434"
    generator_model: str = "qwen2.5:3b"
    verifier_model: str = "llama3.2:3b"
    # Optional dedicated model for the citizen assistant. Empty means "reuse
    # the generator model", so teams that only want to demo the assistant can
    # point ASSISTANT_MODEL at whatever model they already have pulled locally
    # (e.g. llama3.1:latest) without disturbing the pipeline defaults.
    assistant_model: str = ""

    @property
    def effective_assistant_model(self) -> str:
        return self.assistant_model or self.generator_model

    # --- Verification thresholds ---
    fact_fidelity_pass_threshold: float = 90.0
    max_simplification_retries: int = 2
    nli_low_confidence_band: float = 0.15  # escalate to LLM judge within this band of the threshold

    # --- Data layer: SQLite by default, Postgres/Supabase via DATABASE_URL ---
    database_url: str = f"sqlite:///{STORAGE_DIR / 'nobar.db'}"

    # --- Supabase (optional; falls back to local disk storage when unset) ---
    supabase_url: str | None = None
    supabase_service_key: str | None = None

    # --- PRISM (Block Convey) ---
    prismtrace_host: str = "https://prism-api-prod.up.railway.app"
    prismtrace_project_id: str | None = None
    prismtrace_api_key: str | None = None

    @property
    def prism_enabled(self) -> bool:
        return bool(self.prismtrace_project_id and self.prismtrace_api_key)

    # --- TTS ---
    tts_voice_en: str = "Samantha"
    tts_voice_hi: str = "Lekha"
    tts_voice_ta: str = "Vani"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Auth (HMAC-signed JWTs). Override JWT_SECRET in production/.env. ---
    jwt_secret: str = "nobar-dev-secret-change-me"
    jwt_expiry_minutes: int = 60 * 24


settings = Settings()
