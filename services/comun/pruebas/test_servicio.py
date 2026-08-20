"""
Pruebas del ensamblado de un microservicio.

Aqui se comprueba el cableado completo de extremo a extremo con una app real:
que el rate limit responde 429 con Retry-After, que el token se exige donde
toca, que el rol de admin se respeta y que una configuracion insegura impide
arrancar en produccion.
"""
import fakeredis
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from revo_comun.ajustes import AjustesBase
from revo_comun.seguridad.tokens import Principal
from revo_comun.servicio import ServicioREVO

SECRETO = "un-secreto-de-pruebas-suficientemente-largo-para-hs256"
SECRETO_PASARELA = "un-secreto-de-pasarela-largo-y-aleatorio-para-pruebas"

# Una URL valida sintacticamente. SQLAlchemy no conecta hasta que se usa, asi
# que estas pruebas no necesitan un Postgres levantado.
URL_FALSA = "postgresql://usuario:clave@localhost:5432/revo_db"


def crear_ajustes(**extra):
    valores = {
        "SERVICE_NAME": "revo-pruebas",
        "DATABASE_URL": URL_FALSA,
        "JWT_SECRET": SECRETO,
        "ENVIRONMENT": "development",
    }
    valores.update(extra)
    return AjustesBase(**valores)


@pytest.fixture
def servicio():
    # El cliente de Redis se inyecta: las pruebas no dependen de la red y no
    # gastan el timeout de conexion en cada caso.
    return ServicioREVO(crear_ajustes(), cliente_redis=fakeredis.FakeStrictRedis())


@pytest.fixture
def cliente(servicio):
    app = servicio.crear_app(titulo="Pruebas")

    @app.get("/publico")
    def publico(_: None = Depends(servicio.limitar("login"))):
        return {"ok": True}

    @app.get("/privado")
    def privado(quien: Principal = Depends(servicio.principal)):
        return {"user_id": quien.user_id}

    @app.get("/admin")
    def solo_admin(quien: Principal = Depends(servicio.admin)):
        return {"admin": quien.user_id}

    return TestClient(app)


class TestRateLimit:
    def test_deja_pasar_dentro_del_cupo(self, cliente):
        assert cliente.get("/publico").status_code == 200

    def test_responde_429_al_agotar_el_cupo(self, cliente):
        for _ in range(8):
            cliente.get("/publico")

        assert cliente.get("/publico").status_code == 429

    def test_dice_cuanto_esperar(self, cliente):
        for _ in range(9):
            cliente.get("/publico")

        respuesta = cliente.get("/publico")

        assert int(respuesta.headers["retry-after"]) > 0

    def test_el_mensaje_es_comprensible_para_un_alumno(self, cliente):
        for _ in range(9):
            cliente.get("/publico")

        detalle = cliente.get("/publico").json()["detail"]

        assert "Demasiadas peticiones" in detalle

    def test_una_politica_inexistente_falla_al_arrancar_no_en_caliente(self, servicio):
        # Un nombre mal escrito debe reventar al montar la ruta, no la primera
        # vez que un alumno la usa en produccion.
        with pytest.raises(KeyError):
            servicio.limitar("politica_que_no_existe")


class TestAislamientoDelAula:
    def test_dos_alumnos_tras_la_misma_ip_no_se_estorban(self, servicio):
        app = servicio.crear_app(titulo="Pruebas")

        @app.get("/jugar")
        def jugar(
            quien: Principal = Depends(servicio.principal),
            _: None = Depends(servicio.limitar("submit_phase")),
        ):
            return {"user_id": quien.user_id}

        cliente = TestClient(app)
        token_ana = servicio.tokens.issue(user_id=1, role="student")
        token_beto = servicio.tokens.issue(user_id=2, role="student")

        # Ana agota su cupo de submit_phase (20 en 5 min).
        for _ in range(25):
            cliente.get("/jugar", headers={"Authorization": f"Bearer {token_ana}"})

        agotada = cliente.get("/jugar", headers={"Authorization": f"Bearer {token_ana}"})
        companero = cliente.get("/jugar", headers={"Authorization": f"Bearer {token_beto}"})

        assert agotada.status_code == 429
        assert companero.status_code == 200


class TestCredencialEnElCuerpo:
    def test_el_cupo_de_login_cuenta_por_cuenta_atacada(self, servicio):
        app = servicio.crear_app(titulo="Pruebas")

        class Credenciales(BaseModel):
            email: str
            password: str

        @app.post("/login")
        def login(cuerpo: Credenciales, _: None = Depends(servicio.limitar("login", por_credencial=True))):
            return {"email": cuerpo.email}

        cliente = TestClient(app)
        atacada = {"email": "victima@uni.pe", "password": "x"}
        otra = {"email": "otro@uni.pe", "password": "x"}

        for _ in range(10):
            cliente.post("/login", json=atacada)

        assert cliente.post("/login", json=atacada).status_code == 429
        assert cliente.post("/login", json=otra).status_code == 200

    def test_leer_el_email_no_deja_al_endpoint_sin_cuerpo(self, servicio):
        # El limitador consume el cuerpo para sacar el email. Si no se
        # reaprovecha, el endpoint recibe un cuerpo vacio y todo login falla.
        app = servicio.crear_app(titulo="Pruebas")

        class Credenciales(BaseModel):
            email: str
            password: str

        @app.post("/login")
        def login(cuerpo: Credenciales, _: None = Depends(servicio.limitar("login", por_credencial=True))):
            return {"email": cuerpo.email}

        respuesta = TestClient(app).post("/login", json={"email": "ana@uni.pe", "password": "x"})

        assert respuesta.status_code == 200
        assert respuesta.json()["email"] == "ana@uni.pe"


