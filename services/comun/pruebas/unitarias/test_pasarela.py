"""
Pruebas del control de acceso por pasarela.

Requisito: "no quiero ninguna API expuesta". La defensa principal es de red
(los servicios no publican puertos y solo Nginx sale a internet), pero la red
se configura mal con facilidad. Este control es la segunda capa: aunque el
puerto quede abierto por error, el servicio rechaza lo que no venga de la
pasarela.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from revo_comun.seguridad.pasarela import PasarelaMiddleware

SECRETO = "un-secreto-de-pasarela-largo-y-aleatorio-para-pruebas"


def crear_cliente(**kwargs):
    app = FastAPI()
    app.add_middleware(PasarelaMiddleware, secret=SECRETO, **kwargs)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/sessions/1")
    def sesion():
        return {"id": 1}

    return TestClient(app)


class TestExigenciaActiva:
    def test_deja_pasar_al_trafico_que_viene_de_la_pasarela(self):
        cliente = crear_cliente(enabled=True)

        respuesta = cliente.get("/sessions/1", headers={"x-revo-gateway": SECRETO})

        assert respuesta.status_code == 200

    def test_rechaza_una_peticion_directa_al_puerto_del_servicio(self):
        cliente = crear_cliente(enabled=True)

        assert cliente.get("/sessions/1").status_code == 403

    def test_rechaza_un_secreto_equivocado(self):
        cliente = crear_cliente(enabled=True)

        assert cliente.get("/sessions/1", headers={"x-revo-gateway": "otro"}).status_code == 403

    def test_el_rechazo_no_confirma_que_la_ruta_exista(self):
        cliente = crear_cliente(enabled=True)

        cuerpo = cliente.get("/sessions/1").json()

        assert "gateway" not in str(cuerpo).lower()
        assert "secret" not in str(cuerpo).lower()

    def test_la_sonda_de_salud_sigue_accesible(self):
        # Docker y Render consultan /health sin pasar por Nginx. Si se
        # bloquea, el orquestador reinicia el servicio en bucle.
        cliente = crear_cliente(enabled=True)

        assert cliente.get("/health").status_code == 200


class TestExigenciaDesactivada:
    def test_en_desarrollo_no_estorba(self):
        cliente = crear_cliente(enabled=False)

        assert cliente.get("/sessions/1").status_code == 200


class TestConfiguracion:
    def test_no_arranca_si_se_exige_pasarela_sin_secreto(self):
        # Un secreto vacio comparado con compare_digest deja pasar a
        # cualquiera que mande la cabecera vacia. Mejor no arrancar.
        app = FastAPI()

        with pytest.raises(ValueError):
            app.add_middleware(PasarelaMiddleware, secret="", enabled=True)
            TestClient(app).get("/")

    def test_no_arranca_con_un_secreto_demasiado_corto(self):
        app = FastAPI()

        with pytest.raises(ValueError):
            app.add_middleware(PasarelaMiddleware, secret="corto", enabled=True)
            TestClient(app).get("/")
