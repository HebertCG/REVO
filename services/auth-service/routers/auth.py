from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError
from datetime import timedelta

from database import get_db, User
from schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    UserResponse, MessageResponse, UpdateProfileRequest
)
from security import hash_password, verify_password, create_access_token, decode_token
from config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/form")


# ─── Dependency: usuario actual ──────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a administradores"
        )
    return current_user


# ─── POST /auth/register ─────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    # Verificar email duplicado
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Verificar código de estudiante duplicado
    if body.student_code and db.query(User).filter(User.student_code == body.student_code).first():
        raise HTTPException(status_code=400, detail="El código de estudiante ya existe")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        student_code=body.student_code,
        semester=body.semester,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user=UserResponse.model_validate(user),
    )


# ─── POST /auth/login ────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user=UserResponse.model_validate(user),
    )


# ─── POST /auth/login/form (OAuth2 compatible) ───────────────
@router.post("/login/form", response_model=TokenResponse)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    return login(LoginRequest(email=form.username, password=form.password), db)


# ─── GET /auth/me ────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ─── PUT /auth/me ────────────────────────────────────────────
@router.put("/me", response_model=UserResponse)
def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if body.full_name: current_user.full_name = body.full_name
    if body.student_code: current_user.student_code = body.student_code
    if body.semester: current_user.semester = body.semester
    if body.avatar_url: current_user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ─── GET /auth/verify ────────────────────────────────────────
@router.get("/verify", response_model=MessageResponse)
def verify_token(current_user: User = Depends(get_current_user)):
    return MessageResponse(message=f"Token válido para {current_user.email}")


# ─── Admin: GET /auth/users ──────────────────────────────────
@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0, limit: int = 50,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    return [UserResponse.model_validate(u) for u in
            db.query(User).offset(skip).limit(limit).all()]


# ─── Admin: PATCH /auth/users/{id}/toggle ───────────────────
@router.patch("/users/{user_id}/toggle", response_model=UserResponse)
def toggle_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
