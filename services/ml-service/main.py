"""
main.py — Punto de entrada del ml-service.

Lo transversal lo monta ServicioREVO. Aqui queda solo el arranque propio del
servicio: asegurarse de que hay un modelo entrenado en disco.
"""
import logging

from model.trainer import cargar_artefacto_activo, train_model
from routers.courses import router as router_cursos
from routers.predict import router as router_prediccion
from routers.stats import router as router_estadisticas
from servicio_revo import servicio

logger = logging.getLogger("revo.ml")

def preparar_modelo() -> None:
    """
    Deja un modelo activo antes de aceptar peticiones.

    Tres caminos, en orden:
      1. Ya hay una version activa en el almacen -> se carga.
      2. No la hay, pero existe el .pkl suelto del esquema anterior -> se
         adopta como version heredada (lo hace cargar_artefacto_activo).
      3. No hay nada -> se entrena por primera vez.

    Corre con el contexto RLS del rol 'service': necesita leer el dataset
    completo de ml_training_data, que ningun alumno puede ver.
    """
    try:
        artefacto = cargar_artefacto_activo()
        logger.info(
            "Modelo activo: %s%s",
            artefacto.version,
            "" if artefacto.esta_calibrado else " (SIN CALIBRAR: reentrenar)",
        )
        return
    except FileNotFoundError:
        pass

    logger.info("No hay modelo activo. Entrenando por primera vez.")
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
# Cursos: que hacer con el resultado. Van indexados por especializacion,
# que es lo que este servicio produce.
#
# El router de empleos se retiro con la tabla `jobs` (migracion 20): la
# pantalla de resultado dejo de leerlo cuando paso a consultar la API de
# Remotive en tiempo real (frontend/src/pages/Results.jsx). Una oferta de
# hace tres meses servida como actual es peor que no servir ninguna.
app.include_router(router_cursos)
