"""
Pruebas del saneado de errores.

Un traceback devuelto al cliente regala rutas del servidor, nombres de tablas
y versiones de librerias. Un error de integridad sin sanear confirma que un
email existe en la base de datos, que es una fuga de datos personales.
"""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from revo_comun.errores import registrar_manejadores


class Cuerpo(BaseModel):
    edad: int


def crear_cliente(debug=False):
    app = FastAPI()
    registrar_manejadores(app, debug=debug)

    @app.get("/revienta")
    def revienta():
        raise RuntimeError("la contrasena de postgres es hunter2")

    @app.get("/duplicado")
    def duplicado():
        raise IntegrityError(
            "INSERT INTO users (email) VALUES ('a@b.pe')",
            {},
            Exception('duplicate key value violates unique constraint "users_email_key"'),
        )

    @app.get("/prohibido")
    def prohibido():
        raise HTTPException(status_code=403, detail="Acceso denegado")

    @app.post("/valida")
    def valida(cuerpo: Cuerpo):
        return {"edad": cuerpo.edad}

    return TestClient(app, raise_server_exceptions=False)


class TestErrorNoControlado:
    def test_devuelve_500_generico(self):
        respuesta = crear_cliente().get("/revienta")

        assert respuesta.status_code == 500

    def test_no_filtra_el_mensaje_de_la_excepcion(self):
        cuerpo = crear_cliente().get("/revienta").text

        assert "hunter2" not in cuerpo
        assert "RuntimeError" not in cuerpo

    def test_no_filtra_el_traceback(self):
        cuerpo = crear_cliente().get("/revienta").text

        assert "Traceback" not in cuerpo
        assert ".py" not in cuerpo

    def test_entrega_un_identificador_para_rastrear_el_fallo(self):
        # Sin un identificador comun, el alumno reporta "me salio error" y
        # no hay forma de encontrar su fallo entre miles de lineas de log.
        respuesta = crear_cliente().get("/revienta")

        assert respuesta.json()["error_id"]
        assert respuesta.headers["x-error-id"] == respuesta.json()["error_id"]

    def test_el_detalle_completo_si_queda_en_el_log_del_servidor(self, caplog):
        with caplog.at_level(logging.ERROR):
            crear_cliente().get("/revienta")

        assert "hunter2" in caplog.text


class TestErrorDeIntegridad:
    def test_responde_409_y_no_500(self):
        assert crear_cliente().get("/duplicado").status_code == 409

    def test_no_revela_la_estructura_de_la_base_de_datos(self):
        cuerpo = crear_cliente().get("/duplicado").text

        assert "users_email_key" not in cuerpo
        assert "INSERT INTO" not in cuerpo
        assert "constraint" not in cuerpo.lower()

    def test_no_confirma_que_ese_email_ya_existe(self):
        cuerpo = crear_cliente().get("/duplicado").text

        assert "a@b.pe" not in cuerpo


class TestErrorDeValidacion:
    def test_responde_422(self):
        assert crear_cliente().post("/valida", json={"edad": "no soy un numero"}).status_code == 422

    def test_dice_que_campo_falla_sin_devolver_el_valor_enviado(self):
        # Devolver el valor tal cual convierte la respuesta de error en un
        # reflejo de la entrada: material para XSS si algo lo pinta en HTML.
        respuesta = crear_cliente().post("/valida", json={"edad": "<script>alert(1)</script>"})

        cuerpo = respuesta.text
        assert "edad" in cuerpo
        assert "<script>" not in cuerpo


class TestErroresIntencionados:
    def test_un_403_explicito_conserva_su_mensaje(self):
        respuesta = crear_cliente().get("/prohibido")

        assert respuesta.status_code == 403
        assert respuesta.json()["detail"] == "Acceso denegado"


class TestModoDepuracion:
    def test_en_depuracion_si_se_ve_el_detalle(self):
        # Util en local; jamas en produccion. El flag viene de la config.
        cuerpo = crear_cliente(debug=True).get("/revienta").text

        assert "hunter2" in cuerpo
