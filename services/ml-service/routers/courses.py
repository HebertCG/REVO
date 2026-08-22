"""
courses.py — Cursos recomendados por especializacion.

Catalogo publico. Lleva cupo de peticiones igual que el resto: sin el, un
bucle sobre esta ruta agota el pool de conexiones para toda el aula.
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Course
from servicio_revo import servicio

router = APIRouter(prefix="/courses", tags=["Cursos"])

#: Hay 10 especializaciones. Acotar el rango en la propia ruta evita que un
#: id absurdo llegue siquiera a la base de datos.
NUM_ESPECIALIZACIONES = 10


class CourseOut(BaseModel):
    id: int
    specialization_id: int
    platform: str
    title: str
    url: str
    level: str
    price_model: str
    thumbnail_url: str | None = None

    model_config = {"from_attributes": True}


@router.get("/specialization/{spec_id}", response_model=list[CourseOut])
def cursos_por_especializacion(
    spec_id: int = Path(ge=1, le=NUM_ESPECIALIZACIONES),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    cursos = list(db.scalars(select(Course).where(Course.specialization_id == spec_id)))
    if not cursos:
        raise HTTPException(status_code=404, detail="No hay cursos para esta rama")
    return cursos
