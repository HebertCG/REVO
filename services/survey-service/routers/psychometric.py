"""
psychometric.py — Preguntas de perfil profesional (Fase 3).

La ruta /all se restringe a administradores: devolver el banco completo de
preguntas psicometricas a cualquiera permite estudiarlo y responder el
cuestionario con una respuesta preparada, ademas de regalar el contenido que
distingue a la plataforma.
"""
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import PsychometricQuestion
from revo_comun.seguridad.tokens import Principal
from servicio_revo import servicio

router = APIRouter(prefix="/psychometric", tags=["Psicometrico"])

NUM_ESPECIALIZACIONES = 10


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


@router.get("/specialization/{spec_id}", response_model=list[PsychometricQuestionOut])
def preguntas_por_especializacion(
    spec_id: int = Path(ge=1, le=NUM_ESPECIALIZACIONES),
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """
    Las preguntas de la rama que le toco al alumno.

    Ahora exige token: antes era publica, asi que cualquiera podia
    descargarse el banco de preguntas rama por rama sin tener cuenta.
    """
    return list(
        db.scalars(
            select(PsychometricQuestion)
            .where(
                PsychometricQuestion.specialization_id == spec_id,
                PsychometricQuestion.is_active.is_(True),
            )
            .order_by(PsychometricQuestion.order_index)
        )
    )


@router.get("/all", response_model=list[PsychometricQuestionOut])
def todas_las_preguntas(
    quien: Principal = Depends(servicio.admin),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("admin")),
):
    """Banco completo. Solo administradores."""
    return list(
        db.scalars(
            select(PsychometricQuestion)
            .where(PsychometricQuestion.is_active.is_(True))
            .order_by(
                PsychometricQuestion.specialization_id,
                PsychometricQuestion.order_index,
            )
        )
    )
