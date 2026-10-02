"""
predict.py — Inferencia del modelo y retroalimentacion del alumno.

La logica de ML (model/predictor.py y model/trainer.py) no se toca. Lo que
cambia aqui es infraestructura:
  - La identidad sale del token verificado (emisor, audiencia, proposito) y
    se propaga a la base de datos como contexto RLS.
  - Cada ruta declara su cupo de peticiones.
  - El reentrenamiento en segundo plano corre con el rol 'service', que puede
    leer el dataset completo sin hacerse pasar por administrador.
"""
import logging
import threading

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import catalogo
import consultas_vectoriales
from config import settings
from database import MLTrainingData, ModelTrainingLog, Prediction, PredictionFeedback
from model import conformal, incertidumbre
from model.predictor import get_feature_importances, predict
from model.trainer import train_model
from revo_comun.seguridad.tokens import Principal
from schemas import FeatureImportance, FeedbackRequest, PredictRequest, PredictResponse
from servicio_revo import servicio

logger = logging.getLogger("revo.ml.predict")

router = APIRouter(prefix="/predict", tags=["Prediccion"])


#: Clave del cerrojo consultivo de PostgreSQL que serializa los
#: reentrenamientos entre workers y procesos. Cualquier entero fijo vale; se
#: deja escrito para que nadie la reutilice para otra cosa.
CLAVE_CERROJO_REENTRENAMIENTO = 7_361_001

#: Y dentro de un mismo proceso, entre hilos de BackgroundTasks.
_reentrenando = threading.Lock()


def check_and_retrain():
    """
    Reentrena si han llegado suficientes muestras nuevas, UNA vez a la vez.

    DEFECTO QUE ESTO CORRIGE, medido en la prueba de carga (2026-09-21): cada
    prediccion programa esta funcion en segundo plano, y en cuanto habia 50
    nuevas TODAS las siguientes veian el umbral superado y arrancaban su
    propio entrenamiento, hasta que el primero terminaba y lo registraba. Con
    135 alumnos a la vez hubo 12 entrenamientos en paralelo: la CPU por alumno
    paso de 0,8 s a 4,2 s y la prediccion tardo 8,9 s en el percentil 95.

    Dos cerrojos, porque hay dos niveles de concurrencia:

      proceso   un Lock: los hilos de BackgroundTasks de este worker
      sistema   pg_try_advisory_lock: los demas workers y servicios. Vive en
                una conexion propia porque el cerrojo es de CONEXION, y la
                sesion de entrenamiento cambia de conexion entre commits;
                si muriera el proceso, al cerrarse la conexion se suelta solo.

    Los dos son "try": quien no lo consigue no espera, se va. Cuando el que
    entrena termine, las 50 predicciones ya contaran como entrenadas.
    """
    if not _reentrenando.acquire(blocking=False):
        return
    try:
        with servicio.motor.connect() as conexion:
            libre = conexion.execute(
                text("SELECT pg_try_advisory_lock(:clave)"),
                {"clave": CLAVE_CERROJO_REENTRENAMIENTO},
            ).scalar()
            if not libre:
                return
            try:
                _reentrenar_si_toca()
            except Exception as exc:  # noqa: BLE001 - segundo plano: se registra
                logger.error("El reentrenamiento automatico fallo: %s", exc, exc_info=True)
            finally:
                conexion.execute(
                    text("SELECT pg_advisory_unlock(:clave)"),
                    {"clave": CLAVE_CERROJO_REENTRENAMIENTO},
                )
    finally:
        _reentrenando.release()


def _reentrenar_si_toca() -> None:
    """
    Cuenta las predicciones nuevas y entrena si llegan al umbral.

    Se cuenta DENTRO del cerrojo: quien lo consigue justo despues de otro
    entrenamiento ve el contador ya a cero y no repite el trabajo.

    Corre fuera del ciclo de la peticion, con identidad de servicio: necesita
    contar TODAS las predicciones y leer el dataset completo, cosa que el
    contexto de un alumno no permite.
    """
    db = servicio.sesion_de_servicio()
    try:
        last_log = db.query(ModelTrainingLog).order_by(ModelTrainingLog.trained_at.desc()).first()
        new_preds = 0
        if last_log and last_log.trained_at:
            new_preds = db.query(Prediction).filter(Prediction.created_at >= last_log.trained_at).count()
        else:
            new_preds = db.query(Prediction).count()
        
        if new_preds >= settings.UMBRAL_REENTRENAMIENTO:
            logger.info(
                "Llegaron %s muestras nuevas: reentrenando en segundo plano", new_preds
            )
            train_model(db, trained_by_id=None)
    finally:
        db.close()


