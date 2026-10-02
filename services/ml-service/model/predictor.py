"""
predictor.py — Inferencia con probabilidades calibradas y su incertidumbre.

QUE CAMBIO

Antes esto devolvia `clf.predict_proba` tal cual y el frontend lo pintaba
como "87 % de confianza". Ahora:

  * Las probabilidades pasan por la temperatura de calibracion del artefacto.
  * Se acompanan de un diagnostico de incertidumbre que distingue "encajas en
    varias ramas" de "nunca vimos un perfil como el tuyo".
  * Se calcula el conjunto conformal, que decide CUANTAS ramas merece la pena
    mostrar en vez de devolver siempre tres.

El top-3 se conserva en la respuesta por compatibilidad con la pantalla
actual, pero `presentacion.mostrar_n` es lo que deberia mandar.

SOBRE EL MAPA DE ESPECIALIZACIONES

`SPECIALIZATION_MAP` era la unica fuente de nombres y colores aqui, y estaba
duplicado en la tabla `specializations`, en Results.jsx y en Admin.jsx. Los
cuatro ya divergieron: esta tabla y el frontend discrepan en el color de
todas las ramas.

Ahora `predict` acepta el catalogo leido de la base y el mapa se queda solo
como respaldo para cuando la consulta no este disponible (por ejemplo en las
pruebas unitarias). La fuente de verdad es la tabla.
"""
import numpy as np

from model import calibracion, conformal, incertidumbre
from model.trainer import cargar_artefacto_activo

#: Respaldo. NO es la fuente de verdad: lo es la tabla `specializations`.
#: Se conserva para que el servicio pueda responder si la consulta al
#: catalogo falla, y porque las pruebas unitarias no tienen base de datos.
SPECIALIZATION_MAP = {
    1: {"name": "Desarrollo de Software",     "icon": "💻", "color": "#3B82F6"},
    2: {"name": "Data Science & IA",          "icon": "🧠", "color": "#10B981"},
    3: {"name": "Infraestructura & Cloud",    "icon": "☁️", "color": "#8B5CF6"},
    4: {"name": "Ciberseguridad",             "icon": "🔐", "color": "#EF4444"},
    5: {"name": "Soporte Técnico & IT Ops",   "icon": "🛠️", "color": "#F59E0B"},
    6: {"name": "QA & Testing",               "icon": "🧪", "color": "#EC4899"},
    7: {"name": "Gestión y Producto",         "icon": "📈", "color": "#6366F1"},
    8: {"name": "Diseño UX/UI",               "icon": "🎨", "color": "#F43F5E"},
    9: {"name": "Sistemas Empresariales",     "icon": "🏢", "color": "#14B8A6"},
    10: {"name": "Investigación e Innovación", "icon": "🔬", "color": "#64748B"},
}

DESCONOCIDA = {"name": "Desconocida", "icon": "❓", "color": "#999999"}

N_AFINIDADES = 10


#: Relleno de un perfil de fase 3 ausente. 0.25 en las cuatro, no 0.0.
#:
#: Son PROPORCIONES que suman 1: un 0.0 significa "este alumno no eligio
#: nunca ese estilo", que es un valor real y extremo. Para decir "no lo
#: sabemos" el valor honesto es el reparto uniforme.
PERFIL_NEUTRO = 0.25


def build_feature_vector(answers: dict, columnas: list[str] | None = None) -> np.ndarray:
    """
    Convierte {aff_1: 0.9, ...} en el array que espera el modelo.

    `columnas` viene de los metadatos del artefacto. Es lo que garantiza que
    el vector se construya con las MISMAS entradas y en el MISMO orden con
    los que se entreno: un modelo entrenado con perfil de fase 3 y otro sin
    el no son intercambiables, y alimentar 10 columnas a un modelo de 14 no
    falla de forma limpia, falla con un error de forma a media peticion.

    Una afinidad que falte se rellena con 0.0: las afinidades van de 0 a 1 y
    0.0 significa "esta rama no se exploro", que es lo que pasa de verdad con
    las ramas fuera del top 3. Un perfil que falte se rellena con el reparto
    uniforme, por el motivo de PERFIL_NEUTRO.
    """
    if columnas is None:
        columnas = [f"aff_{i}" for i in range(1, N_AFINIDADES + 1)]

    vector = [
        float(answers.get(col, PERFIL_NEUTRO if col.startswith("psy_") else 0.0))
        for col in columnas
    ]
    return np.array(vector).reshape(1, -1)


def _info_de(spec_id: int, catalogo: dict | None) -> dict:
    """Nombre, icono y color de una rama. La base manda; el mapa es respaldo."""
    if catalogo and spec_id in catalogo:
        return catalogo[spec_id]
    return SPECIALIZATION_MAP.get(spec_id, DESCONOCIDA)


