"""Configuracion aislada para las pruebas del auth-service.

Las variables se definen antes de importar ``config``. De ese modo las
pruebas unitarias no leen secretos ni direcciones de la base de produccion y
las de integracion pueden seguir optando por una base real mediante
``REVO_TEST_DATABASE_URL``.
"""
import os


os.environ.setdefault(
    "JWT_SECRET", "secreto-de-pruebas-suficientemente-largo-para-hs256"
)
_URL_PRUEBAS = os.environ.get("REVO_TEST_DATABASE_URL", "")
os.environ.setdefault(
    "DATABASE_URL",
    _URL_PRUEBAS or "postgresql://sin-usar:sin-usar@localhost:5432/sin-usar",
)
os.environ["ENVIRONMENT"] = "test"
os.environ["REQUIRE_GATEWAY"] = "false"
