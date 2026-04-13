from pydantic import BaseModel
from typing import Optional


class PredictRequest(BaseModel):
    session_id: int
    user_id: int
    feature_vector: dict  # {q1: 4.0, q2: 3.0, ...}


class SpecializationResult(BaseModel):
    specialization_id: int
    name: str
    icon: str
    color: str
    confidence: float
    confidence_pct: float


class PredictResponse(BaseModel):
    prediction_id: int
    session_id: int
    primary: SpecializationResult
    primary_specialization: str = ""       # nombre plano para el frontend (Fase 3 adaptativa)
    primary_specialization_id: int = 0      # ID de la especialización para cargar preguntas de BD
    top3: list[SpecializationResult]
    all_probabilities: dict
    model_version: str



class TrainRequest(BaseModel):
    notes: Optional[str] = None


class TrainResponse(BaseModel):
    model_version: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    training_samples: int
    test_samples: int
    tree_depth: int
    n_leaves: int


class FeatureImportance(BaseModel):
    feature: str
    importance: float
    pct: float
