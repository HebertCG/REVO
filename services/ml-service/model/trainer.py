"""
trainer.py — Entrena, calibra, mide y decide si el modelo sale a produccion.

El modelo fue un DecisionTreeClassifier al principio del proyecto. Se cambio
porque el arbol concentraba las predicciones en unas pocas hojas y sesgaba el
resultado hacia las ramas mas frecuentes. La regresion logistica reparte
probabilidad entre las diez clases, que es lo que la pantalla necesita.

QUE CAMBIO RESPECTO A LA VERSION ANTERIOR

Antes esto era "ajusta y sobrescribe el .pkl". Ahora es un procedimiento con
cuatro partes que tenian que existir para poder afirmar algo:

  1. PARTICION EN TRES. Antes habia dos (80/20) y el conjunto de prueba se
     usaba para reportar metricas. Calibrar necesita datos que el modelo no
     haya visto Y que no sean los de la evaluacion final: si se calibra sobre
     el conjunto de prueba, el ECE que se reporta esta medido sobre los
     mismos datos con los que se ajusto la temperatura, y sale mejor de lo
     que es.

  2. CALIBRACION. La confianza que ve el alumno pasa por temperature scaling.
     Ver model/calibracion.py.

  3. CONJUNTOS CONFORMALES. Umbral ajustado en la misma particion de
     calibracion. Ver model/conformal.py.

  4. PUERTA DE PROMOCION. Entrenar ya no implica desplegar. Ver
     model/promocion.py y model/artefactos.py.

LO QUE NO CAMBIO, Y HAY QUE SEGUIR DICIENDO

El dataset de arranque es sintetico y su etiqueta es argmax(aff_1..aff_10)
por construccion, asi que el lift sobre la regla trivial es ~0. Ninguna de
las cuatro mejoras de arriba arregla eso: se arregla cambiando el dataset
(ver PLAN.md, Fase 4) y anclando la etiqueta fuera del alumno (Fase 2).
"""
import logging
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score
)
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from config import settings
from database import MLTrainingData, ModelTrainingLog
from model import artefactos, calibracion, conformal, incertidumbre, promocion, vecinos

logger = logging.getLogger("revo.ml.entrenador")

#: Afinidades declaradas (fases 1 y 2). Siempre presentes.
COLUMNAS_AFINIDAD = [f"aff_{i}" for i in range(1, 11)]

#: Perfil de trabajo (fase 3): analitico, pragmatico, colaborativo,
#: perfeccionista. Son la unica senal del cuestionario que la regla
#: argmax(aff) no puede ver, y miden +2 puntos de acierto sobre el dataset
#: de arranque.
COLUMNAS_PERFIL = ["psy_a", "psy_b", "psy_c", "psy_d"]

#: Compatibilidad: el nombre historico. Lo usan las pruebas y el registro de
#: entrenamientos. El conjunto REAL lo decide `columnas_utilizables`.
FEATURE_COLS = COLUMNAS_AFINIDAD

#: Reparto entrenamiento / calibracion / prueba.
PROPORCION_PRUEBA = 0.20
PROPORCION_CALIBRACION = 0.20

#: Por debajo de esto no se puede partir en tres manteniendo la
#: estratificacion (10 clases x 3 particiones x 2 muestras minimas).
MINIMO_PARA_TRES_PARTICIONES = 150

MAX_ITER = 1000


def columnas_utilizables(filas: list) -> list[str]:
    """
    Decide si el perfil de la fase 3 entra en el modelo.

    Solo entra si lo traen TODAS las filas. Con una parte a NULL, el
    entrenador las convertiria en 0.0 y el modelo aprenderia "psy distinto de
    cero" como senal: eso no es una caracteristica del alumno, es CUANDO se
    cargo la fila. Es fuga de informacion, y ademas del tipo que produce
    metricas excelentes y un modelo inservible.

    Hoy pasa de verdad: el dataset sintetico trae perfil, pero las filas que
    llegan de la realimentacion del alumno todavia no, porque survey-service
    aun no envia las proporciones (PLAN.md, Fase 1.b). Asi que esta funcion
    devolvera solo las afinidades en cuanto entre la primera fila humana, y
    volvera a incluir el perfil cuando esa pieza este conectada.

    El interruptor de configuracion va PRIMERO por un motivo distinto y
    igual de importante: aunque todas las filas de entrenamiento traigan
    perfil, entrenar con el solo tiene sentido si en INFERENCIA tambien
    llega. Mientras survey-service no lo envie en /predict/, el modelo
    recibiria un relleno neutro en cuatro de sus catorce entradas.
    """
    if not settings.USAR_PERFIL_FASE3:
        return list(COLUMNAS_AFINIDAD)

    completas = all(
        all(getattr(fila, col, None) is not None for col in COLUMNAS_PERFIL)
        for fila in filas
    )
    if not completas:
        faltan = sum(
            1 for fila in filas
            if any(getattr(fila, col, None) is None for col in COLUMNAS_PERFIL)
        )
        logger.warning(
            "%s de %s filas no traen perfil de fase 3: se entrena SOLO con las "
            "afinidades. Mezclarlas le enseñaria al modelo cuando se cargo cada fila.",
            faltan, len(filas),
        )
        return list(COLUMNAS_AFINIDAD)
    return COLUMNAS_AFINIDAD + COLUMNAS_PERFIL


