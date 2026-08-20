"""
sessions.py — Sesiones del cuestionario por fases.

La logica de negocio (como se eligen las preguntas, como se calculan las
afinidades, como se decide el top 3) se conserva exactamente igual. Lo que
cambia es la infraestructura:

  - La identidad sale del token verificado y se propaga a la base de datos
    como contexto RLS. Los `WHERE user_id == ...` siguen ahi, pero ahora son
    una segunda linea: aunque uno se olvidara, Postgres no devolveria filas
    de otro alumno.
  - Cada ruta declara su cupo de peticiones.
  - La llamada al ml-service viaja por la red interna con el secreto de la
    pasarela y un timeout explicito.
"""
import logging
import random

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database import Answer, Question, QuestionnaireSession
from revo_comun.seguridad.pasarela import GATEWAY_HEADER
from revo_comun.seguridad.tokens import Principal
from schemas import (
    AnswerOut,
    BulkAnswerIn,
    QuestionOut,
    SessionOut,
)
from servicio_revo import servicio

logger = logging.getLogger("revo.survey.sesiones")

router = APIRouter(prefix="/sessions", tags=["Sesiones"])

# Numero de especializaciones (1..10). Antes estaba repetido como
# `range(1, 11)` en cuatro sitios distintos.
NUM_SPECS = 10
SPEC_IDS = range(1, NUM_SPECS + 1)

#: Preguntas de fase 1: una por especializacion.
PREGUNTAS_FASE_1 = NUM_SPECS

#: Preguntas de fase 2: 5 por cada una de las 3 especializaciones del top.
PREGUNTAS_POR_SPEC_FASE_2 = 5

#: Puntuacion maxima de una rama explorada: 1 pregunta de fase 1 + 5 de
#: fase 2, a 5 puntos cada una.
PUNTUACION_MAXIMA_RAMA = 30.0

#: Vigencia del token que survey-service emite para hablar con ml-service.
#: Solo tiene que durar una peticion.
TOKEN_INTERNO_SEGUNDOS = 60


def _spec_totals(db: Session, session_id: int) -> dict[int, dict]:
    """
    Suma y conteo de respuestas agrupadas por especializacion, en UNA query.

    Antes esto era un N+1: un SELECT a `questions` por cada respuesta
    (25 en fase 2), es decir 27 round-trips a PostgreSQL en el endpoint
    que cierra el cuestionario.
    """
    filas = db.execute(
        select(
            Question.specialization_id,
            func.sum(Answer.value).label("total"),
            func.count(Answer.id).label("cnt"),
        )
        .join(Answer, Answer.question_id == Question.id)
        .where(Answer.session_id == session_id)
        .group_by(Question.specialization_id)
    ).all()

    totales = {i: {"sum": 0.0, "count": 0} for i in SPEC_IDS}
    for spec_id, total, cnt in filas:
        if spec_id in totales:
            totales[spec_id] = {"sum": float(total or 0), "count": int(cnt or 0)}
    return totales


def _sesion_activa(db: Session, session_id: int, user_id: int) -> QuestionnaireSession:
    """
    Recupera una sesion en curso del alumno.

    El filtro por user_id se conserva aunque RLS ya lo garantice: leerlo aqui
    documenta la intencion y hace que la ruta siga siendo correcta si alguna
    vez se ejecuta contra una base sin politicas.
    """
    sesion = db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.id == session_id,
            QuestionnaireSession.user_id == user_id,
            QuestionnaireSession.status == "in_progress",
        )
    )
    if sesion is None:
        raise HTTPException(status_code=404, detail="Sesion no activa")
    return sesion


# ── POST /sessions/ — Iniciar cuestionario ──────────────────
@router.post("/", response_model=SessionOut, status_code=201)
def crear_sesion(
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("submit_phase")),
):
    previa = db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.user_id == quien.user_id,
            QuestionnaireSession.status == "in_progress",
        )
    )
    if previa:
        previa.status = "abandoned"

    sesion = QuestionnaireSession(user_id=quien.user_id, phase=1, phase_data={})
    db.add(sesion)
    # Un solo commit: antes se hacian dos, y si el segundo fallaba el alumno
    # se quedaba sin sesion activa y sin la anterior.
    db.commit()
    db.refresh(sesion)
    return sesion


