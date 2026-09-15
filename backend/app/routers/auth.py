from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.security import create_access_token, hash_password, verify_password
from db.repository import create_user, get_session, get_user_by_email

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(default="")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
        "aadhaar_masked": user.aadhaar_masked,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/register")
def register(body: RegisterRequest):
    with get_session() as session:
        if get_user_by_email(session, body.email):
            raise HTTPException(409, "an account with this email already exists")
        user = create_user(
            session,
            email=body.email,
            password_hash=hash_password(body.password),
            full_name=body.full_name,
        )
        token = create_access_token(user.id)
        return {"token": token, "user": _public_user(user)}


@router.post("/login")
def login(body: LoginRequest):
    with get_session() as session:
        user = get_user_by_email(session, body.email)
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "invalid email or password")
        token = create_access_token(user.id)
        return {"token": token, "user": _public_user(user)}