def _resultado(spec_id: int, probabilidad: float, catalogo: dict | None) -> dict:
    info = _info_de(spec_id, catalogo)
    return {
        "specialization_id": spec_id,
        "name": info["name"],
        "icon": info.get("icon", ""),
        "color": info.get("color", ""),
        "confidence": round(probabilidad, 4),
        "confidence_pct": round(probabilidad * 100, 1),
    }


def predict(answers: dict, catalogo: dict | None = None) -> dict:
    """
    Predice la especializacion mas adecuada para un conjunto de respuestas.

    `catalogo` es {id: {"name","icon","color"}} leido de `specializations`.
    Si no llega, se usa el mapa de respaldo.
    """
    artefacto = cargar_artefacto_activo()
    clf = artefacto.modelo
    # Las columnas salen del artefacto, no de una constante: el modelo activo
    # puede haberse entrenado con perfil de fase 3 o sin el.
    X = build_feature_vector(answers, artefacto.metadatos.get("features"))

    # Probabilidades CALIBRADAS. La temperatura es monotona, asi que el
    # argmax no cambia: lo que cambia es cuanta confianza se declara.
    probabilidades = calibracion.aplicar_temperatura(
        clf.decision_function(X), artefacto.temperatura
    )[0]
    clases = [int(c) for c in clf.classes_]

    ordenadas = sorted(
        zip(clases, (float(p) for p in probabilidades)),
        key=lambda par: par[1], reverse=True,
    )

    desacuerdo = (
        incertidumbre.desacuerdo(artefacto.conjunto, X) if artefacto.conjunto else None
    )
    diagnostico = incertidumbre.diagnosticar(probabilidades, desacuerdo)

    conjunto_ids, presentacion = _conjunto_conformal(artefacto, probabilidades, clases)

    primary_id, primary_score = ordenadas[0]
    return {
        "primary": _resultado(primary_id, primary_score, catalogo),
        "top3": [_resultado(sid, score, catalogo) for sid, score in ordenadas[:3]],
        "all_probabilities": {
            _info_de(sid, catalogo)["name"]: round(score * 100, 1)
            for sid, score in ordenadas
        },
        "feature_vector": answers,
        "model_version": artefacto.version,
        "calibrado": artefacto.esta_calibrado,
        "incertidumbre": diagnostico,
        "conjunto_conformal": [
            _resultado(sid, dict(ordenadas)[sid], catalogo) for sid in conjunto_ids
        ],
        "presentacion": presentacion,
        # Para las consultas a pgvector que hace la ruta despues de guardar
        # (ver consultas_vectoriales.py): la probabilidad de cada rama por su
        # id, en 0..1, y el umbral de vecindario con el que se entreno.
        "probabilidades_por_id": {sid: score for sid, score in ordenadas},
        "vecindario_entrenamiento": artefacto.metadatos.get("vecindario"),
    }


def _conjunto_conformal(artefacto, probabilidades, clases) -> tuple[list[int], dict]:
    """
    Conjunto de ramas con cobertura garantizada, y que hacer con el.

    Si el artefacto no trae umbral (modelo sin calibrar o con pocas muestras),
    se degrada al top-3 de siempre y se dice que se ha degradado. Callarlo
    haria pasar por garantizado algo que no lo es.
    """
    umbral = artefacto.conformal or {}
    if not umbral.get("suficientes_muestras"):
        ids = [sid for sid, _ in sorted(
            zip(clases, probabilidades), key=lambda par: par[1], reverse=True)][:3]
        return ids, {
            "modo": "sin_garantia",
            "mostrar_n": 3,
            "mensaje": "Estas son tus tres ramas mas probables.",
            "aviso_interno": (
                "Sin umbral conformal (faltan muestras de calibracion): "
                "el conjunto es el top-3 de siempre, sin cobertura garantizada."
            ),
        }

    indices = conformal.conjunto_prediccion(probabilidades, umbral["q"])
    ids = [clases[i] for i in indices]
    return ids, conformal.decidir_presentacion(ids)


def get_feature_importances() -> list[dict]:
    """
    Peso de cada afinidad en la decision del modelo.

    Un arbol da esto hecho en `feature_importances_`. Una regresion no tiene
    ese atributo: lo que hay son coeficientes con signo, uno por clase y
    afinidad. Se toma la media del valor ABSOLUTO por afinidad (el signo dice
    hacia que clase empuja, no cuanto pesa) y se normaliza a 100 %.
    """
    clf = cargar_artefacto_activo().modelo
    importancias = np.abs(clf.coef_).mean(axis=0)
    if importancias.sum() > 0:
        importancias = importancias / importancias.sum()

    resultado = [
        {
            "feature": f"aff_{i + 1}",
            "importance": round(float(valor), 4),
            "pct": round(float(valor) * 100, 2),
        }
        for i, valor in enumerate(importancias)
    ]
    return sorted(resultado, key=lambda fila: fila["importance"], reverse=True)