# ── POST /predict/ ───────────────────────────────────────────
#: Lo que se guarda en `predictions.detalle` y devuelve el GET. Solo lo que
#: NO tiene columna propia: repetir primary o model_version aqui abriria la
#: puerta a que discrepen. `probabilidades_por_id` tampoco: sus claves son
#: enteros y JSON las convertiria en texto al leerlas de vuelta.
CAMPOS_DETALLE = (
    "all_probabilities", "calibrado", "incertidumbre", "conjunto_conformal",
    "presentacion", "vecindario", "ocupaciones_afines",
)


def con_vecindario(result: dict, vectorial: dict) -> dict:
    """
    El resultado con la lectura y la presentacion corregidas por el vecindario.

    Sin esto, la alerta de "perfil poco visto" quedaba guardada en su propio
    campo pero el mensaje seguia diciendo "apuntan claramente a una rama".
    """
    diagnostico = incertidumbre.incorporar_vecindario(
        result["incertidumbre"], vectorial["vecindario"])
    return {
        **result,
        "incertidumbre": diagnostico,
        "presentacion": conformal.ajustar_por_lectura(result["presentacion"], diagnostico),
    }


def detalle_de(result: dict, vectorial: dict) -> dict:
    """El resultado completo, tal como se guardara y se devolvera."""
    completo = {**result, **vectorial}
    return {campo: completo[campo] for campo in CAMPOS_DETALLE if campo in completo}


@router.post("/", response_model=PredictResponse)
def make_prediction(
    body: PredictRequest,
    background_tasks: BackgroundTasks,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("predict")),
):
    """
    Recibe el feature_vector del survey-service y devuelve la
    especializacion recomendada.
    """
    try:
        # El catalogo sale de la tabla `specializations`, no del mapa
        # duplicado de predictor.py. Ver catalogo.py.
        result = predict(body.feature_vector, catalogo=catalogo.obtener(db))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    primary = result["primary"]

    # ANTES de escribir nada: si pgvector fallara, consultas_vectoriales deshace
    # una transaccion que todavia no contiene la prediccion, y la sesion
    # reaplica el contexto RLS al empezar la siguiente. Asi todo va en un
    # solo INSERT (revo_ml no tiene UPDATE sobre predictions).
    vectorial = consultas_vectoriales.enriquecer(db, body.feature_vector, result)
    result = con_vecindario(result, vectorial)
    detalle = detalle_de(result, vectorial)

    # Guardar predicción en BD
    pred_record = Prediction(
        session_id                = body.session_id,
        # Identidad tomada del token, no del body (ver PredictRequest).
        user_id                   = quien.user_id,
        primary_specialization_id = primary["specialization_id"],
        confidence_score          = primary["confidence"],
        secondary_specializations = result["top3"][1:],  # posiciones 2 y 3
        feature_vector            = body.feature_vector,
        # La version REAL del artefacto que hizo esta prediccion, no la
        # constante 'v1.0' de la configuracion. Con la constante era imposible
        # saber que modelo produjo que prediccion, y sin eso no se puede
        # analizar deriva ni comparar versiones.
        model_version             = result["model_version"],
        detalle                   = detalle,
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
        model_version             = result["model_version"],
        **detalle,
    )