# ── GET /sessions/active ─────────────────────────────────────
@router.get("/active", response_model=SessionOut)
def sesion_activa(
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    sesion = db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.user_id == quien.user_id,
            QuestionnaireSession.status == "in_progress",
        )
    )
    if sesion is None:
        raise HTTPException(status_code=404, detail="No hay sesion activa")
    return sesion


# ── GET /sessions/{id}/questions ─────────────────────────────
@router.get("/{session_id}/questions", response_model=list[QuestionOut])
def preguntas_de_la_sesion(
    session_id: int,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    sesion = _sesion_activa(db, session_id, quien.user_id)

    if sesion.phase == 1:
        # FASE 1: 1 pregunta por cada especializacion (10 preguntas).
        # Se aleatoriza para que el pool de 100 se use y el examen no sea
        # identico entre alumnos.
        preguntas = []
        for spec_id in SPEC_IDS:
            pregunta = db.scalar(
                select(Question)
                .where(Question.specialization_id == spec_id)
                .order_by(func.random())
                .limit(1)
            )
            if pregunta:
                preguntas.append(pregunta)
        return preguntas

    if sesion.phase == 2:
        # FASE 2: 5 preguntas de cada una de las top 3 = 15 preguntas.
        # Se excluyen las ya respondidas en fase 1.
        respondidas = list(
            db.scalars(select(Answer.question_id).where(Answer.session_id == session_id))
        )
        top3 = (sesion.phase_data or {}).get("top3_specs", [])

        preguntas = []
        for spec_id in top3:
            consulta = select(Question).where(Question.specialization_id == spec_id)
            if respondidas:
                consulta = consulta.where(Question.id.notin_(respondidas))
            preguntas.extend(
                db.scalars(
                    consulta.order_by(func.random()).limit(PREGUNTAS_POR_SPEC_FASE_2)
                )
            )
        return preguntas

    return []


# ── POST /sessions/{id}/answers ──────────────────────────────
@router.post("/{session_id}/answers", response_model=list[AnswerOut])
def guardar_respuestas(
    session_id: int,
    body: BulkAnswerIn,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("answers")),
):
    _sesion_activa(db, session_id, quien.user_id)

    ids_entrantes = [a.question_id for a in body.answers]

    # Validar que las preguntas existen antes de tocar la BD: un question_id
    # inexistente provocaba una violacion de FK y un HTTP 500 con traza.
    ids_validos = set(
        db.scalars(select(Question.id).where(Question.id.in_(ids_entrantes)))
    )
    desconocidas = set(ids_entrantes) - ids_validos
    if desconocidas:
        raise HTTPException(
            status_code=400,
            detail=f"Preguntas inexistentes: {sorted(desconocidas)}",
        )

    existentes = {
        a.question_id: a
        for a in db.scalars(
            select(Answer).where(
                Answer.session_id == session_id,
                Answer.question_id.in_(ids_entrantes),
            )
        )
    }

    # UN solo commit al final: antes se hacia commit + refresh por iteracion
    # (61 sentencias y 15 transacciones para guardar 15 respuestas), y si
    # fallaba a mitad la sesion quedaba en un estado inconsistente.
    guardadas = []
    for respuesta in body.answers:
        fila = existentes.get(respuesta.question_id)
        if fila:
            fila.value = respuesta.value
            fila.answered_at = func.now()
        else:
            fila = Answer(
                session_id=session_id,
                question_id=respuesta.question_id,
                value=respuesta.value,
            )
            db.add(fila)
        guardadas.append(fila)

    db.commit()
    for fila in guardadas:
        db.refresh(fila)
    return guardadas


