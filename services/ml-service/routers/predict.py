from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from database import get_db, Prediction, ModelTrainingLog, PredictionFeedback, MLTrainingData
from model.predictor import predict, get_feature_importances
from model.trainer import load_model, train_model
from schemas import PredictRequest, PredictResponse, FeatureImportance, FeedbackRequest
from config import settings

router = APIRouter(prefix="/predict", tags=["Predicción"])


def extract_user_id(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(authorization.split(" ")[1], settings.JWT_SECRET,
                             algorithms=[settings.JWT_ALGORITHM])
        return int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


def check_and_retrain():
    from database import SessionLocal
    db = SessionLocal()
    try:
        last_log = db.query(ModelTrainingLog).order_by(ModelTrainingLog.trained_at.desc()).first()
        new_preds = 0
        if last_log and last_log.trained_at:
            new_preds = db.query(Prediction).filter(Prediction.created_at >= last_log.trained_at).count()
        else:
            new_preds = db.query(Prediction).count()
        
        if new_preds >= 50:
            print(f"🚀 [AUTO-RETRAIN] Muestras nuevas llegaron a 50. Entrenando el modelo en background...")
            train_model(db, trained_by_id=None)
    except Exception as e:
        print(f"❌ [AUTO-RETRAIN FAIL] {e}")
    finally:
        db.close()


# ── POST /predict/ ───────────────────────────────────────────
@router.post("/", response_model=PredictResponse)
def make_prediction(
    body: PredictRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: int = Depends(extract_user_id)
):
    """
    Recibe el feature_vector del survey-service y devuelve la
    especialización recomendada con el árbol de decisión.
    """
    try:
        result = predict(body.feature_vector)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    primary = result["primary"]

    # Guardar predicción en BD
    pred_record = Prediction(
        session_id                = body.session_id,
        user_id                   = body.user_id,
        primary_specialization_id = primary["specialization_id"],
        confidence_score          = primary["confidence"],
        secondary_specializations = result["top3"][1:],  # posiciones 2 y 3
        feature_vector            = body.feature_vector,
        model_version             = settings.MODEL_VERSION,
    )
    db.add(pred_record)
    db.commit()
    db.refresh(pred_record)

    background_tasks.add_task(check_and_retrain)

    return PredictResponse(
        prediction_id             = pred_record.id,
        session_id                = body.session_id,
        primary                   = primary,
        primary_specialization    = primary["name"],
        primary_specialization_id = primary["specialization_id"],
        top3                      = result["top3"],
        all_probabilities         = result["all_probabilities"],
        model_version             = settings.MODEL_VERSION,
    )





# ── GET /predict/{prediction_id} ─────────────────────────────
@router.get("/{prediction_id}", response_model=PredictResponse)
def get_prediction(
    prediction_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(extract_user_id)
):
    pred = db.query(Prediction).filter(
        Prediction.id == prediction_id,
        Prediction.user_id == user_id
    ).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")

    from model.predictor import SPECIALIZATION_MAP
    spec = SPECIALIZATION_MAP.get(pred.primary_specialization_id, {})

    primary = {
        "specialization_id": pred.primary_specialization_id,
        "name":    spec.get("name", ""),
        "icon":    spec.get("icon", ""),
        "color":   spec.get("color", ""),
        "confidence":     float(pred.confidence_score),
        "confidence_pct": round(float(pred.confidence_score) * 100, 1),
    }

    return PredictResponse(
        prediction_id     = pred.id,
        session_id        = pred.session_id,
        primary           = primary,
        top3              = pred.secondary_specializations or [],
        all_probabilities = {},
        model_version     = pred.model_version,
    )


# ── GET /predict/user/{user_id}/history ─────────────────────
@router.get("/user/{uid}/history")
def get_user_history(
    uid: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(extract_user_id)
):
    if uid != user_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    preds = db.query(Prediction).filter(
        Prediction.user_id == uid
    ).order_by(Prediction.created_at.desc()).limit(10).all()

    from model.predictor import SPECIALIZATION_MAP
    results = []
    for p in preds:
        spec = SPECIALIZATION_MAP.get(p.primary_specialization_id, {})
        results.append({
            "prediction_id":    p.id,
            "session_id":       p.session_id,
            "specialization":   spec.get("name", ""),
            "icon":             spec.get("icon", ""),
            "color":            spec.get("color", ""),
            "confidence_pct":   round(float(p.confidence_score) * 100, 1),
            "created_at":       p.created_at.isoformat() if p.created_at else None,
        })
    return results


# ── GET /predict/importances ─────────────────────────────────
@router.get("/model/importances", response_model=list[FeatureImportance])
def feature_importances():
    """Retorna qué preguntas son más determinantes en el árbol."""
    try:
        return get_feature_importances()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── GET /predict/model/tree ──────────────────────────────────
@router.get("/model/tree")
def get_tree_visualization():
    """Exporta el árbol de decisión en texto para mostrar en el frontend."""
    from model.trainer import get_tree_text
    QUESTION_LABELS = [
        "Afinidad Dev Software", "Afinidad Data/IA",
        "Afinidad Infra/Cloud", "Afinidad Ciberseguridad",
        "Afinidad Soporte IT", "Afinidad QA/Testing",
        "Afinidad Gestión", "Afinidad UX/UI",
        "Afinidad Sist Emp", "Afinidad Innovación"
    ]
    CLASS_NAMES = [
        "Soft Dev", "Data/IA", "Infra/Cloud", 
        "Ciberseguridad", "Soporte", "QA/Testing", 
        "Gestión", "UX/UI", "Sistemas Emp", "Innovación"
    ]
    try:
        tree_text = get_tree_text(QUESTION_LABELS, CLASS_NAMES)
        return {"tree": tree_text}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── POST /predict/{id}/feedback ──────────────────────────────
@router.post("/{prediction_id}/feedback", status_code=201)
def save_feedback(
    prediction_id: int,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(extract_user_id)
):
    """
    Guarda la retroalimentación del alumno sobre la predicción.
    Si el alumno confirmó afinidad, inyecta el vector como dato 'human' en ml_training_data.
    """
    pred = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")
    if pred.user_id != user_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    # Guardar feedback (upsert simple con try/except)
    try:
        fb = PredictionFeedback(
            prediction_id=prediction_id,
            user_id=user_id,
            session_id=pred.session_id,
            diagnostic_affinity=body.diagnostic_affinity,
            discovery_level=body.discovery_level,
        )
        db.add(fb)
        db.flush()
    except Exception:
        db.rollback()
        return {"status": "already_submitted"}

    # Si el alumno confirmó que el diagnóstico fue correcto,
    # inyectar su vector como dato humano en el dataset de entrenamiento.
    if body.diagnostic_affinity and pred.feature_vector:
        fv = pred.feature_vector
        sample = MLTrainingData(
            aff_1=fv.get("aff_1", 0), aff_2=fv.get("aff_2", 0),
            aff_3=fv.get("aff_3", 0), aff_4=fv.get("aff_4", 0),
            aff_5=fv.get("aff_5", 0), aff_6=fv.get("aff_6", 0),
            aff_7=fv.get("aff_7", 0), aff_8=fv.get("aff_8", 0),
            aff_9=fv.get("aff_9", 0), aff_10=fv.get("aff_10", 0),
            specialization_id=pred.primary_specialization_id,
            source="human"
        )
        db.add(sample)

    db.commit()
    return {"status": "ok", "prediction_id": prediction_id}
