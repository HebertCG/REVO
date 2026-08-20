"""
auth.py — Registro, login y perfil.

Cambios frente a la version anterior:
  - Cada ruta declara su cupo de rate limit. El login cuenta por cuenta
    atacada, no por IP: un aula entera comparte IP y no debe estorbarse.
  - El registro graba el consentimiento en la MISMA transaccion que crea la
    cuenta. No puede existir una cuenta sin su registro de consentimiento.
  - El login responde igual exista o no la cuenta, para no confirmar que
    correos estan registrados.
  - La identidad sale del token verificado con emisor, audiencia y proposito,
    no de un decode suelto.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import consentimiento
from database import User
from revo_comun.basedatos.contexto import ContextoSeguridad
from revo_comun.basedatos.motor import fijar_contexto
from revo_comun.seguridad.ip_cliente import extract_client_ip, ip_para_almacenar
from revo_comun.seguridad.tokens import Principal
from schemas import (
    ActualizarConsentimiento,
    EstadoConsentimiento,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from security import hash_password, verify_password
from servicio_revo import servicio

router = APIRouter(prefix="/auth", tags=["Autenticacion"])

#: Mensaje unico para cualquier fallo de login. Distinguir entre "no existe"
#: y "contrasena incorrecta" convierte el login en un verificador de correos
#: registrados, que es una fuga de datos personales por si sola.
CREDENCIALES_INVALIDAS = "Correo o contrasena incorrectos"


def _datos_de_origen(request: Request) -> tuple[str | None, str | None]:
    """IP y navegador, para acreditar desde donde se dio el consentimiento."""
    ip = extract_client_ip(request, servicio.ajustes.TRUSTED_PROXY_COUNT)
    return ip_para_almacenar(ip), request.headers.get("user-agent")


def _usuario_actual(db: Session, quien: Principal) -> User:
    """
    Carga el usuario del token.

    RLS ya limita la consulta a su propia fila, asi que este SELECT no puede
    devolver a otro alumno aunque el filtro estuviera mal.
    """
    usuario = db.scalar(select(User).where(User.id == quien.user_id))
    if usuario is None or not usuario.is_active:
        raise HTTPException(status_code=401, detail="Sesion no valida")
    return usuario


# ── POST /auth/register ──────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
def registrar(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("register")),
):
    ip, navegador = _datos_de_origen(request)

    # El alta pasa por revo_crear_alumno (ver database/13_registro.sql) y no
    # por el ORM. Dos motivos:
    #   1. El registro no tiene identidad, y el INSERT ... RETURNING del ORM
    #      aplica tambien la politica de SELECT sobre la fila devuelta, que
    #      sin contexto es falsa. Lo detectaron las pruebas de integracion.
    #   2. La funcion fija role = 'student' internamente, asi que crear un
    #      administrador desde el registro es imposible por construccion.
    resultado = db.execute(
        text(
            "SELECT nuevo_id, motivo FROM revo_crear_alumno("
            ":email, :password_hash, :full_name, :student_code, :semester)"
        ),
        {
            "email": body.email,
            "password_hash": hash_password(body.password),
            "full_name": body.full_name,
            "student_code": body.student_code,
            "semester": body.semester,
        },
    ).first()

    nuevo_id, motivo = resultado

    if motivo == "email_duplicado":
        raise HTTPException(status_code=400, detail="El email ya esta registrado")
    if motivo == "codigo_duplicado":
        raise HTTPException(status_code=400, detail="El codigo de estudiante ya existe")
    if nuevo_id is None:
        raise HTTPException(status_code=400, detail="No se pudo crear la cuenta")

    # Ya hay identidad: se abre el contexto para que el consentimiento y la
    # lectura del perfil pasen por RLS como cualquier otra operacion.
    # Sigue siendo la MISMA transaccion, asi que cuenta y consentimiento se
    # confirman juntos o no se confirma ninguno.
    fijar_contexto(db, ContextoSeguridad(user_id=nuevo_id, role="student"))

    try:
        consentimiento.registrar_consentimiento_inicial(
            db,
            user_id=nuevo_id,
            acepta_obligatorios=body.accept_terms,
            acepta_comercial=body.consent_data_commercial,
            acepta_entrenamiento=body.consent_ai_training,
            ip=ip,
            user_agent=navegador,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    db.commit()

    usuario = db.scalar(select(User).where(User.id == nuevo_id))

    token = servicio.tokens.issue(user_id=nuevo_id, role="student")
    return TokenResponse(
        access_token=token,
        expires_in=servicio.tokens.expires_in_seconds,
        user=UserResponse.model_validate(usuario),
    )


# ── POST /auth/login ─────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("login", por_credencial=True)),
):
    # La sesion todavia no tiene contexto RLS (nadie esta autenticado), asi
    # que la tabla users esta cerrada. Se usa la funcion acotada que definen
    # las politicas: devuelve una fila por email exacto y nada mas.
    fila = db.execute(
        text(
            "SELECT id, password_hash, role, is_active "
            "FROM revo_credenciales_por_email(:email)"
        ),
        {"email": body.email},
    ).first()

    if fila is None:
        # Se verifica igualmente contra un hash de descarte para que el
        # tiempo de respuesta no delate si la cuenta existe.
        verify_password(body.password, hash_password("no-existe-esta-cuenta"))
        raise HTTPException(status_code=401, detail=CREDENCIALES_INVALIDAS)

    user_id, password_hash, role, is_active = fila

    if not verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail=CREDENCIALES_INVALIDAS)

    if not is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    # Ya hay identidad: se abre el contexto RLS para poder leer el perfil.
    db.commit()  # cierra la transaccion que corrio sin contexto
    fijar_contexto(db, ContextoSeguridad(user_id=user_id, role=role))
    usuario = db.scalar(select(User).where(User.id == user_id))

    token = servicio.tokens.issue(user_id=user_id, role=role)
    return TokenResponse(
        access_token=token,
        expires_in=servicio.tokens.expires_in_seconds,
        user=UserResponse.model_validate(usuario),
    )


# ── POST /auth/login/form (compatible con OAuth2) ────────────
@router.post("/login/form", response_model=TokenResponse)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("login")),
):
    return login(LoginRequest(email=form.username, password=form.password), db, None)


# ── GET /auth/me ─────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def perfil(
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    return UserResponse.model_validate(_usuario_actual(db, quien))


# ── PUT /auth/me ─────────────────────────────────────────────
@router.put("/me", response_model=UserResponse)
def actualizar_perfil(
    body: UpdateProfileRequest,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    usuario = _usuario_actual(db, quien)

    # Solo campos de perfil. `role` y `is_active` no aparecen aqui a
    # proposito: si el schema los aceptara, un alumno se ascenderia a admin
    # con un PUT.
    if body.full_name is not None:
        usuario.full_name = body.full_name
    if body.student_code is not None:
        usuario.student_code = body.student_code
    if body.semester is not None:
        usuario.semester = body.semester
    if body.avatar_url is not None:
        usuario.avatar_url = body.avatar_url

    db.commit()
    db.refresh(usuario)
    return UserResponse.model_validate(usuario)


# ── GET /auth/verify ─────────────────────────────────────────
@router.get("/verify", response_model=MessageResponse)
def verificar(
    quien: Principal = Depends(servicio.principal),
    _: None = Depends(servicio.limitar("read")),
):
    # No devuelve el email: el frontend solo necesita saber si sigue viva.
    return MessageResponse(message="Sesion valida")


# ── GET /auth/me/consents ────────────────────────────────────
@router.get("/me/consents", response_model=list[EstadoConsentimiento])
def mis_consentimientos(
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """Que ha autorizado el alumno y desde cuando."""
    return consentimiento.estado_actual(db, quien.user_id)


# ── PUT /auth/me/consents ────────────────────────────────────
@router.put("/me/consents", response_model=list[EstadoConsentimiento])
def cambiar_mi_consentimiento(
    body: ActualizarConsentimiento,
    request: Request,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """
    Activa o retira una autorizacion opcional.

    El derecho a revocar el consentimiento es tan exigible como el de darlo:
    sin esta ruta, las casillas del registro no serian consentimiento valido.
    """
    ip, navegador = _datos_de_origen(request)
    try:
        consentimiento.cambiar_consentimiento(
            db,
            user_id=quien.user_id,
            doc_type=body.doc_type,
            otorgado=body.granted,
            ip=ip,
            user_agent=navegador,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return consentimiento.estado_actual(db, quien.user_id)


# ── Admin: GET /auth/users ───────────────────────────────────
@router.get("/users", response_model=list[UserResponse])
def listar_usuarios(
    skip: int = 0,
    limit: int = 50,
    quien: Principal = Depends(servicio.admin),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("admin")),
):
    # El limite se topa en el servidor: `?limit=999999` no puede volcar la
    # tabla entera en una sola respuesta.
    tope = max(1, min(limit, 100))
    desplazamiento = max(0, skip)

    usuarios = db.scalars(
        select(User).order_by(User.id).offset(desplazamiento).limit(tope)
    ).all()
    return [UserResponse.model_validate(u) for u in usuarios]


# ── Admin: PATCH /auth/users/{id}/toggle ─────────────────────
@router.patch("/users/{user_id}/toggle", response_model=UserResponse)
def alternar_usuario(
    user_id: int,
    quien: Principal = Depends(servicio.admin),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("admin")),
):
    if user_id == quien.user_id:
        # Un admin que se desactiva a si mismo deja el sistema sin
        # administracion si es el unico.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta",
        )

    usuario = db.scalar(select(User).where(User.id == user_id))
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.is_active = not usuario.is_active
    db.commit()
    db.refresh(usuario)
    return UserResponse.model_validate(usuario)
