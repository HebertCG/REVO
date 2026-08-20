"""
schemas.py — Contratos de entrada y salida del auth-service.

La validacion aqui es la primera frontera del sistema: todo lo que pase de
este punto se trata como dato de confianza. Por eso los campos declaran
longitud maxima ademas de tipo. Un `str` sin tope deja mandar un nombre de
diez megas que llega hasta la base de datos.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from config import settings

#: Tipos de consentimiento que el registro acepta. Coincide con el CHECK de
#: la tabla user_consents.
TipoDocumento = Literal["terms", "privacy", "data_commercial", "ai_training"]

#: Contrasenas que aparecen en cualquier lista de las mas usadas. No pretende
#: ser exhaustivo (eso es trabajo de un servicio como HaveIBeenPwned); frena
#: lo que un atacante prueba en los primeros diez intentos.
PASSWORDS_PROHIBIDAS = frozenset(
    {
        "password", "contrasena", "12345678", "123456789", "1234567890",
        "qwertyuiop", "administrador", "estudiante", "universidad",
        "password1", "abc12345", "iloveyou", "principal", "sistemas",
    }
)


# ── Entrada ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=150)
    student_code: Optional[str] = Field(default=None, max_length=30)
    semester: Optional[int] = Field(default=None, ge=1, le=12)

    # ── Consentimiento ───────────────────────────────────────
    # Obligatorios: sin ellos no hay cuenta.
    accept_terms: bool = Field(
        description="Aceptacion de los Terminos y Condiciones y la Politica de Privacidad"
    )
    # Opcionales: por defecto en False. Un opt-in que llega marcado de fabrica
    # no es consentimiento libre bajo la Ley 29733.
    consent_data_commercial: bool = False
    consent_ai_training: bool = False

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        # Sin esto, Ana@x.com y ana@x.com son cuentas distintas: el UNIQUE de
        # la base de datos distingue mayusculas.
        return valor.strip().lower()

    @field_validator("full_name")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        limpio = " ".join(valor.split())
        if not limpio:
            raise ValueError("El nombre no puede estar vacio")
        return limpio

    @field_validator("student_code")
    @classmethod
    def normalizar_codigo(cls, valor: Optional[str]) -> Optional[str]:
        # "" no es None: pasaba el `if body.student_code` del router y luego
        # chocaba contra el UNIQUE al registrarse un segundo usuario vacio.
        if valor is None:
            return None
        limpio = valor.strip()
        return limpio or None

    @field_validator("password")
    @classmethod
    def contrasena_solida(cls, valor: str) -> str:
        if len(valor) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"La contrasena debe tener al menos {settings.PASSWORD_MIN_LENGTH} caracteres"
            )
        if valor.lower() in PASSWORDS_PROHIBIDAS:
            raise ValueError("Esa contrasena es demasiado comun. Elige otra.")
        if valor.isdigit():
            raise ValueError("La contrasena no puede ser solo numeros")
        if valor.isalpha():
            raise ValueError("La contrasena debe combinar letras con numeros o simbolos")
        return valor

    @model_validator(mode="after")
    def exigir_terminos(self):
        if not self.accept_terms:
            raise ValueError(
                "Debes aceptar los Terminos y Condiciones y la Politica de Privacidad"
            )
        return self

    @model_validator(mode="after")
    def contrasena_distinta_del_email(self):
        # Una contrasena igual al correo es la primera que prueba cualquiera.
        if self.password.lower() == self.email.lower():
            raise ValueError("La contrasena no puede ser igual a tu correo")
        return self


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return valor.strip().lower()


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    student_code: Optional[str] = Field(default=None, max_length=30)
    semester: Optional[int] = Field(default=None, ge=1, le=12)
    avatar_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("avatar_url")
    @classmethod
    def solo_urls_http(cls, valor: Optional[str]) -> Optional[str]:
        # Sin esta comprobacion se puede guardar "javascript:..." o un
        # data: URI, que el frontend acabaria pintando en un <img> o un href.
        if valor is None:
            return None
        limpio = valor.strip()
        if not limpio:
            return None
        if not limpio.startswith(("https://", "http://")):
            raise ValueError("La URL del avatar debe empezar por http:// o https://")
        return limpio


class ActualizarConsentimiento(BaseModel):
    """Cambio de una casilla opcional desde el perfil."""

    doc_type: Literal["data_commercial", "ai_training"]
    granted: bool


# ── Salida ───────────────────────────────────────────────────
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
    expires_in: int
    user: UserResponse


class DocumentoLegalResumen(BaseModel):
    """Lo que necesita la casilla del formulario, sin el texto completo."""

    doc_type: str
    version: str
    title: str
    summary: str
    is_required: bool

    model_config = {"from_attributes": True}


class DocumentoLegalCompleto(DocumentoLegalResumen):
    """El documento entero, para el 'Leer mas'."""

    body_md: str

    model_config = {"from_attributes": True}


class EstadoConsentimiento(BaseModel):
    doc_type: str
    doc_version: str
    granted: bool
    granted_at: Optional[datetime]


class MessageResponse(BaseModel):
    message: str
    success: bool = True
