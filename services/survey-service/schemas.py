from pydantic import BaseModel, field_validator
from typing import Optional, Any
from datetime import datetime


class QuestionOut(BaseModel):
    id: int
    text: str
    category: str
    question_type: str
    options: Optional[Any]
    min_label: Optional[str]
    max_label: Optional[str]
    weight: float
    order_index: int
    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    pass  # El user_id viene del token JWT


class SessionOut(BaseModel):
    id: int
    user_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    model_config = {"from_attributes": True}


class AnswerIn(BaseModel):
    question_id: int
    value: float

    @field_validator("value")
    @classmethod
    def validate_value(cls, v):
        if not (1.0 <= v <= 5.0):
            raise ValueError("El valor debe estar entre 1 y 5")
        return v


class BulkAnswerIn(BaseModel):
    answers: list[AnswerIn]


class AnswerOut(BaseModel):
    id: int
    session_id: int
    question_id: int
    value: float
    answered_at: datetime
    model_config = {"from_attributes": True}


class SessionWithAnswers(BaseModel):
    session: SessionOut
    answers: list[AnswerOut]
    total_questions: int
    answered: int
    progress_pct: float


class SessionComplete(BaseModel):
    session_id: int
    feature_vector: dict  # {q1: val, q2: val, ...} para enviar al ML service
