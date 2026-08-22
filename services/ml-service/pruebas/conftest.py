"""
conftest.py — Entorno de las pruebas del ml-service.

Esto tiene que estar en un conftest y no dentro de una fixture. Motivo:
`config.settings` es un singleton con @lru_cache que se construye la primera
vez que ALGUIEN importa `config`. Si otro fichero de pruebas lo importa antes
(por orden alfabetico, test_entrenador va primero), la configuracion queda
fijada con las variables del contenedor y un `os.environ[...]` posterior no
cambia nada.

El sintoma era desconcertante: las pruebas de integracion pasaban al
ejecutarlas solas y fallaban al ejecutarlas junto al resto.

pytest importa el conftest antes que cualquier modulo de prueba, asi que aqui
las variables llegan a tiempo.
"""
import os

os.environ.setdefault("JWT_SECRET", "secreto-de-pruebas-suficientemente-largo-para-hs256")
os.environ["ENVIRONMENT"] = "development"

# TestClient habla directamente con la aplicacion, sin pasar por Nginx, asi
# que no trae el secreto de la pasarela. Que la pasarela filtre bien se
# comprueba aparte, en infraestructura/verificar_despliegue.sh.
os.environ["REQUIRE_GATEWAY"] = "false"

_URL_PRUEBAS = os.environ.get("REVO_TEST_DATABASE_URL", "")
if _URL_PRUEBAS:
    os.environ["DATABASE_URL"] = _URL_PRUEBAS
else:
    # Las pruebas unitarias no tocan la base, pero config exige la variable
    # para construirse. SQLAlchemy no conecta hasta que se usa.
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://sin-usar:sin-usar@localhost:5432/sin-usar"
    )
