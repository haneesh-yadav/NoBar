from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.eligibility import matched_schemes
from app.pdf_report import build_user_report_pdf
from app.security import decode_access_token
from db.repository import (
    apply_to_scheme,
    get_document,
    get_session,
    get_user,
    is_scheme_saved,
    list_applications,
    list_library,
    list_saved_schemes,
    save_scheme_for_user,
    unsave_scheme_for_user,
    update_user_profile,
)

logger = logging.getLogger("nobar.users")
router = APIRouter()


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency resolving the logged-in citizen from the JWT bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "not authenticated")
    token = authorization[7:].strip()
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(401, "invalid or expired token")
    with get_session() as session:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(401, "account not found")
        return _user_dict(user)


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    disability_status: Optional[str] = None
    disability_type: Optional[str] = None
    caste_category: Optional[str] = None
    bpl_status: Optional[str] = None
    annual_income: Optional[float] = None
    employment_type: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    pincode: Optional[str] = None
    aadhaar_masked: Optional[str] = None


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "dob": user.dob,
        "gender": user.gender,
        "marital_status": user.marital_status,
        "disability_status": user.disability_status,
        "disability_type": user.disability_type,
        "caste_category": user.caste_category,
        "bpl_status": user.bpl_status,
        "annual_income": user.annual_income,
        "employment_type": user.employment_type,
        "state": user.state,
        "district": user.district,
        "pincode": user.pincode,
        "aadhaar_masked": user.aadhaar_masked,
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.put("/me")
def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    with get_session() as session:
        fresh = get_user(session, user["id"])
        update_user_profile(session, fresh, updates)
        return _user_dict(fresh)


def _user_scheme_payload(session, user_id: str) -> dict:
    fresh = get_user(session, user_id)
    library = list_library(session, published_only=True)
    matching = matched_schemes(fresh, library)

    saved = []
    for s in list_saved_schemes(session, user_id):
        doc = s.document
        saved.append(
            {
                "document_id": s.document_id,
                "title": doc.title if doc else "",
                "category": doc.category if doc else "",
                "scheme_url": doc.scheme_url if doc else "",
                "saved_at": s.created_at.isoformat(),
            }
        )

    applications = []
    for a in list_applications(session, user_id):
        doc = a.document
        applications.append(
            {
                "document_id": a.document_id,
                "title": doc.title if doc else "",
                "category": doc.category if doc else "",
                "scheme_url": doc.scheme_url if doc else "",
                "status": a.status,
                "applied_at": a.applied_at.isoformat(),
            }
        )
    return {"matched": matching, "saved": saved, "applications": applications}


@router.get("/me/schemes")
def my_schemes(user: dict = Depends(get_current_user)):
    """Everything the login unlocks: matched + saved + applied schemes."""
    with get_session() as session:
        return _user_scheme_payload(session, user["id"])


@router.get("/me/schemes/pdf")
def my_report_pdf(user: dict = Depends(get_current_user)):
    """Stream the citizen's full entitlement & profile report as a PDF."""
    with get_session() as session:
        payload = _user_scheme_payload(session, user["id"])
        fresh = get_user(session, user["id"])
        profile = _user_dict(fresh)  # serialize before the session closes

    pdf_bytes = build_user_report_pdf(
        profile,
        matched=payload["matched"],
        saved=payload["saved"],
        applications=payload["applications"],
    )
    safe_name = (user.get("full_name") or user["email"]).replace(" ", "_").replace("@", "_")
    filename = f"nobar_entitlement_report_{safe_name}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/me/schemes/{document_id}/save")
def save_scheme(document_id: str, user: dict = Depends(get_current_user)):
    with get_session() as session:
        doc = get_document(session, document_id)
        if doc is None or doc.status != "published":
            raise HTTPException(404, "scheme not found")
        save_scheme_for_user(session, user["id"], document_id)
        return {"saved": True, "document_id": document_id}


@router.delete("/me/schemes/{document_id}/save")
def unsave_scheme(document_id: str, user: dict = Depends(get_current_user)):
    with get_session() as session:
        unsave_scheme_for_user(session, user["id"], document_id)
        return {"saved": False, "document_id": document_id}


@router.get("/me/schemes/{document_id}/saved-status")
def saved_status(document_id: str, user: dict = Depends(get_current_user)):
    with get_session() as session:
        return {"saved": is_scheme_saved(session, user["id"], document_id)}


@router.post("/me/schemes/{document_id}/apply")
def apply_scheme(document_id: str, user: dict = Depends(get_current_user)):
    with get_session() as session:
        doc = get_document(session, document_id)
        if doc is None or doc.status != "published":
            raise HTTPException(404, "scheme not found")
        application = apply_to_scheme(session, user["id"], document_id)
        return {
            "applied": True,
            "document_id": document_id,
            "status": application.status,
            "official_url": doc.scheme_url or "",
        }