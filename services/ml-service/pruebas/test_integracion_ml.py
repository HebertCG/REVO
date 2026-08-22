"""
Pruebas de integracion del ml-service contra un Postgres real.

Se salta entera si no hay base apuntada por REVO_TEST_DATABASE_URL:

    REVO_TEST_DATABASE_URL=postgresql://revo_ml:CLAVE@localhost:5434/revo_db \\
        python -m pytest services/ml-service/pruebas -q

Cubre los catalogos de cursos y empleos, que llegaron desde survey-service
junto con sus pruebas: son "que hacer con tu resultado" y van indexados por
especializacion, que es lo que este servicio produce.
"""
import os

import pytest

URL_PRUEBAS = os.environ.get("REVO_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not URL_PRUEBAS,
    reason="Define REVO_TEST_DATABASE_URL para ejecutar las pruebas de integracion",
)

@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient

    # El entorno (DATABASE_URL, ENVIRONMENT, REQUIRE_GATEWAY) lo prepara
    # conftest.py, que pytest importa antes que este modulo. Ponerlo aqui
    # llegaria tarde: config.settings ya estaria construido y cacheado.

    # Se usa el Redis REAL, no uno simulado. Motivo: la politica de las rutas
    # de administracion tiene fail_open=False a proposito, asi que si el
    # limitador degrada a memoria responde 429 y la prueba mide el fallo del
    # doble de Redis en vez del comportamiento del servicio.
    import servicio_revo

    if servicio_revo.servicio.limitador._redis is None:
        pytest.skip("Estas pruebas necesitan el Redis real (REDIS_URL)")

    import main

    return TestClient(main.app)


@pytest.fixture(scope="module")
def token_alumno(cliente):
    import servicio_revo

    return servicio_revo.servicio.tokens.issue(user_id=1, role="student")


@pytest.fixture(scope="module")
def token_admin(cliente):
    import servicio_revo

    return servicio_revo.servicio.tokens.issue(user_id=1, role="admin")


class TestCatalogoDeCursos:
    def test_los_cursos_se_consultan_por_rama(self, cliente):
        assert cliente.get("/courses/specialization/1").status_code in (200, 404)

    def test_una_rama_inexistente_se_rechaza_antes_de_consultar(self, cliente):
        # El rango se valida en la ruta: un id absurdo no llega a la base.
        assert cliente.get("/courses/specialization/99").status_code == 422
        assert cliente.get("/courses/specialization/0").status_code == 422

    def test_un_id_que_no_es_numero_se_rechaza(self, cliente):
        assert cliente.get("/courses/specialization/../../etc/passwd").status_code in (404, 422)

    def test_los_cursos_devueltos_pertenecen_a_la_rama_pedida(self, cliente):
        respuesta = cliente.get("/courses/specialization/1")

        if respuesta.status_code == 200:
            assert all(c["specialization_id"] == 1 for c in respuesta.json())


class TestCatalogoDeEmpleos:
    def test_los_empleos_se_consultan_por_rama(self, cliente):
        assert cliente.get("/jobs/specialization/1").status_code in (200, 404)

    def test_una_rama_inexistente_se_rechaza(self, cliente):
        assert cliente.get("/jobs/specialization/99").status_code == 422

    def test_los_empleos_devueltos_pertenecen_a_la_rama_pedida(self, cliente):
        respuesta = cliente.get("/jobs/specialization/1")

        if respuesta.status_code == 200:
            assert all(e["specialization_id"] == 1 for e in respuesta.json())


class TestAccesoRestringido:
    def test_un_alumno_no_descarga_el_dataset(self, cliente, token_alumno):
        respuesta = cliente.get(
            "/stats/export-csv", headers={"Authorization": f"Bearer {token_alumno}"}
        )

        assert respuesta.status_code == 403

    def test_un_alumno_no_ve_el_panel(self, cliente, token_alumno):
        respuesta = cliente.get(
            "/stats/overview", headers={"Authorization": f"Bearer {token_alumno}"}
        )

        assert respuesta.status_code == 403

    def test_un_alumno_no_lee_los_pesos_del_modelo(self, cliente, token_alumno):
        respuesta = cliente.get(
            "/predict/model/importances", headers={"Authorization": f"Bearer {token_alumno}"}
        )

        assert respuesta.status_code == 403

    def test_sin_token_no_se_predice(self, cliente):
        respuesta = cliente.post("/predict/", json={"session_id": 1, "feature_vector": {}})

        assert respuesta.status_code == 401

    def test_un_alumno_no_alcanza_la_prediccion_de_otro(self, cliente):
        import servicio_revo

        otro = servicio_revo.servicio.tokens.issue(user_id=999_999, role="student")

        respuesta = cliente.get("/predict/1", headers={"Authorization": f"Bearer {otro}"})

        assert respuesta.status_code in (403, 404)


class TestPanelDeAdministracion:
    def test_el_admin_ve_el_resumen(self, cliente, token_admin):
        respuesta = cliente.get(
            "/stats/overview", headers={"Authorization": f"Bearer {token_admin}"}
        )

        assert respuesta.status_code == 200
        assert "total_predictions" in respuesta.json()

    def test_el_resumen_no_filtra_datos_de_alumnos(self, cliente, token_admin):
        # El panel muestra agregados. Si aparece un correo, se esta filtrando
        # informacion personal a una pantalla pensada para estadisticas.
        cuerpo = cliente.get(
            "/stats/overview", headers={"Authorization": f"Bearer {token_admin}"}
        ).text

        assert "@" not in cuerpo


class TestCabecerasYErrores:
    def test_las_respuestas_traen_las_cabeceras_de_seguridad(self, cliente):
        cabeceras = cliente.get("/health").headers

        assert cabeceras["x-content-type-options"] == "nosniff"
        assert cabeceras["x-frame-options"] == "DENY"

    def test_un_error_no_devuelve_traza(self, cliente):
        respuesta = cliente.get("/predict/1", headers={"Authorization": "Bearer basura"})

        assert "Traceback" not in respuesta.text
        assert ".py" not in respuesta.text
