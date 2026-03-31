"""
trainer.py — Entrena el DecisionTreeClassifier con datos de revo_db.
Guarda el modelo en disco como .pkl y registra métricas en model_training_logs.
"""
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sklearn.tree import DecisionTreeClassifier, export_text
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

    # ── Árbol de Decisión ─────────────────────────────────────
    clf = DecisionTreeClassifier(
        max_depth=8,
        criterion="gini",
        min_samples_leaf=2,
        min_samples_split=4,
        class_weight="balanced",
        random_state=42,
    )
    clf.fit(X_train, y_train)

    # ── Métricas ──────────────────────────────────────────────
    y_pred = clf.predict(X_test)
    acc   = round(float(accuracy_score(y_test, y_pred)), 4)
    prec  = round(float(precision_score(y_test, y_pred, average="weighted", zero_division=0)), 4)
    rec   = round(float(recall_score(y_test, y_pred, average="weighted", zero_division=0)), 4)
    f1    = round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4)

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
        max_depth        = clf.get_depth(),
        features_used    = FEATURE_COLS,
        hyperparams      = {
            "max_depth": 8,
            "criterion": "gini",
            "min_samples_leaf": 2,
            "min_samples_split": 4,
            "class_weight": "balanced",
        },
        model_path       = settings.MODEL_PATH,
        trained_by       = trained_by_id,
        notes            = f"Auto-train con {len(X)} muestras sintéticas"
    )
    db.add(log)
    db.commit()

    return {
        "model_version":    version,
        "accuracy":         acc,
        "precision":        prec,
        "recall":           rec,
        "f1":               f1,
        "training_samples": len(X_train),
        "test_samples":     len(X_test),
        "tree_depth":       clf.get_depth(),
        "n_leaves":         clf.get_n_leaves(),
        "model_path":       settings.MODEL_PATH,
    }


def load_model() -> DecisionTreeClassifier:
    """Carga el modelo guardado en disco."""
    if not os.path.exists(settings.MODEL_PATH):
        raise FileNotFoundError(f"Modelo no encontrado en {settings.MODEL_PATH}. Entrene primero.")
    return joblib.load(settings.MODEL_PATH)


def get_tree_text(feature_names: list[str] = None, class_names: list[str] = None) -> str:
    """Exporta el árbol como texto legible para el frontend."""
    clf = load_model()
    return export_text(
        clf,
        feature_names=feature_names or FEATURE_COLS,
        class_names=class_names,
        max_depth=5,
    )
