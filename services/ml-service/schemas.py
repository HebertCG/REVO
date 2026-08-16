from pydantic import BaseModel, field_validator
from typing import Optional


class PredictRequest(BaseModel):
    session_id: int
    # user_id se toma del token JWT, NUNCA del body: si viene del cliente,
    # cualquier usuario puede crear predicciones a nombre de otro.
    feature_vector: dict[str, float]  # {"aff_1": 0.8, ...} valores 0.0-1.0

    @field_validator("feature_vector")
    @classmethod
    def validate_affinities(cls, v: dict) -> dict:
        expected = {f"aff_{i}" for i in range(1, 11)}
        unknown = set(v) - expected
        if unknown:
            raise ValueError(f"Claves no reconocidas: {sorted(unknown)}")
        for key, val in v.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"{key}={val} fuera del rango 0.0-1.0")
        return v


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
    # Accuracy de la regla trivial argmax(aff) y cuanto aporta el modelo
    # por encima de ella. Es la unica cifra honesta para una sustentacion.
    baseline_accuracy: float = 0.0
    lift_over_baseline: float = 0.0
    training_samples: int
    test_samples: int
    tree_depth: int
    n_leaves: int


class FeatureImportance(BaseModel):
    feature: str
    importance: float
    pct: float


class FeedbackRequest(BaseModel):
    diagnostic_affinity: bool
    discovery_level: str
