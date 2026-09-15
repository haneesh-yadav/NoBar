from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from app import aadhaar_demo
from app.security import (
    aadhaar_digest,
    aadhaar_placeholder_email,
    create_access_token,
    hash_password,
    mask_aadhaar,
    normalize_aadhaar,
    verify_password,
)
from db.repository import create_user, get_session, get_user_by_aadhaar, get_user_by_email

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(default="")
    aadhaar: str = ""

    @field_validator("aadhaar")
    @classmethod
    def _aadhaar_valid(cls, value: str) -> str:
        if value and value.strip():
            normalize_aadhaar(value)  # raises 422 on invalid format
        return value.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AadhaarOtpRequest(BaseModel):
    aadhaar: str

    @field_validator("aadhaar")
    @classmethod
    def _aadhaar_valid(cls, value: str) -> str:
        return normalize_aadhaar(value)


class AadhaarLoginRequest(AadhaarOtpRequest):
    otp: str


def _public_user(user) -> dict:
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
        "aadhaar_masked": user.aadhaar_masked or "",
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/register")
def register(body: RegisterRequest):
    with get_session() as session:
        if get_user_by_email(session, body.email):
            raise HTTPException(409, "an account with this email already exists")

        aadhaar_hash = aadhaar_masked = ""
        if body.aadhaar:
            aadhaar_hash = aadhaar_digest(body.aadhaar)
            if get_user_by_aadhaar(session, aadhaar_hash):
                raise HTTPException(409, "this Aadhaar number is already linked to an account")
            aadhaar_masked = mask_aadhaar(body.aadhaar)

        user = create_user(
            session,
            email=body.email,
            password_hash=hash_password(body.password),
            full_name=body.full_name,
            aadhaar_hash=aadhaar_hash or None,
            aadhaar_masked=aadhaar_masked,
        )
        token = create_access_token(user.id)
        return {"token": token, "user": _public_user(user), "created": True}


@router.post("/login")
def login(body: LoginRequest):
    with get_session() as session:
        user = get_user_by_email(session, body.email)
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "invalid email or password")
        token = create_access_token(user.id)
        return {"token": token, "user": _public_user(user)}


def _verify_otp(body: AadhaarLoginRequest) -> str:
    try:
        digits = normalize_aadhaar(body.aadhaar)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not aadhaar_demo.otp_matches(digits, body.otp):
        raise HTTPException(401, "invalid or expired OTP")
    return digits


@router.post("/aadhaar/request-otp")
def request_aadhaar_otp(body: AadhaarOtpRequest):
    """Simulated 'send OTP' — returns the demo OTP alongside the officer's-look
    summary so the flow is reviewable without a real phone."""
    digits = body.aadhaar
    with get_session() as session:
        registered = get_user_by_aadhaar(session, aadhaar_digest(digits)) is not None
    summary = aadhaar_demo.aadhaar_summary(digits)
    return {"registered": registered, **summary}


@router.post("/aadhaar/login")
def login_with_aadhaar(body: AadhaarLoginRequest):
    """Fetch the citizen's details from Aadhaar (simulated e-KYC) and either
    sign into their existing account or create one pre-filled from Aadhaar."""
    digits = _verify_otp(body)
    details = aadhaar_demo.fetch_aadhaar_details(digits)
    aadhaar_hash = aadhaar_digest(digits)
    masked = mask_aadhaar(digits)

    with get_session() as session:
        user = get_user_by_aadhaar(session, aadhaar_hash)
        created = False
        if user is None:
            created = True
            user = create_user(
                session,
                email=aadhaar_placeholder_email(aadhaar_hash),
                password_hash=hash_password(secrets.token_urlsafe(24)),
                full_name=details["full_name"],
                aadhaar_hash=aadhaar_hash,
                aadhaar_masked=masked,
            )
            profile = {
                "dob": details.get("dob", ""),
                "gender": details.get("gender", ""),
                "state": details.get("state", ""),
                "district": details.get("district", ""),
                "pincode": details.get("pincode", ""),
            }
            for field, value in profile.items():
                setattr(user, field, value)
            session.flush()
        token = create_access_token(user.id)
        return {
            "token": token,
            "user": _public_user(user),
            "created": created,
            "details": details,
        }