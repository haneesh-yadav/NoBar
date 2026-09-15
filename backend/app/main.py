from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import assistant, auth, documents, library, review, users
from db.models import init_db
from prism.client import close_prism, get_prism_callback_handler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nobar.app")

app = FastAPI(title="NoBar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    if not settings.prism_enabled:
        logger.warning(
            "PRISM is not configured — set PRISMTRACE_PROJECT_ID and PRISMTRACE_API_KEY "
            "in backend/.env to enable observability. The app will run without it."
        )
    else:
        get_prism_callback_handler()
        logger.info("PRISM tracing enabled, project=%s", settings.prismtrace_project_id)


@app.on_event("shutdown")
def on_shutdown():
    close_prism()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "prism_enabled": settings.prism_enabled,
        "generator_model": settings.generator_model,
        "verifier_model": settings.verifier_model,
    }


app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(library.router, prefix="/api/library", tags=["library"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["assistant"])
