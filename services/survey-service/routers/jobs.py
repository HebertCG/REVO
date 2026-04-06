from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Job
from pydantic import BaseModel

router = APIRouter(prefix="/jobs", tags=["Jobs"])

class JobOut(BaseModel):
    id: int
    specialization_id: int
    company: str
    title: str
    salary_range: str | None = None
    location: str
    url: str
    posted_days_ago: int

    class Config:
        from_attributes = True

@router.get("/specialization/{spec_id}", response_model=list[JobOut])
def get_jobs_by_specialization(spec_id: int, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.specialization_id == spec_id).all()
    if not jobs:
        raise HTTPException(status_code=404, detail="No hay ofertas para esta rama")
    return jobs
