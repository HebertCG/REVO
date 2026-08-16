import requests
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timezone
from jose import JWTError, jwt

from database import get_db, QuestionnaireSession, Answer, Question
from schemas import SessionOut, AnswerIn, BulkAnswerIn, AnswerOut, SessionWithAnswers, SessionComplete, QuestionOut
from config import settings

router = APIRouter(prefix="/sessions", tags=["Sessions"])

# Numero de especializaciones (1..10). Antes estaba repetido como
# `range(1, 11)` en cuatro sitios distintos.
NUM_SPECS = 10
SPEC_IDS = range(1, NUM_SPECS + 1)


def _spec_totals(db: Session, session_id: int) -> dict[int, dict]:
    """
    Suma y conteo de respuestas agrupadas por especializacion, en UNA query.

    Antes esto era un N+1: un SELECT a `questions` por cada respuesta
    (25 en fase 2), es decir 27 round-trips a PostgreSQL en el endpoint
    que cierra el cuestionario.
    """
    rows = (
        db.query(
            Question.specialization_id,
            func.sum(Answer.value).label("total"),
            func.count(Answer.id).label("cnt"),
        )
        .join(Answer, Answer.question_id == Question.id)
        .filter(Answer.session_id == session_id)
        .group_by(Question.specialization_id)
        .all()
    )
    totals = {i: {"sum": 0.0, "count": 0} for i in SPEC_IDS}
    for spec_id, total, cnt in rows:
        if spec_id in totals:
            totals[spec_id] = {"sum": float(total or 0), "count": int(cnt or 0)}
    return totals