# ── POST /sessions/{id}/submit_phase ─────────────────────────
@router.post("/{session_id}/submit_phase")
def cerrar_fase(
    session_id: int,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("submit_phase")),
):
    sesion = _sesion_activa(db, session_id, quien.user_id)
    total_respuestas = db.scalar(
        select(func.count(Answer.id)).where(Answer.session_id == session_id)
    )

    if sesion.phase == 1:
        if total_respuestas < PREGUNTAS_FASE_1:
            raise HTTPException(status_code=400, detail="Faltan respuestas de Fase 1")

        # Calcular los top 3 (1 query agregada en vez de 10 individuales)
        puntuaciones = {i: t["sum"] for i, t in _spec_totals(db, session_id).items()}

        # IMPORTANTE: se mezclan las llaves antes de ordenar para destruir el
        # sesgo de empates matematicos.
        claves = list(puntuaciones.keys())
        random.shuffle(claves)
        top3 = sorted(claves, key=lambda k: puntuaciones[k], reverse=True)[:3]

        sesion.phase = 2
        sesion.phase_data = {"top3_specs": top3, "phase_1_scores": puntuaciones}
        db.commit()
        return {"message": "Fase 1 completada", "next_phase": 2, "top3": top3}

    if sesion.phase == 2:
        # Construir afinidades de 1 a 10 (de 0.0 a 1.0).
        # Una rama explorada tiene 6 preguntas maximas (1 de Fase 1 + 5 de
        # Fase 2) = 30 pts. Se divide la suma de TODO entre 30.0 para todas.
        # Esto colapsa las ramas no exploradas (max 5/30 = 16.6%),
        # alineandose con la data sintetica de ML.
        totales = _spec_totals(db, session_id)
        afinidades = {
            f"aff_{spec_id}": round(totales[spec_id]["sum"] / PUNTUACION_MAXIMA_RAMA, 4)
            for spec_id in SPEC_IDS
        }

        sesion.status = "completed"
        sesion.completed_at = func.now()
        db.commit()
        db.refresh(sesion)

        return _pedir_prediccion(session_id, afinidades, quien)

    raise HTTPException(status_code=400, detail="La sesion no esta en una fase valida")


def _pedir_prediccion(session_id: int, afinidades: dict, quien: Principal) -> dict:
    """
    Llama al ml-service por la red interna.

    No se reenvia la cabecera Authorization del alumno: se emite un token
    nuevo con la misma identidad pero con una caducidad de un minuto. Si ese
    token acaba en un log o en un volcado del ml-service, deja de servir casi
    de inmediato; el del alumno seguiria valiendo 24 horas.
    """
    cabeceras = {
        "Authorization": (
            "Bearer "
            + servicio.tokens.issue(
                quien.user_id, quien.role, expire_seconds=TOKEN_INTERNO_SEGUNDOS
            )
        ),
        "Content-Type": "application/json",
    }
    if settings.GATEWAY_SECRET:
        cabeceras[GATEWAY_HEADER] = settings.GATEWAY_SECRET

    url = f"{settings.ML_SERVICE_URL.rstrip('/')}/predict/"

    try:
        respuesta = requests.post(
            url,
            json={"session_id": session_id, "feature_vector": afinidades},
            headers=cabeceras,
            timeout=settings.ML_TIMEOUT_SECONDS,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except requests.RequestException as exc:
        # El cuestionario ya esta guardado: el alumno no pierde su trabajo.
        # Se devuelven las afinidades para que el frontend pueda reintentar.
        logger.error("El ml-service no respondio para la sesion %s: %s", session_id, exc)
        return {
            "message": "El servicio de prediccion no esta disponible",
            "error": "ml_no_disponible",
            "affinities": afinidades,
        }

    return {
        "message": "Cuestionario completado",
        "prediction_id": datos["prediction_id"],
        "primary_specialization": datos.get("primary_specialization", ""),
        "primary_specialization_id": datos.get("primary_specialization_id"),
    }


# ── GET /sessions/ — Historial ───────────────────────────────
@router.get("/", response_model=list[SessionOut])
def historial(
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    sesiones = db.scalars(
        select(QuestionnaireSession)
        .where(QuestionnaireSession.user_id == quien.user_id)
        .order_by(QuestionnaireSession.created_at.desc())
        .limit(20)
    )
    return [SessionOut.model_validate(s) for s in sesiones]
