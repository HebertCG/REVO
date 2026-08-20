"""
jobs.py — Ofertas de empleo por especializacion.

Catalogo publico, con las mismas protecciones que el resto de rutas.
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Job
from servicio_revo import servicio

router = APIRouter(prefix="/jobs", tags=["Empleos"])

NUM_ESPECIALIZACIONES = 10


class JobOut(BaseModel):
    id: int
    specialization_id: int
    company: str
    title: str
    salary_range: str | None = None
    location: str
    url: str
    posted_days_ago: int

    model_config = {"from_attributes": True}


@router.get("/specialization/{spec_id}", response_model=list[JobOut])
def empleos_por_especializacion(
    spec_id: int = Path(ge=1, le=NUM_ESPECIALIZACIONES),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    empleos = list(db.scalars(select(Job).where(Job.specialization_id == spec_id)))
    if not empleos:
        raise HTTPException(status_code=404, detail="No hay ofertas para esta rama")
    return empleos
