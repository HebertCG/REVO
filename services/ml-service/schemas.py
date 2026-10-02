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

    # ── Lo que el modelo sabe sobre su propia respuesta ──────
    #: False cuando el modelo se entreno sin particion de calibracion. El
    #: frontend debe atenuar el porcentaje cuando esto es False, porque
    #: entonces no significa lo que parece.
    calibrado: bool = False
    #: Entropia, margenes y la lectura ("definido" / "encaja_en_varias" /
    #: "perfil_poco_visto"). Ver model/incertidumbre.py.
    incertidumbre: dict = {}
    #: Ramas con cobertura garantizada. Puede tener 1, 2, 3 o mas elementos:
    #: el tamano ES la medida de incertidumbre.
    conjunto_conformal: list[SpecializationResult] = []
    #: Que debe hacer la pantalla con lo anterior. Ver conformal.decidir_presentacion.
    presentacion: dict = {}

    # ── Lo que aporta pgvector (ver consultas_vectoriales.py) ─
    #: Distancia a los alumnos mas parecidos del dataset y si el perfil es
    #: de los que el modelo casi no ha visto. `disponible: False` si no se
    #: pudo medir: no es lo mismo que "perfil normal".
    vecindario: dict = {}
    #: Ocupaciones reales de O*NET con un perfil de intereses parecido al que
    #: el modelo atribuye al alumno. Intereses parecidos, no "de tu rama".
    ocupaciones_afines: list[dict] = []



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
    # Complejidad de la regresion. Sustituyen a tree_depth y n_leaves, que
    # describian un arbol y viajaban siempre a 0.
    algorithm: str = "LogisticRegression"
    n_iterations: int = 0
    n_coefficients: int = 0
    converged: bool = True

    # ── Particion de calibracion ─────────────────────────────
    calibration_samples: int = 0
    #: Temperatura, ECE antes/despues, Brier y el diagrama de fiabilidad.
    calibracion: dict = {}
    #: Umbral conformal y la cobertura real que produce sobre el test.
    conformal: dict = {}
    #: argmax y clase mayoritaria. Sin estas cifras el accuracy no dice nada.
    lineas_base: dict = {}

    # ── Puerta de promocion ──────────────────────────────────
    #: False significa que el modelo se entreno y se guardo, pero NO salio a
    #: produccion. Quien entrena tiene que poder saberlo.
    promovido: bool = True
    motivo: str = ""
    avisos: list[str] = []


class FeatureImportance(BaseModel):
    feature: str
    importance: float
    pct: float


class FeedbackRequest(BaseModel):
    diagnostic_affinity: bool
    discovery_level: str
    #: Cuando el alumno dice que el diagnostico NO lo representa, cual cree
    #: que si. Es la pieza que faltaba para romper el bucle de
    #: realimentacion: antes solo se reinyectaban los ACIERTOS confirmados,
    #: asi que el modelo se reforzaba a si mismo y no se corregia nunca.
    #:
    #: Opcional: el alumno puede discrepar sin saber cual es la correcta, y
    #: obligarle a elegir produciria correcciones inventadas, que son peores
    #: que ninguna.
    corrected_specialization_id: Optional[int] = None

    @field_validator("corrected_specialization_id")
    @classmethod
    def validar_rama(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 10):
            raise ValueError("La especializacion corregida tiene que estar entre 1 y 10")
        return v
