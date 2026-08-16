"""
trainer.py — Entrena el DecisionTreeClassifier con datos de revo_db.
Guarda el modelo en disco como .pkl y registra métricas en model_training_logs.
"""
import os
import joblib
import numpy as np
import pandas as pd
from functools import lru_cache
from datetime import datetime, timezone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score
)
from sqlalchemy.orm import Session

from database import MLTrainingData, ModelTrainingLog, Specialization
from config import settings

FEATURE_COLS = [f"aff_{i}" for i in range(1, 11)]  # aff_1..aff_10


def load_training_data(db: Session) -> tuple[np.ndarray, np.ndarray]:
    """Carga los datos de entrenamiento desde PostgreSQL."""
    rows = db.query(MLTrainingData).all()
    if not rows:
        raise ValueError("No hay datos de entrenamiento en ml_training_data")

    X, y = [], []
    for row in rows:
        features = [float(getattr(row, col) or 0) for col in FEATURE_COLS]
        X.append(features)
        y.append(row.specialization_id)

    return np.array(X), np.array(y)


def train_model(db: Session, trained_by_id: int = None) -> dict:
    """
    Entrena un DecisionTreeClassifier y lo guarda en disco.
    Retorna un dict con métricas del entrenamiento.
    """
    X, y = load_training_data(db)

    # Separar train / test (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # ── Regresión Logística ───────────────────────────────────
    # multi_class="multinomial" se quitó: está deprecado desde scikit-learn
    # 1.5 y se elimina en 1.8. Multinomial ya es el comportamiento por
    # defecto, así que el modelo entrenado es idéntico.
    clf = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=42
    )
    clf.fit(X_train, y_train)

    # ── Métricas ──────────────────────────────────────────────
    y_pred = clf.predict(X_test)
    acc   = round(float(accuracy_score(y_test, y_pred)), 4)
    prec  = round(float(precision_score(y_test, y_pred, average="weighted", zero_division=0)), 4)
    rec   = round(float(recall_score(y_test, y_pred, average="weighted", zero_division=0)), 4)
    f1    = round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4)

    # ── Métrica honesta: comparación contra la regla trivial ──
    # El accuracy suelto no dice nada aquí: con el dataset sintético actual
    # la etiqueta es (casi siempre) argmax(aff_1..aff_10), así que una regla
    # de una línea sin ML alcanza ~99.8%. Lo único informativo es el "lift":
    # cuánto aporta el modelo POR ENCIMA de esa regla. Si el lift es <= 0,
    # el modelo no está aprendiendo nada que no sea el argmax.
    baseline_pred = X_test.argmax(axis=1) + 1
    baseline_acc  = round(float(accuracy_score(y_test, baseline_pred)), 4)
    lift          = round(acc - baseline_acc, 4)

    # ── Guardar modelo ────────────────────────────────────────
    os.makedirs(os.path.dirname(settings.MODEL_PATH), exist_ok=True)
    joblib.dump(clf, settings.MODEL_PATH)

    # ── Generar versión ───────────────────────────────────────
    version = f"v{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"

    # ── Registrar en BD ───────────────────────────────────────
    log = ModelTrainingLog(
        model_version    = version,
        accuracy         = acc,
        precision_score  = prec,
        recall_score     = rec,
        f1_score         = f1,
        training_samples = len(X_train),
        test_samples     = len(X_test),
        max_depth        = 0,
        features_used    = FEATURE_COLS,
        hyperparams      = {
            "max_iter": 1000,
            "class_weight": "balanced",
            "multi_class": "multinomial",
        },
        model_path       = settings.MODEL_PATH,
        trained_by       = trained_by_id,
        notes            = (
            f"{len(X)} muestras. Accuracy={acc:.4f} vs baseline argmax="
            f"{baseline_acc:.4f} (lift={lift:+.4f})"
        )
    )
    db.add(log)
    db.commit()

    # El modelo cambió: invalidar la caché en memoria del predictor.
    load_model.cache_clear()

    return {
        "model_version":    version,
        "accuracy":         acc,
        "precision":        prec,
        "recall":           rec,
        "f1":               f1,
        "baseline_accuracy": baseline_acc,
        "lift_over_baseline": lift,
        "training_samples": len(X_train),
        "test_samples":     len(X_test),
        "tree_depth":       0,
        "n_leaves":         0,
        "model_path":       settings.MODEL_PATH,
    }


@lru_cache(maxsize=1)
def load_model() -> LogisticRegression:
    """
    Carga el modelo guardado en disco.

    Cacheado en memoria: antes se leía el .pkl desde disco en CADA
    predicción y en cada poll del panel admin (/predict/model/importances
    se llama cada 5s). train_model() llama a cache_clear() al reentrenar.
    """
    if not os.path.exists(settings.MODEL_PATH):
        raise FileNotFoundError(f"Modelo no encontrado en {settings.MODEL_PATH}. Entrene primero.")
    return joblib.load(settings.MODEL_PATH)


def get_tree_text(feature_names: list[str] = None, class_names: list[str] = None) -> str:
    """Retorna una descripción legible del modelo de Regresión Logística."""
    clf = load_model()
    lines = ["=== Modelo: Regresión Logística Multinomial ==="]
    lines.append(f"Clases: {clf.classes_.tolist()}")
    lines.append(f"Iteraciones de convergencia: {clf.n_iter_.tolist()}")
    lines.append(f"Coeficientes (forma): {clf.coef_.shape}")
    return "\n".join(lines)