def load_training_data(db: Session) -> tuple[np.ndarray, np.ndarray]:
    """
    Carga los datos de entrenamiento desde PostgreSQL.

    Devuelve solo X e y por compatibilidad. Las columnas realmente usadas se
    consultan con `columnas_utilizables`; `train_model` las necesita para
    registrarlas en el artefacto.
    """
    X, y, _ = cargar_datos_y_columnas(db)
    return X, y


def cargar_datos_y_columnas(db: Session) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Como load_training_data, pero diciendo que columnas se usaron."""
    filas = db.query(MLTrainingData).all()
    if not filas:
        raise ValueError("No hay datos de entrenamiento en ml_training_data")

    columnas = columnas_utilizables(filas)
    X = np.array([
        [float(getattr(fila, col) or 0) for col in columnas] for fila in filas
    ])
    y = np.array([fila.specialization_id for fila in filas])
    return X, y, columnas


def _partir(X: np.ndarray, y: np.ndarray) -> tuple:
    """
    Parte en entrenamiento / calibracion / prueba, estratificando.

    Si no hay muestras suficientes devuelve la calibracion vacia en vez de
    fallar: un dataset pequeno tiene que poder entrenar un modelo, aunque sea
    sin calibrar. La alternativa (exigir 150 filas) dejaria el servicio sin
    modelo en cualquier despliegue nuevo.
    """
    X_ent, X_prueba, y_ent, y_prueba = train_test_split(
        X, y, test_size=PROPORCION_PRUEBA, random_state=42, stratify=y
    )

    if len(y) < MINIMO_PARA_TRES_PARTICIONES:
        vacio = np.empty((0, X.shape[1])), np.empty((0,), dtype=y.dtype)
        return X_ent, y_ent, vacio[0], vacio[1], X_prueba, y_prueba

    # La proporcion se recalcula sobre lo que queda, no sobre el total: un
    # 0.20 aplicado al 80 % restante daria un 16 % del total, no un 20 %.
    proporcion = PROPORCION_CALIBRACION / (1 - PROPORCION_PRUEBA)
    X_ent, X_cal, y_ent, y_cal = train_test_split(
        X_ent, y_ent, test_size=proporcion, random_state=42, stratify=y_ent
    )
    return X_ent, y_ent, X_cal, y_cal, X_prueba, y_prueba


def _indices_de_clase(y: np.ndarray, clases: np.ndarray) -> np.ndarray:
    """
    Pasa de etiquetas (1..10) a indices de columna (0..9).

    Las metricas de calibracion y conformal trabajan sobre las columnas de
    `predict_proba`, no sobre el valor de la etiqueta. Confundirlos produce
    un ECE calculado contra la clase equivocada, que es un fallo silencioso:
    devuelve un numero plausible y erroneo.
    """
    posicion = {int(clase): i for i, clase in enumerate(clases)}
    return np.array([posicion[int(valor)] for valor in y])


def _metricas_basicas(y_verdadero: np.ndarray, y_predicho: np.ndarray) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_verdadero, y_predicho)), 4),
        "precision": round(float(precision_score(
            y_verdadero, y_predicho, average="weighted", zero_division=0)), 4),
        "recall": round(float(recall_score(
            y_verdadero, y_predicho, average="weighted", zero_division=0)), 4),
        "f1": round(float(f1_score(
            y_verdadero, y_predicho, average="weighted", zero_division=0)), 4),
    }


def _lineas_base(X_prueba: np.ndarray, y_prueba: np.ndarray, y_ent: np.ndarray) -> dict:
    """
    Las reglas sin aprendizaje contra las que hay que compararse.

    El accuracy suelto no dice nada: lo unico informativo es cuanto aporta el
    modelo POR ENCIMA de estas. Si el lift es <= 0, una linea de codigo hace
    el mismo trabajo.
    """
    # Solo las diez primeras columnas: la regla trivial es argmax sobre las
    # AFINIDADES. Si el perfil de la fase 3 esta en X, incluirlo aqui haria
    # que la "regla trivial" mirara columnas que no son afinidades y el
    # baseline dejaria de significar lo que dice significar.
    argmax = X_prueba[:, :len(COLUMNAS_AFINIDAD)].argmax(axis=1) + 1
    clase_mayoritaria = np.bincount(y_ent).argmax()

    return {
        "argmax": round(float(accuracy_score(y_prueba, argmax)), 4),
        "clase_mayoritaria": round(float(accuracy_score(
            y_prueba, np.full_like(y_prueba, clase_mayoritaria))), 4),
    }


def train_model(db: Session, trained_by_id: int = None) -> dict:
    """
    Entrena un candidato, lo mide, y lo promueve solo si procede.

    Devuelve las metricas mas el veredicto de promocion. Que devuelva el
    veredicto y no solo las metricas es deliberado: quien llama tiene que
    poder saber si lo que acaba de entrenar esta sirviendo o no.
    """
    X, y, columnas = cargar_datos_y_columnas(db)
    X_ent, y_ent, X_cal, y_cal, X_prueba, y_prueba = _partir(X, y)

    clf = LogisticRegression(
        max_iter=MAX_ITER, class_weight="balanced", random_state=42
    )
    clf.fit(X_ent, y_ent)

    metricas = _metricas_basicas(y_prueba, clf.predict(X_prueba))
    lineas_base = _lineas_base(X_prueba, y_prueba, y_ent)
    lift = round(metricas["accuracy"] - lineas_base["argmax"], 4)

    informe_calibracion, informe_conformal = _calibrar(clf, X_cal, y_cal, X_prueba, y_prueba)

    conjunto = incertidumbre.entrenar_conjunto(clf, X_ent, y_ent)

    # Solo las afinidades: es lo que pgvector guarda como vector y contra lo
    # que se medira al alumno nuevo (ver model/vecinos.py). El perfil de
    # fase 3, si el modelo lo usa, no entra en la geometria del vecindario.
    columnas_afinidad = [i for i, c in enumerate(columnas) if c in COLUMNAS_AFINIDAD]
    informe_vecindario = vecinos.calcular_umbral(X_ent[:, columnas_afinidad])

    n_iteraciones = int(np.max(clf.n_iter_))
    # version_libre y no la marca de tiempo a secas: dos entrenamientos en el
    # mismo segundo generarian la misma cadena, el segundo pisaria el
    # directorio del primero, y la puerta de promocion acabaria comparandose
    # consigo misma y aprobando cualquier cosa.
    version = artefactos.version_libre(
        settings.MODEL_DIR,
        f"v{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
    )

    resultado = {
        "model_version": version,
        **metricas,
        "baseline_accuracy": lineas_base["argmax"],
        "lift_over_baseline": lift,
        "lineas_base": lineas_base,
        "training_samples": len(X_ent),
        "calibration_samples": len(X_cal),
        "test_samples": len(X_prueba),
        "algorithm": type(clf).__name__,
        "n_iterations": n_iteraciones,
        "n_coefficients": int(clf.coef_.size),
        "converged": n_iteraciones < MAX_ITER,
        "calibracion": informe_calibracion,
        "conformal": informe_conformal,
        "n_modelos_conjunto": len(conjunto),
        "vecindario": informe_vecindario,
        # Que columnas entraron de verdad. Un modelo entrenado con perfil de
        # fase 3 y otro sin el NO son intercambiables: el predictor tiene que
        # construir el vector con las mismas columnas y en el mismo orden.
        "features": columnas,
        "usa_perfil_fase3": len(columnas) > len(COLUMNAS_AFINIDAD),
    }

    veredicto = _promover_si_procede(version, clf, conjunto, resultado)
    resultado.update(veredicto.como_dict())
    resultado["model_path"] = str(artefactos.ruta_de(settings.MODEL_DIR, version))

    _registrar(db, resultado, trained_by_id)
    return resultado


def _calibrar(clf, X_cal, y_cal, X_prueba, y_prueba) -> tuple[dict, dict]:
    """
    Ajusta temperatura y umbral conformal, y mide lo que producen.

    Los dos se ajustan sobre la particion de CALIBRACION y se evaluan sobre
    la de PRUEBA. Hacerlo al reves (ajustar y medir en el mismo sitio) da
    numeros optimistas que no se sostienen en produccion.
    """
    if len(y_cal) == 0:
        aviso = (
            f"Menos de {MINIMO_PARA_TRES_PARTICIONES} muestras: no hay "
            "particion de calibracion. El modelo sirve SIN calibrar y el "
            "porcentaje que ve el alumno no es de fiar."
        )
        logger.warning(aviso)
        return {"temperatura": 1.0, "calibrado": False, "avisos": [aviso]}, {}

    clases = clf.classes_
    idx_cal = _indices_de_clase(y_cal, clases)
    idx_prueba = _indices_de_clase(y_prueba, clases)

    logits_cal = clf.decision_function(X_cal)
    temperatura = calibracion.ajustar_temperatura(logits_cal, idx_cal)

    # Se evalua sobre PRUEBA, que no intervino en el ajuste.
    informe = calibracion.evaluar_calibracion(
        clf.decision_function(X_prueba), idx_prueba, temperatura,
        datos_sinteticos=settings.DATASET_SINTETICO,
    )
    informe["calibrado"] = True

    probs_cal = calibracion.aplicar_temperatura(logits_cal, temperatura)
    umbral = conformal.ajustar_umbral(probs_cal, idx_cal)

    if umbral.get("suficientes_muestras"):
        probs_prueba = calibracion.aplicar_temperatura(
            clf.decision_function(X_prueba), temperatura
        )
        umbral["evaluacion"] = conformal.evaluar_cobertura(
            probs_prueba, idx_prueba, umbral["q"]
        )

    return informe, umbral


def _promover_si_procede(version, clf, conjunto, resultado) -> promocion.Veredicto:
    """Guarda siempre; promueve solo si pasa la puerta."""
    base = settings.MODEL_DIR

    artefactos.guardar(
        base, version, clf,
        metadatos={
            "algoritmo": resultado["algorithm"],
            # Las columnas REALES, no la constante: el predictor las lee de
            # aqui para construir el vector en el mismo orden.
            "features": resultado["features"],
            "usa_perfil_fase3": resultado["usa_perfil_fase3"],
            "metricas": {
                clave: resultado[clave]
                for clave in ("accuracy", "precision", "recall", "f1",
                              "baseline_accuracy", "lift_over_baseline")
            },
            "hiperparametros": {
                clave: valor for clave, valor in clf.get_params().items()
                if clave in ("max_iter", "class_weight", "solver", "C", "random_state")
            },
            "entrenado_en": datetime.now(timezone.utc).isoformat(),
            # Viaja con el modelo: un modelo nuevo no puede acabar juzgado
            # con el umbral de otro dataset.
            "vecindario": resultado["vecindario"],
        },
        calibracion=resultado["calibracion"],
        conformal=resultado["conformal"] or None,
        conjunto=conjunto,
    )

    activo = _metricas_del_activo(base)
    veredicto = promocion.decidir(
        resultado, activo,
        exigir_lift_positivo=settings.EXIGIR_LIFT_POSITIVO,
        tolerancia_f1=settings.TOLERANCIA_REGRESION_F1,
    )

    for aviso in veredicto.avisos:
        logger.warning("%s", aviso)

    if veredicto.promover:
        artefactos.promover(base, version)
        cargar_artefacto_activo.cache_clear()
    else:
        logger.warning(
            "El modelo %s NO se promovio: %s. Sigue sirviendo el anterior.",
            version, veredicto.motivo,
        )

    return veredicto


def _metricas_del_activo(base: str) -> dict | None:
    """Metricas del modelo en produccion, o None si no hay ninguno."""
    version = artefactos.version_activa(base)
    if version is None:
        return None
    try:
        return artefactos.cargar(base, version).metadatos.get("metricas")
    except artefactos.ArtefactoNoEncontrado:
        # El puntero apunta a algo que ya no esta. Se trata como "no hay
        # activo" para que el candidato pueda entrar y el servicio se
        # recupere solo.
        logger.error("El puntero apunta a %s, que no existe. Se promovera el candidato.", version)
        return None


def _registrar(db: Session, resultado: dict, trained_by_id: int | None) -> None:
    """Deja constancia en model_training_logs."""
    cal = resultado.get("calibracion") or {}
    notas = [
        f"{resultado['training_samples']}+{resultado['calibration_samples']}+"
        f"{resultado['test_samples']} muestras (ent/cal/prueba).",
        f"Accuracy={resultado['accuracy']:.4f} vs argmax="
        f"{resultado['baseline_accuracy']:.4f} (lift={resultado['lift_over_baseline']:+.4f}).",
        f"ECE={cal.get('ece_despues', 'n/d')} con T={cal.get('temperatura', 'n/d')}.",
        f"{resultado['n_iterations']} iteraciones"
        f"{'' if resultado['converged'] else ' SIN CONVERGER: subir max_iter'}.",
        f"Promocion: {resultado['motivo']}",
    ]

    db.add(ModelTrainingLog(
        model_version=resultado["model_version"],
        algorithm=resultado["algorithm"],
        accuracy=resultado["accuracy"],
        precision_score=resultado["precision"],
        recall_score=resultado["recall"],
        f1_score=resultado["f1"],
        training_samples=resultado["training_samples"],
        test_samples=resultado["test_samples"],
        n_iterations=resultado["n_iterations"],
        features_used=resultado["features"],
        hyperparams={
            "calibracion": cal,
            "conformal": resultado.get("conformal") or {},
            "lineas_base": resultado.get("lineas_base") or {},
        },
        model_path=resultado["model_path"],
        trained_by=trained_by_id,
        notes=" ".join(notas),
    ))
    db.commit()


# ── Carga del modelo en produccion ───────────────────────────

def cargar_artefacto_activo() -> artefactos.Artefacto:
    """
    Artefacto en produccion, cacheado en memoria POR VERSION.

    Sin cache, cada prediccion y cada refresco del panel de administracion
    (que consulta cada 5 s) releian el .pkl entero.

    POR QUE SE MIRA EL PUNTERO EN CADA LLAMADA

    Antes era `lru_cache(maxsize=1)` y la invalidaba `train_model` al
    promover. Con 2 workers eso solo limpiaba la cache del proceso que
    entrenaba: el otro seguia sirviendo el modelo anterior hasta reiniciarse,
    y la mitad de las predicciones salian de un modelo retirado. El puntero
    `activo.json` es compartido por los dos; leerlo es abrir un JSON de una
    linea, y el .pkl solo se relee cuando la version cambia.

    Si el almacen esta vacio pero existe el .pkl del esquema anterior, se
    adopta: es el camino del primer despliegue de este codigo sobre una
    instalacion que ya tenia modelo.
    """
    base = settings.MODEL_DIR
    version = artefactos.version_activa(base)
    if version is None:
        artefactos.adoptar_heredado(base, settings.MODEL_PATH_HEREDADO)
        version = artefactos.version_activa(base)
    return _cargar_version(str(base), version)


@lru_cache(maxsize=2)
def _cargar_version(base: str, version: str | None) -> artefactos.Artefacto:
    # maxsize=2: durante un cambio de version conviven la saliente y la
    # entrante sin releer ninguna del disco.
    return artefactos.cargar_activo(base)


# `train_model` y las pruebas siguen llamando a cache_clear().
cargar_artefacto_activo.cache_clear = _cargar_version.cache_clear


def load_model():
    """Estimador en produccion. Se conserva el nombre por compatibilidad."""
    return cargar_artefacto_activo().modelo


#: Alias historico. `train_model` y las pruebas lo usan para invalidar.
load_model.cache_clear = cargar_artefacto_activo.cache_clear


def describir_modelo() -> str:
    """Descripcion legible del modelo activo, para el panel de administracion."""
    artefacto = cargar_artefacto_activo()
    clf = artefacto.modelo
    cal = artefacto.calibracion or {}

    lineas = [
        "=== Modelo: Regresion Logistica Multinomial ===",
        f"Version activa: {artefacto.version}",
        f"Clases: {clf.classes_.tolist()}",
        f"Iteraciones hasta converger: {clf.n_iter_.tolist()}",
        f"Coeficientes (clases x afinidades): {clf.coef_.shape}",
        f"Terminos independientes: {clf.intercept_.shape}",
        "",
        "=== Calibracion ===",
    ]
    if artefacto.esta_calibrado:
        lineas += [
            f"Temperatura: {cal.get('temperatura')}",
            f"ECE antes -> despues: {cal.get('ece_antes')} -> {cal.get('ece_despues')}",
            f"Brier antes -> despues: {cal.get('brier_antes')} -> {cal.get('brier_despues')}",
        ]
        lineas += [f"AVISO: {aviso}" for aviso in cal.get("avisos", [])]
    else:
        lineas.append("SIN CALIBRAR: el porcentaje mostrado al alumno no es de fiar.")

    if artefacto.conjunto:
        lineas += ["", f"=== Conjunto bootstrap: {len(artefacto.conjunto)} modelos ==="]

    return "\n".join(lineas)