# ── GET /predict/{prediction_id} ─────────────────────────────
@router.get("/{prediction_id}", response_model=PredictResponse)
def get_prediction(
    prediction_id: int,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    # El filtro por user_id se mantiene, pero RLS ya impide que esta consulta
    # alcance la prediccion de otro alumno aunque el filtro desapareciera.
    pred = db.scalar(
        select(Prediction).where(
            Prediction.id == prediction_id,
            Prediction.user_id == quien.user_id,
        )
    )
    if not pred:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")

    spec = catalogo.obtener(db).get(pred.primary_specialization_id, {})

    primary = {
        "specialization_id": pred.primary_specialization_id,
        "name":    spec.get("name", ""),
        "icon":    spec.get("icon", ""),
        "color":   spec.get("color", ""),
        "confidence":     float(pred.confidence_score),
        "confidence_pct": round(float(pred.confidence_score) * 100, 1),
    }

    # Lo que el modelo dijo EN SU MOMENTO (migracion 38). Recalcularlo aqui
    # daria otro resultado si el modelo se ha reentrenado desde entonces.
    # Las predicciones anteriores no lo tienen: salen como antes.
    guardado = {campo: valor for campo, valor in (pred.detalle or {}).items()
                if campo in CAMPOS_DETALLE}

    return PredictResponse(
        prediction_id     = pred.id,
        session_id        = pred.session_id,
        primary           = primary,
        top3              = pred.secondary_specializations or [],
        model_version     = pred.model_version,
        **{"all_probabilities": {}, **guardado},
    )


# ── GET /predict/user/{user_id}/history ─────────────────────
@router.get("/user/{uid}/history")
def get_user_history(
    uid: int,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    if uid != quien.user_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    preds = list(
        db.scalars(
            select(Prediction)
            .where(Prediction.user_id == quien.user_id)
            .order_by(Prediction.created_at.desc())
            .limit(10)
        )
    )

    ramas = catalogo.obtener(db)
    results = []
    for p in preds:
        spec = ramas.get(p.primary_specialization_id, {})
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
def feature_importances(
    quien: Principal = Depends(servicio.admin),
    _: None = Depends(servicio.limitar("admin")),
):
    """
    Peso de cada feature en el modelo. Solo administradores.

    Antes era publica. Los pesos del modelo son la receta del producto: con
    ellos se deduce que responder para obtener la especializacion que se
    quiera, y se replica el sistema sin el dataset.
    """
    try:
        return get_feature_importances()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── GET /predict/model/resumen ───────────────────────────────
@router.get("/model/resumen")
def get_model_summary(
    quien: Principal = Depends(servicio.admin),
    _: None = Depends(servicio.limitar("admin")),
):
    """
    Descripcion legible del modelo, para el panel admin. Solo administradores.

    La ruta se llamaba /model/tree y la funcion get_tree_visualization, de
    cuando el modelo era un arbol de decision. Las dos listas de etiquetas
    que habia aqui (QUESTION_LABELS y CLASS_NAMES) se pasaban a la funcion y
    esta no las usaba nunca: eran la firma de sklearn.tree.export_text.
    """
    from model.trainer import describir_modelo
    try:
        return {"resumen": describir_modelo()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── POST /predict/{id}/feedback ──────────────────────────────
@router.post("/{prediction_id}/feedback", status_code=201)
def save_feedback(
    prediction_id: int,
    body: FeedbackRequest,
    quien: Principal = Depends(servicio.principal),
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """
    Guarda la retroalimentacion del alumno y alimenta el dataset con ella.

    EL BUCLE QUE ESTA RUTA TENIA ROTO

    Antes, solo se reinyectaba el vector cuando `diagnostic_affinity` era
    True. Cuando el alumno decia que el diagnostico NO lo representaba, eso
    incrementaba un contador del panel y nada mas.

    El efecto compuesto es el peor posible: el dataset solo recibe ejemplos
    que el modelo YA acertaba, asi que cada reentrenamiento refuerza lo que
    el modelo ya creia y no corrige nada. El modelo se parece cada vez mas a
    si mismo. Es un bucle de realimentacion de manual, y ademas el
    reentrenamiento es automatico cada 50 predicciones, o sea que la deriva
    ocurre sin que nadie intervenga.

    Ahora tambien entra el desacuerdo: si el alumno dice cual era su rama, la
    muestra se guarda con la etiqueta CORREGIDA y source='human_corrected'.
    Esas son las unicas filas del dataset que pueden enseñarle algo nuevo al
    modelo.

    Si discrepa pero no dice cual, se registra el desacuerdo sin inventar
    etiqueta: una correccion inventada es peor que ninguna.
    """
    pred = db.scalar(select(Prediction).where(Prediction.id == prediction_id))
    if not pred:
        raise HTTPException(status_code=404, detail="Prediccion no encontrada")
    if pred.user_id != quien.user_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    try:
        db.add(PredictionFeedback(
            prediction_id=prediction_id,
            user_id=quien.user_id,
            session_id=pred.session_id,
            diagnostic_affinity=body.diagnostic_affinity,
            discovery_level=body.discovery_level,
            corrected_specialization_id=body.corrected_specialization_id,
        ))
        db.flush()
    except IntegrityError:
        # Solo un duplicado (prediction_id es UNIQUE) significa "ya enviada".
        # Antes se capturaba Exception y cualquier fallo -de permisos, de
        # conexion- se contestaba como "ya enviada": el alumno creia que su
        # respuesta constaba y no constaba.
        db.rollback()
        return {"status": "already_submitted"}

    aportacion = _muestra_desde_feedback(pred, body)
    if aportacion is not None:
        db.execute(sentencia_de_aportacion(aportacion))

    db.commit()
    return {
        "status": "ok",
        "prediction_id": prediction_id,
        # Se devuelve para que quede claro en las pruebas y en los logs si
        # esta respuesta aporto dato o solo quedo registrada.
        "aporte_al_dataset": aportacion.source if aportacion is not None else None,
    }


def sentencia_de_aportacion(aportacion: MLTrainingData):
    """
    INSERT de la muestra en el dataset, SIN `RETURNING`.

    DEFECTO QUE ESTO CORRIGE, encontrado en la prueba de carga: con
    `db.add()` el ORM hace INSERT ... RETURNING id, y RETURNING exige poder
    LEER la fila nueva. La politica de ml_training_data no deja a ningun
    alumno leer el dataset (10_rls.sql), asi que cada realimentacion fallaba
    con 503 y el bucle -las etiquetas 'human' y 'human_corrected'- no recibio
    nunca un dato real. Sin RETURNING solo se comprueba el permiso de APORTAR,
    que el alumno si tiene. El id no hace falta: nadie lo usa despues.
    """
    valores = {
        columna.name: getattr(aportacion, columna.key)
        for columna in MLTrainingData.__table__.columns
        if columna.name != "id" and getattr(aportacion, columna.key) is not None
    }
    # .inline(): sin esto SQLAlchemy 2.0 anade RETURNING id por su cuenta,
    # incluso en un insert() de Core, para conocer la clave primaria.
    return insert(MLTrainingData).values(**valores).inline()


def _muestra_desde_feedback(pred: Prediction, body: FeedbackRequest):
    """
    Convierte la respuesta del alumno en una fila de entrenamiento, o en nada.

    Tres casos y solo dos producen dato:

      * Confirma        -> 'human', con la etiqueta que el modelo predijo.
      * Corrige         -> 'human_corrected', con la etiqueta del alumno.
                           Son las unicas filas que corrigen al modelo.
      * Discrepa sin decir cual -> nada. Queda el registro del desacuerdo en
                           prediction_feedbacks, que es lo que hay que mirar
                           para saber si el modelo esta fallando, pero no se
                           fabrica una etiqueta.
    """
    if not pred.feature_vector:
        return None

    if body.diagnostic_affinity:
        etiqueta, procedencia = pred.primary_specialization_id, "human"
    elif body.corrected_specialization_id is not None:
        etiqueta, procedencia = body.corrected_specialization_id, "human_corrected"
    else:
        return None

    fv = pred.feature_vector
    return MLTrainingData(
        **{f"aff_{i}": fv.get(f"aff_{i}", 0) for i in range(1, 11)},
        specialization_id=etiqueta,
        source=procedencia,
        # Trazabilidad: de que prediccion salio esta fila. Permite auditarla
        # y retirarla si el alumno revoca el consentimiento (Ley 29733).
        prediction_id=pred.id,
    )