class TestAutenticacion:
    def test_sin_token_no_se_entra(self, cliente):
        assert cliente.get("/privado").status_code == 401

    def test_con_token_valido_se_entra(self, cliente, servicio):
        token = servicio.tokens.issue(user_id=7, role="student")

        respuesta = cliente.get("/privado", headers={"Authorization": f"Bearer {token}"})

        assert respuesta.json()["user_id"] == 7

    def test_un_alumno_no_entra_al_panel_de_admin(self, cliente, servicio):
        token = servicio.tokens.issue(user_id=7, role="student")

        respuesta = cliente.get("/admin", headers={"Authorization": f"Bearer {token}"})

        assert respuesta.status_code == 403

    def test_un_admin_si_entra(self, cliente, servicio):
        token = servicio.tokens.issue(user_id=1, role="admin")

        respuesta = cliente.get("/admin", headers={"Authorization": f"Bearer {token}"})

        assert respuesta.status_code == 200


class TestDocumentacion:
    def test_en_desarrollo_los_docs_estan_disponibles(self, cliente):
        assert cliente.get("/docs").status_code == 200

    def test_en_produccion_los_docs_estan_cerrados(self):
        ajustes = crear_ajustes(
            ENVIRONMENT="production",
            REDIS_URL="redis://localhost:6379/0",
            REQUIRE_GATEWAY=True,
            GATEWAY_SECRET=SECRETO_PASARELA,
            TRUSTED_PROXY_COUNT=1,
            DB_REQUIRE_SSL=True,
            CORS_ORIGINS="https://revo.pe",
        )
        servicio = ServicioREVO(ajustes, cliente_redis=fakeredis.FakeStrictRedis())
        app = servicio.crear_app(titulo="Pruebas")
        cliente = TestClient(app)

        # Puede ser 404 (la ruta no existe) o 403 (la pasarela corta antes
        # de enrutar). Lo que importa es que no se sirve el mapa de la API.
        assert cliente.get("/docs").status_code in (403, 404)
        assert cliente.get("/openapi.json").status_code in (403, 404)


class TestConfiguracionDeProduccion:
    def crear_en_produccion(self, **extra):
        base = {
            "ENVIRONMENT": "production",
            "REDIS_URL": "redis://localhost:6379/0",
            "REQUIRE_GATEWAY": True,
            "GATEWAY_SECRET": SECRETO_PASARELA,
            "TRUSTED_PROXY_COUNT": 1,
            "DB_REQUIRE_SSL": True,
            "CORS_ORIGINS": "https://revo.pe",
        }
        base.update(extra)
        servicio = ServicioREVO(crear_ajustes(**base), cliente_redis=fakeredis.FakeStrictRedis())
        return servicio.crear_app(titulo="Pruebas")

    def test_una_configuracion_correcta_arranca(self):
        assert self.crear_en_produccion() is not None

    def test_sin_redis_no_arranca_en_produccion(self):
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            self.crear_en_produccion(REDIS_URL="")

    def test_sin_pasarela_no_arranca_en_produccion(self):
        with pytest.raises(RuntimeError, match="REQUIRE_GATEWAY"):
            self.crear_en_produccion(REQUIRE_GATEWAY=False)

    def test_con_cors_en_http_no_arranca(self):
        with pytest.raises(RuntimeError, match="https"):
            self.crear_en_produccion(CORS_ORIGINS="http://revo.pe")

    def test_con_cors_comodin_no_arranca(self):
        with pytest.raises(RuntimeError, match="comodin"):
            self.crear_en_produccion(CORS_ORIGINS="https://*.vercel.app")

    def test_sin_ssl_a_la_base_de_datos_no_arranca(self):
        with pytest.raises(RuntimeError, match="SSL"):
            self.crear_en_produccion(DB_REQUIRE_SSL=False)

    def test_en_desarrollo_no_estorba(self):
        # Las mismas condiciones "inseguras" en desarrollo no bloquean nada.
        servicio = ServicioREVO(
            crear_ajustes(ENVIRONMENT="development"), cliente_redis=fakeredis.FakeStrictRedis()
        )

        assert servicio.crear_app(titulo="Pruebas") is not None


class TestSalud:
    def test_la_sonda_responde(self, cliente):
        assert cliente.get("/health").json() == {"status": "ok"}

    def test_la_sonda_no_revela_version_ni_servicio(self, cliente):
        # Es informacion de reconocimiento gratuita para un atacante.
        cuerpo = cliente.get("/health").json()

        assert set(cuerpo.keys()) == {"status"}
