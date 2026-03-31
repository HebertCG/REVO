from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Question
from schemas import QuestionOut

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get("/", response_model=list[QuestionOut])
def get_all_questions(
    category: str = None,
    db: Session = Depends(get_db)
):
    """Retorna todas las preguntas activas (opcionalmente filtradas por categoría)."""
    q = db.query(Question).filter(Question.is_active == True)
    if category:
        q = q.filter(Question.category == category)
    return q.order_by(Question.order_index).all()


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    return q


@router.get("/categories/list")
def get_categories():
    return {
        "categories": [
            {"key": "academic",     "label": "Académico",     "icon": "📚", "color": "#6C63FF"},
            {"key": "skills",       "label": "Habilidades",   "icon": "🛠️", "color": "#00D4FF"},
            {"key": "interests",    "label": "Intereses",     "icon": "❤️", "color": "#FF6B6B"},
            {"key": "personality",  "label": "Personalidad",  "icon": "🧠", "color": "#10B981"},
        ]
    }
