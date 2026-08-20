"""
Pruebas de integracion del auth-service contra un Postgres real con RLS.

Se salta entera si no hay base de datos apuntada por REVO_TEST_DATABASE_URL.
Para levantarla:

    bash services/auth-service/pruebas/preparar_base.sh
    REVO_TEST_DATABASE_URL=postgresql://revo_app:apppass@localhost:55433/revo_db \\
        python -m pytest services/auth-service/pruebas -q

Por que integracion y no solo unitarias: la mitad de la seguridad de este
servicio vive en las politicas RLS de Postgres. Una prueba con la base de
datos simulada verificaria el codigo Python y se perderia justo la capa que
impide que un alumno lea los datos de otro.
"""
import os
import uuid

import fakeredis
import pytest

URL_PRUEBAS = os.environ.get("REVO_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not URL_PRUEBAS,
    reason="Define REVO_TEST_DATABASE_URL para ejecutar las pruebas de integracion",
)


@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient

    # La configuracion se inyecta por entorno ANTES de importar el servicio:
    # config.py lee las variables al importarse.
    os.environ["DATABASE_URL"] = URL_PRUEBAS
    os.environ["JWT_SECRET"] = "secreto-de-integracion-suficientemente-largo-para-hs256"
    os.environ["ENVIRONMENT"] = "development"

    import servicio_revo

    servicio_revo.servicio.limitador._redis = fakeredis.FakeStrictRedis()

    import main

    return TestClient(main.app)


def cuenta_nueva(**extra):
    sufijo = uuid.uuid4().hex[:8]
    cuerpo = {
        "email": f"alumno.{sufijo}@uni.pe",
        "password": "ClaveSegura2026!",
        "full_name": "Alumno De Prueba",
        "student_code": f"U{sufijo}",
        "semester": 7,
        "accept_terms": True,
    }
    cuerpo.update(extra)
    return cuerpo


class TestRegistro:
    def test_una_cuenta_valida_se_crea_y_devuelve_token(self, cliente):
        respuesta = cliente.post("/auth/register", json=cuenta_nueva())

        assert respuesta.status_code == 201
        assert respuesta.json()["access_token"]

    def test_sin_aceptar_terminos_no_hay_cuenta(self, cliente):
        respuesta = cliente.post("/auth/register", json=cuenta_nueva(accept_terms=False))

        assert respuesta.status_code == 422

    def test_una_contrasena_debil_se_rechaza(self, cliente):
        respuesta = cliente.post("/auth/register", json=cuenta_nueva(password="12345678"))

        assert respuesta.status_code == 422

    def test_la_contrasena_no_puede_ser_el_correo(self, cliente):
        cuerpo = cuenta_nueva()
        cuerpo["password"] = cuerpo["email"]

        assert cliente.post("/auth/register", json=cuerpo).status_code == 422

    def test_el_alta_nunca_crea_un_administrador(self, cliente):
        # Aunque el cliente mande role, el schema lo ignora y la politica RLS
        # de users lo bloquearia igualmente.
        respuesta = cliente.post("/auth/register", json=cuenta_nueva(role="admin"))

        assert respuesta.status_code == 201
        assert respuesta.json()["user"]["role"] == "student"

    def test_el_correo_duplicado_se_rechaza(self, cliente):
        cuerpo = cuenta_nueva()
        cliente.post("/auth/register", json=cuerpo)

        segunda = cliente.post("/auth/register", json=cuenta_nueva(email=cuerpo["email"]))

        assert segunda.status_code == 400

    def test_la_contrasena_no_vuelve_en_la_respuesta(self, cliente):
        respuesta = cliente.post("/auth/register", json=cuenta_nueva())

        assert "password" not in respuesta.text
        assert "hash" not in respuesta.text.lower()


