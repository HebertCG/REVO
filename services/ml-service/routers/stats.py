from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from jose import JWTError, jwt

from database import get_db, Prediction, ModelTrainingLog
from model.trainer import train_model
from schemas import TrainRequest, TrainResponse
from config import settings

router = APIRouter(prefix="/stats", tags=["Estadísticas & Admin"])


def require_admin(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(authorization.split(" ")[1], settings.JWT_SECRET,
                             algorithms=[settings.JWT_ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Solo administradores")
        return int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ── POST /stats/train ────────────────────────────────────────
@router.post("/train", response_model=TrainResponse)
def retrain_model(
    body: TrainRequest = TrainRequest(),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin)
):
    """Re-entrena el árbol de decisión con todos los datos actuales."""
    try:
        metrics = train_model(db, trained_by_id=admin_id)
        return TrainResponse(
            model_version    = metrics["model_version"],
            accuracy         = metrics["accuracy"],
            precision        = metrics["precision"],
            recall           = metrics["recall"],
            f1               = metrics["f1"],
            training_samples = metrics["training_samples"],
            test_samples     = metrics["test_samples"],
            tree_depth       = metrics["tree_depth"],
            n_leaves         = metrics["n_leaves"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /stats/overview ──────────────────────────────────────
@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """Estadísticas globales para el dashboard admin."""
    total_preds = db.query(Prediction).count()

    # Distribución de especializaciones
    dist_raw = db.execute(text("""
        SELECT s.name, s.icon, s.color_hex, COUNT(p.id) as total
        FROM specializations s
        LEFT JOIN predictions p ON p.primary_specialization_id = s.id
        GROUP BY s.id, s.name, s.icon, s.color_hex
        ORDER BY total DESC
    """)).fetchall()
    distribution = [
        {"name": r[0], "icon": r[1], "color": r[2], "total": r[3]}
        for r in dist_raw
    ]

    # Último entrenamiento
    last_log = db.query(ModelTrainingLog).order_by(
        ModelTrainingLog.trained_at.desc()
    ).first()
    last_train = None
    if last_log:
        last_train = {
            "model_version": last_log.model_version,
            "accuracy":     float(last_log.accuracy) if last_log.accuracy else None,
            "f1":           float(last_log.f1_score) if last_log.f1_score else None,
            "trained_at":   last_log.trained_at.isoformat() if last_log.trained_at else None,
            "samples":      last_log.training_samples,
        }

    # Promedio de confianza
    avg_conf = db.execute(text(
        "SELECT ROUND(AVG(confidence_score) * 100, 1) FROM predictions"
    )).scalar()

    return {
        "total_predictions":   total_preds,
        "avg_confidence_pct":  float(avg_conf) if avg_conf else 0,
        "specialization_dist": distribution,
        "last_training":       last_train,
    }


# ── GET /stats/training-history ─────────────────────────────
@router.get("/training-history")
def get_training_history(db: Session = Depends(get_db)):
    """Historial de entrenamientos del modelo."""
    logs = db.query(ModelTrainingLog).order_by(
        ModelTrainingLog.trained_at.desc()
    ).limit(20).all()
    return [
        {
            "model_version":    l.model_version,
            "accuracy":         float(l.accuracy) if l.accuracy else None,
            "f1":               float(l.f1_score) if l.f1_score else None,
            "training_samples": l.training_samples,
            "tree_depth":       l.max_depth,
            "trained_at":       l.trained_at.isoformat() if l.trained_at else None,
        }
        for l in logs
    ]
