"""
Pruebas de las cabeceras de seguridad y del limite de tamano de peticion.

Son controles baratos que cierran clases enteras de ataque: clickjacking,
sniffing de tipo MIME, fuga del token por Referer y agotamiento de memoria
con un cuerpo gigante.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from revo_comun.seguridad.cabeceras import (
    CabecerasSeguridadMiddleware,
    LimiteTamanoMiddleware,
)


def crear_app(**kwargs):
    app = FastAPI()
    app.add_middleware(CabecerasSeguridadMiddleware, **kwargs)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


class TestCabecerasDeSeguridad:
    def test_prohibe_incrustar_la_api_en_un_iframe(self):
        cliente = TestClient(crear_app())

        respuesta = cliente.get("/ping")

        assert respuesta.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in respuesta.headers["content-security-policy"]

    def test_impide_que_el_navegador_adivine_el_tipo_de_contenido(self):
        cliente = TestClient(crear_app())

        assert cliente.get("/ping").headers["x-content-type-options"] == "nosniff"

    def test_no_filtra_la_url_con_el_token_a_terceros(self):
        cliente = TestClient(crear_app())

        assert cliente.get("/ping").headers["referrer-policy"] == "no-referrer"

    def test_la_respuesta_de_api_no_se_guarda_en_cache(self):
        # Una respuesta con datos del alumno cacheada en un proxy compartido
        # del aula la puede leer el siguiente alumno.
        cliente = TestClient(crear_app())

        assert "no-store" in cliente.get("/ping").headers["cache-control"]

    def test_desactiva_permisos_del_navegador_que_la_api_no_usa(self):
        cliente = TestClient(crear_app())

        permisos = cliente.get("/ping").headers["permissions-policy"]

        assert "camera=()" in permisos
        assert "microphone=()" in permisos
        assert "geolocation=()" in permisos

    def test_una_api_json_no_necesita_cargar_nada_externo(self):
        cliente = TestClient(crear_app())

        assert "default-src 'none'" in cliente.get("/ping").headers["content-security-policy"]

    def test_oculta_la_version_del_servidor(self):
        cliente = TestClient(crear_app())

        assert "server" not in {k.lower() for k in cliente.get("/ping").headers}


class TestHsts:
    def test_exige_https_cuando_esta_en_produccion(self):
        cliente = TestClient(crear_app(hsts=True))

        hsts = cliente.get("/ping").headers["strict-transport-security"]

        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts

    def test_no_lo_manda_en_desarrollo_para_no_romper_localhost(self):
        # HSTS en localhost deja el navegador del desarrollador forzando
        # https durante meses contra un servidor que solo habla http.
        cliente = TestClient(crear_app(hsts=False))

        assert "strict-transport-security" not in cliente.get("/ping").headers


class TestLimiteDeTamano:
    def crear_app_con_limite(self, max_bytes):
        app = FastAPI()
        app.add_middleware(LimiteTamanoMiddleware, max_bytes=max_bytes)

        @app.post("/respuestas")
        async def respuestas(cuerpo: dict):
            return {"recibido": len(cuerpo)}

        return TestClient(app)

    def test_acepta_un_cuerpo_de_tamano_normal(self):
        cliente = self.crear_app_con_limite(10_000)

        assert cliente.post("/respuestas", json={"a": 1}).status_code == 200

    def test_rechaza_un_cuerpo_desmesurado_antes_de_leerlo(self):
        cliente = self.crear_app_con_limite(100)

        respuesta = cliente.post("/respuestas", json={"relleno": "x" * 5000})

        assert respuesta.status_code == 413

    def test_el_rechazo_no_revela_detalles_internos(self):
        cliente = self.crear_app_con_limite(100)

        cuerpo = cliente.post("/respuestas", json={"relleno": "x" * 5000}).json()

        assert "traceback" not in str(cuerpo).lower()
        assert "max_bytes" not in str(cuerpo).lower()