class TestConsentimiento:
    def test_el_registro_deja_las_cuatro_decisiones_grabadas(self, cliente):
        token = cliente.post("/auth/register", json=cuenta_nueva()).json()["access_token"]

        estado = cliente.get(
            "/auth/me/consents", headers={"Authorization": f"Bearer {token}"}
        ).json()

        assert {fila["doc_type"] for fila in estado} == {
            "terms",
            "privacy",
            "data_commercial",
            "ai_training",
        }

    def test_lo_opcional_llega_desmarcado_si_no_se_pide(self, cliente):
        token = cliente.post("/auth/register", json=cuenta_nueva()).json()["access_token"]

        estado = cliente.get(
            "/auth/me/consents", headers={"Authorization": f"Bearer {token}"}
        ).json()
        opcionales = {f["doc_type"]: f["granted"] for f in estado}

        assert opcionales["data_commercial"] is False
        assert opcionales["ai_training"] is False

    def test_lo_opcional_se_puede_autorizar_en_el_alta(self, cliente):
        token = cliente.post(
            "/auth/register",
            json=cuenta_nueva(consent_data_commercial=True, consent_ai_training=True),
        ).json()["access_token"]

        estado = cliente.get(
            "/auth/me/consents", headers={"Authorization": f"Bearer {token}"}
        ).json()
        opcionales = {f["doc_type"]: f["granted"] for f in estado}

        assert opcionales["data_commercial"] is True
        assert opcionales["ai_training"] is True

    def test_se_puede_retirar_despues(self, cliente):
        # El derecho a revocar es lo que hace valido el consentimiento.
        token = cliente.post(
            "/auth/register", json=cuenta_nueva(consent_ai_training=True)
        ).json()["access_token"]
        cabeceras = {"Authorization": f"Bearer {token}"}

        estado = cliente.put(
            "/auth/me/consents",
            json={"doc_type": "ai_training", "granted": False},
            headers=cabeceras,
        ).json()

        assert {f["doc_type"]: f["granted"] for f in estado}["ai_training"] is False

    def test_lo_obligatorio_no_se_puede_retirar(self, cliente):
        # Retirar los terminos equivale a borrar la cuenta: es otra ruta.
        token = cliente.post("/auth/register", json=cuenta_nueva()).json()["access_token"]

        respuesta = cliente.put(
            "/auth/me/consents",
            json={"doc_type": "terms", "granted": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert respuesta.status_code == 422

    def test_los_documentos_se_leen_sin_tener_cuenta(self, cliente):
        # Hay que poder leerlos antes de registrarse, o el consentimiento no
        # seria informado.
        respuesta = cliente.get("/legal/documents")

        assert respuesta.status_code == 200
        assert len(respuesta.json()) == 4

    def test_el_texto_completo_esta_disponible_para_leer_mas(self, cliente):
        respuesta = cliente.get("/legal/documents/privacy")

        assert respuesta.status_code == 200
        assert "Ley 29733" in respuesta.json()["body_md"]

    def test_un_tipo_de_documento_inventado_da_404(self, cliente):
        assert cliente.get("/legal/documents/../../etc/passwd").status_code == 404
        assert cliente.get("/legal/documents/inventado").status_code == 404


class TestLogin:
    def test_las_credenciales_correctas_entran(self, cliente):
        cuerpo = cuenta_nueva()
        cliente.post("/auth/register", json=cuerpo)

        respuesta = cliente.post(
            "/auth/login", json={"email": cuerpo["email"], "password": cuerpo["password"]}
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["user"]["email"] == cuerpo["email"]

    def test_la_contrasena_incorrecta_no_entra(self, cliente):
        cuerpo = cuenta_nueva()
        cliente.post("/auth/register", json=cuerpo)

        respuesta = cliente.post(
            "/auth/login", json={"email": cuerpo["email"], "password": "OtraClave2026!"}
        )

        assert respuesta.status_code == 401

    def test_el_error_no_revela_si_el_correo_existe(self, cliente):
        cuerpo = cuenta_nueva()
        cliente.post("/auth/register", json=cuerpo)

        existente = cliente.post(
            "/auth/login", json={"email": cuerpo["email"], "password": "MalaClave2026!"}
        )
        inexistente = cliente.post(
            "/auth/login", json={"email": "nadie@uni.pe", "password": "MalaClave2026!"}
        )

        assert existente.status_code == inexistente.status_code == 401
        assert existente.json()["detail"] == inexistente.json()["detail"]


class TestAislamientoEntreAlumnos:
    def test_un_alumno_no_alcanza_el_perfil_de_otro(self, cliente):
        primera = cliente.post("/auth/register", json=cuenta_nueva()).json()
        segunda = cliente.post("/auth/register", json=cuenta_nueva()).json()

        perfil = cliente.get(
            "/auth/me", headers={"Authorization": f"Bearer {primera['access_token']}"}
        ).json()

        assert perfil["id"] == primera["user"]["id"]
        assert perfil["id"] != segunda["user"]["id"]

    def test_un_alumno_no_lista_usuarios(self, cliente):
        token = cliente.post("/auth/register", json=cuenta_nueva()).json()["access_token"]

        respuesta = cliente.get("/auth/users", headers={"Authorization": f"Bearer {token}"})

        assert respuesta.status_code == 403

    def test_un_alumno_no_ve_los_consentimientos_de_otro(self, cliente):
        primera = cliente.post("/auth/register", json=cuenta_nueva()).json()
        cliente.post("/auth/register", json=cuenta_nueva(consent_ai_training=True))

        estado = cliente.get(
            "/auth/me/consents",
            headers={"Authorization": f"Bearer {primera['access_token']}"},
        ).json()

        # Solo ve los suyos: cuatro filas, ni una mas.
        assert len(estado) == 4

    def test_sin_token_no_se_llega_al_perfil(self, cliente):
        assert cliente.get("/auth/me").status_code == 401

    def test_un_token_manipulado_no_sirve(self, cliente):
        token = cliente.post("/auth/register", json=cuenta_nueva()).json()["access_token"]
        manipulado = token[:-6] + "AAAAAA"

        respuesta = cliente.get("/auth/me", headers={"Authorization": f"Bearer {manipulado}"})

        assert respuesta.status_code == 401


class TestInyeccion:
    @pytest.mark.parametrize(
        "carga",
        [
            "' OR '1'='1",
            "admin@uni.pe'--",
            "'; DROP TABLE users;--",
            "%",
            "_",
        ],
    )
    def test_el_login_trata_la_carga_como_texto(self, cliente, carga):
        respuesta = cliente.post("/auth/login", json={"email": carga, "password": "x"})

        # 422 si el formato de correo no valida, 401 si valida y no existe.
        # Lo que no puede pasar es 200 ni un 500 con traza.
        assert respuesta.status_code in (401, 422)

    def test_la_tabla_de_usuarios_sigue_en_pie(self, cliente):
        cliente.post("/auth/login", json={"email": "x'; DROP TABLE users;--", "password": "x"})

        # Si la tabla hubiera caido, este registro fallaria con 500.
        assert cliente.post("/auth/register", json=cuenta_nueva()).status_code == 201


class TestCabecerasDeSeguridad:
    def test_las_respuestas_traen_las_cabeceras(self, cliente):
        cabeceras = cliente.get("/health").headers

        assert cabeceras["x-content-type-options"] == "nosniff"
        assert cabeceras["x-frame-options"] == "DENY"
        assert "no-store" in cabeceras["cache-control"]

    def test_un_error_no_devuelve_traza(self, cliente):
        respuesta = cliente.get("/auth/me", headers={"Authorization": "Bearer basura"})

        assert "Traceback" not in respuesta.text
        assert ".py" not in respuesta.text
