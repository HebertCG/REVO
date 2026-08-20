"""
main.py — Punto de entrada del survey-service.

Lo transversal (CORS, cabeceras, pasarela, limite de tamano, errores
saneados, cierre de /docs en produccion) lo monta ServicioREVO.
"""
from routers.courses import router as router_cursos
from routers.jobs import router as router_empleos
from routers.psychometric import router as router_psicometrico
from routers.questions import router as router_preguntas
from routers.sessions import router as router_sesiones
from servicio_revo import servicio

app = servicio.crear_app(
    titulo="REVO - Survey Service",
    descripcion="Cuestionario por fases: preguntas, sesiones y respuestas.",
)

app.include_router(router_preguntas)
app.include_router(router_sesiones)
app.include_router(router_cursos)
app.include_router(router_empleos)
app.include_router(router_psicometrico)
