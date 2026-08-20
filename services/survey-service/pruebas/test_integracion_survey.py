"""
Pruebas de integracion del survey-service contra un Postgres real con RLS.

Lo que se comprueba aqui es lo que las pruebas unitarias no pueden ver: que
un alumno no alcance la sesion, las respuestas ni el historial de otro,
aunque conozca el identificador exacto y lo pida por la URL.

Requiere REVO_TEST_DATABASE_URL apuntando a una base con las migraciones
01..13 aplicadas.
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

SECRETO = "secreto-de-integracion-suficientemente-largo-para-hs256"


@pytest.fixture(scope="module")
def entorno():
    """Levanta el servicio y devuelve el cliente junto al emisor de tokens."""
    from fastapi.testclient import TestClient

    os.environ["DATABASE_URL"] = URL_PRUEBAS
    os.environ["JWT_SECRET"] = SECRETO
    os.environ["ENVIRONMENT"] = "development"

    import servicio_revo

    servicio_revo.servicio.limitador._redis = fakeredis.FakeStrictRedis()

    import main

    return TestClient(main.app), servicio_revo.servicio


@pytest.fixture(scope="module")
def alumnos(entorno):
    """
    Crea dos alumnos reales en la base y devuelve sus cabeceras.

    Se insertan con la misma funcion que usa el registro, para no depender de
    que el auth-service este levantado.
    """
    from sqlalchemy import text

    _, servicio = entorno
    creados = []

    with servicio.fabrica_sesiones() as db:
        for _ in range(2):
            sufijo = uuid.uuid4().hex[:8]
            fila = db.execute(
                text(
                    "SELECT nuevo_id, motivo FROM revo_crear_alumno("
                    ":email, :hash, :nombre, :codigo, :ciclo)"
                ),
                {
                    "email": f"survey.{sufijo}@uni.pe",
                    "hash": "$2b$12$abcdefghijklmnopqrstuv",
                    "nombre": "Alumno Survey",
                    "codigo": f"S{sufijo}",
                    "ciclo": 7,
                },
            ).first()
            db.commit()
            creados.append(fila[0])

    return [
        {"id": uid, "headers": {"Authorization": f"Bearer {servicio.tokens.issue(uid, 'student')}"}}
        for uid in creados
    ]


def crear_sesion(cliente, alumno):
    respuesta = cliente.post("/sessions/", headers=alumno["headers"])
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


class TestSesiones:
    def test_un_alumno_puede_abrir_su_cuestionario(self, entorno, alumnos):
        cliente, _ = entorno

        assert crear_sesion(cliente, alumnos[0]) > 0

    def test_sin_token_no_se_abre_ninguna_sesion(self, entorno):
        cliente, _ = entorno

        assert cliente.post("/sessions/").status_code == 401

    def test_la_fase_1_entrega_diez_preguntas_distintas(self, entorno, alumnos):
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])

        preguntas = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()

        assert len(preguntas) == 10
        assert len({p["id"] for p in preguntas}) == 10

    def test_las_preguntas_no_revelan_a_que_rama_pertenecen(self, entorno, alumnos):
        # Si la respuesta trajera specialization_id, el alumno sabria que
        # pregunta puntua a que rama y podria dirigir su resultado. El
        # cuestionario dejaria de medir nada.
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])

        preguntas = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()

        assert all("specialization_id" not in p for p in preguntas)


class TestAislamientoEntreAlumnos:
    def test_no_se_alcanza_la_sesion_de_otro_ni_conociendo_su_id(self, entorno, alumnos):
        cliente, _ = entorno
        ajena = crear_sesion(cliente, alumnos[1])

        respuesta = cliente.get(
            f"/sessions/{ajena}/questions", headers=alumnos[0]["headers"]
        )

        assert respuesta.status_code == 404

    def test_no_se_escriben_respuestas_en_la_sesion_de_otro(self, entorno, alumnos):
        cliente, _ = entorno
        ajena = crear_sesion(cliente, alumnos[1])

        respuesta = cliente.post(
            f"/sessions/{ajena}/answers",
            json={"answers": [{"question_id": 1, "value": 5}]},
            headers=alumnos[0]["headers"],
        )

        assert respuesta.status_code == 404

    def test_no_se_cierra_la_fase_de_otro(self, entorno, alumnos):
        cliente, _ = entorno
        ajena = crear_sesion(cliente, alumnos[1])

        respuesta = cliente.post(
            f"/sessions/{ajena}/submit_phase", headers=alumnos[0]["headers"]
        )

        assert respuesta.status_code == 404

    def test_el_historial_solo_trae_lo_propio(self, entorno, alumnos):
        cliente, _ = entorno
        crear_sesion(cliente, alumnos[0])
        crear_sesion(cliente, alumnos[1])

        historial = cliente.get("/sessions/", headers=alumnos[0]["headers"]).json()

        assert all(s["user_id"] == alumnos[0]["id"] for s in historial)


class TestGuardadoDeRespuestas:
    def test_se_guardan_las_respuestas_de_la_fase_1(self, entorno, alumnos):
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])
        preguntas = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()

        respuesta = cliente.post(
            f"/sessions/{sid}/answers",
            json={"answers": [{"question_id": p["id"], "value": 4} for p in preguntas]},
            headers=alumnos[0]["headers"],
        )

        assert respuesta.status_code == 200
        assert len(respuesta.json()) == 10

    def test_una_pregunta_inexistente_da_400_y_no_500(self, entorno, alumnos):
        # Antes provocaba una violacion de clave foranea y un 500 con traza.
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])

        respuesta = cliente.post(
            f"/sessions/{sid}/answers",
            json={"answers": [{"question_id": 999999, "value": 4}]},
            headers=alumnos[0]["headers"],
        )

        assert respuesta.status_code == 400

    def test_un_valor_fuera_de_escala_se_rechaza(self, entorno, alumnos):
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])
        preguntas = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()

        respuesta = cliente.post(
            f"/sessions/{sid}/answers",
            json={"answers": [{"question_id": preguntas[0]["id"], "value": 99}]},
            headers=alumnos[0]["headers"],
        )

        assert respuesta.status_code == 422


class TestFlujoDeFases:
    def test_la_fase_1_incompleta_no_avanza(self, entorno, alumnos):
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])

        respuesta = cliente.post(
            f"/sessions/{sid}/submit_phase", headers=alumnos[0]["headers"]
        )

        assert respuesta.status_code == 400

    def test_la_fase_1_completa_abre_la_fase_2_con_tres_ramas(self, entorno, alumnos):
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])
        preguntas = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()
        cliente.post(
            f"/sessions/{sid}/answers",
            json={"answers": [{"question_id": p["id"], "value": 4} for p in preguntas]},
            headers=alumnos[0]["headers"],
        )

        cierre = cliente.post(
            f"/sessions/{sid}/submit_phase", headers=alumnos[0]["headers"]
        ).json()

        assert cierre["next_phase"] == 2
        assert len(cierre["top3"]) == 3

    def test_la_fase_2_entrega_quince_preguntas_nuevas(self, entorno, alumnos):
        cliente, _ = entorno
        sid = crear_sesion(cliente, alumnos[0])
        fase1 = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()
        cliente.post(
            f"/sessions/{sid}/answers",
            json={"answers": [{"question_id": p["id"], "value": 4} for p in fase1]},
            headers=alumnos[0]["headers"],
        )
        cliente.post(f"/sessions/{sid}/submit_phase", headers=alumnos[0]["headers"])

        fase2 = cliente.get(
            f"/sessions/{sid}/questions", headers=alumnos[0]["headers"]
        ).json()

        assert len(fase2) == 15
        # Ninguna se repite respecto a la fase 1.
        assert not ({p["id"] for p in fase2} & {p["id"] for p in fase1})


class TestCatalogosPublicos:
    def test_los_cursos_se_consultan_por_rama(self, entorno):
        cliente, _ = entorno

        assert cliente.get("/courses/specialization/1").status_code in (200, 404)

    def test_una_rama_inexistente_se_rechaza_antes_de_consultar(self, entorno):
        cliente, _ = entorno

        assert cliente.get("/courses/specialization/99").status_code == 422
        assert cliente.get("/courses/specialization/0").status_code == 422

    def test_el_banco_psicometrico_completo_es_solo_de_admin(self, entorno, alumnos):
        cliente, _ = entorno

        assert cliente.get("/psychometric/all", headers=alumnos[0]["headers"]).status_code == 403

    def test_las_preguntas_psicometricas_exigen_token(self, entorno):
        # Antes eran publicas: cualquiera se descargaba el banco rama a rama.
        cliente, _ = entorno

        assert cliente.get("/psychometric/specialization/1").status_code == 401


class TestValidacionDeEntrada:
    def test_una_categoria_inventada_se_rechaza(self, entorno):
        cliente, _ = entorno

        assert cliente.get("/questions/?category=inventada").status_code == 400

    def test_una_categoria_con_carga_sql_se_rechaza(self, entorno):
        cliente, _ = entorno

        respuesta = cliente.get("/questions/?category=' OR '1'='1")

        assert respuesta.status_code == 400

    def test_el_limite_de_resultados_esta_topado(self, entorno):
        cliente, _ = entorno

        assert cliente.get("/questions/?limit=999999").status_code == 422
