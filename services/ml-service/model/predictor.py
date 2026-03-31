"""
predictor.py — Realiza predicciones con el DecisionTreeClassifier entrenado.
Retorna la especialización principal + top-3 con probabilidades.
"""
import numpy as np
from model.trainer import load_model, FEATURE_COLS

# Mapa label → nombre de especialización (sincronizado con tabla specializations)
SPECIALIZATION_MAP = {
    1: {"name": "Desarrollo de Software",             "icon": "💻", "color": "#3B82F6"},
    2: {"name": "Data Science & IA",                  "icon": "🧠", "color": "#10B981"},
    3: {"name": "Infraestructura & Cloud",            "icon": "☁️", "color": "#8B5CF6"},
    4: {"name": "Ciberseguridad",                     "icon": "🔐", "color": "#EF4444"},
    5: {"name": "Soporte Técnico & IT Ops",           "icon": "🛠️", "color": "#F59E0B"},
    6: {"name": "QA & Testing",                       "icon": "🧪", "color": "#EC4899"},
    7: {"name": "Gestión y Producto",                 "icon": "📈", "color": "#6366F1"},
    8: {"name": "Diseño UX/UI",                       "icon": "🎨", "color": "#F43F5E"},
    9: {"name": "Sistemas Empresariales",             "icon": "🏢", "color": "#14B8A6"},
    10:{"name": "Investigación e Innovación",         "icon": "🔬", "color": "#64748B"},
}


def build_feature_vector(answers: dict) -> np.ndarray:
    """
    Convierte un dict {q1: 4.0, q2: 3.0, ...} a un array numpy ordenado.
    Rellena con 3.0 (valor neutro) si falta alguna pregunta.
    """
    vector = [float(answers.get(f"aff_{i}", 0.0)) for i in range(1, 11)]
    return np.array(vector).reshape(1, -1)


def predict(answers: dict) -> dict:
    """
    Predice la especialización más adecuada para un set de respuestas.

    Args:
        answers: dict con keys q1..q20 y valores 1.0–5.0

    Returns:
        {
          primary: {specialization_id, name, icon, color, confidence},
          top3: [...],
          all_probabilities: {...},
          feature_vector: {...}
        }
    """
    clf = load_model()
    X = build_feature_vector(answers)

    # Predicción determinística
    predicted_label = int(clf.predict(X)[0])

    # Probabilidades para todas las clases
    probabilities = clf.predict_proba(X)[0]
    classes = clf.classes_

    # Construir lista ordenada de predicciones
    ranked = sorted(
        [(int(label), float(prob)) for label, prob in zip(classes, probabilities)],
        key=lambda x: x[1],
        reverse=True
    )

    primary_id, primary_score = ranked[0]
    primary_info = SPECIALIZATION_MAP.get(primary_id, {"name": "Desconocida", "icon": "❓", "color": "#999"})

    top3 = []
    for spec_id, score in ranked[:3]:
        info = SPECIALIZATION_MAP.get(spec_id, {"name": "Desconocida", "icon": "❓", "color": "#999"})
        top3.append({
            "specialization_id": spec_id,
            "name":              info["name"],
            "icon":              info["icon"],
            "color":             info["color"],
            "confidence":        round(score, 4),
            "confidence_pct":    round(score * 100, 1),
        })

    all_probs = {
        SPECIALIZATION_MAP.get(int(label), {}).get("name", str(label)): round(float(prob) * 100, 1)
        for label, prob in zip(classes, probabilities)
    }

    return {
        "primary": {
            "specialization_id": primary_id,
            "name":              primary_info["name"],
            "icon":              primary_info["icon"],
            "color":             primary_info["color"],
            "confidence":        round(primary_score, 4),
            "confidence_pct":    round(primary_score * 100, 1),
        },
        "top3":               top3,
        "all_probabilities":  all_probs,
        "feature_vector":     answers,
    }


def get_feature_importances() -> list[dict]:
    """Retorna la importancia de cada feature (pregunta) en el modelo."""
    clf = load_model()
    importances = clf.feature_importances_
    result = []
    for i, imp in enumerate(importances):
        result.append({
            "feature":    f"aff_{i+1}",
            "importance": round(float(imp), 4),
            "pct":        round(float(imp) * 100, 2),
        })
    return sorted(result, key=lambda x: x["importance"], reverse=True)
