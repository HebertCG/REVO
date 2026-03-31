from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


# ── Request Schemas ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    student_code: Optional[str] = None
    semester: Optional[int] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v

    @field_validator("semester")
    @classmethod
    def semester_range(cls, v):
        if v is not None and not (1 <= v <= 12):
            raise ValueError("El semestre debe estar entre 1 y 12")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    student_code: Optional[str] = None
    semester: Optional[int] = None
    avatar_url: Optional[str] = None


# ── Response Schemas ─────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    student_code: Optional[str]
    semester: Optional[int]
    role: str
    is_active: bool
    avatar_url: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int      # segundos
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
    success: bool = True
