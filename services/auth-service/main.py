"""
main.py — Punto de entrada del auth-service.

Todo lo transversal (CORS, cabeceras de seguridad, limite de tamano,
pasarela, manejo de errores, cierre de /docs en produccion) lo monta
ServicioREVO. Aqui solo quedan las rutas propias del servicio.
"""
from routers.auth import router as router_auth
from routers.legal import router as router_legal
from servicio_revo import servicio

app = servicio.crear_app(
    titulo="REVO - Auth Service",
    descripcion="Registro, autenticacion y consentimiento informado.",
)

app.include_router(router_auth)
app.include_router(router_legal)
