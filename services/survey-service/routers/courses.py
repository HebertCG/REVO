from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Course
from pydantic import BaseModel

router = APIRouter(prefix="/courses", tags=["Courses"])

class CourseOut(BaseModel):
    id: int
    specialization_id: int
    platform: str
    title: str
    url: str
    level: str
    price_model: str
    thumbnail_url: str | None = None

    class Config:
        from_attributes = True

@router.get("/specialization/{spec_id}", response_model=list[CourseOut])
def get_courses_by_specialization(spec_id: int, db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.specialization_id == spec_id).all()
    if not courses:
        raise HTTPException(status_code=404, detail="No hay cursos para esta rama")
    return courses
