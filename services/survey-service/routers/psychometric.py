from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, PsychometricQuestion

router = APIRouter(prefix="/psychometric", tags=["Psychometric"])


class PsychometricQuestionOut(BaseModel):
    id: int
    specialization_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    order_index: int

    model_config = {"from_attributes": True}


# ── GET /psychometric/specialization/{spec_id} ─────────────────
# Devuelve las 4 preguntas psicométricas de una especialización dada
@router.get("/specialization/{spec_id}", response_model=list[PsychometricQuestionOut])
def get_questions_by_spec(spec_id: int, db: Session = Depends(get_db)):
    questions = (
        db.query(PsychometricQuestion)
        .filter(
            PsychometricQuestion.specialization_id == spec_id,
            PsychometricQuestion.is_active == True,
        )
        .order_by(PsychometricQuestion.order_index)
        .all()
    )
    return questions


# ── GET /psychometric/all ──────────────────────────────────────
# Devuelve todas las preguntas agrupadas (útil para debug / admin)
@router.get("/all", response_model=list[PsychometricQuestionOut])
def get_all_questions(db: Session = Depends(get_db)):
    questions = (
        db.query(PsychometricQuestion)
        .filter(PsychometricQuestion.is_active == True)
        .order_by(PsychometricQuestion.specialization_id, PsychometricQuestion.order_index)
        .all()
    )
    return questions