def extract_user_id(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ── POST /sessions/ — Iniciar cuestionario ──────────────────
@router.post("/", response_model=SessionOut, status_code=201)
def create_session(db: Session = Depends(get_db), user_id: int = Depends(extract_user_id)):
    prev = db.query(QuestionnaireSession).filter(
        QuestionnaireSession.user_id == user_id,
        QuestionnaireSession.status == "in_progress"
    ).first()
    if prev:
        prev.status = "abandoned"
        db.commit()

    session = QuestionnaireSession(user_id=user_id, phase=1, phase_data={})
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ── GET /sessions/active ─────────────────────────────────────
@router.get("/active", response_model=SessionOut)
def get_active_session(db: Session = Depends(get_db), user_id: int = Depends(extract_user_id)):
    session = db.query(QuestionnaireSession).filter(
        QuestionnaireSession.user_id == user_id, QuestionnaireSession.status == "in_progress"
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="No hay sesión activa")
    return session


# ── GET /sessions/{id}/questions — Obtener las preguntas adaptativas del ciclo actual ─
@router.get("/{session_id}/questions", response_model=list[QuestionOut])
def get_session_questions(session_id: int, db: Session = Depends(get_db), user_id: int = Depends(extract_user_id)):
    session = db.query(QuestionnaireSession).filter(
        QuestionnaireSession.id == session_id, QuestionnaireSession.user_id == user_id, QuestionnaireSession.status == "in_progress"
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no activa")

    if session.phase == 1:
        # FASE 1: 1 pregunta por cada especialización (10 preguntas)
        # Randomizamos para que el pool de 100 pregs se use y el examen no sea idéntico
        q_list = []
        for spec_id in range(1, 11):
            q = db.query(Question).filter(Question.specialization_id == spec_id).order_by(func.random()).first()
            if q: q_list.append(q)
        return q_list

    elif session.phase == 2:
        # FASE 2: 5 preguntas de las Top 3 especializaciones = 15 preguntas
        # Excluimos las que ya respondió en Fase 1
        answers = db.query(Answer).filter(Answer.session_id == session_id).all()
        answered_ids = [a.question_id for a in answers]
        
        top3_specs = session.phase_data.get("top3_specs", [])
        q_list = []
        for spec_id in top3_specs:
            qs = db.query(Question).filter(
                Question.specialization_id == spec_id,
                ~Question.id.in_(answered_ids)
            ).order_by(func.random()).limit(5).all()
            q_list.extend(qs)
        return q_list
    else:
        return []


# ── POST /sessions/{id}/answers — Guardar el progreso ────────
@router.post("/{session_id}/answers", response_model=list[AnswerOut])
def save_answers(session_id: int, body: BulkAnswerIn, db: Session = Depends(get_db), user_id: int = Depends(extract_user_id)):
    session = db.query(QuestionnaireSession).filter(
        QuestionnaireSession.id == session_id, QuestionnaireSession.user_id == user_id, QuestionnaireSession.status == "in_progress"
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    incoming_ids = [a.question_id for a in body.answers]

    # Validar que las preguntas existen antes de tocar la BD: un question_id
    # inexistente provocaba una violacion de FK y un HTTP 500 con traza.
    valid_ids = {
        qid for (qid,) in db.query(Question.id).filter(Question.id.in_(incoming_ids)).all()
    }
    unknown = set(incoming_ids) - valid_ids
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Preguntas inexistentes: {sorted(unknown)}",
        )

    existing_map = {
        a.question_id: a
        for a in db.query(Answer).filter(
            Answer.session_id == session_id,
            Answer.question_id.in_(incoming_ids),
        ).all()
    }

    # UN solo commit al final: antes se hacia commit + refresh por iteracion
    # (61 sentencias y 15 transacciones para guardar 15 respuestas), y si
    # fallaba a mitad la sesion quedaba en un estado inconsistente.
    now = datetime.now(timezone.utc)
    saved = []
    for ans in body.answers:
        row = existing_map.get(ans.question_id)
        if row:
            row.value = ans.value
            row.answered_at = now
        else:
            row = Answer(session_id=session_id, question_id=ans.question_id, value=ans.value)
            db.add(row)
        saved.append(row)

    db.commit()
    return saved


# ── POST /sessions/{id}/submit_phase — Transicionar fase o finalizar ─
@router.post("/{session_id}/submit_phase")
def submit_phase(session_id: int, request_headers: dict = Depends(lambda: {}), db: Session = Depends(get_db), authorization: str = Header(None)):
    user_id = extract_user_id(authorization)
    session = db.query(QuestionnaireSession).filter(
        QuestionnaireSession.id == session_id, QuestionnaireSession.user_id == user_id, QuestionnaireSession.status == "in_progress"
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    answers = db.query(Answer).filter(Answer.session_id == session_id).all()
    
    if session.phase == 1:
        # Validar si contestó las 10
        if len(answers) < 10:
            raise HTTPException(status_code=400, detail="Faltan respuestas de Fase 1")
            
        # Calcular los top 3 (1 query agregada en vez de 10 individuales)
        spec_scores = {i: t["sum"] for i, t in _spec_totals(db, session_id).items()}

        # Ordenar y sacar las 3 mejores claves
        # IMPORTANTE: Mezclamos las llaves antes de ordenar para destruir el sesgo de empates matemáticos
        import random
        keys = list(spec_scores.keys())
        random.shuffle(keys)
        top3 = sorted(keys, key=lambda k: spec_scores[k], reverse=True)[:3]
        
        # Actualizar sesión a fase 2
        session.phase = 2
        session.phase_data = {"top3_specs": top3, "phase_1_scores": spec_scores}
        db.commit()
        return {"message": "Fase 1 completada", "next_phase": 2, "top3": top3}
        
    elif session.phase == 2:
        # Validar si contestó fase 1 + fase 2 (10 + 15 = 25)
        # O calcular afinidades directas.
        
        # Construir afinidades de 1 a 10 (matemáticas de 0.0 a 1.0)
        # Por cada especialidad: suma_respuestas / maxima_puntuacion_posible
        # 1 query agregada en vez de 25 individuales
        questions_answered = _spec_totals(db, session_id)


        # Una rama explorada tiene 6 preguntas máximas (1 Fase 1 + 5 Fase 2) = 30 pts.
        # Dividiremos la suma de TODO entre 30.0 para todos.
        # Esto colapsa las ramas no exploradas (max 5/30 = 16.6%),
        # alineándose perfectamente con la data sintética de ML.
        affinities = {}
        for spec_id in range(1, 11):
            sum_val = questions_answered[spec_id]["sum"]
            aff = sum_val / 30.0
            affinities[f"aff_{spec_id}"] = round(aff, 4)
            
        now = datetime.now(timezone.utc)
        session.status = "completed"
        session.completed_at = now
        session.duration_seconds = int((now - session.started_at.replace(tzinfo=timezone.utc)).total_seconds())
        db.commit()

        # Llamar a ml-service
        try:
            import os
            headers = {"Authorization": authorization, "Content-Type": "application/json"}
            # user_id ya no se envia: ml-service lo toma del token JWT.
            payload = {
                "session_id": session_id,
                "feature_vector": affinities
            }
            base_ml = settings.ML_SERVICE_URL.rstrip("/")
            ml_url = f"{base_ml}/predict/"
            res = requests.post(ml_url, json=payload, headers=headers, timeout=30)
            res.raise_for_status()
            pred_data = res.json()
            return {
                "message": "Cuestionario completado",
                "prediction_id": pred_data["prediction_id"],
                # Nombre e ID de la especialización para que la Fase 3 sea adaptativa
                "primary_specialization": pred_data.get("primary_specialization", ""),
                "primary_specialization_id": pred_data.get("primary_specialization_id", None),
            }
        except Exception as e:
            return {"message": "Error al conectar con ml-service", "error": str(e), "affinities": affinities}



# ── GET /sessions/ — Historial ─────────────────────────────────
@router.get("/", response_model=list[SessionOut])
def get_history(db: Session = Depends(get_db), user_id: int = Depends(extract_user_id)):
    sessions = db.query(QuestionnaireSession).filter(QuestionnaireSession.user_id == user_id).order_by(QuestionnaireSession.created_at.desc()).limit(20).all()
    return [SessionOut.model_validate(s) for s in sessions]
