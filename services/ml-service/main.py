"""
main.py — Punto de entrada del ml-service.

Lo transversal lo monta ServicioREVO. Aqui queda solo el arranque propio del
servicio: asegurarse de que hay un modelo entrenado en disco.
"""
import logging
import os

from config import settings
from model.trainer import load_model, train_model
from routers.courses import router as router_cursos
from routers.jobs import router as router_empleos
from routers.predict import router as router_prediccion
from routers.stats import router as router_estadisticas
from servicio_revo import servicio

logger = logging.getLogger("revo.ml")

def preparar_modelo() -> None:
    """
    Entrena el modelo la primera vez, si no hay uno guardado.

    Corre con el contexto RLS del rol 'service': necesita leer el dataset
    completo de ml_training_data, que ningun alumno puede ver.
    """
    if os.path.exists(settings.MODEL_PATH):
        load_model()
        logger.info("Modelo cargado desde disco")
        return

    logger.info("No hay modelo guardado. Entrenando por primera vez.")
    db = servicio.sesion_de_servicio()
    try:
        metricas = train_model(db)
        logger.info(
            "Modelo entrenado: version=%s accuracy=%.4f lift sobre argmax=%+.4f",
            metricas["model_version"],
            metricas["accuracy"],
            metricas["lift_over_baseline"],
        )
    except Exception as exc:  # noqa: BLE001
        # Que no haya modelo no debe impedir arrancar: /predict responde 503
        # y el resto del sistema sigue en pie.
        logger.error("No se pudo entrenar el modelo al arrancar: %s", exc)
    finally:
        db.close()


app = servicio.crear_app(
    titulo="REVO - ML Service",
    descripcion="Prediccion de especializacion, recomendaciones y estadisticas del modelo.",
    al_arrancar=preparar_modelo,
)

app.include_router(router_prediccion)
app.include_router(router_estadisticas)
# Cursos y empleos: que hacer con el resultado. Van indexados por
# especializacion, que es lo que este servicio produce.
app.include_router(router_cursos)
app.include_router(router_empleos)
