"""
questions.py — Catalogo de preguntas.

Es informacion publica (no hay datos de ningun alumno), pero sigue teniendo
cupo de peticiones: sin el, cualquiera puede pedir el catalogo completo en
bucle y saturar el pool de conexiones para toda el aula.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Question
from schemas import QuestionOut
from servicio_revo import servicio

router = APIRouter(prefix="/questions", tags=["Preguntas"])

#: Categorias validas. La lista cerrada evita que el filtro que llega por la
#: URL se use tal cual contra la base de datos.
CATEGORIAS = {
    "academic": {"label": "Academico", "icon": "📚", "color": "#6C63FF"},
    "skills": {"label": "Habilidades", "icon": "🛠️", "color": "#00D4FF"},
    "interests": {"label": "Intereses", "icon": "❤️", "color": "#FF6B6B"},
    "personality": {"label": "Personalidad", "icon": "🧠", "color": "#10B981"},
}

#: Tope de preguntas por respuesta. El pool completo son unas 100; devolverlo
#: entero en cada peticion es innecesario y caro.
LIMITE_MAXIMO = 200


@router.get("/", response_model=list[QuestionOut])
def listar_preguntas(
    category: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=100, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """Preguntas activas, opcionalmente filtradas por categoria."""
    if category is not None and category not in CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoria no valida")

    consulta = select(Question).where(Question.is_active.is_(True))
    if category:
        consulta = consulta.where(Question.category == category)

    return list(db.scalars(consulta.order_by(Question.order_index).limit(limit)))


@router.get("/categories/list")
def listar_categorias(_: None = Depends(servicio.limitar("read"))):
    return {
        "categories": [
            {"key": clave, **datos} for clave, datos in CATEGORIAS.items()
        ]
    }


@router.get("/{question_id}", response_model=QuestionOut)
def obtener_pregunta(
    question_id: int,
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    pregunta = db.scalar(select(Question).where(Question.id == question_id))
    if pregunta is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    return pregunta
